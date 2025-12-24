import os
import time
from datetime import datetime
import argparse

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# Reuse driver and config from scraper.main
from .main import (
    get_driver,
    BVK_URL,
    BVK_MAIN_INFO_URL,
    USERNAME,
    PASSWORD,
    logger,
)


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def save_text(path: str, content: str):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def snapshot_workflow(out_dir: str, include_screens: bool = False):
    ensure_dir(out_dir)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    def p(name: str) -> str:
        return os.path.join(out_dir, f"{ts}_{name}")

    driver = None
    try:
        logger.info("Starting snapshot workflow...")
        driver = get_driver()

        # 1) Login page
        logger.info("Opening BVK login page...")
        driver.get(BVK_URL)

        # Accept cookies if present
        try:
            cookie_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//input[@value='Souhlasím']"))
            )
            cookie_btn.click()
            logger.info("Accepted cookies on login page.")
        except TimeoutException:
            logger.info("No cookie banner on login page or already accepted.")

        # Save login page
        save_text(p("login_page.html"), driver.page_source)
        if include_screens:
            driver.save_screenshot(p("login_page.png"))
        logger.info("Saved login page mockups.")

        # Try to login (if credentials are provided)
        if not USERNAME or not PASSWORD:
            logger.warning("BVK_USERNAME/BVK_PASSWORD not set. Skipping login.")
        else:
            try:
                WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.ID, "ctl00_ctl00_lvLoginForm_LoginDialog1_edEmail"))
                )
                driver.find_element(By.ID, "ctl00_ctl00_lvLoginForm_LoginDialog1_edEmail").send_keys(USERNAME)
                driver.find_element(By.ID, "ctl00_ctl00_lvLoginForm_LoginDialog1_edPassword").send_keys(PASSWORD)
                driver.find_element(By.ID, "btnLogin").click()
            except TimeoutException:
                logger.warning("Login inputs not found; continuing anyway.")

        # 2) MainInfo page
        logger.info("Opening MainInfo page...")
        time.sleep(2)
        driver.get(BVK_MAIN_INFO_URL)

        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
        except TimeoutException:
            logger.warning("MainInfo page did not load fully in time.")

        save_text(p("main_info_page.html"), driver.page_source)
        if include_screens:
            driver.save_screenshot(p("main_info_page.png"))
        logger.info("Saved MainInfo page mockups.")

        # 3) Discover Suez URL
        logger.info("Finding Suez link...")
        suez_url = None
        try:
            suez_link = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//a[contains(@href, 'cz-sitr.suezsmartsolutions.com')]"))
            )
            suez_url = suez_link.get_attribute("href")
            logger.info(f"Found Suez URL: {suez_url}")
            save_text(p("suez_url.txt"), suez_url or "")
        except TimeoutException:
            logger.error("Suez link not found on MainInfo page.")

        # 4) Suez page
        if suez_url:
            driver.get(suez_url)
            try:
                WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
            except TimeoutException:
                logger.warning("Suez page body not detected in time.")

            save_text(p("suez_page.html"), driver.page_source)
            if include_screens:
                driver.save_screenshot(p("suez_page.png"))
            logger.info("Saved Suez page mockups.")

            # 5) Raw meter canvas
            try:
                canvas = WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".OdometerIndexCanvas canvas"))
                )
            except TimeoutException:
                # Try generic login/submit on Suez
                try:
                    login_btn = driver.find_element(By.XPATH, "//input[@type='submit'] | //button[@type='submit']")
                    login_btn.click()
                    logger.info("Clicked a submit button on Suez, waiting for canvas again...")
                    canvas = WebDriverWait(driver, 20).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".OdometerIndexCanvas canvas"))
                    )
                except Exception:
                    canvas = None

            if canvas is not None:
                logger.info("Waiting for meter animation before capturing canvas...")
                time.sleep(15)

                # Re-locate canvas to avoid staleness
                try:
                    canvas = driver.find_element(By.CSS_SELECTOR, ".OdometerIndexCanvas canvas")
                except Exception:
                    pass

                # Element screenshot (PNG)
                if include_screens:
                    try:
                        canvas.screenshot(p("raw_meter_canvas.png"))
                    except Exception as e:
                        logger.warning(f"Element screenshot failed: {e}")

                # Canvas toDataURL snapshot (higher fidelity if supported)
                try:
                    b64 = driver.execute_script(
                        "return arguments[0].toDataURL('image/png').substring(22);",
                        canvas,
                    )
                    import base64

                    with open(p("raw_meter_canvas_base64.png"), "wb") as f:
                        f.write(base64.b64decode(b64))
                except Exception as e:
                    logger.warning(f"Canvas toDataURL capture failed: {e}")

                logger.info("Saved raw meter canvas mockups.")

        logger.info(f"Snapshot workflow finished. Files saved to: {out_dir}")

    finally:
        if driver is not None:
            driver.quit()


if __name__ == "__main__":
    # Default output path inside repository: scraper/tests/resources
    repo_default_out = os.path.join(os.path.dirname(__file__), "tests", "resources")

    parser = argparse.ArgumentParser(description="Capture BVK workflow mockups")
    parser.add_argument(
        "--out",
        dest="out",
        default=repo_default_out,
        help="Output directory for mockups (default: scraper/tests/resources)",
    )
    parser.add_argument(
        "--include-screens",
        action="store_true",
        help="Also save full-page and element screenshots (PNG). By default only HTML and canvas base64 PNG are saved.",
    )
    args = parser.parse_args()

    snapshot_workflow(out_dir=args.out, include_screens=args.include_screens)
