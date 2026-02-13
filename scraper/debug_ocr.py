import os
from pathlib import Path

import pytesseract

from scraper.ocr import ocr_meter_reading_from_path


def main() -> None:
    img_path = Path(
        os.environ.get("BVK_OCR_IMAGE", "scraper/tests/resources/144_786.png")
    )
    debug_dir = Path(os.environ.get("BVK_OCR_DEBUG_DIR", "/app/data/ocr_debug"))

    print(f"tesseract: {pytesseract.get_tesseract_version()}")
    print(f"image: {img_path}")
    reading = ocr_meter_reading_from_path(img_path, debug_dir=debug_dir)
    print(f"reading: {reading}")
    print(f"debug_dir: {debug_dir}")


if __name__ == "__main__":
    main()
