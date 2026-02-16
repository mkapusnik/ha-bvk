from __future__ import annotations

import re

import pytesseract
from PIL import Image, ImageChops, ImageOps

from scraper.ocr.base import OcrEngine


class TesseractSplitDigitsEngine(OcrEngine):
    """Alternative OCR: segment decimals into 3 digit crops and OCR each digit.

    The integer part is still read as a block, but decimals are treated as 3 separate
    glyphs, which can help when Tesseract fails to segment '786' as a group.
    """

    name = "tesseract_split_digits"

    def _threshold(self, image: Image.Image, *, cutoff: int) -> Image.Image:
        return image.point(lambda px: 0 if px < cutoff else 255, "L")

    def _to_bw(self, image: Image.Image, *, cutoff: int) -> Image.Image:
        gray = image.convert("L")
        thr = self._threshold(gray, cutoff=cutoff)
        return thr.convert("1")

    def _extract_red_ink_bw(self, image: Image.Image) -> Image.Image:
        """Extract red digits into a BW mask.

        Fixtures show decimals in red on a light background. A plain grayscale
        threshold often erases the red strokes. Instead, we build a simple
        "redness" score: R - max(G,B), then threshold that.
        """

        rgb = image.convert("RGB")

        # Decimals are the rightmost ~3 wheels. Cropping reduces background noise
        # and makes the color-based segmentation stable.
        w, h = rgb.size
        dec = rgb.crop((int(w * 0.65), 0, w, h))
        dw, dh = dec.size
        dec = dec.resize((dw * 8, dh * 8), Image.Resampling.LANCZOS)

        r, g, b = dec.split()
        # Average of G and B: (g + b) / 2
        avg_gb = ImageChops.add(g, b, scale=2.0)
        # Use a scale to boost weak differences; red digits can be "only slightly" red.
        red_strength = ImageChops.subtract(r, avg_gb, scale=0.5)
        red_strength = ImageOps.autocontrast(red_strength)

        # In the live BVK/Suez canvas, red digits become darker in this image.
        bw = red_strength.point(lambda px: 0 if px < 140 else 255, "L")
        return bw.convert("1")

    def _crop_to_ink(self, image: Image.Image, *, pad_px: int = 8) -> Image.Image | None:
        bbox = image.getbbox()
        if bbox is None:
            return None
        w, h = image.size
        left, top, right, bottom = bbox
        left = max(0, left - pad_px)
        top = max(0, top - pad_px)
        right = min(w, right + pad_px)
        bottom = min(h, bottom + pad_px)
        return image.crop((left, top, right, bottom))

    def _ocr_digit(self, image: Image.Image) -> str:
        cfg = (
            "--oem 3 --psm 10 "
            "-c tessedit_char_whitelist=0123456789 "
            "-c classify_bln_numeric_mode=1 "
            "-c load_system_dawg=0 -c load_freq_dawg=0"
        )
        try:
            s = pytesseract.image_to_string(image, config=cfg)
        except pytesseract.TesseractError:
            return ""
        d = "".join(re.findall(r"\d+", s))
        return d[:1] if d else ""

    def _ocr_digits(self, image: Image.Image, *, psm: int) -> str:
        cfg = (
            f"--oem 3 --psm {psm} "
            "-c tessedit_char_whitelist=0123456789 "
            "-c classify_bln_numeric_mode=1 "
            "-c load_system_dawg=0 -c load_freq_dawg=0"
        )
        try:
            return pytesseract.image_to_string(image, config=cfg).strip()
        except pytesseract.TesseractError:
            return ""

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
        # Keep right part mostly intact; decimals are processed with red extraction.
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
        if not re.search(r"\d", text_int):
            text_int = self._ocr_digits(left, psm=8)
        val_int = "".join(re.findall(r"\d+", text_int)).lstrip("0") or "0"

        # Decimals: extract red ink to BW, crop to ink, then split.
        bw_red = self._extract_red_ink_bw(right)
        cropped = self._crop_to_ink(bw_red, pad_px=12)
        dec_base = cropped if cropped is not None else bw_red

        # First try to OCR all three decimals at once; this is surprisingly robust
        # once the red mask is clean.
        text_dec = self._ocr_digits(dec_base.convert("L"), psm=7)
        val_dec = "".join(re.findall(r"\d+", text_dec))
        if len(val_dec) >= 3:
            val_dec = val_dec[:3]
        else:
            parts = self._split_3(dec_base.convert("L"))
            digits = []
            for part in parts:
                d = self._ocr_digit(part)
                digits.append(d if d else "0")
            val_dec = "".join(digits)

        # Retry with a lower red threshold if we got nothing useful.
        if val_dec == "000":
            rgb = right.convert("RGB")
            r, g, b = rgb.split()
            gb_max = ImageChops.lighter(g, b)
            red_strength = ImageChops.subtract(r, gb_max, scale=0.5)
            red_strength = ImageOps.autocontrast(red_strength)
            bw2 = red_strength.point(lambda px: 0 if px < 200 else 255, "L").convert("1")
            cropped2 = self._crop_to_ink(bw2, pad_px=12)
            base2 = cropped2 if cropped2 is not None else bw2
            text_dec2 = self._ocr_digits(base2.convert("L"), psm=7)
            val_dec2 = "".join(re.findall(r"\d+", text_dec2))
            if len(val_dec2) >= 3:
                val_dec = val_dec2[:3]
            else:
                parts2 = self._split_3(base2.convert("L"))
                digits2 = []
                for part in parts2:
                    d2 = self._ocr_digit(part)
                    digits2.append(d2 if d2 else "0")
                val_dec = "".join(digits2)
        return f"{val_int}.{val_dec}"
