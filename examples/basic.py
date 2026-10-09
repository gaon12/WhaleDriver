"""Run a small Selenium example against Whale without contacting an external site."""

from urllib.parse import quote

from selenium.webdriver.common.by import By

from whaledriver import Options, Whale


def main() -> None:
    html = "<title>WhaleDriver example</title><p id='message'>Hello from NAVER Whale!</p>"
    with Whale(options=Options(headless=True)) as driver:
        driver.get("data:text/html;charset=utf-8," + quote(html))
        print(f"Page title: {driver.title}")
        print(f"Message: {driver.find_element(By.ID, 'message').text}")
        print(f"Whale version: {driver.browser_info.whale_version}")
        print(f"Chromium engine: {driver.browser_info.chromium_version}")


if __name__ == "__main__":
    main()
