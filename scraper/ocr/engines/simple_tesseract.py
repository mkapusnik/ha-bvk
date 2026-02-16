from __future__ import annotations

import re

import pytesseract
from PIL import Image, ImageOps

from scraper.ocr.base import OcrEngine


class SimpleTesseractEngine(OcrEngine):
    """Simpler OCR: binarize whole image and let Tesseract read digits.

    This is intentionally different from the split/invert approach. It can be used as
    a quick alternative if the portal changes the meter rendering.
    """

    name = "simple_tesseract"

    def _ocr_digits(self, image: Image.Image) -> str:
        cfg = (
            "--oem 3 --psm 7 "
            "-c tessedit_char_whitelist=0123456789. "
            "-c load_system_dawg=0 -c load_freq_dawg=0"
        )
        return pytesseract.image_to_string(image, config=cfg).strip()

    def read_meter(self, image: Image.Image) -> str:
        img = image.convert("L")
        w, h = img.size
        img = img.resize((w * 4, h * 4), Image.Resampling.LANCZOS)
        img = ImageOps.autocontrast(img)
        img = img.point(lambda px: 0 if px < 165 else 255, "L")
        img = ImageOps.expand(img, border=40, fill=255)

        text = self._ocr_digits(img)
        digits = re.findall(r"\d+", text)
        flat = "".join(digits)
        if not flat:
            return "0.0"
        if len(flat) <= 3:
            return f"0.{flat.zfill(3)}"
        return f"{flat[:-3].lstrip('0') or '0'}.{flat[-3:]}"
