# Replaceable ChromeDriver input

For a Windows x64 build, extract these files from the official ChromeDriver
`chromedriver-win64.zip` archive into `drivers/win64/`:

- `chromedriver.exe`
- `LICENSE.chromedriver`
- `THIRD_PARTY_NOTICES.chromedriver`

Then run `build.cmd` or `./build.ps1` from the repository. Replace all three files
when updating ChromeDriver so the notices match the executable being distributed.
The builder reads the executable's actual version; no source edit is required.
This input directory is ignored by Git.

When no local executable exists, the builder installs an official driver for the
engine in `releases/driver.json` and copies it here. Use
`build.cmd --chromium-version 150.0.7871.252` to select a different engine build.
When a local executable exists, an explicit engine version also checks that its
major version matches before building.

Build on Windows x64. The portable ZIP contains the executable, this replaceable
backend, a Python runtime, and license files. Users must extract the entire ZIP.
