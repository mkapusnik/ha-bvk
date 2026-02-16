from __future__ import annotations

import base64
import io
import json
import os
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from PIL import Image
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from scraper.ocr.api import ocr_meter_reading_from_image
from scraper.ocr.base import OcrConfig


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


def dump_live_meter_image(*, out_dir: Path, wait_seconds: int = 15) -> Image.Image:
    bvk_url = "https://zis.bvk.cz"
    bvk_main_info_url = "https://zis.bvk.cz/Userdata/MainInfo.aspx"
    username = os.environ.get("BVK_USERNAME")
    password = os.environ.get("BVK_PASSWORD")
    if not username or not password:
        raise RuntimeError("BVK_USERNAME and BVK_PASSWORD must be set")

    out_dir.mkdir(parents=True, exist_ok=True)

    driver = None
    try:
        driver = _get_driver()
        driver.get(bvk_url)

        try:
            cookie_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//input[@value='Souhlasím']"))
            )
            cookie_btn.click()
        except TimeoutException:
            pass

        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "ctl00_ctl00_lvLoginForm_LoginDialog1_edEmail"))
        )
        driver.find_element(By.ID, "ctl00_ctl00_lvLoginForm_LoginDialog1_edEmail").send_keys(
            username
        )
        driver.find_element(By.ID, "ctl00_ctl00_lvLoginForm_LoginDialog1_edPassword").send_keys(
            password
        )
        driver.find_element(By.ID, "btnLogin").click()

        time.sleep(2)
        driver.get(bvk_main_info_url)

        suez_link = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.XPATH, "//a[contains(@href, 'cz-sitr.suezsmartsolutions.com')]")
            )
        )
        suez_url = suez_link.get_attribute("href")
        driver.get(suez_url)

        try:
            canvas = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".OdometerIndexCanvas canvas"))
            )
        except TimeoutException:
            try:
                login_btn = driver.find_element(
                    By.XPATH, "//input[@type='submit'] | //button[@type='submit']"
                )
                login_btn.click()
                canvas = WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".OdometerIndexCanvas canvas"))
                )
            except Exception as e:
                raise RuntimeError(f"Failed to find canvas/login to Suez: {e}") from e

        time.sleep(wait_seconds)
        canvas = driver.find_element(By.CSS_SELECTOR, ".OdometerIndexCanvas canvas")

        canvas_base64 = driver.execute_script(
            "return arguments[0].toDataURL('image/png').substring(21);", canvas
        )
        image_bytes = base64.b64decode(canvas_base64)
        image = Image.open(io.BytesIO(image_bytes))
        image.save(out_dir / "raw_meter.png")
        return image
    finally:
        if driver:
            driver.quit()


def main() -> None:
    data_dir = Path(os.environ.get("DATA_DIR", "/app/data"))
    out_dir = data_dir / "ocr_debug_live"
    algorithm = (os.environ.get("OCR_ALGORITHM", "tesseract_v1") or "tesseract_v1").strip()

    ts = datetime.now().isoformat(timespec="seconds")
    img = dump_live_meter_image(out_dir=out_dir)
    reading = ocr_meter_reading_from_image(img, config=OcrConfig(algorithm=algorithm))

    payload = {
        "timestamp": ts,
        "algorithm": algorithm,
        "reading": reading,
    }
    (out_dir / "result.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # Keep a rolling archive of raw captures too
    safe_ts = ts.replace(":", "-")
    img.save(out_dir / f"{safe_ts}.png")

    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
