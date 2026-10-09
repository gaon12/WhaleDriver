# Contributing to WhaleDriver

WhaleDriver is unofficial and independent of NAVER. Preserve the ownership and
affiliation notices when updating documentation, package metadata, or examples.
Project source code uses BSD 3-Clause. Do not copy browser binaries or branding
into the repository, and preserve upstream notices with downloaded ChromeDriver.

## Required workflow

Complete these steps for each coherent change:

1. Modify the relevant code, documentation, and tests.
1. Format the modified files and run linting.
1. Run tests and other validation appropriate to the change.
1. Review the diff, then create a focused Git commit.

```powershell
uv sync --locked --group dev
uv run ruff format .
uv run mdformat README.md CONTRIBUTING.md THIRD_PARTY_NOTICES.md docs drivers releases
uv run ruff check .
uv run mdformat --check README.md CONTRIBUTING.md THIRD_PARTY_NOTICES.md docs drivers releases
uv run pytest
```

Use `uv run pytest --run-integration` for browser startup, process cleanup,
driver installation, Selenium session behavior, or local service changes.
Run `uv build` after changing public APIs or packaging. Integration tests create
isolated profiles and use a local fixture page instead of an external website.
Keep the regular suite runnable without Whale or network access.

## Code and test expectations

- Prefer clear function and variable names over abbreviations.
- Write comments and documents in easy, detailed English. Explain why behavior
  is needed when the reason is not apparent from the code.
- Keep Whale's product version separate from Chromium's engine version.
- Close only processes created by the current operation. Do not close a user's
  existing browser or use a personal profile in an automated test.
- Test behavior that matters: browser identity, driver compatibility, capability
  propagation, cleanup, and meaningful error paths.
- Mark tests that launch Whale or download an upstream binary with `integration`.
- Record real browser versions and operations in `docs/compatibility.md`. Treat
  an untested platform or feature as unverified.

## Commit messages

Create separate commits for independent features, fixes, or documentation work.
Do not combine an unrelated cleanup with a feature just because the files are
nearby. Include the tests belonging to a behavior change in the same commit.

Write the title and body in clear English. Describe the problem, the resulting
behavior, and the actual validation. A useful structure is:

```text
feat: add an offline driver installation mode

Allow a verified local driver or a compatible cache entry to be used without
requesting remote release metadata. Report how to populate an empty cache.

Validation: Ruff formatting and linting passed. Tests cover cache selection,
version mismatch, and the guarantee that offline mode makes no download request.
```

Do not report skipped tests or a configured CI workflow as completed real-browser
validation. Publication, package uploads, and remote repository changes should
be requested separately from local development.
