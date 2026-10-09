# WhaleDriver

An independent, unofficial Selenium integration for the NAVER Whale browser.

**NAVER Whale is owned by NAVER Corporation. This project has no affiliation
with NAVER Corporation or the NAVER Whale team and is not endorsed, sponsored,
or supported by them.**

The project uses the BSD 3-Clause license, the same license type as ChromeDriver.
See [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Development

Use Python 3.10 or newer and [uv](https://docs.astral.sh/uv/).

```powershell
uv sync --group dev
uv run ruff format .
uv run ruff check .
uv run pytest
uv build
```

Changes should be committed in small, coherent units after formatting, linting,
and validation. Write clear English comments, documentation, and commit messages.
