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
1. Update `releases/driver.json` if the automatic backend selection should change.
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

The workflow can also be dispatched manually with an existing version tag to
recover a failed build or incomplete draft. Add a new release-note file for each
new tag. Local ChromeDriver replacement files are not pushed, so CI downloads
according to `releases/driver.json`; use that file to select the CI engine build.
