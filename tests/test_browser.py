import sys
from pathlib import Path

import pytest

from whaledriver.browser import _parse_version_info, find_whale, probe_browser
from whaledriver.errors import BrowserNotFoundError, BrowserProbeError


def version_payload(product="Chrome/150.0.7871.252"):
    return {
        "Browser": product,
        "User-Agent": "Mozilla/5.0 HeadlessChrome/150.0.0.0 Whale/5.39.412.57 Safari/537.36",
    }


def test_probe_uses_full_engine_version_instead_of_product_or_reduced_user_agent():
    info = _parse_version_info(Path("whale"), version_payload())
    assert info.chromium_version == "150.0.7871.252"
    assert info.whale_version == "5.39.412.57"


@pytest.mark.parametrize("product", ["Whale/5.39.412.57", "Chrome/150", "", None])
def test_rejects_missing_or_incomplete_chromium_version(product):
    with pytest.raises(BrowserProbeError, match="full Chromium"):
        _parse_version_info(Path("whale"), version_payload(product))


def test_rejects_chrome_executable_without_whale_identity():
    with pytest.raises(BrowserProbeError, match="Whale browser"):
        _parse_version_info(Path("chrome"), {"Browser": "Chrome/150.0.7871.252"})


def test_explicit_binary_takes_precedence_over_environment(tmp_path, monkeypatch):
    executable = tmp_path / "custom-browser"
    executable.touch()
    monkeypatch.setenv("WHALE_BINARY", str(tmp_path / "missing-browser"))
    assert find_whale(executable) == executable.resolve()


def test_environment_binary_is_respected(tmp_path, monkeypatch):
    executable = tmp_path / "custom-browser"
    executable.touch()
    monkeypatch.setenv("WHALE_BINARY", str(executable))
    assert find_whale() == executable.resolve()


def test_invalid_explicit_binary_does_not_fall_back_to_another_browser(tmp_path):
    with pytest.raises(BrowserNotFoundError, match="does not exist"):
        find_whale(tmp_path / "missing-browser")


def test_windows_discovery_selects_versioned_executable(tmp_path, monkeypatch):
    application = tmp_path / "Naver/Naver Whale/Application"
    application.mkdir(parents=True)
    (application / "whale.exe").touch()
    for version in ("5.9.100.1", "5.39.412.57", "5.40.100.1"):
        directory = application / version
        directory.mkdir()
        (directory / "whale.exe").touch()
    monkeypatch.setattr("whaledriver.browser.sys.platform", "win32")
    monkeypatch.delenv("WHALE_BINARY", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert find_whale() == (application / "5.40.100.1/whale.exe").resolve()


def test_linux_discovery_uses_path(tmp_path, monkeypatch):
    executable = tmp_path / "whale"
    executable.touch()
    monkeypatch.setattr("whaledriver.browser.sys.platform", "linux")
    monkeypatch.delenv("WHALE_BINARY", raising=False)
    monkeypatch.setattr("whaledriver.browser.shutil.which", lambda _: str(executable))
    assert find_whale() == executable.resolve()


def test_failed_process_is_reported_and_temporary_profile_is_removed(tmp_path, monkeypatch):
    monkeypatch.setattr("whaledriver.browser.tempfile.tempdir", str(tmp_path))
    with pytest.raises(BrowserProbeError, match="exited before opening DevTools"):
        probe_browser(sys.executable, timeout=3)
    assert not list(tmp_path.glob("whaledriver-probe-*"))


def test_timeout_must_be_positive():
    with pytest.raises(ValueError, match="greater than zero"):
        probe_browser(timeout=0)


@pytest.mark.integration
def test_installed_whale_reports_distinct_engine_and_product_versions():
    info = probe_browser()
    assert info.binary.is_file()
    assert int(info.chromium_version.split(".")[0]) >= 115
    assert info.whale_version != info.chromium_version
    assert f"Whale/{info.whale_version}" in info.user_agent
