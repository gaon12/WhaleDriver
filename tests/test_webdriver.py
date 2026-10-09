import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as conditions
from selenium.webdriver.support.ui import WebDriverWait

from whaledriver import BrowserInfo, DriverManager, Options, Service, Whale, probe_browser


@pytest.fixture
def configured_driver(tmp_path, monkeypatch):
    info = BrowserInfo(tmp_path / "whale", "150.0.7871.252", "5.39.412.57", "Whale/5.39.412.57")
    driver_path = tmp_path / "chromedriver"
    calls = {}

    def probe(binary, *, timeout):
        calls["binary"] = binary
        calls["probe_timeout"] = timeout
        return info

    def install(manager, engine, *, driver_path):
        calls.update(engine=engine, requested_driver=driver_path, offline=manager.offline)
        return tmp_path / "chromedriver"

    def start(driver, **kwargs):
        calls.update(kwargs)

    monkeypatch.setattr("whaledriver.webdriver.probe_browser", probe)
    monkeypatch.setattr("whaledriver.webdriver.DriverManager.install", install)
    monkeypatch.setattr("whaledriver.webdriver.ChromeWebDriver.__init__", start)
    return info, driver_path, calls


def test_webdriver_preserves_callers_options_and_sets_explicit_service_path(configured_driver):
    info, driver_path, calls = configured_driver
    options = ChromeOptions()
    options.add_argument("--window-size=1200,800")
    options.binary_location = "requested-browser"
    driver = Whale(options=options, offline=True, keep_alive=False, probe_timeout=7)
    assert options.binary_location == "requested-browser"
    assert calls["options"].binary_location == str(info.binary)
    assert calls["options"].arguments == options.arguments
    assert calls["service"].path == str(driver_path)
    assert calls["engine"] == info.chromium_version
    assert calls["offline"] is True
    assert calls["keep_alive"] is False
    assert calls["probe_timeout"] == 7
    assert driver.browser_info == info


def test_explicit_binary_overrides_options_binary(configured_driver):
    _, _, calls = configured_driver
    options = Options()
    options.binary_location = "options-browser"
    Whale(options=options, binary="explicit-browser")
    assert calls["binary"] == "explicit-browser"


def test_provided_service_settings_and_path_are_respected(configured_driver):
    _, driver_path, calls = configured_driver
    service = Service(executable_path=str(driver_path), port=9518, service_args=["--verbose"])
    Whale(service=service)
    assert calls["service"] is service
    assert calls["requested_driver"] == str(driver_path)
    assert service.port == 9518
    assert "--verbose" in service.command_line_args()


def test_conflicting_explicit_driver_paths_are_rejected(configured_driver):
    _, driver_path, _ = configured_driver
    with pytest.raises(ValueError, match="different ChromeDriver"):
        Whale(service=Service(executable_path=str(driver_path)), driver_path="another-driver")


def test_headless_options_keep_standard_chrome_capabilities():
    options = Options(headless=True)
    assert "--headless=new" in options.arguments
    assert options.to_capabilities()["browserName"] == "chrome"
    assert "goog:chromeOptions" in options.to_capabilities()


@pytest.fixture
def fixture_url():
    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

    handler = partial(QuietHandler, directory=str(Path(__file__).parent / "fixtures"))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/webdriver.html"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


@pytest.mark.integration
def test_selenium_controls_real_whale_and_quit_removes_the_session_profile(fixture_url):
    info = probe_browser()
    DriverManager().install(info.chromium_version)
    driver = Whale(options=Options(headless=True), offline=True)
    with driver:
        driver.get(fixture_url)
        assert driver.title == "WhaleDriver integration fixture"
        driver.find_element(By.ID, "name").send_keys("Whale")
        driver.find_element(By.ID, "greet").click()
        WebDriverWait(driver, 5).until(
            conditions.text_to_be_present_in_element((By.ID, "greeting"), "Hello, Whale!")
        )
        assert "Whale/" in driver.execute_script("return navigator.userAgent")
        driver.add_cookie({"name": "whaledriver-test", "value": "works"})
        assert driver.get_cookie("whaledriver-test")["value"] == "works"
        assert driver.get_screenshot_as_png().startswith(b"\x89PNG\r\n\x1a\n")
        driver.switch_to.frame(driver.find_element(By.ID, "frame"))
        assert driver.find_element(By.ID, "inside").text == "Frame content"
        driver.switch_to.default_content()
        original_window = driver.current_window_handle
        driver.switch_to.new_window("tab")
        driver.get(fixture_url + "?tab=second")
        assert len(driver.window_handles) == 2
        driver.close()
        driver.switch_to.window(original_window)
        assert driver.find_element(By.ID, "greeting").text == "Hello, Whale!"
        profile = Path(driver.capabilities["chrome"]["userDataDir"])
        service_process = driver.service.process
    assert service_process.poll() is not None
    deadline = time.monotonic() + 3
    while profile.exists() and time.monotonic() < deadline:
        time.sleep(0.1)
    assert not profile.exists()
