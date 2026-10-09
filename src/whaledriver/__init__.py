"""Independent, unofficial Selenium integration for NAVER Whale."""

from whaledriver.browser import BrowserInfo, find_whale, probe_browser
from whaledriver.errors import WhaleDriverError
from whaledriver.manager import DriverManager
from whaledriver.webdriver import Options, Service, Whale

__all__ = [
    "BrowserInfo",
    "DriverManager",
    "Options",
    "Service",
    "Whale",
    "WhaleDriverError",
    "find_whale",
    "probe_browser",
]

__version__ = "0.1.0"
