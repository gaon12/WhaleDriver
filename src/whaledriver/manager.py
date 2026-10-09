"""Select and cache unmodified ChromeDriver binaries from Chrome for Testing."""

from __future__ import annotations

import io
import json
import os
import platform
import re
import stat
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from whaledriver.errors import DriverDownloadError, DriverVersionError, UnsupportedPlatformError

BUILD_METADATA_URL = (
    "https://googlechromelabs.github.io/chrome-for-testing/"
    "latest-patch-versions-per-build-with-downloads.json"
)
MILESTONE_METADATA_URL = (
    "https://googlechromelabs.github.io/chrome-for-testing/"
    "latest-versions-per-milestone-with-downloads.json"
)
VERSION_PATTERN = re.compile(r"\d+\.\d+\.\d+\.\d+")


@dataclass(frozen=True)
class DriverRelease:
    """An upstream version and its exact official archive URL."""

    version: str
    platform: str
    url: str


def driver_platform() -> str:
    """Return a platform that actually has upstream ChromeDriver downloads."""
    machine = platform.machine().lower()
    if sys.platform == "win32":
        if machine in {"amd64", "x86_64"}:
            return "win64"
        if machine in {"x86", "i386", "i686"}:
            return "win32"
    elif sys.platform == "darwin":
        if machine in {"arm64", "aarch64"}:
            return "mac-arm64"
        if machine in {"x86_64", "amd64"}:
            return "mac-x64"
    elif sys.platform.startswith("linux") and machine in {"x86_64", "amd64"}:
        return "linux64"
    raise UnsupportedPlatformError(
        f"Chrome for Testing has no supported driver for {sys.platform}/{machine}. "
        "Provide a compatible driver_path explicitly if you have a working build."
    )


def default_cache_dir() -> Path:
    """Use a per-user cache without writing inside the browser installation."""
    if configured := os.environ.get("WHALEDRIVER_CACHE"):
        return Path(configured).expanduser()
    if sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local")))
        return root / "WhaleDriver"
    if sys.platform == "darwin":
        return Path.home() / "Library/Caches/whaledriver"
    return Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "whaledriver"


def _check_engine_version(version: str) -> None:
    if not VERSION_PATTERN.fullmatch(version):
        raise DriverVersionError(f"Expected a full Chromium version, received {version!r}.")
    if int(version.split(".")[0]) < 115:
        raise DriverVersionError("Automatic driver selection requires Chromium 115 or newer.")


