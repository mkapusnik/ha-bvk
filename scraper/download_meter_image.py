import base64
import io
import os
from pathlib import Path

from PIL import Image
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


BVK_URL = "https://zis.bvk.cz"
BVK_MAIN_INFO_URL = "https://zis.bvk.cz/Userdata/MainInfo.aspx"


def _get_driver() -> webdriver.Chrome:
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--allow-running-insecure-content")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    chrome_options.binary_location = "/usr/bin/chromium"

    from selenium.webdriver.chrome.service import Service

    service = Service("/usr/bin/chromedriver")
    return webdriver.Chrome(service=service, options=chrome_options)


def download_current_meter_image(
    output_path: str | Path, *, wait_seconds: int = 15
) -> Path:
    username = os.environ.get("BVK_USERNAME")
    password = os.environ.get("BVK_PASSWORD")
    if not username or not password:
        raise RuntimeError(
            "BVK_USERNAME and BVK_PASSWORD must be set (use .env / docker compose)."
        )

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    driver: webdriver.Chrome | None = None
    try:
        driver = _get_driver()

        driver.get(BVK_URL)

        try:
            driver.save_screenshot(str(out_path.with_suffix(".login.png")))
        except Exception:
            pass

        try:
            cookie_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//input[@value='Souhlasím']"))
            )
            cookie_btn.click()
        except TimeoutException:
            pass

        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located(
                (By.ID, "ctl00_ctl00_lvLoginForm_LoginDialog1_edEmail")
            )
        )
        driver.find_element(
            By.ID, "ctl00_ctl00_lvLoginForm_LoginDialog1_edEmail"
        ).send_keys(username)
        driver.find_element(
            By.ID, "ctl00_ctl00_lvLoginForm_LoginDialog1_edPassword"
        ).send_keys(password)
        driver.find_element(By.ID, "btnLogin").click()

        try:
            driver.save_screenshot(str(out_path.with_suffix(".after_login.png")))
        except Exception:
            pass

        driver.get(BVK_MAIN_INFO_URL)

        try:
            driver.save_screenshot(str(out_path.with_suffix(".maininfo.png")))
        except Exception:
            pass

        suez_link = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located(
                (By.XPATH, "//a[contains(@href, 'cz-sitr.suezsmartsolutions.com')]")
            )
        )
        suez_url = suez_link.get_attribute("href")
        driver.get(suez_url)

        try:
            canvas = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, ".OdometerIndexCanvas canvas")
                )
            )
        except TimeoutException:
            login_btn = driver.find_element(
                By.XPATH, "//input[@type='submit'] | //button[@type='submit']"
            )
            login_btn.click()
            canvas = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, ".OdometerIndexCanvas canvas")
                )
            )

        import time

        time.sleep(wait_seconds)

        canvas = driver.find_element(By.CSS_SELECTOR, ".OdometerIndexCanvas canvas")
        canvas_base64 = driver.execute_script(
            "return arguments[0].toDataURL('image/png').substring(21);", canvas
        )

        image_bytes = base64.b64decode(canvas_base64)
        image = Image.open(io.BytesIO(image_bytes))
        image.save(out_path)
        return out_path
    finally:
        if driver:
            driver.quit()


def main() -> None:
    output = os.environ.get("BVK_OUTPUT_IMAGE", "tests/resources/144_786.png")
    saved = download_current_meter_image(output)
    print(f"Saved: {saved}")


if __name__ == "__main__":
    main()
