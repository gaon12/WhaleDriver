import io
import subprocess
import zipfile
from pathlib import Path

import pytest

from whaledriver.errors import DriverDownloadError, DriverVersionError, UnsupportedPlatformError
from whaledriver.manager import (
    BUILD_METADATA_URL,
    MILESTONE_METADATA_URL,
    DriverManager,
    DriverRelease,
    driver_platform,
    verify_driver,
)

ENGINE = "150.0.7871.252"
DRIVER = "150.0.7871.100"
ARCHIVE_URL = f"https://storage.googleapis.com/chrome-for-testing-public/{DRIVER}/win64/chromedriver-win64.zip"


def release_record(version=DRIVER, url=ARCHIVE_URL):
    return {"version": version, "downloads": {"chromedriver": [{"platform": "win64", "url": url}]}}


def make_archive(extra=None):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("chromedriver-win64/chromedriver.exe", b"test executable")
        archive.writestr("chromedriver-win64/LICENSE.chromedriver", b"upstream license")
        archive.writestr(
            "chromedriver-win64/THIRD_PARTY_NOTICES.chromedriver", b"third-party notice"
        )
        if extra:
            archive.writestr(extra, b"unexpected content")
    return output.getvalue()


def fake_version(executable, engine, *, expected_version=None):
    assert Path(executable).is_file()
    assert engine.split(".")[0] == ENGINE.split(".")[0]
    assert expected_version == DRIVER
    return DRIVER


@pytest.mark.parametrize(
    ("system", "machine", "expected"),
    [
        ("win32", "AMD64", "win64"),
        ("win32", "x86", "win32"),
        ("darwin", "arm64", "mac-arm64"),
        ("darwin", "x86_64", "mac-x64"),
        ("linux", "x86_64", "linux64"),
    ],
)
def test_platform_selection(system, machine, expected, monkeypatch):
    monkeypatch.setattr("whaledriver.manager.sys.platform", system)
    monkeypatch.setattr("whaledriver.manager.platform.machine", lambda: machine)
    assert driver_platform() == expected


def test_linux_arm_is_not_treated_as_x86(monkeypatch):
    monkeypatch.setattr("whaledriver.manager.sys.platform", "linux")
    monkeypatch.setattr("whaledriver.manager.platform.machine", lambda: "aarch64")
    with pytest.raises(UnsupportedPlatformError, match="no supported driver"):
        driver_platform()


def test_build_release_is_preferred_without_milestone_request(tmp_path, monkeypatch):
    manager = DriverManager(tmp_path)
    urls = []

    def metadata(url):
        urls.append(url)
        return {"builds": {"150.0.7871": release_record()}}

    monkeypatch.setattr(manager, "_read_json", metadata)
    assert manager.resolve(ENGINE, "win64").version == DRIVER
    assert urls == [BUILD_METADATA_URL]


def test_missing_build_falls_back_only_to_same_milestone(tmp_path, monkeypatch):
    manager = DriverManager(tmp_path)
    data = {
        BUILD_METADATA_URL: {"builds": {}},
        MILESTONE_METADATA_URL: {"milestones": {"150": release_record()}},
    }
    monkeypatch.setattr(manager, "_read_json", data.__getitem__)
    assert manager.resolve(ENGINE, "win64").url == ARCHIVE_URL


@pytest.mark.parametrize(
    "record",
    [None, {}, release_record("149.0.100.1"), release_record(url="https://example.com/driver.zip")],
)
def test_missing_malformed_or_untrusted_release_is_rejected(record, tmp_path, monkeypatch):
    manager = DriverManager(tmp_path)
    monkeypatch.setattr(manager, "_read_json", lambda _: {"builds": {"150.0.7871": record}})
    with pytest.raises(DriverDownloadError, match="No valid official"):
        manager.resolve(ENGINE, "win64")


@pytest.mark.parametrize("version", ["5.39.412.57", "114.0.5735.90", "150", "../../escape"])
def test_unsupported_engine_version_is_rejected_before_network(version, tmp_path):
    with pytest.raises(DriverVersionError):
        DriverManager(tmp_path).resolve(version, "win64")


def test_archive_install_preserves_notices_and_reuses_valid_cache(tmp_path, monkeypatch):
    manager = DriverManager(tmp_path)
    downloads = []
    monkeypatch.setattr("whaledriver.manager.driver_platform", lambda: "win64")
    monkeypatch.setattr("whaledriver.manager.verify_driver", fake_version)
    monkeypatch.setattr(manager, "resolve", lambda *_: DriverRelease(DRIVER, "win64", ARCHIVE_URL))

    def download(url, *, limit):
        downloads.append(url)
        return make_archive()

    monkeypatch.setattr(manager, "_download", download)
    executable = manager.install(ENGINE)
    assert executable.read_bytes() == b"test executable"
    assert (executable.parent / "LICENSE.chromedriver").read_bytes() == b"upstream license"
    assert (executable.parent / "THIRD_PARTY_NOTICES.chromedriver").is_file()
    assert manager.install(ENGINE) == executable
    assert downloads == [ARCHIVE_URL]
    assert not list((tmp_path / "win64").glob(".download-*"))


