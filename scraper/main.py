import os
import time
import json
import logging
import schedule
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("/app/data/scraper.log")
    ]
)
logger = logging.getLogger(__name__)

# Configuration
BVK_URL = "https://zis.bvk.cz"
BVK_MAIN_INFO_URL = "https://zis.bvk.cz/Userdata/MainInfo.aspx"
USERNAME = os.environ.get("BVK_USERNAME")
PASSWORD = os.environ.get("BVK_PASSWORD")
CHECK_INTERVAL_HOURS = int(os.environ.get("CHECK_INTERVAL_HOURS", 4))
DATA_DIR = "/app/data"

def get_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--allow-running-insecure-content")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Chromium specific options
    chrome_options.binary_location = "/usr/bin/chromium"
    
    # Initialize driver with service
    from selenium.webdriver.chrome.service import Service
    service = Service("/usr/bin/chromedriver")
    
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def save_data(reading):
    timestamp = datetime.now().isoformat()
    data = {
        "timestamp": timestamp,
        "reading": reading
    }
    
    # Save latest
    latest_path = os.path.join(DATA_DIR, "latest.json")
    with open(latest_path, "w") as f:
        json.dump(data, f, indent=2)
    
    # Append to history
    history_path = os.path.join(DATA_DIR, "history.json")
    history = []
    if os.path.exists(history_path):
        try:
            with open(history_path, "r") as f:
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
        return True # No history, assume valid

    try:
        with open(history_path, "r") as f:
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
                m = re.search(r'\d+(\.\d+)?', s)
                if m:
                    return float(m.group(0))
                return 0.0

            new_val = parse_float(new_reading_str)
            last_val = parse_float(last_reading_str)
            
            logger.info(f"Validation Check: New={new_val}, Old={last_val}")
            
            if new_val >= last_val:
                return True
            
            # Reset detection
            if new_val < 1 and last_val > 100:
                logger.warning(f"Detected potential meter reset: {last_val} -> {new_val}. Accepting.")
                return True
                
            logger.warning(f"Validation FAILED: New ({new_val}) < Old ({last_val}). Ignoring.")
            return False
            
        except Exception as e:
            logger.warning(f"Could not parse readings for validation: {e}. Accepting.")
            return True # Fail open if parsing fails
            
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
            WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "ctl00_ctl00_lvLoginForm_LoginDialog1_edEmail")))
            driver.find_element(By.ID, "ctl00_ctl00_lvLoginForm_LoginDialog1_edEmail").send_keys(USERNAME)
            driver.find_element(By.ID, "ctl00_ctl00_lvLoginForm_LoginDialog1_edPassword").send_keys(PASSWORD)
            driver.find_element(By.ID, "btnLogin").click()
        except TimeoutException:
            logger.error(f"Login timeout. Current title: {driver.title}")
            logger.error(f"Page source snippet: {driver.page_source[:500]}")
            # Do NOT raise here if you want to retry or just log. But for now raising is fine as schedule will run again or container restarts.
            pass # Continue to try navigation? No, login is usually required.
            
        
        # 2. Navigate to MainInfo
        logger.info("Navigating to MainInfo...")
        # Wait for login to complete (check for redirect or specific element)
        time.sleep(2) 
        driver.get(BVK_MAIN_INFO_URL)
        
        # 3. Find Suez link
        logger.info("Finding Suez link...")
        suez_link = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//a[contains(@href, 'cz-sitr.suezsmartsolutions.com')]"))
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
                login_btn = driver.find_element(By.XPATH, "//input[@type='submit'] | //button[@type='submit']")
                login_btn.click()
                logger.info("Clicked login button. Waiting for canvas again...")
                
                canvas = WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".OdometerIndexCanvas canvas"))
                )
            except Exception as e:
                logger.error(f"Failed to recover from login page: {e}")
                return # Skip this run
        
        # Wait for animation to finish
        logger.info("Waiting for meter animation...")
        time.sleep(15)
        
        # Re-acquire canvas to avoid StaleElementReferenceException
        canvas = driver.find_element(By.CSS_SELECTOR, ".OdometerIndexCanvas canvas")

        # Get canvas as base64 image
        canvas_base64 = driver.execute_script("return arguments[0].toDataURL('image/png').substring(21);", canvas)
        
        # Decode and open image
        import base64
        import io
        from PIL import Image, ImageOps
        import pytesseract
        image_bytes = base64.b64decode(canvas_base64)
        image = Image.open(io.BytesIO(image_bytes))
        
        # Save RAW image for tuning (Disabled for production)
        # image.save(os.path.join(DATA_DIR, "raw_meter.png"))
        
        # Preprocessing
        # 1. Convert to grayscale
        image = image.convert('L')
        
        # 2. Resize (3x - Verified working in logs)
        width, height = image.size
        # Scale 3x
        image = image.resize((width * 3, height * 3), Image.Resampling.LANCZOS)
        
        # 3. Handle mixed polarity
        # IMPORTANT: Split adjusted to 0.67 as meter crossed 100m³ (5→6 digits)
        # User confirmed 0.67 looks visually correct
        split_x = int(image.width * 0.67)
        
        left_part = image.crop((0, 0, split_x, image.height))
        right_part = image.crop((split_x, 0, image.width, image.height))
        
        # Process Left (Integers)
        left_part = ImageOps.invert(left_part)
        left_part = ImageOps.autocontrast(left_part) # Re-enabled: needed for reliable OCR
        left_part = left_part.point(lambda x: 0 if x < 150 else 255, 'L')
        
        # Process Right (Decimals)
        # Apply autocontrast to normalize red digits against white background
        right_part = ImageOps.autocontrast(right_part)
        # Then apply threshold (180 worked in Step 1539)
        right_part = right_part.point(lambda x: 0 if x < 180 else 255, 'L')
          
        # Stitch back
        processed_image = Image.new('L', (width * 3, height * 3))
        processed_image.paste(left_part, (0, 0))
        processed_image.paste(right_part, (split_x, 0))
        
        # Add PADDING to the full image to help OCR with edges
        processed_image = ImageOps.expand(processed_image, border=50, fill=255)
        
        # Save debug image (Disabled for production)
        # processed_image.save(os.path.join(DATA_DIR, "debug_meter_processed.png"))
        
        # Perform OCR on full image
        custom_config = r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789'
        text = pytesseract.image_to_string(processed_image, config=custom_config).strip()
        
        logger.info(f"OCR Raw Result: {text}")
        
        # Format Reading
        import re
        raw_digits = "".join(re.findall(r'\d+', text))
        
        if len(raw_digits) > 3:
            # Assume last 3 digits are decimals
            val_dec = raw_digits[-3:]
            val_int = raw_digits[:-3]
        else:
            # Fallback for short numbers
            val_int = raw_digits
            val_dec = "0"
            
        # Strip leading zeros from integer part
        val_int = val_int.lstrip('0') or "0"
            
        if len(val_int) > 6:
            val_int = val_int[-6:]
            
        # Decimal: Max 3 digits.
        if len(val_dec) > 3:
            val_dec = val_dec[:3]
            
        reading = f"{val_int}.{val_dec}"
            
        logger.info(f"Formatted Reading: {reading}")
        
        if reading and validate_reading(reading):
            logger.info(f"Found valid reading: {reading}")
            save_data(reading)
        else:
            logger.warning("OCR failed or reading was rejected by validation.")
            
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        if driver:
            try:
                driver.save_screenshot(os.path.join(DATA_DIR, "error_screenshot.png"))
                logger.info("Saved error screenshot.")
            except:
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

    # Run once immediately
    job()

    # Schedule
    logger.info(f"Scheduling job every {CHECK_INTERVAL_HOURS} hours.")
    schedule.every(CHECK_INTERVAL_HOURS).hours.do(job)

    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()
