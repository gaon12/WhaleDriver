"""Actionable errors shared by browser discovery, driver installation, and the CLI."""


class WhaleDriverError(RuntimeError):
    """Base error for failures that callers can report without a traceback."""


class BrowserNotFoundError(WhaleDriverError):
    """The requested Whale executable could not be found."""


class BrowserProbeError(WhaleDriverError):
    """An isolated Whale process could not report its Chromium version."""


class DriverDownloadError(WhaleDriverError):
    """A compatible upstream ChromeDriver could not be downloaded or installed."""


class DriverVersionError(WhaleDriverError):
    """A driver executable does not match the detected Chromium engine."""


class UnsupportedPlatformError(WhaleDriverError):
    """Upstream ChromeDriver has no supported binary for this platform."""