@pytest.mark.parametrize("unsafe", ["../../escape.exe", "/absolute.exe", "folder\\escape.exe"])
def test_unsafe_archive_is_rejected_without_extracting_outside_staging(tmp_path, unsafe):
    release = DriverRelease(DRIVER, "win64", ARCHIVE_URL)
    archive = make_archive(unsafe)
    # ZipFile normalizes Windows separators when writing a test archive. Restore
    # the raw unsafe entry in both ZIP headers to exercise the reader on Windows.
    if "\\" in unsafe:
        archive = archive.replace(unsafe.replace("\\", "/").encode(), unsafe.encode())
    with pytest.raises(DriverDownloadError, match="unsafe path"):
        DriverManager._unpack(archive, release, tmp_path, "chromedriver.exe")
    assert not (tmp_path.parent / "escape.exe").exists()


def test_archive_requires_upstream_license(tmp_path):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("chromedriver-win64/chromedriver.exe", b"test executable")
    with pytest.raises(DriverDownloadError, match="license notice"):
        DriverManager._unpack(
            output.getvalue(),
            DriverRelease(DRIVER, "win64", ARCHIVE_URL),
            tmp_path,
            "chromedriver.exe",
        )


def test_offline_empty_cache_is_actionable_and_does_not_request_network(tmp_path, monkeypatch):
    monkeypatch.setattr("whaledriver.manager.driver_platform", lambda: "win64")
    manager = DriverManager(tmp_path, offline=True)
    monkeypatch.setattr(manager, "resolve", lambda *_: pytest.fail("Offline mode used the network"))
    with pytest.raises(DriverDownloadError, match="Run online once"):
        manager.install(ENGINE)


def test_offline_cache_can_use_a_same_milestone_driver(tmp_path, monkeypatch):
    executable = tmp_path / "win64" / DRIVER / "chromedriver.exe"
    executable.parent.mkdir(parents=True)
    executable.touch()
    (executable.parent / "LICENSE.chromedriver").touch()
    monkeypatch.setattr("whaledriver.manager.driver_platform", lambda: "win64")
    monkeypatch.setattr("whaledriver.manager.verify_driver", fake_version)
    assert DriverManager(tmp_path, offline=True).install("150.0.9999.1") == executable.resolve()


@pytest.mark.parametrize("output", ["ChromeDriver 149.0.100.1", "WhaleDriver 150.0.7871.100", ""])
def test_verify_rejects_mismatched_or_invalid_executable(tmp_path, monkeypatch, output):
    executable = tmp_path / "driver"
    executable.touch()
    monkeypatch.setattr(
        "whaledriver.manager.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, stdout=output),
    )
    with pytest.raises(DriverVersionError):
        verify_driver(executable, ENGINE)


def test_explicit_driver_bypasses_platform_and_network(tmp_path, monkeypatch):
    executable = tmp_path / "driver"
    executable.touch()
    monkeypatch.setattr("whaledriver.manager.verify_driver", lambda *_: DRIVER)
    monkeypatch.setattr(
        "whaledriver.manager.driver_platform", lambda: pytest.fail("Platform lookup")
    )
    assert (
        DriverManager(tmp_path, offline=True).install(ENGINE, driver_path=executable) == executable
    )


def test_portable_backend_is_used_before_cache_or_network(tmp_path, monkeypatch):
    launcher = tmp_path / "whaledriver.exe"
    launcher.touch()
    backend = tmp_path / "drivers/win64/chromedriver.exe"
    backend.parent.mkdir(parents=True)
    backend.touch()
    monkeypatch.setattr("whaledriver.manager.sys.frozen", True, raising=False)
    monkeypatch.setattr("whaledriver.manager.sys.executable", str(launcher))
    monkeypatch.setattr("whaledriver.manager.driver_platform", lambda: "win64")
    monkeypatch.setattr("whaledriver.manager.verify_driver", lambda *_: DRIVER)
    manager = DriverManager(tmp_path / "empty-cache", offline=True)
    assert manager.install(ENGINE) == backend


def test_incompatible_portable_backend_reports_a_mismatch_instead_of_downloading(
    tmp_path, monkeypatch
):
    backend = tmp_path / "chromedriver.exe"
    backend.touch()
    monkeypatch.setattr("whaledriver.manager.driver_platform", lambda: "win64")
    monkeypatch.setattr("whaledriver.manager.bundled_driver_path", lambda _: backend)

    def mismatch(*_):
        raise DriverVersionError("Bundled ChromeDriver does not match the browser")

    monkeypatch.setattr("whaledriver.manager.verify_driver", mismatch)
    with pytest.raises(DriverVersionError, match="does not match"):
        DriverManager(tmp_path).install(ENGINE)


@pytest.mark.integration
def test_install_and_verify_driver_for_installed_whale():
    from whaledriver.browser import probe_browser

    info = probe_browser()
    executable = DriverManager().install(info.chromium_version)
    assert (
        verify_driver(executable, info.chromium_version).split(".")[0]
        == info.chromium_version.split(".")[0]
    )
    assert (executable.parent / "LICENSE.chromedriver").is_file()
