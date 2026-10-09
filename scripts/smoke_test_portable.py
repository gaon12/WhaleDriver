"""Verify a frozen Windows build against the installed Whale browser."""

from __future__ import annotations

import argparse
import contextlib
import json
import queue
import subprocess
import threading
import urllib.error
import urllib.request
from pathlib import Path

import psutil
from selenium import webdriver

from whaledriver import Options


def smoke_test(executable: Path) -> None:
    executable = executable.resolve()
    installation = subprocess.run(
        [str(executable), "install", "--offline", "--json"],
        capture_output=True,
        text=True,
        timeout=40,
        check=True,
    )
    driver_path = Path(json.loads(installation.stdout)["driver"]).resolve()
    if not driver_path.is_relative_to(executable.parent / "drivers"):
        raise RuntimeError("The portable build did not select its bundled ChromeDriver.")
    process = subprocess.Popen(
        [str(executable), "serve", "--port", "0", "--offline"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    lines = queue.Queue()
    reader = threading.Thread(target=lambda: lines.put(process.stdout.readline()), daemon=True)
    reader.start()
    service_url = None
    try:
        line = lines.get(timeout=40)
        if not line:
            raise RuntimeError(f"Portable service exited before starting: {process.stderr.read()}")
        payload = json.loads(line)
        service_url = payload["url"]
        options = Options(headless=True)
        options.binary_location = payload["binary"]
        with webdriver.Remote(service_url, options=options) as driver:
            driver.get("data:text/html,<title>Portable WhaleDriver test</title><p>Works</p>")
            assert driver.title == "Portable WhaleDriver test"
            assert "Whale/" in driver.execute_script("return navigator.userAgent")
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(service_url + "/shutdown", timeout=3):
            pass
        if process.wait(timeout=10) != 0:
            raise RuntimeError("Portable service failed during shutdown.")
        print("Portable smoke test passed: bundled backend, real Whale session, and shutdown.")
    finally:
        if process.poll() is None and service_url:
            with (
                contextlib.suppress(OSError, urllib.error.URLError),
                urllib.request.urlopen(service_url + "/shutdown", timeout=3),
            ):
                pass
            with contextlib.suppress(subprocess.TimeoutExpired):
                process.wait(timeout=5)
        if process.poll() is None:
            with contextlib.suppress(psutil.Error):
                for child in psutil.Process(process.pid).children(recursive=True):
                    with contextlib.suppress(psutil.Error):
                        child.terminate()
            process.terminate()
            process.wait(timeout=5)
        reader.join(timeout=3)
        process.stdout.close()
        process.stderr.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    smoke_test(parser.parse_args().executable)
