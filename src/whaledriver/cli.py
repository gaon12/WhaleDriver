"""Diagnose Whale, install its compatible driver, or run a local WebDriver service."""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from selenium.common.exceptions import WebDriverException

from whaledriver import __version__
from whaledriver.browser import probe_browser
from whaledriver.errors import WhaleDriverError
from whaledriver.manager import DriverManager, default_cache_dir, driver_platform
from whaledriver.webdriver import Service


def _port(value: str) -> int:
    try:
        port = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("Port must be an integer.") from error
    if not 0 <= port <= 65535:
        raise argparse.ArgumentTypeError("Port must be between 0 and 65535.")
    return port


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="whaledriver",
        description=(
            "Independent, unofficial Selenium support for NAVER Whale. "
            "Whale is owned by NAVER; this project has no affiliation with NAVER."
        ),
    )
    parser.add_argument("--version", action="version", version=f"WhaleDriver {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser("doctor", help="Inspect the installed Whale without downloading.")
    install = commands.add_parser("install", help="Print the path to a compatible ChromeDriver.")
    serve = commands.add_parser(
        "serve", help="Run a local ChromeDriver service for remote clients."
    )
    for command in (doctor, install, serve):
        command.add_argument("--binary", type=Path, help="Path to the Whale executable.")
    for command in (doctor, install):
        command.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    for command in (install, serve):
        command.add_argument("--cache-dir", type=Path, help="Override the per-user driver cache.")
        command.add_argument("--offline", action="store_true", help="Use local drivers only.")
        command.add_argument(
            "--driver-path", type=Path, help="Use a compatible local ChromeDriver."
        )
    serve.add_argument(
        "--port", type=_port, default=9515, help="Service port; 0 selects a free port."
    )
    serve.add_argument("--verbose", action="store_true", help="Enable upstream ChromeDriver logs.")
    serve.add_argument("--log-path", type=Path, help="Write service logs to this file.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Return an exit status so CLI failures can be handled by scripts."""
    arguments = _parser().parse_args(argv)
    try:
        info = probe_browser(arguments.binary)
        if arguments.command == "doctor":
            payload = asdict(info)
            payload["binary"] = str(info.binary)
            payload["driver_platform"] = driver_platform()
            payload["cache_directory"] = str(default_cache_dir())
            payload["unofficial"] = True
            if arguments.json:
                print(json.dumps(payload))
            else:
                print(f"Whale executable: {info.binary}")
                print(f"Whale version: {info.whale_version}")
                print(f"Chromium engine: {info.chromium_version}")
                print(f"Driver platform: {payload['driver_platform']}")
                print(f"Driver cache: {payload['cache_directory']}")
                print("Unofficial project. Whale belongs to NAVER; no NAVER affiliation.")
            return 0

        executable = DriverManager(arguments.cache_dir, offline=arguments.offline).install(
            info.chromium_version, driver_path=arguments.driver_path
        )
        if arguments.command == "install":
            if arguments.json:
                print(
                    json.dumps(
                        {
                            "driver": str(executable),
                            "binary": str(info.binary),
                            "chromium_version": info.chromium_version,
                        }
                    )
                )
            else:
                print(executable)
            return 0

        service = Service(
            executable_path=str(executable),
            port=arguments.port,
            service_args=["--verbose"] if arguments.verbose else [],
            log_output=str(arguments.log_path) if arguments.log_path else None,
        )
        try:
            service.start()
            print(
                json.dumps(
                    {
                        "url": service.service_url,
                        "binary": str(info.binary),
                        "chromium_version": info.chromium_version,
                    }
                ),
                flush=True,
            )
            print(
                "Set the remote client's ChromeOptions binary to the reported Whale path.",
                file=sys.stderr,
            )
            print("Press Ctrl+C to stop the local service.", file=sys.stderr)
            while service.process.poll() is None:
                time.sleep(0.2)
            return service.process.returncode or 0
        finally:
            service.stop()
    except KeyboardInterrupt:
        return 0
    except (WhaleDriverError, OSError, WebDriverException) as error:
        print(f"WhaleDriver error: {error}", file=sys.stderr)
        return 1
