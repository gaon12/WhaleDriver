import json
from pathlib import Path

import pytest

from whaledriver import BrowserInfo
from whaledriver.cli import main
from whaledriver.errors import BrowserNotFoundError


@pytest.fixture
def cli_browser(tmp_path, monkeypatch):
    info = BrowserInfo(tmp_path / "whale", "150.0.7871.252", "5.39.412.57", "Whale/5.39.412.57")
    monkeypatch.setattr("whaledriver.cli.probe_browser", lambda _: info)
    monkeypatch.setattr("whaledriver.cli.driver_platform", lambda: "win64")
    return info


def test_doctor_json_keeps_product_and_engine_versions_separate(cli_browser, capsys):
    assert main(["doctor", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["whale_version"] == cli_browser.whale_version
    assert payload["chromium_version"] == cli_browser.chromium_version
    assert payload["unofficial"] is True


def test_browser_error_has_nonzero_status_without_traceback(monkeypatch, capsys):
    def missing(_):
        raise BrowserNotFoundError("Set WHALE_BINARY to the installed browser")

    monkeypatch.setattr("whaledriver.cli.probe_browser", missing)
    assert main(["doctor"]) == 1
    assert "Set WHALE_BINARY" in capsys.readouterr().err


def test_install_propagates_explicit_driver_and_offline_setting(cli_browser, monkeypatch, capsys):
    requested = {}

    def install(manager, version, *, driver_path):
        requested.update(offline=manager.offline, path=driver_path, version=version)
        return Path("validated-driver")

    monkeypatch.setattr("whaledriver.cli.DriverManager.install", install)
    assert main(["install", "--offline", "--driver-path", "local-driver", "--json"]) == 0
    assert requested == {
        "offline": True,
        "path": Path("local-driver"),
        "version": cli_browser.chromium_version,
    }
    assert json.loads(capsys.readouterr().out)["driver"] == "validated-driver"


@pytest.mark.parametrize("port", ["-1", "65536", "not-a-port"])
def test_invalid_service_port_is_rejected_before_launch(port):
    with pytest.raises(SystemExit) as error:
        main(["serve", "--port", port])
    assert error.value.code == 2


def test_serve_stops_service_on_interrupt(cli_browser, monkeypatch, capsys):
    events = []

    class FakeProcess:
        def poll(self):
            return None

    class FakeService:
        service_url = "http://localhost:9515"
        process = FakeProcess()

        def __init__(self, **kwargs):
            events.append(kwargs)

        def start(self):
            events.append("start")

        def stop(self):
            events.append("stop")

    def interrupt(_):
        raise KeyboardInterrupt

    monkeypatch.setattr("whaledriver.cli.DriverManager.install", lambda *_, **__: Path("driver"))
    monkeypatch.setattr("whaledriver.cli.Service", FakeService)
    monkeypatch.setattr("whaledriver.cli.time.sleep", interrupt)
    assert main(["serve", "--offline"]) == 0
    assert events[-2:] == ["start", "stop"]
    assert json.loads(capsys.readouterr().out)["binary"] == str(cli_browser.binary)
