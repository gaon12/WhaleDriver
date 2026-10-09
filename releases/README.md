# Building and publishing releases

The default branch is `main`. Generated ChromeDriver inputs, compiled programs,
and archives are ignored by Git; source changes belong in focused commits.

## Local Windows build

1. Install Python 3.10 or newer and uv.
1. Replace the executable and both upstream notice files under `drivers/win64/`.
   If those inputs are absent, `releases/driver.json` selects the automatic download.
1. Run `build.cmd --smoke-test` when Whale is installed, or `build.cmd` for packaging only.
1. Find `whaledriver-<version>-win64-chromium<major>.zip` and its `.sha256` file in `dist/`.

The build reads the replacement executable's reported version. A changed backend
is included in the next ZIP without modifying Python source. Replacing a file does
not trigger a background build; executing the build script starts it explicitly.

The compiler creates a folder distribution. Extract the entire release ZIP, including
`_internal`, `drivers`, license files, and build metadata. Run `whaledriver.exe doctor`
or `whaledriver.exe serve --offline` from that folder.

## GitHub release workflow

Before making a new version:

1. Update `pyproject.toml` and `src/whaledriver/__init__.py` to the same version.
1. Set `whale_version` and `chromium_version` in `releases/driver.json` to the full
   browser versions verified for this release. The Chromium value also selects
   the automatic backend download.
1. Add `releases/v<version>.md` with clear English release notes.
1. Format, lint, test, build, and commit each coherent change.
1. Push `main`, then create and push an annotated version tag.

```powershell
git push origin main
git tag -a v0.1.0 -m "Release WhaleDriver 0.1.0"
git push origin v0.1.0
```

The `Release` workflow checks that the tag matches both version declarations,
runs quality checks and regular tests, builds the wheel and source distribution,
and compiles a Windows x64 portable ZIP using the default driver selection.
CI has no installed Whale and runs the compiled `--version` check; real Whale
smoke testing remains a local step before tagging.

After successful builds, the workflow creates a draft GitHub release with the
wheel, source archive, portable ZIP, and ZIP checksum. It publishes the release
as a prerelease only after upload succeeds. It does not replace an already
published release. Choose a new version tag for changed published artifacts.

The GitHub release title uses `<Whale version> / <Chromium version>`, for example
`5.39.412.57 / 150.0.7871.252`. Both values come from `releases/driver.json` and
must contain four numeric components. Use the full Chromium engine version
reported by the browser diagnostic command, because the user-agent string may
shorten that version. Package versions, Git tags such as `v0.1.0`, and download
filenames continue to identify the WhaleDriver code version separately.

Published releases and their downloads appear on the repository's
[Releases page](https://github.com/gaon12/WhaleDriver/releases).
GitHub uses `/releases/tag/<tag>` as the address of an individual release;
the tag connects that published release to its source commit.

The workflow can also be dispatched manually with an existing version tag to
recover a failed build or incomplete draft. Add a new release-note file for each
new tag. Local ChromeDriver replacement files are not pushed, so CI downloads
according to `releases/driver.json`; use that file to select the CI engine build.
