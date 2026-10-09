import hashlib
import importlib.metadata
import zipfile
from pathlib import Path

import pytest

from scripts.build_release import DRIVER_NOTICES, collect_licenses, create_archive, prepare_backend
from whaledriver.errors import DriverVersionError, WhaleDriverError


def replacement_driver(directory, version="150.0.7871.124"):
    directory.mkdir()
    (directory / "chromedriver.exe").write_text(version)
    for notice in DRIVER_NOTICES:
        (directory / notice).write_text("Notice for " + version)


@pytest.fixture
def driver_versions(monkeypatch):
    def verify(executable, engine):
        version = Path(executable).read_text()
        if version.split(".")[0] != engine.split(".")[0]:
            raise DriverVersionError("Driver major does not match")
        return version

    monkeypatch.setattr("scripts.build_release.read_driver_version", lambda path: path.read_text())
    monkeypatch.setattr("scripts.build_release.verify_driver", verify)


def test_replaced_driver_controls_build_version_without_network(
    tmp_path, driver_versions, monkeypatch
):
    directory = tmp_path / "win64"
    replacement_driver(directory, "151.0.8000.10")
    monkeypatch.setattr(
        "scripts.build_release.DriverManager.install", lambda *_: pytest.fail("Unexpected download")
    )
    backend = prepare_backend(directory, "win64")
    assert backend.version == "151.0.8000.10"
    assert backend.major == "151"


def test_explicit_engine_rejects_incompatible_replacement(tmp_path, driver_versions):
    directory = tmp_path / "win64"
    replacement_driver(directory)
    with pytest.raises(DriverVersionError, match="major does not match"):
        prepare_backend(directory, "win64", "151.0.8000.10")


def test_missing_notices_prevent_redistribution(tmp_path, driver_versions):
    directory = tmp_path / "win64"
    replacement_driver(directory)
    (directory / DRIVER_NOTICES[1]).unlink()
    with pytest.raises(WhaleDriverError, match="missing THIRD_PARTY_NOTICES"):
        prepare_backend(directory, "win64")


def test_absent_backend_is_downloaded_with_matching_notices(tmp_path, driver_versions, monkeypatch):
    downloaded = tmp_path / "downloaded"
    replacement_driver(downloaded)
    monkeypatch.setattr(
        "scripts.build_release.DriverManager.install",
        lambda *args: downloaded / "chromedriver.exe",
    )
    directory = tmp_path / "input"
    backend = prepare_backend(directory, "win64", "150.0.7871.252")
    assert backend.version == "150.0.7871.124"
    assert all((directory / name).is_file() for name in DRIVER_NOTICES)


def test_archive_retains_runtime_and_notices_and_has_valid_checksum(tmp_path):
    bundle = tmp_path / "whaledriver"
    bundle.mkdir()
    (bundle / "whaledriver.exe").write_bytes(b"runtime")
    driver = bundle / "drivers/win64"
    driver.mkdir(parents=True)
    replacement = driver / "LICENSE.chromedriver"
    replacement.write_text("upstream license")
    archive = tmp_path / "portable.zip"
    create_archive(bundle, archive)
    with zipfile.ZipFile(archive) as output:
        assert output.read("whaledriver/whaledriver.exe") == b"runtime"
        assert output.read("whaledriver/drivers/win64/LICENSE.chromedriver") == b"upstream license"
    checksum = archive.with_suffix(".zip.sha256").read_text().split()[0]
    assert checksum == hashlib.sha256(archive.read_bytes()).hexdigest()
    assert not archive.with_suffix(".zip.tmp").exists()


def test_license_collection_includes_dependency_and_python_notices(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    (source / "LICENSE").write_text("dependency license")
    (source / "LICENSE.txt").write_text("Python license")

    class Distribution:
        metadata = {"Name": "Test dependency"}
        version = "1.0"
        requires = []
        files = [importlib.metadata.PackagePath("LICENSE")]

        def locate_file(self, relative):
            return source / relative

    monkeypatch.setattr(
        "scripts.build_release.importlib.metadata.distribution", lambda _: Distribution()
    )
    monkeypatch.setattr("scripts.build_release.sys.base_prefix", str(source))
    destination = tmp_path / "licenses"
    collect_licenses(destination)
    assert (destination / "whaledriver/LICENSE").read_text() == "dependency license"
    assert (destination / "PYTHON_LICENSE.txt").read_text() == "Python license"


def test_license_collection_fails_when_a_dependency_notice_is_missing(tmp_path, monkeypatch):
    class Distribution:
        files = []

    monkeypatch.setattr(
        "scripts.build_release.importlib.metadata.distribution", lambda _: Distribution()
    )
    with pytest.raises(WhaleDriverError, match="No installed license files"):
        collect_licenses(tmp_path / "licenses")
