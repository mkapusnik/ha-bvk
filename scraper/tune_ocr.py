import os

import pytesseract
from PIL import Image, ImageOps

DATA_DIR = "/app/data"
RAW_IMAGE_PATH = os.path.join(DATA_DIR, "raw_meter.png")


def process_and_read(image, scale=2, threshold_method="autocontrast", padding=50):
    # 1. Grayscale
    img = image.convert("L")

    # 2. Resize
    width, height = img.size
    img = img.resize((width * scale, height * scale), Image.Resampling.LANCZOS)

    # 3. Split (65%)
    split_x = int(img.width * 0.65)
    left_part = img.crop((0, 0, split_x, img.height))
    right_part = img.crop((split_x, 0, img.width, img.height))

    # Process Left (Integers)
    left_part = ImageOps.invert(left_part)
    left_part = left_part.point(lambda x: 0 if x < 150 else 255, "L")

    # Process Right (Decimals)
    if threshold_method == "autocontrast":
        right_part = ImageOps.autocontrast(right_part)
    elif threshold_method == "standard":
        right_part = right_part.point(lambda x: 0 if x < 150 else 255, "L")
    elif threshold_method == "aggressive":
        right_part = right_part.point(lambda x: 0 if x < 200 else 255, "L")

    # OCR Separately
    custom_config = r"--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789"
    custom_config_dec = r"--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789"

    left_padded = ImageOps.expand(left_part, border=padding, fill=255)
    text_int = pytesseract.image_to_string(left_padded, config=custom_config).strip()

    right_padded = ImageOps.expand(right_part, border=padding, fill=255)
    text_dec = pytesseract.image_to_string(right_padded, config=custom_config_dec).strip()

    # Construct result
    import re

    val_int = "".join(re.findall(r"\d+", text_int))
    val_int = val_int.lstrip("0") or "0"

    val_dec = "".join(re.findall(r"\d+", text_dec))

    if len(val_dec) > 3:
        val_dec = val_dec[:3]

    val_dec = val_dec or "0"

    return f"{val_int}.{val_dec}"

    print(f"Loading {RAW_IMAGE_PATH}...")
    original = Image.open(RAW_IMAGE_PATH)

    scales = [2, 3]
    # methods = ["autocontrast", "aggressive"] # Old methods
    # paddings = [50]
    thresholds = [150, 170, 190, 200, 210, 220, 230]

    for scale in scales:
        print(f"\n--- Testing: Scale {scale}x ---")

        # Test Autocontrast
        res = process_and_read(original, scale, "autocontrast", 50)
        print(f"[Autocontrast] Pad=50: '{res}'")

        # Test granular thresholds
        for _th in thresholds:
            # Manually implement thresholding here since process_and_read has fixed methods
            # Or better, update process_and_read to accept int threshold
            pass


def process_and_read_v2(image, scale=2, threshold_val=None, padding=50):
    # 1. Grayscale
    img = image.convert("L")

    # 2. Resize
    width, height = img.size
    img = img.resize((width * scale, height * scale), Image.Resampling.LANCZOS)

    # 3. Split (65%)
    split_x = int(img.width * 0.65)
    left_part = img.crop((0, 0, split_x, img.height))
    right_part = img.crop((split_x, 0, img.width, img.height))

    # Process Left (Integers)
    left_part = ImageOps.invert(left_part)
    left_part = left_part.point(lambda x: 0 if x < 150 else 255, "L")

    # Process Right (Decimals)
    if threshold_val == "autocontrast":
        right_part = ImageOps.autocontrast(right_part)
    elif isinstance(threshold_val, int):
        right_part = right_part.point(lambda x: 0 if x < threshold_val else 255, "L")

    # Stitch
    processed_image = Image.new("L", (img.width, img.height))
    processed_image.paste(left_part, (0, 0))
    processed_image.paste(right_part, (split_x, 0))

    # Padding
    processed_image = ImageOps.expand(processed_image, border=padding, fill=255)

    # OCR
    custom_config = r"--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789"
    text = pytesseract.image_to_string(processed_image, config=custom_config).strip()
    return text


def main_v2():
    if not os.path.exists(RAW_IMAGE_PATH):
        print(f"File not found: {RAW_IMAGE_PATH}")
        return

    print(f"Loading {RAW_IMAGE_PATH}...")
    original = Image.open(RAW_IMAGE_PATH)

    scales = [2, 3]
    thresholds = ["autocontrast", 140, 150, 160, 170, 180, 190, 200, 210, 220]

    for scale in scales:
        print(f"\n--- Testing: Scale {scale}x ---")
        for th in thresholds:
            res = process_and_read_v2(original, scale, th, 50)
            print(f"Th={th}: '{res}'")


if __name__ == "__main__":
    main_v2()
