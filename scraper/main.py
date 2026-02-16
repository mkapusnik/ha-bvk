import json
import logging
import os
import sys
import time
from datetime import datetime

import schedule
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from scraper.ocr.api import ocr_meter_reading_from_image
from scraper.ocr.base import OcrConfig
from scraper.ocr.factory import create_ocr_engine

# Configure logging (stdout only, guard against double-initialization)
_root_logger = logging.getLogger()
if not _root_logger.handlers:
    handler = logging.StreamHandler(stream=sys.stdout)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    _root_logger.setLevel(logging.INFO)
    _root_logger.addHandler(handler)

# Use a module logger that propagates to root (no extra handlers to avoid duplicates)
logger = logging.getLogger(__name__)


# Configuration
BVK_URL = "https://zis.bvk.cz"
BVK_MAIN_INFO_URL = "https://zis.bvk.cz/Userdata/MainInfo.aspx"
USERNAME = os.environ.get("BVK_USERNAME")
PASSWORD = os.environ.get("BVK_PASSWORD")
CHECK_INTERVAL_HOURS = int(os.environ.get("CHECK_INTERVAL_HOURS", 4))
OCR_ALGORITHM = os.environ.get("OCR_ALGORITHM", "tesseract_v1")
DATA_DIR = "/app/data"
IMAGES_DIR = os.path.join(DATA_DIR, "images")
OCR_DEBUG_DIR = os.path.join(DATA_DIR, "ocr_debug_live")


def get_driver():
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

    # Chromium specific options
    chrome_options.binary_location = "/usr/bin/chromium"

    # Initialize driver with service
    from selenium.webdriver.chrome.service import Service

    service = Service("/usr/bin/chromedriver")

    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver


def save_data(reading, image_filename=None):
    timestamp = datetime.now().isoformat()
    data = {"timestamp": timestamp, "reading": reading}
    if image_filename:
        data["image"] = image_filename

    # Save latest
    latest_path = os.path.join(DATA_DIR, "latest.json")
    with open(latest_path, "w") as f:
        json.dump(data, f, indent=2)

    # Append to history
    history_path = os.path.join(DATA_DIR, "history.json")
    history = []
    if os.path.exists(history_path):
        try:
            with open(history_path) as f:
                history = json.load(f)
        except json.JSONDecodeError:
            logger.warning("Could not decode history.json, starting fresh.")

    history.append(data)
    with open(history_path, "w") as f:
        json.dump(history, f, indent=2)

    logger.info(f"Saved reading: {reading}")


def validate_reading(new_reading_str):
    """
    Validates that the new reading is consistent with history.
    Rule: New >= Old (unless New is very small, implying reset).
    """
    history_path = os.path.join(DATA_DIR, "history.json")
    if not os.path.exists(history_path):
        return True  # No history, assume valid

    try:
        with open(history_path) as f:
            history = json.load(f)

        if not history:
            return True

        # Get last valid reading
        last_entry = history[-1]
        last_reading_str = last_entry["reading"]

        # Clean strings to floats
        try:
            # Remove purely non-numeric tail if any, though our format is clean
            import re

            def parse_float(s):
                # match first float-like pattern
                m = re.search(r"\d+(\.\d+)?", s)
                if m:
                    return float(m.group(0))
                return 0.0

            new_val = parse_float(new_reading_str)
            last_val = parse_float(last_reading_str)

            logger.info(f"Validation Check: New={new_val}, Old={last_val}")

            if new_val >= last_val:
                # Check for massive jumps (consumption > 500 * days)
                # Parse timestamps
                try:
                    last_ts_str = last_entry["timestamp"]
                    # Current time is basically "now" since we are validating a reading just taken
                    # But we can't easily pass "now" here without changing signature.
                    # However, "timestamp" in save_data is datetime.now().isoformat()
                    # We can assume "now" or relatively close.
                    from datetime import datetime

                    last_ts = datetime.fromisoformat(last_ts_str)
                    now_ts = datetime.now()

                    diff = now_ts - last_ts
                    days_diff = diff.total_seconds() / 86400.0

                    # Avoid division by zero or weirdness if ran immediately
                    if days_diff < 0.01:
                        days_diff = 0.01

                    consumption = new_val - last_val
                    max_allowed = 500 * days_diff

                    # If it's been a long time (e.g. first run in weeks), this might be large,
                    # but 500 per day is huge (avg household is <1 m3/day).
                    # 500 is extremely generous, so it catches only massive OCR errors
                    # (decimals shift).

                    if consumption > max_allowed:
                        logger.warning(
                            f"Validation FAILED: Consumption {consumption:.2f} > Max"
                            f" {max_allowed:.2f} (Days: {days_diff:.2f}). Huge jump detected."
                        )
                        return False

                except Exception as e:
                    logger.warning(
                        f"Validation timestamp check failed: {e}. Proceeding with simple check."
                    )

                return True

            # Reset detection
            if new_val < 1 and last_val > 100:
                logger.warning(
                    f"Detected potential meter reset: {last_val} -> {new_val}. Accepting."
                )
                return True

            logger.warning(f"Validation FAILED: New ({new_val}) < Old ({last_val}). Ignoring.")
            return False

        except Exception as e:
            logger.warning(f"Could not parse readings for validation: {e}. Accepting.")
            return True  # Fail open if parsing fails

    except Exception as e:
        logger.error(f"Error reading history for validation: {e}")
        return True


