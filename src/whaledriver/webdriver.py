"""A Selenium WebDriver that configures Whale before starting ChromeDriver."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.webdriver import WebDriver as ChromeWebDriver

from whaledriver.browser import probe_browser
from whaledriver.manager import DriverManager


class Options(ChromeOptions):
    """Use standard Chrome options, with an optional headless convenience flag."""

    def __init__(self, *, headless: bool = False) -> None:
        super().__init__()
        self.add_argument("--no-first-run")
        self.add_argument("--no-default-browser-check")
        if headless:
            self.add_argument("--headless=new")


class Whale(ChromeWebDriver):
    """Launch NAVER Whale through a matching, unmodified upstream ChromeDriver.

    Selenium retains its normal element, navigation, wait, action, cookie, and
    JavaScript APIs. The returned browserName remains 'chrome' because that is
    the capability understood by upstream ChromeDriver.
    """

    def __init__(
        self,
        options: ChromeOptions | None = None,
        service: Service | None = None,
        keep_alive: bool = True,
        *,
        binary: str | Path | None = None,
        driver_path: str | Path | None = None,
        cache_dir: str | Path | None = None,
        offline: bool = False,
        probe_timeout: float = 15,
    ) -> None:
        configured_options = deepcopy(options) if options is not None else Options()
        requested_binary = (
            binary if binary is not None else configured_options.binary_location or None
        )
        self.browser_info = probe_browser(requested_binary, timeout=probe_timeout)
        configured_options.binary_location = str(self.browser_info.binary)
        configured_service = service if service is not None else Service()
        if (
            driver_path is not None
            and configured_service.path
            and Path(driver_path).expanduser().resolve()
            != Path(configured_service.path).expanduser().resolve()
        ):
            raise ValueError(
                "driver_path and service.path refer to different ChromeDriver executables."
            )
        requested_driver = (
            driver_path if driver_path is not None else configured_service.path or None
        )
        self.driver_path = DriverManager(cache_dir, offline=offline).install(
            self.browser_info.chromium_version, driver_path=requested_driver
        )
        configured_service.path = str(self.driver_path)
        super().__init__(
            options=configured_options, service=configured_service, keep_alive=keep_alive
        )
