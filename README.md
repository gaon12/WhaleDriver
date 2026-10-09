# WhaleDriver

An independent, unofficial Selenium integration for the NAVER Whale browser.

**NAVER Whale is owned by NAVER Corporation. This project has no affiliation
with NAVER Corporation or the NAVER Whale team and is not endorsed, sponsored,
or supported by them.**

The project uses the BSD 3-Clause license, the same license type as ChromeDriver.
See [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

WhaleDriver discovers the installed Whale browser, reads its actual Chromium
engine version, and connects it to a compatible, unmodified ChromeDriver. It
provides a Python Selenium API and a CLI for diagnostics, driver installation,
and running a local WebDriver service. It is a compatibility layer, not a rebuilt
C++ ChromeDriver fork. No browser or driver binary is included in this repository.

## Requirements and installation

- Python 3.10 or newer.
- A desktop installation of NAVER Whale using Chromium 115 or newer.
- Internet access for the first automatic driver installation, or a compatible
  local ChromeDriver supplied through `driver_path`.

Install from this repository; this version has not been published to PyPI:

```powershell
python -m pip install .
whaledriver doctor
```

For development, use `uv sync --group dev` and prefix commands with `uv run`.
You can also run every CLI command through `python -m whaledriver`.

## Python quick start

```python
from selenium.webdriver.common.by import By
from whaledriver import Options, Whale

with Whale(options=Options(headless=True)) as driver:
    driver.get("data:text/html,<title>Whale test</title><p id='message'>Hello, Whale!</p>")
    print(driver.title)
    print(driver.find_element(By.ID, "message").text)
```

Run the complete example with `uv run python examples/basic.py`.
Use `Options()` without `headless=True` to open a visible browser. Standard Selenium
methods, locators, explicit waits, actions, cookies, screenshots, frames, and windows
remain available. See the [Selenium Chrome documentation](https://www.selenium.dev/documentation/webdriver/browsers/chrome/)
for the underlying options and APIs.

```python
from whaledriver import Options, Service, Whale

options = Options(headless=True)
options.add_argument("--window-size=1280,800")

with Whale(
    options=options,
    binary=r"C:\Program Files\Naver\Naver Whale\Application\whale.exe",
    driver_path=r"C:\Tools\chromedriver.exe",
    offline=True,
) as driver:
    driver.get("data:text/html,<title>Local driver</title>")
    print(driver.browser_info.whale_version)
    print(driver.browser_info.chromium_version)

# Service settings are accepted too. When it has an executable path, that
# executable is validated and used instead of an automatic download.
service = Service(executable_path=r"C:\Tools\chromedriver.exe", port=9518)
```

The `binary` argument takes priority over `options.binary_location`. Otherwise,
WhaleDriver checks `WHALE_BINARY` and common installation paths. Supplied options
are copied before setting the browser path. On Windows, the versioned executable
is selected directly because Whale's outer launcher can exit after starting it.

The driver retains `browserName="chrome"` and `goog:chromeOptions`, as required by
upstream ChromeDriver. The browser it opens is Whale. Its `browserVersion` capability
is the Chromium engine version; `driver.browser_info.whale_version` identifies the
separate Whale product version.

## Driver selection and caching

Whale's product version and Chromium engine version are different. For example,
the tested Whale `5.39.412.57` uses Chromium `150.0.7871.252`. Picking ChromeDriver
based on the leading `5` would select the wrong driver.

WhaleDriver launches a short headless probe in a temporary profile and reads the
full engine version from DevTools. It does not use the reduced version in the
user agent. It closes the probe and its children before removing the profile.
Normal Selenium sessions also use temporary profiles unless you explicitly
add your own `--user-data-dir` argument.

Following [ChromeDriver's version selection guidance](https://developer.chrome.com/docs/chromedriver/downloads/version-selection),
the manager selects the latest patch for the same `MAJOR.MINOR.BUILD`. When that
build is unavailable, it selects a release from the same major milestone.
It downloads from official Chrome for Testing URLs, checks the executable's
reported version, and keeps the supplied license and third-party notice files
beside the executable. Existing valid drivers for the same build are reused.

Set `offline=True` to prohibit all driver metadata and download requests. Offline
mode prefers a cached driver for the same build, then another cached driver for
the same major version. An empty or incompatible cache produces an actionable
error. Browser detection still launches a local probe in offline mode.

| Setting             | Purpose                                                           |
| ------------------- | ----------------------------------------------------------------- |
| `WHALE_BINARY`      | Override the automatically discovered Whale executable.           |
| `WHALEDRIVER_CACHE` | Override the per-user driver cache directory.                     |
| `cache_dir`         | Override the cache for one `Whale` or `DriverManager` instance.   |
| `driver_path`       | Use a local executable after checking its Chromium major version. |
| `probe_timeout`     | Set the browser probe startup timeout in seconds; default: 15.    |

Default caches use `%LOCALAPPDATA%\WhaleDriver` on Windows,
`~/Library/Caches/whaledriver` on macOS, and `$XDG_CACHE_HOME/whaledriver` or
`~/.cache/whaledriver` on Linux.

## CLI and remote Selenium clients

```powershell
whaledriver doctor --json
whaledriver install
whaledriver install --offline --json
whaledriver serve --port 9515
```

`doctor` reports the discovered browser, both versions, the download platform,
and cache location. It does not download a driver. `install` prints the verified
driver path; its JSON output also includes the Whale binary and engine version.
Both commands return a nonzero status on failure.

`serve` starts the upstream ChromeDriver service with its default local access
policy. Its first stdout line is JSON containing `url`, `binary`, and
`chromium_version`. Use the reported `binary` in the remote client's Chrome
options. The server does not inject Whale into remote session capabilities.

```python
from selenium import webdriver
from whaledriver import Options, find_whale

options = Options(headless=True)
options.binary_location = str(find_whale())

# Run this client on the same computer as `whaledriver serve`.
with webdriver.Remote("http://localhost:9515", options=options) as driver:
    driver.get("data:text/html,<title>Remote Whale session</title>")
    print(driver.title)
```

Java, JavaScript, C#, and other Selenium clients can use the same service with
their standard Chrome options and the reported Whale binary path. For Java:

```java
ChromeOptions options = new ChromeOptions();
options.setBinary("<binary from the serve output>");
options.addArguments("--headless=new");
WebDriver driver = new RemoteWebDriver(new URL("http://localhost:9515"), options);
try {
    driver.get("data:text/html,<title>Whale</title>");
} finally {
    driver.quit();
}
```

Quit remote sessions before stopping the server with Ctrl+C. Use `--port 0` for
an automatically assigned port, `--verbose` for ChromeDriver logging, or
`--log-path driver.log` to save service logs. `--binary`, `--driver-path`,
`--cache-dir`, and `--offline` are available on `install` and `serve`.
The CLI is not a drop-in native executable for Selenium's `Service` constructor;
use `Whale`, or supply the executable printed by `install` and a Whale binary.

## Windows portable release

Download the Windows x64 ZIP from [GitHub Releases](https://github.com/gaon12/WhaleDriver/releases)
and extract the entire `whaledriver` folder. Keep `_internal`, `drivers`, and the
license files beside `whaledriver.exe`. Python is included in this distribution;
it does not need to be installed on the target computer. Whale must be installed.

```powershell
.\whaledriver.exe doctor
.\whaledriver.exe serve --port 9515 --offline
```

The included backend is used before the download cache. Its Chromium major must
match the installed Whale engine. A mismatch reports an error so you can replace
the backend, supply `--driver-path`, or rebuild for the new engine. The portable
server uses the same remote Chrome options described below.

## Rebuild after replacing ChromeDriver

Install Python 3.10 or newer and uv on the build computer. Extract the official
Windows x64 ChromeDriver archive into `drivers/win64/`, preserving these files:

```text
drivers/win64/chromedriver.exe
drivers/win64/LICENSE.chromedriver
drivers/win64/THIRD_PARTY_NOTICES.chromedriver
```

Replace all three files when updating the backend, then double-click `build.cmd`
or run the following command. The builder installs locked build dependencies,
reads the replacement's version, builds the standalone program, collects notices,
and writes the portable ZIP and SHA-256 checksum into `dist/`.

```powershell
.\build.cmd
# Also verify the compiled program against the installed Whale:
.\build.cmd --smoke-test
```

When the input directory is empty, the first build automatically installs the
official driver selected by `releases/driver.json`. Use
`.\build.cmd --chromium-version 150.0.7871.252` to request another engine version.
When a replacement already exists, it takes priority and an explicit engine
version checks its major version. Builds currently require Windows x64; they
can run without Whale unless `--smoke-test` is selected. No C++ toolchain is needed.

`build.ps1` and `uv run --group build --group dev python scripts/build_release.py`
provide the same build process. See [drivers/README.md](drivers/README.md).

Tags matching the package version, such as `v0.1.0`, trigger the release workflow.
It runs formatting, linting, and regular tests, builds the Python distributions
and Windows ZIP, uploads them to a draft release, then publishes it as a prerelease.
See [the release instructions](releases/README.md) for future versions.

## Compatibility and limits

| Platform                | Automatic download          | Real Whale validation                  |
| ----------------------- | --------------------------- | -------------------------------------- |
| Windows x64             | Implemented                 | Passed locally                         |
| Windows x86             | Implemented                 | Not yet tested                         |
| macOS x64 / ARM64       | Implemented                 | Not yet tested                         |
| Linux x64               | Implemented                 | Not yet tested                         |
| Linux ARM / Windows ARM | No native upstream download | A working local driver can be supplied |

See [the validation record](docs/compatibility.md) for exact tested versions.
Only the listed browser operations have been tested against real Whale. Whale
updates and differences from Chromium can affect additional commands. This
project does not implement Whale-specific sidebars, account features, or mobile
automation, and does not claim full WebDriver or BiDi conformance.

## Troubleshooting

- **Whale was not found:** use `--binary`, the `binary` argument, or `WHALE_BINARY`.
- **Driver version mismatch:** run `doctor` and select a driver for the reported
  Chromium engine, not the Whale product version.
- **No cached driver in offline mode:** run `whaledriver install` online once,
  or pass a compatible `driver_path`.
- **Download failed:** check connectivity to the official Chrome for Testing
  endpoints, or install a local driver and use offline mode.
- **Probe startup failed:** check that the binary runs and that temporary files
  can be created. `probe_timeout` can accommodate a slow browser startup.

## Development

Use Python 3.10 or newer and [uv](https://docs.astral.sh/uv/).

```powershell
uv sync --group dev
uv run ruff format .
uv run ruff check .
uv run mdformat README.md CONTRIBUTING.md THIRD_PARTY_NOTICES.md docs drivers releases
uv run pytest
uv run pytest --run-integration
uv build
```

Changes should be committed in small, coherent units after formatting, linting,
and validation. Write clear English comments, documentation, and commit messages.
See [CONTRIBUTING.md](CONTRIBUTING.md) for the required workflow. Regular tests
need no installed browser and perform no real downloads. Integration tests
explicitly launch Whale and may download the compatible official ChromeDriver.
The GitHub Actions workflow checks formatting, linting, regular tests, and package
builds on Windows, macOS, and Linux with Python 3.10 and 3.13. Real Whale integration
remains an explicit local validation step.
