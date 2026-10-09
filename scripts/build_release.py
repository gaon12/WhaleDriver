"""Build a portable Windows distribution with a validated, replaceable backend."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from packaging.requirements import Requirement

from whaledriver import __version__
from whaledriver.errors import WhaleDriverError
from whaledriver.manager import DriverManager, driver_platform, read_driver_version, verify_driver

ROOT = Path(__file__).resolve().parents[1]
DRIVER_NOTICES = ("LICENSE.chromedriver", "THIRD_PARTY_NOTICES.chromedriver")


@dataclass(frozen=True)
class Backend:
    directory: Path
    version: str
    target: str

    @property
    def major(self) -> str:
        return self.version.split(".")[0]


def prepare_backend(directory: Path, target: str, chromium_version: str | None = None) -> Backend:
    """Prefer the user's replacement; download only when the input is absent."""
    filename = "chromedriver.exe" if target.startswith("win") else "chromedriver"
    executable = directory / filename
    if executable.is_file():
        version = read_driver_version(executable)
        verify_driver(executable, chromium_version or version)
    else:
        engine = chromium_version
        if engine is None:
            engine = json.loads((ROOT / "releases/driver.json").read_text(encoding="utf-8"))[
                "chromium_version"
            ]
        downloaded = DriverManager().install(engine)
        missing = [
            notice for notice in DRIVER_NOTICES if not (downloaded.parent / notice).is_file()
        ]
        if missing:
            raise WhaleDriverError(
                f"Downloaded ChromeDriver is missing notices: {', '.join(missing)}"
            )
        directory.mkdir(parents=True, exist_ok=True)
        for source in (downloaded, *(downloaded.parent / notice for notice in DRIVER_NOTICES)):
            shutil.copy2(source, directory / source.name)
        version = verify_driver(executable, engine)
    missing = [notice for notice in DRIVER_NOTICES if not (directory / notice).is_file()]
    if missing:
        raise WhaleDriverError(
            f"ChromeDriver input in {directory} is missing {', '.join(missing)}. "
            "Extract the executable and both notices from the same official archive."
        )
    return Backend(directory.resolve(), version, target)


def collect_licenses(destination: Path) -> None:
    """Retain license and notice files for the active runtime dependency graph."""
    pending = ["whaledriver", "pyinstaller"]
    seen = set()
    index = []
    while pending:
        name = pending.pop()
        normalized = name.lower().replace("_", "-")
        if normalized in seen:
            continue
        seen.add(normalized)
        distribution = importlib.metadata.distribution(name)
        copied = []
        for relative in distribution.files or []:
            text = str(relative).lower()
            if not any(word in text for word in ("license", "copying", "notice")):
                continue
            if ".." in relative.parts or relative.is_absolute():
                continue
            source = Path(distribution.locate_file(relative))
            if not source.is_file():
                continue
            output = destination / normalized / relative
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, output)
            copied.append(str(relative))
        if not copied:
            raise WhaleDriverError(f"No installed license files were found for dependency {name}.")
        index.append(f"{distribution.metadata['Name']} {distribution.version}")
        for requirement_text in distribution.requires or []:
            requirement = Requirement(requirement_text)
            if requirement.marker is None or requirement.marker.evaluate({"extra": ""}):
                pending.append(requirement.name)
    python_license = next(
        (
            Path(sys.base_prefix) / name
            for name in ("LICENSE.txt", "LICENSE")
            if (Path(sys.base_prefix) / name).is_file()
        ),
        None,
    )
    if python_license is None:
        raise WhaleDriverError(
            "The Python installation is missing its LICENSE or LICENSE.txt file."
        )
    shutil.copy2(python_license, destination / "PYTHON_LICENSE.txt")
    (destination / "INDEX.txt").write_text(
        "License files retained for these dependencies:\n\n" + "\n".join(sorted(index)) + "\n",
        encoding="utf-8",
    )


def create_archive(bundle: Path, archive: Path) -> None:
    """Publish the completed ZIP atomically and write a matching SHA-256 checksum."""
    temporary = archive.with_suffix(".zip.tmp")
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as output:
            for source in sorted(bundle.rglob("*")):
                if source.is_file():
                    output.write(source, Path(bundle.name) / source.relative_to(bundle))
        os.replace(temporary, archive)
    finally:
        temporary.unlink(missing_ok=True)
    hasher = hashlib.sha256()
    with archive.open("rb") as content:
        for chunk in iter(lambda: content.read(1024 * 1024), b""):
            hasher.update(chunk)
    digest = hasher.hexdigest()
    archive.with_suffix(".zip.sha256").write_text(f"{digest}  {archive.name}\n", encoding="utf-8")


