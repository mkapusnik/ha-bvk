from __future__ import annotations

import re

import pytesseract
from PIL import Image
from PIL import ImageOps

from scraper.ocr.base import OcrEngine


class TesseractSplitDigitsEngine(OcrEngine):
    """Alternative OCR: segment decimals into 3 digit crops and OCR each digit.

    The integer part is still read as a block, but decimals are treated as 3 separate
    glyphs, which can help when Tesseract fails to segment '786' as a group.
    """

    name = "tesseract_split_digits"

    def _ocr_digit(self, image: Image.Image) -> str:
        cfg = (
            "--oem 3 --psm 10 "
            "-c tessedit_char_whitelist=0123456789 "
            "-c classify_bln_numeric_mode=1 "
            "-c load_system_dawg=0 -c load_freq_dawg=0"
        )
        s = pytesseract.image_to_string(image, config=cfg)
        d = "".join(re.findall(r"\d+", s))
        return d[:1] if d else ""

    def _ocr_digits(self, image: Image.Image, *, psm: int) -> str:
        cfg = (
            f"--oem 3 --psm {psm} "
            "-c tessedit_char_whitelist=0123456789 "
            "-c classify_bln_numeric_mode=1 "
            "-c load_system_dawg=0 -c load_freq_dawg=0"
        )
        return pytesseract.image_to_string(image, config=cfg).strip()

    def _preprocess(self, image: Image.Image) -> tuple[Image.Image, Image.Image]:
        img = image.convert("L")
        w, h = img.size
        img = img.resize((w * 3, h * 3), Image.Resampling.LANCZOS)
        split_x = int(img.width * 0.65)
        left = img.crop((0, 0, split_x, img.height))
        right = img.crop((split_x, 0, img.width, img.height))

        left = ImageOps.invert(left)
        left = ImageOps.autocontrast(left)
        left = left.point(lambda x: 0 if x < 150 else 255, "L")
        left = ImageOps.expand(left, border=50, fill=255)

        right = ImageOps.autocontrast(right)
        right = right.point(lambda x: 0 if x < 170 else 255, "L")
        # remove border frame if present
        rw, rh = right.size
        margin = max(1, int(min(rw, rh) * 0.06))
        right = right.crop((margin, margin, rw - margin, rh - margin))
        right = ImageOps.expand(right, border=30, fill=255)

        return left, right

    def _split_3(self, img: Image.Image) -> list[Image.Image]:
        w, h = img.size
        step = max(1, w // 3)
        boxes = [(0, step), (step, step * 2), (step * 2, w)]
        out = []
        for x0, x1 in boxes:
            crop = img.crop((x0, 0, x1, h))
            crop = ImageOps.expand(crop, border=20, fill=255)
            out.append(crop)
        return out

    def read_meter(self, image: Image.Image) -> str:
        left, right = self._preprocess(image)
        text_int = self._ocr_digits(left, psm=7)
        val_int = "".join(re.findall(r"\d+", text_int)).lstrip("0") or "0"

        parts = self._split_3(right)
        digits = []
        for part in parts:
            d = self._ocr_digit(part)
            digits.append(d if d else "0")
        val_dec = "".join(digits)
        return f"{val_int}.{val_dec}"