def verify_driver(
    executable: str | Path, chromium_version: str, *, expected_version: str | None = None
) -> str:
    """Check executable identity and engine compatibility before starting a service."""
    _check_engine_version(chromium_version)
    path = Path(executable).expanduser().resolve()
    if not path.is_file():
        raise DriverVersionError(f"ChromeDriver executable does not exist: {path}")
    try:
        result = subprocess.run(
            [str(path), "--version"], capture_output=True, text=True, timeout=10, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise DriverVersionError(f"Could not run ChromeDriver at {path}: {error}") from error
    match = re.search(r"\bChromeDriver (\d+\.\d+\.\d+\.\d+)\b", result.stdout)
    if result.returncode != 0 or not match:
        raise DriverVersionError(f"The executable at {path} did not report a ChromeDriver version.")
    driver_version = match.group(1)
    if driver_version.split(".")[0] != chromium_version.split(".")[0]:
        raise DriverVersionError(
            f"ChromeDriver {driver_version} does not match Whale's Chromium {chromium_version}. "
            "Use a driver with the same Chromium major version."
        )
    if expected_version is not None and driver_version != expected_version:
        raise DriverVersionError(
            f"ChromeDriver reported {driver_version}; expected cached release {expected_version}."
        )
    return driver_version


class DriverManager:
    """Install matching drivers with optional, strictly network-free cache reuse."""

    def __init__(
        self, cache_dir: str | Path | None = None, *, offline: bool = False, timeout: float = 30
    ) -> None:
        if timeout <= 0:
            raise ValueError("Download timeout must be greater than zero.")
        self.cache_dir = (
            Path(cache_dir).expanduser() if cache_dir is not None else default_cache_dir()
        )
        self.offline = offline
        self.timeout = timeout

    def _download(self, url: str, *, limit: int) -> bytes:
        if self.offline:
            raise DriverDownloadError("Offline mode does not allow network requests.")
        request = urllib.request.Request(url, headers={"User-Agent": "WhaleDriver/0.1.0"})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                content = response.read(limit + 1)
        except (OSError, urllib.error.URLError) as error:
            raise DriverDownloadError(f"Could not download {url}: {error}") from error
        if len(content) > limit:
            raise DriverDownloadError(f"Download exceeds the allowed size: {url}")
        return content

    def _read_json(self, url: str) -> dict[str, Any]:
        try:
            payload = json.loads(self._download(url, limit=32 * 1024 * 1024))
        except (ValueError, UnicodeDecodeError) as error:
            raise DriverDownloadError(f"Invalid Chrome for Testing metadata: {url}") from error
        if not isinstance(payload, dict):
            raise DriverDownloadError(f"Chrome for Testing metadata must be an object: {url}")
        return payload

    def resolve(self, chromium_version: str, target_platform: str | None = None) -> DriverRelease:
        """Prefer an exact engine build; fall back to the same milestone as upstream advises."""
        _check_engine_version(chromium_version)
        target = target_platform or driver_platform()
        build = chromium_version.rsplit(".", 1)[0]
        major = chromium_version.split(".")[0]
        try:
            record = self._read_json(BUILD_METADATA_URL).get("builds", {}).get(build)
            if record is None:
                record = self._read_json(MILESTONE_METADATA_URL).get("milestones", {}).get(major)
            version = record["version"]
            if not isinstance(version, str) or not VERSION_PATTERN.fullmatch(version):
                raise ValueError("Invalid driver version")
            if version.split(".")[0] != major:
                raise ValueError("Driver milestone does not match the browser")
            downloads = record["downloads"]["chromedriver"]
            download = next(item for item in downloads if item["platform"] == target)
            expected_url = (
                f"https://storage.googleapis.com/chrome-for-testing-public/"
                f"{version}/{target}/chromedriver-{target}.zip"
            )
            if download["url"] != expected_url:
                raise ValueError("Unexpected driver archive URL")
        except (KeyError, TypeError, AttributeError, ValueError, StopIteration) as error:
            raise DriverDownloadError(
                f"No valid official ChromeDriver release for Chromium {chromium_version} "
                f"on {target}. Provide driver_path for a manually installed compatible driver."
            ) from error
        return DriverRelease(version, target, expected_url)

    def _cached_driver(self, chromium_version: str, target: str) -> Path | None:
        root = self.cache_dir / target
        if not root.is_dir():
            return None
        major = chromium_version.split(".")[0]
        build = chromium_version.rsplit(".", 1)[0]
        versions = [
            directory
            for directory in root.iterdir()
            if directory.is_dir()
            and VERSION_PATTERN.fullmatch(directory.name)
            and directory.name.split(".")[0] == major
            and (self.offline or directory.name.rsplit(".", 1)[0] == build)
        ]
        versions.sort(
            key=lambda path: (
                path.name.rsplit(".", 1)[0] == build,
                tuple(map(int, path.name.split("."))),
            ),
            reverse=True,
        )
        for directory in versions:
            if not (directory / "LICENSE.chromedriver").is_file():
                continue
            executable = directory / (
                "chromedriver.exe" if target.startswith("win") else "chromedriver"
            )
            try:
                verify_driver(executable, chromium_version, expected_version=directory.name)
            except DriverVersionError:
                continue
            return executable.resolve()
        return None

    def install(self, chromium_version: str, *, driver_path: str | Path | None = None) -> Path:
        """Return a validated explicit executable or install an upstream driver in the cache."""
        _check_engine_version(chromium_version)
        if driver_path is not None:
            executable = Path(driver_path).expanduser().resolve()
            verify_driver(executable, chromium_version)
            return executable
        target = driver_platform()
        if cached := self._cached_driver(chromium_version, target):
            return cached
        if self.offline:
            raise DriverDownloadError(
                f"No valid cached ChromeDriver for Chromium {chromium_version} "
                f"in {self.cache_dir}. "
                "Run online once or provide driver_path."
            )
        release = self.resolve(chromium_version, target)
        filename = "chromedriver.exe" if target.startswith("win") else "chromedriver"
        destination = self.cache_dir / target / release.version
        executable = destination / filename
        if executable.is_file() and (destination / "LICENSE.chromedriver").is_file():
            try:
                verify_driver(executable, chromium_version, expected_version=release.version)
                return executable.resolve()
            except DriverVersionError:
                pass
        archive = self._download(release.url, limit=64 * 1024 * 1024)
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(
                prefix=".download-", dir=destination.parent
            ) as directory:
                staging = Path(directory)
                self._unpack(archive, release, staging, filename)
                staged_driver = staging / filename
                if not target.startswith("win"):
                    staged_driver.chmod(0o755)
                verify_driver(staged_driver, chromium_version, expected_version=release.version)
                destination.mkdir(exist_ok=True)
                # Publish verified files atomically. The executable is last so its notices
                # are already present when another process starts using the cache entry.
                for source in sorted(staging.iterdir(), key=lambda path: path.name == filename):
                    os.replace(source, destination / source.name)
        except (OSError, zipfile.BadZipFile, RuntimeError) as error:
            if isinstance(error, DriverVersionError | DriverDownloadError):
                raise
            raise DriverDownloadError(f"Could not install ChromeDriver: {error}") from error
        return executable.resolve()

    @staticmethod
    def _unpack(archive: bytes, release: DriverRelease, staging: Path, filename: str) -> None:
        with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
            members = bundle.infolist()
            if sum(member.file_size for member in members) > 200 * 1024 * 1024:
                raise DriverDownloadError("Driver archive has an excessive uncompressed size.")
            root = f"chromedriver-{release.platform}"
            copied: set[str] = set()
            for member in members:
                # ZipInfo normalizes backslashes on Windows. Inspect the original
                # archive name as well so malformed entries are rejected consistently.
                path = PurePosixPath(member.orig_filename)
                if (
                    path.is_absolute()
                    or ".." in path.parts
                    or "\\" in member.orig_filename
                    or stat.S_ISLNK(member.external_attr >> 16)
                ):
                    raise DriverDownloadError(
                        "Driver archive contains an unsafe path or symbolic link."
                    )
                if member.is_dir() or len(path.parts) != 2 or path.parts[0] != root:
                    continue
                name = path.name
                if name != filename and not name.startswith(("LICENSE", "THIRD_PARTY_NOTICES")):
                    continue
                if name in copied:
                    raise DriverDownloadError(f"Driver archive contains duplicate files: {name}")
                (staging / name).write_bytes(bundle.read(member))
                copied.add(name)
            if filename not in copied or "LICENSE.chromedriver" not in copied:
                raise DriverDownloadError(
                    "Driver archive is missing its executable or license notice."
                )
