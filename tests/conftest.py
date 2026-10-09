"""Browser integration tests are opt-in; regular tests do not require Whale."""

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-integration", action="store_true", help="Launch Whale and allow driver downloads."
    )


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--run-integration"):
        skip = pytest.mark.skip(reason="Pass --run-integration to launch the installed Whale.")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip)
