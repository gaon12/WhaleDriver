# Compatibility validation

## Verified on October 9, 2026

| Component                         | Tested version or platform |
| --------------------------------- | -------------------------- |
| Operating system                  | Windows x64                |
| Python                            | 3.11.9                     |
| NAVER Whale                       | 5.39.412.57                |
| Chromium engine reported by Whale | 150.0.7871.252             |
| Official ChromeDriver             | 150.0.7871.124             |
| Selenium                          | 4.50.0                     |

ChromeDriver is downloaded unchanged from the official Chrome for Testing
distribution. NAVER owns Whale; this independent project has no NAVER affiliation.

## Verified behavior

- Discover the installed Whale and resolve its versioned Windows executable.
- Read the full Chromium engine version with a headless temporary-profile probe.
- Close a probe and remove its profile, including repeated startup and shutdown.
- Download, verify, and cache a compatible official ChromeDriver with its notices.
- Reuse a cached driver in offline mode.
- Start a headless Whale session through the `Whale` Python API.
- Navigate to a local HTTP page and read its title.
- Find elements, type into an input, click a button, and wait for changed text.
- Execute JavaScript and verify that the actual user agent identifies Whale.
- Set and retrieve a cookie.
- Capture a PNG screenshot.
- Switch into and out of an iframe.
- Create, navigate, close, and switch between tabs.
- Quit the session, stop ChromeDriver, and remove its temporary browser profile.
- Run CLI diagnostics and offline installation through the installed entry point.
- Start a local CLI service, create a remote Selenium session using the reported
  Whale binary, and shut down the service after the session quits.
- Build a Windows x64 portable ZIP with PyInstaller 6.22.3.
- Run the compiled CLI and verify that offline installation selects its bundled
  ChromeDriver instead of the per-user cache.
- Open a real headless Whale session through the compiled service and stop it cleanly.
- Verify the ZIP integrity, bundled backend identity, required license files,
  and SHA-256 checksum.

The initial [GitHub validation run](https://github.com/gaon12/WhaleDriver/actions/runs/37929269063)
passed formatting, linting, browser-independent tests, and package builds on
Windows, macOS, and Linux with Python 3.10 and 3.13. This is separate from real
Whale validation, which was performed on Windows x64 only.

## Unverified behavior

Real Whale integration on macOS, Linux, Windows x86, and ARM platforms has not
been run in this workspace. Platform selection and driver discovery have unit
coverage, but that does not establish real-browser compatibility.

Whale-specific UI features, mobile browsers, Selenium Grid deployment, WebDriver
BiDi, extensions, downloads, proxy configuration, and visible-browser interactions
have not been validated. The project retains upstream Selenium APIs without
claiming that every upstream capability works in Whale.