def build_portable(backend: Backend, output_dir: Path, *, smoke_test: bool = False) -> Path:
    """Freeze the CLI, copy its replaceable backend and notices, then package it."""
    if sys.platform != "win32" or backend.target != "win64":
        raise WhaleDriverError("Portable executable builds currently require Windows x64.")
    output_dir.mkdir(parents=True, exist_ok=True)
    work = ROOT / "build/pyinstaller/win64"
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="portable-", dir=ROOT / "build") as temporary:
        stage = Path(temporary)
        subprocess.run(
            [
                sys.executable,
                "-m",
                "PyInstaller",
                "--noconfirm",
                "--onedir",
                "--name",
                "whaledriver",
                "--noupx",
                "--log-level",
                "WARN",
                "--distpath",
                str(stage),
                "--workpath",
                str(work),
                "--specpath",
                str(work),
                "--paths",
                str(ROOT / "src"),
                "--collect-data",
                "selenium",
                "--recursive-copy-metadata",
                "whaledriver",
                str(ROOT / "scripts/frozen_entry.py"),
            ],
            cwd=ROOT,
            check=True,
        )
        bundle = stage / "whaledriver"
        driver_output = bundle / "drivers" / backend.target
        driver_output.mkdir(parents=True)
        for filename in ("chromedriver.exe", *DRIVER_NOTICES):
            shutil.copy2(backend.directory / filename, driver_output / filename)
        for filename in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
            shutil.copy2(ROOT / filename, bundle / filename)
        collect_licenses(bundle / "third-party-licenses")
        (bundle / "BUILD_INFO.json").write_text(
            json.dumps(
                {
                    "whaledriver_version": __version__,
                    "chromedriver_version": backend.version,
                    "chromium_major": backend.major,
                    "platform": backend.target,
                    "unofficial": True,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (bundle / "PORTABLE_README.txt").write_text(
            "WhaleDriver is an independent, unofficial project with no NAVER affiliation.\n"
            "NAVER Whale belongs to NAVER Corporation. Project code uses BSD 3-Clause.\n\n"
            "Extract the entire ZIP. Keep _internal, drivers, and license files together.\n"
            "Python does not need to be installed on the target computer.\n"
            "Run: whaledriver.exe doctor\n"
            "Run: whaledriver.exe serve --port 9515 --offline\n"
            "Set the remote client's ChromeOptions binary to the reported Whale path.\n"
            "Quit Selenium sessions before stopping the server with Ctrl+C.\n\n"
            f"The included ChromeDriver {backend.version} requires "
            f"Chromium major {backend.major}.\n"
            "After Whale's Chromium major changes, rebuild with a matching driver.\n"
            "Source and instructions: https://github.com/gaon12/WhaleDriver\n",
            encoding="utf-8",
        )
        executable = bundle / "whaledriver.exe"
        subprocess.run([str(executable), "--version"], check=True)
        if smoke_test:
            subprocess.run(
                [sys.executable, str(ROOT / "scripts/smoke_test_portable.py"), str(executable)],
                check=True,
            )
        archive = output_dir / f"whaledriver-{__version__}-win64-chromium{backend.major}.zip"
        create_archive(bundle, archive)
    return archive


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--driver-dir", type=Path, help="Directory with the replacement ChromeDriver."
    )
    parser.add_argument(
        "--chromium-version", help="Engine version to download or validate against."
    )
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    parser.add_argument(
        "--smoke-test", action="store_true", help="Test the build with installed Whale."
    )
    arguments = parser.parse_args(argv)
    try:
        target = driver_platform()
        if target != "win64" or sys.platform != "win32":
            raise WhaleDriverError("Portable executable builds currently require Windows x64.")
        directory = arguments.driver_dir or ROOT / "drivers" / target
        backend = prepare_backend(directory, target, arguments.chromium_version)
        print(
            f"Building WhaleDriver {__version__} with ChromeDriver {backend.version}.", flush=True
        )
        archive = build_portable(backend, arguments.output_dir, smoke_test=arguments.smoke_test)
        print(f"Portable release: {archive}")
        print(f"Checksum: {archive.with_suffix('.zip.sha256')}")
        return 0
    except (WhaleDriverError, OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Build failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
