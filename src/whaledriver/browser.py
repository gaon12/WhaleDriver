"""Discover Whale and read its engine version without opening a personal profile."""

from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psutil
import websocket

from whaledriver.errors import BrowserNotFoundError, BrowserProbeError


@dataclass(frozen=True)
class BrowserInfo:
    """Product and engine versions are separate and must not be interchanged."""

    binary: Path
    chromium_version: str
    whale_version: str
    user_agent: str


def _resolve_launch_binary(binary: Path) -> Path:
    # Whale's Windows launcher exits after starting the versioned executable.
    # Launch that executable directly so we can supervise its process reliably.
    if sys.platform == "win32" and binary.name.lower() == "whale.exe":
        versions = []
        for directory in binary.parent.iterdir():
            if re.fullmatch(r"\d+\.\d+\.\d+\.\d+", directory.name):
                executable = directory / "whale.exe"
                if executable.is_file():
                    versions.append((tuple(map(int, directory.name.split("."))), executable))
        if versions:
            return max(versions)[1].resolve()
    return binary.resolve()


def find_whale(binary: str | Path | None = None) -> Path:
    """Prefer an explicit path, then WHALE_BINARY, then known installation paths."""
    requested = binary if binary is not None else os.environ.get("WHALE_BINARY")
    if requested is not None:
        path = Path(requested).expanduser()
        if not path.is_file():
            raise BrowserNotFoundError(f"Whale executable does not exist: {path}")
        return _resolve_launch_binary(path)

    candidates: list[Path] = []
    if sys.platform == "win32":
        for variable in ("LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)"):
            if root := os.environ.get(variable):
                candidates.append(Path(root) / "Naver/Naver Whale/Application/whale.exe")
    elif sys.platform == "darwin":
        for root in (Path("/Applications"), Path.home() / "Applications"):
            candidates.append(root / "Whale.app/Contents/MacOS/Whale")
    else:
        for command in ("whale", "naver-whale", "whale-browser"):
            if found := shutil.which(command):
                candidates.append(Path(found))
        candidates.extend((Path("/usr/bin/whale"), Path("/opt/whale/whale")))

    for candidate in candidates:
        if candidate.is_file():
            return _resolve_launch_binary(candidate)
    raise BrowserNotFoundError(
        "NAVER Whale was not found. Install Whale or set WHALE_BINARY to its executable path."
    )


def _parse_version_info(binary: Path, payload: dict[str, Any]) -> BrowserInfo:
    product = payload.get("Browser", "")
    user_agent = payload.get("User-Agent", "")
    chromium = re.fullmatch(r"(?:Headless)?Chrome/(\d+\.\d+\.\d+\.\d+)", str(product))
    whale = re.search(r"\bWhale/(\d+\.\d+\.\d+\.\d+)\b", str(user_agent))
    if not chromium or not whale:
        raise BrowserProbeError(
            "DevTools did not report a Whale browser with a full Chromium engine version. "
            f"Browser product: {product!r}. Check the Whale executable path."
        )
    return BrowserInfo(binary, chromium.group(1), whale.group(1), user_agent)


def _stop_probe(
    process: subprocess.Popen,
    owned_children: dict[int, psutil.Process],
    debugger_url: str | None,
) -> None:
    with contextlib.suppress(psutil.Error):
        parent = psutil.Process(process.pid)
        owned_children.update({child.pid: child for child in parent.children(recursive=True)})
    if debugger_url:
        with contextlib.suppress(OSError, websocket.WebSocketException):
            connection = websocket.create_connection(
                debugger_url,
                timeout=2,
                suppress_origin=True,
                http_no_proxy=["127.0.0.1", "localhost"],
            )
            try:
                connection.send(json.dumps({"id": 1, "method": "Browser.close"}))
                connection.recv()
            finally:
                connection.close()
    with contextlib.suppress(psutil.Error):
        parent = psutil.Process(process.pid)
        owned_children.update({child.pid: child for child in parent.children(recursive=True)})
    # Keep the original subprocess handle for the root. A process identity read
    # immediately after Windows starts Whale may not yet have a stable creation time.
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)
    _, alive = psutil.wait_procs(list(owned_children.values()), timeout=1)
    for child in alive:
        with contextlib.suppress(psutil.Error):
            child.terminate()
    _, alive = psutil.wait_procs(alive, timeout=2)
    for child in alive:
        with contextlib.suppress(psutil.Error):
            child.kill()
    psutil.wait_procs(alive, timeout=2)


@contextlib.contextmanager
def _temporary_profile() -> Iterator[str]:
    profile = tempfile.TemporaryDirectory(prefix="whaledriver-probe-")
    try:
        yield profile.name
    finally:
        # Windows can release profile file handles shortly after a process exits.
        # Retry deletion briefly, but report a persistent failure instead of leaving
        # an undeleted profile silently.
        deadline = time.monotonic() + 3
        while True:
            try:
                profile.cleanup()
                break
            except PermissionError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.1)


def probe_browser(binary: str | Path | None = None, *, timeout: float = 15) -> BrowserInfo:
    """Read DevTools metadata from a temporary headless browser and close it."""
    if timeout <= 0:
        raise ValueError("Browser probe timeout must be greater than zero.")
    executable = find_whale(binary)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with _temporary_profile() as profile:
        command = [
            str(executable),
            "--headless=new",
            "--remote-debugging-port=0",
            "--remote-debugging-address=127.0.0.1",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            f"--user-data-dir={profile}",
            "about:blank",
        ]
        try:
            process = subprocess.Popen(
                command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except OSError as error:
            raise BrowserProbeError(f"Could not start Whale: {error}") from error
        owned_children: dict[int, psutil.Process] = {}
        debugger_url = None
        deadline = time.monotonic() + timeout
        port_file = Path(profile) / "DevToolsActivePort"
        try:
            while time.monotonic() < deadline:
                with contextlib.suppress(psutil.Error):
                    owned_children.update(
                        {
                            child.pid: child
                            for child in psutil.Process(process.pid).children(recursive=True)
                        }
                    )
                if port_file.is_file():
                    try:
                        port = int(port_file.read_text(encoding="utf-8").splitlines()[0])
                        if not 0 < port < 65536:
                            raise ValueError("Invalid DevTools port")
                        remaining = max(0.05, deadline - time.monotonic())
                        with opener.open(
                            f"http://127.0.0.1:{port}/json/version", timeout=min(2, remaining)
                        ) as response:
                            payload = json.load(response)
                        if not isinstance(payload, dict):
                            raise BrowserProbeError("DevTools version response was not an object.")
                        # Build the endpoint from the locally created port rather than trusting
                        # an arbitrary host in the response during cleanup.
                        lines = port_file.read_text(encoding="utf-8").splitlines()
                        if len(lines) > 1 and lines[1].startswith("/devtools/browser/"):
                            debugger_url = f"ws://127.0.0.1:{port}{lines[1]}"
                        return _parse_version_info(executable, payload)
                    except (OSError, ValueError, IndexError, urllib.error.URLError):
                        pass
                if process.poll() is not None:
                    raise BrowserProbeError(
                        f"Whale exited before opening DevTools (exit code {process.returncode})."
                    )
                time.sleep(0.05)
            raise BrowserProbeError(f"Whale did not open DevTools within {timeout:g} seconds.")
        finally:
            _stop_probe(process, owned_children, debugger_url)