def job():
    logger.info("Starting scraping job (v4 - tuned ocr)...")
    driver = None
    try:
        driver = get_driver()

        # 1. Login to BVK
        logger.info("Navigating to BVK login page...")
        driver.get(BVK_URL)

        # Accept cookies if present (based on exploration)
        try:
            cookie_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//input[@value='Souhlasím']"))
            )
            cookie_btn.click()
            logger.info("Accepted cookies.")
        except TimeoutException:
            logger.info("No cookie banner found or already accepted.")

        # Login
        logger.info("Logging in...")
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located(
                    (By.ID, "ctl00_ctl00_lvLoginForm_LoginDialog1_edEmail")
                )
            )
            driver.find_element(By.ID, "ctl00_ctl00_lvLoginForm_LoginDialog1_edEmail").send_keys(
                USERNAME
            )
            driver.find_element(By.ID, "ctl00_ctl00_lvLoginForm_LoginDialog1_edPassword").send_keys(
                PASSWORD
            )
            driver.find_element(By.ID, "btnLogin").click()
        except TimeoutException:
            logger.error(f"Login timeout. Current title: {driver.title}")
            logger.error(f"Page source snippet: {driver.page_source[:500]}")
            # Do NOT raise here if you want to retry or just log. But for now raising is fine
            # as schedule will run again or container restarts.
            pass  # Continue to try navigation? No, login is usually required.

        # 2. Navigate to MainInfo
        logger.info("Navigating to MainInfo...")
        # Wait for login to complete (check for redirect or specific element)
        time.sleep(2)
        driver.get(BVK_MAIN_INFO_URL)

        # 3. Find Suez link
        logger.info("Finding Suez link...")
        suez_link = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.XPATH, "//a[contains(@href, 'cz-sitr.suezsmartsolutions.com')]")
            )
        )
        suez_url = suez_link.get_attribute("href")
        logger.info(f"Found Suez URL: {suez_url}")

        # 4. Navigate to Suez
        driver.get(suez_url)

        # 5. Extract reading
        logger.info("Extracting reading...")

        # Wait for canvas to be present
        try:
            canvas = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".OdometerIndexCanvas canvas"))
            )
        except TimeoutException:
            logger.warning("Canvas not found. Checking for login button...")
            try:
                # Try to find a login button (generic approach)
                login_btn = driver.find_element(
                    By.XPATH, "//input[@type='submit'] | //button[@type='submit']"
                )
                login_btn.click()
                logger.info("Clicked login button. Waiting for canvas again...")

                canvas = WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".OdometerIndexCanvas canvas"))
                )
            except Exception as e:
                logger.error(f"Failed to recover from login page: {e}")
                return  # Skip this run

        # Wait for animation to finish
        logger.info("Waiting for meter animation...")
        time.sleep(15)

        # Re-acquire canvas to avoid StaleElementReferenceException
        canvas = driver.find_element(By.CSS_SELECTOR, ".OdometerIndexCanvas canvas")

        # Get canvas as base64 image
        canvas_base64 = driver.execute_script(
            "return arguments[0].toDataURL('image/png').substring(21);", canvas
        )

        # Decode and open image
        import base64
        import io

        from PIL import Image

        image_bytes = base64.b64decode(canvas_base64)
        image = Image.open(io.BytesIO(image_bytes))

        # Save RAW image for tuning (stable filename)
        image.save(os.path.join(DATA_DIR, "raw_meter.png"))

        # Generate OCR debug variants for later tuning (stable filenames)
        try:
            os.makedirs(OCR_DEBUG_DIR, exist_ok=True)
            image.save(os.path.join(OCR_DEBUG_DIR, "raw_meter.png"))

            # Engine-specific preprocessed parts (if supported)
            engine = create_ocr_engine(OcrConfig(algorithm=OCR_ALGORITHM))
            engine_debug = getattr(engine, "debug_preprocessed_parts", None)
            if callable(engine_debug):
                left_dbg, right_dbg = engine_debug(image)
                left_dbg.save(os.path.join(OCR_DEBUG_DIR, "pre_left.png"))
                right_dbg.save(os.path.join(OCR_DEBUG_DIR, "pre_right.png"))

            # Decimals-focused debugging for live canvas (red digits)
            from PIL import ImageChops, ImageOps

            rgb = image.convert("RGB")
            w, h = rgb.size
            dec_crop = rgb.crop((int(w * 0.65), 0, w, h))
            dw, dh = dec_crop.size
            dec_crop_up = dec_crop.resize((dw * 8, dh * 8), Image.Resampling.LANCZOS)
            dec_crop_up.save(os.path.join(OCR_DEBUG_DIR, "dec_crop.png"))

            r, g, b = dec_crop_up.split()
            avg_gb = ImageChops.add(g, b, scale=2.0)
            red_strength = ImageChops.subtract(r, avg_gb, scale=0.5)
            red_strength = ImageOps.autocontrast(red_strength)
            red_strength.save(os.path.join(OCR_DEBUG_DIR, "dec_red_strength.png"))

            dec_bw = red_strength.point(lambda px: 0 if px < 140 else 255, "L")
            dec_bw.save(os.path.join(OCR_DEBUG_DIR, "dec_bw.png"))
        except Exception as dbg_err:
            logger.debug(f"Failed to generate OCR debug images: {dbg_err}")

        reading = ocr_meter_reading_from_image(image, config=OcrConfig(algorithm=OCR_ALGORITHM))

        logger.info(f"Formatted Reading: {reading}")

        # Save timestamped screenshot only when reading changed
        captured_ts = datetime.now().isoformat(timespec="seconds")
        safe_ts = captured_ts.replace(":", "-")

        prev_reading = None
        latest_path = os.path.join(DATA_DIR, "latest.json")
        if os.path.exists(latest_path):
            try:
                with open(latest_path) as f:
                    prev_reading = (json.load(f) or {}).get("reading")
            except Exception:
                prev_reading = None

        changed = prev_reading != reading

        image_filename = None
        if changed:
            image_filename = f"{safe_ts}.png"
            image.save(os.path.join(IMAGES_DIR, image_filename))

            # Archive OCR debug folder on change
            try:
                import shutil

                archive_dir = os.path.join(OCR_DEBUG_DIR, "archive", safe_ts)
                os.makedirs(archive_dir, exist_ok=True)
                for name in os.listdir(OCR_DEBUG_DIR):
                    src = os.path.join(OCR_DEBUG_DIR, name)
                    if os.path.isfile(src):
                        shutil.copy2(src, os.path.join(archive_dir, name))
            except Exception as arch_err:
                logger.debug(f"Failed to archive OCR debug images: {arch_err}")

        if reading and validate_reading(reading):
            logger.info(f"Found valid reading: {reading} (changed={changed})")
            save_data(reading, image_filename=image_filename)
        else:
            logger.warning("OCR failed or reading was rejected by validation.")

        # If we reached this point without raising exceptions, consider the run successful
        # and delete any previous error screenshot to reflect last successful state
        try:
            err_path = os.path.join(DATA_DIR, "error_screenshot.png")
            if os.path.exists(err_path):
                os.remove(err_path)
                logger.info("Removed previous error screenshot.")
        except Exception as _cleanup_err:
            # Do not fail the job because of cleanup
            logger.debug(f"Could not remove error screenshot: {_cleanup_err}")

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        if driver:
            try:
                driver.save_screenshot(os.path.join(DATA_DIR, "error_screenshot.png"))
                logger.info("Saved error screenshot.")
            except Exception:
                pass
    finally:
        if driver:
            driver.quit()
            logger.info("Driver closed.")


def main():
    if not USERNAME or not PASSWORD:
        logger.error("BVK_USERNAME and BVK_PASSWORD environment variables must be set.")
        return

    # Ensure data directory exists
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(IMAGES_DIR, exist_ok=True)

    # Run once immediately
    job()

    # Schedule
    logger.info(f"Scheduling job every {CHECK_INTERVAL_HOURS} hours.")
    schedule.every(CHECK_INTERVAL_HOURS).hours.do(job)
    # Log number of scheduled jobs to ensure it's not duplicated
    logger.info(f"Scheduled jobs: {len(schedule.get_jobs())}")

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
