# Ownership, affiliation, and third-party software

NAVER Whale is owned by NAVER Corporation. The Whale name, browser, branding,
and trademarks belong to NAVER and their respective owners.

WhaleDriver is an independent, unofficial project. It is not affiliated with,
endorsed by, sponsored by, or supported by NAVER Corporation or the NAVER Whale
team. It does not distribute the Whale browser or grant rights to its branding.

WhaleDriver's own source code uses the BSD 3-Clause license, the same license
type used by ChromeDriver's Chromium source code. This does not change the
licenses of Whale, Selenium, or any other dependency.

ChromeDriver is developed by the Chromium project. Its source files refer to
the [Chromium BSD license](https://github.com/chromium/chromium/blob/main/LICENSE).
Downloaded ChromeDriver archives can also contain third-party notices. Keep
these files with the executable when redistributing a downloaded driver.

WhaleDriver uses Selenium (Apache 2.0), websocket-client (Apache 2.0), and psutil
(BSD 3-Clause) as separately installed dependencies. Their respective packages
carry their license information. No third-party source code or browser binary
is copied into this repository.

Portable release ZIPs redistribute the unmodified ChromeDriver, a Python runtime,
and bundled dependencies. They include ChromeDriver's own license and third-party
notices, Python's license, and installed dependency license files under
`third-party-licenses/`. `INDEX.txt` identifies the collected distributions.
Whale itself is not included.

Portable executables are built with PyInstaller. Its bootloader is covered by
GPL 2.0 with an exception that permits generated applications to use their own
license, subject to dependency licenses. See the
[PyInstaller license documentation](https://pyinstaller.org/en/stable/license.html).
The builder retains the installed PyInstaller notices as well. This does not
change the BSD 3-Clause license of WhaleDriver's own source code.
