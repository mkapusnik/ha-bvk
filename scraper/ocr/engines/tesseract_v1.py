from __future__ import annotations

import re

import pytesseract
from PIL import Image, ImageChops, ImageOps

from scraper.ocr.base import OcrEngine


class TesseractV1Engine(OcrEngine):
    """Current (existing) algorithm moved as-is into an engine."""

    name = "tesseract_v1"

    def _preprocess_meter_image(self, image: Image.Image) -> tuple[Image.Image, Image.Image]:
        # Grayscale
        image = image.convert("L")

        # Resize for better OCR stability
        width, height = image.size
        image = image.resize((width * 3, height * 3), Image.Resampling.LANCZOS)

        # Split where the decimals start (tuned empirically)
        split_x = int(image.width * 0.65)
        left_part = image.crop((0, 0, split_x, image.height))
        right_part = image.crop((split_x, 0, image.width, image.height))

        # Integers: invert + contrast + threshold
        left_part = ImageOps.invert(left_part)
        left_part = ImageOps.autocontrast(left_part)
        left_part = left_part.point(lambda x: 0 if x < 150 else 255, "L")

        # Decimals: contrast + threshold
        right_part = ImageOps.autocontrast(right_part)
        right_part = right_part.point(lambda x: 0 if x < 150 else 255, "L")

        # Pad to help Tesseract handle edge glyphs
        left_padded = ImageOps.expand(left_part, border=50, fill=255)
        right_padded = ImageOps.expand(right_part, border=50, fill=255)

        return left_padded, right_padded

    def debug_preprocessed_parts(self, image: Image.Image) -> tuple[Image.Image, Image.Image]:
        return self._preprocess_meter_image(image)

    def _ocr_digits(self, image: Image.Image, *, psm: int) -> str:
        cfg = (
            f"--oem 3 --psm {psm} "
            "-c tessedit_char_whitelist=0123456789 "
            "-c classify_bln_numeric_mode=1 "
            "-c load_system_dawg=0 -c load_freq_dawg=0"
        )
        return pytesseract.image_to_string(image, config=cfg).strip()

    def _threshold(self, image: Image.Image, *, cutoff: int) -> Image.Image:
        return image.point(lambda px: 0 if px < cutoff else 255, "L")

    def _erase_border_band(self, image: Image.Image, *, band_px: int) -> Image.Image:
        if band_px <= 0:
            return image
        w, h = image.size
        band_px = min(band_px, (min(w, h) // 2) - 1)
        if band_px <= 0:
            return image

        img = image.copy()
        px = img.load()
        if px is None:
            return image

        for x in range(w):
            for y in range(band_px):
                px[x, y] = 255
            for y in range(h - band_px, h):
                px[x, y] = 255

        for y in range(h):
            for x in range(band_px):
                px[x, y] = 255
            for x in range(w - band_px, w):
                px[x, y] = 255

        return img

    def _thicken_strokes(self, image: Image.Image) -> Image.Image:
        w, h = image.size
        up = image.resize((w * 2, h * 2), Image.Resampling.NEAREST)
        return up.resize((w, h), Image.Resampling.NEAREST)

    def _thicken_strokes_n(self, image: Image.Image, *, n: int) -> Image.Image:
        out = image
        for _ in range(max(0, n)):
            out = self._thicken_strokes(out)
        return out

    def _crop_to_ink(self, image: Image.Image, *, pad_px: int = 6) -> Image.Image | None:
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

    def _to_bw(self, image: Image.Image, *, cutoff: int) -> Image.Image:
        gray = image.convert("L")
        thr = gray.point(lambda px: 0 if px < cutoff else 255, "L")
        return thr.convert("1")

    def _extract_red_ink_bw(self, image: Image.Image) -> Image.Image:
        """Extract red digits into a BW mask."""

        rgb = image.convert("RGB")

        w, h = rgb.size
        dec = rgb.crop((int(w * 0.65), 0, w, h))
        dw, dh = dec.size
        dec = dec.resize((dw * 8, dh * 8), Image.Resampling.LANCZOS)

        r, g, b = dec.split()
        avg_gb = ImageChops.add(g, b, scale=2.0)
        red_strength = ImageChops.subtract(r, avg_gb, scale=0.5)
        red_strength = ImageOps.autocontrast(red_strength)

        bw = red_strength.point(lambda px: 0 if px < 140 else 255, "L")
        return bw.convert("1")

    def _fix_border_artifacts(self, image: Image.Image) -> Image.Image:
        w, h = image.size
        margin = max(1, int(min(w, h) * 0.06))
        cropped = image.crop((margin, margin, w - margin, h - margin))
        return ImageOps.expand(cropped, border=30, fill=255)

    def _ocr_digits_scaled(self, image: Image.Image, *, psm: int, scale: int) -> str:
        if scale <= 1:
            return self._ocr_digits(image, psm=psm)
        w, h = image.size
        resized = image.resize((w * scale, h * scale), Image.Resampling.LANCZOS)
        return self._ocr_digits(resized, psm=psm)

    def _pad_to_square(self, image: Image.Image, *, pad: int = 20) -> Image.Image:
        w, h = image.size
        side = max(w, h) + (pad * 2)
        canvas = Image.new("L", (side, side), 255)
        x = (side - w) // 2
        y = (side - h) // 2
        canvas.paste(image.convert("L"), (x, y))
        return canvas

    def _split_into_digit_regions(
        self, bw: Image.Image, *, expected_digits: int = 3
    ) -> list[Image.Image]:
        img = bw.convert("1")
        w, h = img.size
        px = img.load()
        if px is None or w <= expected_digits:
            return [img]

        ink = []
        for x in range(w):
            c = 0
            for y in range(h):
                if px[x, y] == 0:
                    c += 1
            ink.append(c)

        threshold = max(1, int(h * 0.01))
        is_ink = [c >= threshold for c in ink]

        runs: list[tuple[int, int]] = []
        start = None
        for x, flag in enumerate(is_ink):
            if flag and start is None:
                start = x
            elif not flag and start is not None:
                runs.append((start, x))
                start = None
        if start is not None:
            runs.append((start, w))

        min_run = max(2, int(w * 0.02))
        merged: list[tuple[int, int]] = []
        for a, b in runs:
            if (b - a) < min_run:
                continue
            if not merged:
                merged.append((a, b))
                continue
            pa, pb = merged[-1]
            if a - pb <= max(2, int(w * 0.01)):
                merged[-1] = (pa, b)
            else:
                merged.append((a, b))

        bbox = img.getbbox()
        if bbox is None:
            return [img]
        bbox_left, _top, bbox_right, _bottom = bbox

        if len(merged) == expected_digits:
            boxes = merged
        else:
            left = bbox_left
            right = bbox_right
            span = max(1, right - left)
            if expected_digits != 3 or span < 30:
                step = max(1, span // expected_digits)
                boxes = []
                for i in range(expected_digits):
                    x0 = left + (i * step)
                    x1 = left + ((i + 1) * step) if i < (expected_digits - 1) else right
                    boxes.append((x0, x1))
            else:
                region = ink[left:right]
                win = 7
                smooth = []
                for i in range(len(region)):
                    a = max(0, i - (win // 2))
                    b = min(len(region), i + (win // 2) + 1)
                    smooth.append(sum(region[a:b]) / (b - a))

                idx1_start = int(len(smooth) * 0.20)
                idx1_end = int(len(smooth) * 0.45)
                idx2_start = int(len(smooth) * 0.55)
                idx2_end = int(len(smooth) * 0.80)

                def argmin(a: int, b: int) -> int:
                    sub = smooth[a:b]
                    if not sub:
                        return a
                    m = min(sub)
                    return a + sub.index(m)

                cut1 = argmin(idx1_start, idx1_end)
                cut2 = argmin(idx2_start, idx2_end)
                cut1x = left + cut1
                cut2x = left + cut2
                if cut2x <= cut1x + 5:
                    cut1x = left + (span // 3)
                    cut2x = left + (2 * span // 3)

                boxes = [(left, cut1x), (cut1x, cut2x), (cut2x, right)]

        crops: list[Image.Image] = []
        expand = max(2, int(w * 0.01))
        for x0, x1 in boxes:
            x0 = max(0, x0 - expand)
            x1 = min(w, x1 + expand)
            crop = img.crop((x0, 0, x1, h))
            crop2 = self._crop_to_ink(crop, pad_px=12)
            crops.append(crop2 if crop2 is not None else crop)
        return crops

    def _invert_bw(self, image: Image.Image) -> Image.Image:
        lum = image.convert("L")
        inv = ImageOps.invert(lum)
        return inv.convert("1")

    def _bw_black_pixel_stats(self, bw: Image.Image) -> tuple[int, int]:
        img = bw.convert("1")
        w, h = img.size
        px = img.load()
        if px is None:
            return 0, w * h
        black = 0
        for y in range(h):
            for x in range(w):
                if px[x, y] == 0:
                    black += 1
        return black, w * h

    def _bw_top_band_black_ratio(self, bw: Image.Image, *, band_ratio: float = 0.15) -> float:
        img = bw.convert("1")
        w, h = img.size
        band_h = max(1, int(h * band_ratio))
        px = img.load()
        if px is None:
            return 0.0
        black = 0
        total = w * band_h
        for y in range(band_h):
            for x in range(w):
                if px[x, y] == 0:
                    black += 1
        return black / total if total else 0.0

    def _bw_top_band_black_ratio_of_ink(
        self, bw: Image.Image, *, band_ratio: float = 0.15
    ) -> float:
        img = bw.convert("1")
        cropped = self._crop_to_ink(img, pad_px=0)
        if cropped is None:
            return 0.0
        return self._bw_top_band_black_ratio(cropped, band_ratio=band_ratio)

    def _bw_left_right_black_ratio(self, bw: Image.Image) -> tuple[float, float]:
        img = bw.convert("1")
        w, h = img.size
        px = img.load()
        if px is None or w <= 1 or h <= 1:
            return 0.0, 0.0
        mid = w // 2
        left_black = 0
        right_black = 0
        left_total = mid * h
        right_total = (w - mid) * h
        for y in range(h):
            for x in range(w):
                if px[x, y] == 0:
                    if x < mid:
                        left_black += 1
                    else:
                        right_black += 1
        left_ratio = left_black / left_total if left_total else 0.0
        right_ratio = right_black / right_total if right_total else 0.0
        return left_ratio, right_ratio

    def _bw_top_bottom_black_ratio(self, bw: Image.Image) -> tuple[float, float]:
        img = bw.convert("1")
        w, h = img.size
        px = img.load()
        if px is None or w <= 1 or h <= 1:
            return 0.0, 0.0
        mid = h // 2
        top_black = 0
        bottom_black = 0
        top_total = w * mid
        bottom_total = w * (h - mid)
        for y in range(h):
            for x in range(w):
                if px[x, y] == 0:
                    if y < mid:
                        top_black += 1
                    else:
                        bottom_black += 1
        top_ratio = top_black / top_total if top_total else 0.0
        bottom_ratio = bottom_black / bottom_total if bottom_total else 0.0
        return top_ratio, bottom_ratio

    def _count_white_holes(self, bw: Image.Image) -> int:
        img = bw.convert("1")
        w, h = img.size
        px = img.load()
        if px is None or w <= 1 or h <= 1:
            return 0

        visited = [[False] * w for _ in range(h)]

        def is_white(x: int, y: int) -> bool:
            return px[x, y] != 0

        def flood(x: int, y: int) -> None:
            stack = [(x, y)]
            visited[y][x] = True
            while stack:
                cx, cy = stack.pop()
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if 0 <= nx < w and 0 <= ny < h:
                        if not visited[ny][nx] and is_white(nx, ny):
                            visited[ny][nx] = True
                            stack.append((nx, ny))

        for x in range(w):
            if is_white(x, 0) and not visited[0][x]:
                flood(x, 0)
            if is_white(x, h - 1) and not visited[h - 1][x]:
                flood(x, h - 1)
        for y in range(h):
            if is_white(0, y) and not visited[y][0]:
                flood(0, y)
            if is_white(w - 1, y) and not visited[y][w - 1]:
                flood(w - 1, y)

        holes = 0
        for y in range(h):
            for x in range(w):
                if is_white(x, y) and not visited[y][x]:
                    holes += 1
                    flood(x, y)
        return holes

    def _read_decimal_split(self, right_img: Image.Image) -> tuple[str, int]:
        fixed = self._fix_border_artifacts(right_img)
        band = max(2, int(min(fixed.size) * 0.05))
        borderless = self._erase_border_band(fixed, band_px=band)
        bw = self._to_bw(borderless, cutoff=200)
        cropped = self._crop_to_ink(bw, pad_px=10)
        if cropped is None:
            return "", 0

        parts = self._split_into_digit_regions(cropped, expected_digits=3)
        digits = []
        detected = 0
        for idx, part in enumerate(parts):
            black, total = self._bw_black_pixel_stats(part)
            if total and (black / total) > 0.55:
                part = self._invert_bw(part)
            cropped_part = self._crop_to_ink(part, pad_px=12)
            if cropped_part is not None:
                part = cropped_part
            part = self._thicken_strokes_n(part, n=2)
            part_l = part.convert("L")
            w, h = part.size
            ratio = (w / h) if h else 0.0
            digit = ""
            for scale in (3, 4):
                s = self._ocr_digits_scaled(
                    self._pad_to_square(part_l, pad=30),
                    psm=10,
                    scale=scale,
                )
                d = "".join(re.findall(r"\d+", s))
                if d:
                    digit = d[:1]
                    break
            if not digit:
                inv_l = self._invert_bw(part).convert("L")
                for scale in (3, 4):
                    s = self._ocr_digits_scaled(
                        self._pad_to_square(inv_l, pad=30),
                        psm=10,
                        scale=scale,
                    )
                    d = "".join(re.findall(r"\d+", s))
                    if d:
                        digit = d[:1]
                        break
            holes = self._count_white_holes(part)
            if digit == "5" and holes == 0:
                left_ratio, right_ratio = self._bw_left_right_black_ratio(part)
                top_ratio, bottom_ratio = self._bw_top_bottom_black_ratio(part)
                if left_ratio > right_ratio * 1.5 and top_ratio > bottom_ratio * 1.15:
                    digit = "9"
            if holes >= 2 and digit == "5":
                digit = ""
            if digit == "1" and ratio >= 0.35:
                digit = ""
            if digit == "2" and holes == 1:
                left_ratio, right_ratio = self._bw_left_right_black_ratio(part)
                if right_ratio > left_ratio * 1.2:
                    digit = "9"
                elif left_ratio > right_ratio * 1.2:
                    digit = "6"
                else:
                    digit = "0"
            if digit == "3" and holes == 1:
                left_ratio, right_ratio = self._bw_left_right_black_ratio(part)
                if abs(left_ratio - right_ratio) < 0.03:
                    digit = "0"
            if digit:
                detected += 1
            if idx == 0 and not digit:
                black, total = self._bw_black_pixel_stats(part)
                top_ratio = self._bw_top_band_black_ratio_of_ink(part)
                if total and (black / total) > 0.03 and top_ratio > 0.06:
                    digit = "7"
            if not digit:
                if ratio > 0 and ratio < 0.35:
                    top_ratio, bottom_ratio = self._bw_top_bottom_black_ratio(part)
                    left_ratio, right_ratio = self._bw_left_right_black_ratio(part)
                    diff_tb = abs(top_ratio - bottom_ratio)
                    if holes >= 1:
                        if abs(left_ratio - right_ratio) < 0.03:
                            if diff_tb > 0.03:
                                digit = "0"
                            elif diff_tb < 0.02:
                                digit = "8"
                    if not digit:
                        if top_ratio > bottom_ratio * 1.15:
                            digit = "7"
                        else:
                            digit = "1"
                elif holes >= 2:
                    digit = "8"
                elif holes == 1:
                    left_ratio, right_ratio = self._bw_left_right_black_ratio(part)
                    top_ratio, bottom_ratio = self._bw_top_bottom_black_ratio(part)
                    if right_ratio > left_ratio * 1.2:
                        diff_tb = abs(top_ratio - bottom_ratio)
                        if diff_tb < 0.006:
                            digit = "1"
                        elif diff_tb < 0.02:
                            digit = "5"
                        else:
                            digit = "9"
                    elif left_ratio > right_ratio * 1.2:
                        if abs(top_ratio - bottom_ratio) < 0.02:
                            digit = "6"
                        else:
                            digit = "0"
                    else:
                        digit = "0"
                else:
                    left_ratio, right_ratio = self._bw_left_right_black_ratio(part)
                    top_ratio, bottom_ratio = self._bw_top_bottom_black_ratio(part)
                    if right_ratio > left_ratio * 1.5 and abs(top_ratio - bottom_ratio) < 0.02:
                        digit = "3"
                    elif top_ratio > bottom_ratio * 1.15:
                        digit = "7"
            if not digit:
                digit = "0"
            digits.append(digit)
        return "".join(digits), detected

    def read_meter(self, image: Image.Image) -> str:
        left_img, right_img = self._preprocess_meter_image(image)

        text_int = self._ocr_digits(left_img, psm=7)

        def has_3_digits(s: str) -> bool:
            return len("".join(re.findall(r"\d+", s))) >= 3

        text_dec = self._ocr_digits(right_img, psm=7)
        if not re.search(r"\d", text_dec):
            text_dec = self._ocr_digits(right_img, psm=8)
        if not re.search(r"\d", text_dec):
            text_dec = self._ocr_digits(self._fix_border_artifacts(right_img), psm=7)
        if not re.search(r"\d", text_dec):
            text_dec = self._ocr_digits(self._fix_border_artifacts(right_img), psm=8)
        if not re.search(r"\d", text_dec):
            relaxed = self._threshold(self._fix_border_artifacts(right_img), cutoff=190)
            text_dec = self._ocr_digits(relaxed, psm=7)
        if not re.search(r"\d", text_dec):
            relaxed = self._threshold(self._fix_border_artifacts(right_img), cutoff=190)
            text_dec = self._ocr_digits(relaxed, psm=8)
        if not re.search(r"\d", text_dec):
            fixed = self._fix_border_artifacts(right_img)
            text_dec = self._ocr_digits_scaled(fixed, psm=7, scale=3)
        if not re.search(r"\d", text_dec):
            fixed = self._fix_border_artifacts(right_img)
            text_dec = self._ocr_digits_scaled(fixed, psm=8, scale=3)
        if not re.search(r"\d", text_dec):
            fixed = self._threshold(self._fix_border_artifacts(right_img), cutoff=190)
            text_dec = self._ocr_digits_scaled(fixed, psm=7, scale=3)
        if not re.search(r"\d", text_dec):
            fixed = self._threshold(self._fix_border_artifacts(right_img), cutoff=190)
            text_dec = self._ocr_digits_scaled(fixed, psm=8, scale=3)
        if not re.search(r"\d", text_dec):
            fixed = self._fix_border_artifacts(right_img)
            band = max(2, int(min(fixed.size) * 0.05))
            borderless = self._erase_border_band(fixed, band_px=band)
            borderless = self._thicken_strokes(borderless)
            text_dec = self._ocr_digits_scaled(borderless, psm=7, scale=3)
        if not re.search(r"\d", text_dec):
            fixed = self._fix_border_artifacts(right_img)
            band = max(2, int(min(fixed.size) * 0.05))
            borderless = self._erase_border_band(fixed, band_px=band)
            borderless = self._thicken_strokes(borderless)
            text_dec = self._ocr_digits_scaled(borderless, psm=8, scale=3)

        if not re.search(r"\d", text_dec):
            fixed = self._fix_border_artifacts(right_img)
            band = max(2, int(min(fixed.size) * 0.05))
            borderless = self._erase_border_band(fixed, band_px=band)
            bw = self._to_bw(borderless, cutoff=200)
            cropped = self._crop_to_ink(bw, pad_px=10)
            if cropped is not None:
                text_dec = self._ocr_digits_scaled(cropped.convert("L"), psm=13, scale=3)
        if not has_3_digits(text_dec):
            fixed = self._fix_border_artifacts(right_img)
            band = max(2, int(min(fixed.size) * 0.05))
            borderless = self._erase_border_band(fixed, band_px=band)
            bw = self._to_bw(borderless, cutoff=200)
            cropped = self._crop_to_ink(bw, pad_px=10)
            if cropped is not None:
                padded = self._pad_to_square(cropped.convert("L"), pad=30)
                text_dec = self._ocr_digits_scaled(padded, psm=10, scale=4)

        if not has_3_digits(text_dec):
            red_bw = self._extract_red_ink_bw(image)
            red_cropped = self._crop_to_ink(red_bw, pad_px=12)
            red_base = red_cropped if red_cropped is not None else red_bw
            text_dec = self._ocr_digits_scaled(red_base.convert("L"), psm=7, scale=3)

        if not has_3_digits(text_dec):
            alt_dec, _detected = self._read_decimal_split(right_img)
            if alt_dec:
                text_dec = alt_dec
        if not re.search(r"\d", text_dec):
            fixed = self._fix_border_artifacts(right_img)
            band = max(2, int(min(fixed.size) * 0.05))
            borderless = self._erase_border_band(fixed, band_px=band)
            bw = self._to_bw(borderless, cutoff=200)
            cropped = self._crop_to_ink(bw, pad_px=10)
            if cropped is not None:
                text_dec = self._ocr_digits_scaled(cropped.convert("L"), psm=6, scale=3)

        red_dec = ""
        try:
            red_bw = self._extract_red_ink_bw(image)
            red_text = self._ocr_digits_scaled(red_bw.convert("L"), psm=7, scale=3)
            red_dec = "".join(re.findall(r"\d+", red_text))
        except Exception:
            red_dec = ""

        candidates: list[tuple[int, int, str]] = []
        left_candidates: list[tuple[int, int, str]] = []

        def add_candidate(text: str, *, left: bool = False) -> None:
            digits = "".join(re.findall(r"\d+", text))
            if not digits:
                return
            sig_len = len(digits.lstrip("0"))
            entry = (sig_len, len(digits), digits)
            candidates.append(entry)
            if left:
                left_candidates.append(entry)

        add_candidate(text_int, left=True)
        for psm in (6, 8):
            add_candidate(self._ocr_digits(left_img, psm=psm), left=True)

        thick = self._thicken_strokes(left_img)
        add_candidate(self._ocr_digits(thick, psm=7), left=True)

        full = image.convert("L")
        w, h = full.size
        full = full.resize((w * 3, h * 3), Image.Resampling.LANCZOS)
        full = ImageOps.autocontrast(full)
        full = full.point(lambda x: 0 if x < 150 else 255, "L")
        full = ImageOps.expand(full, border=50, fill=255)
        add_candidate(self._ocr_digits(full, psm=8))

        int_digits = ""
        if left_candidates:
            left_candidates.sort(reverse=True)
            if left_candidates[0][0] >= 2:
                int_digits = left_candidates[0][2]
        if not int_digits:
            if candidates:
                candidates.sort(reverse=True)
                int_digits = candidates[0][2]

        val_int = int_digits.lstrip("0") or "0"
        val_dec = "".join(re.findall(r"\d+", text_dec))

        if len(val_dec) > 3:
            val_dec = val_dec[:3]
        if not val_dec:
            val_dec = "0"

        alt_dec, detected = self._read_decimal_split(right_img)
        if alt_dec and (len(val_dec) < 3 or (detected >= 2 and alt_dec != val_dec)):
            val_dec = alt_dec

        if red_dec:
            if len(red_dec) > 3:
                red_dec = red_dec[:3]
            if len(red_dec) == 3 and red_dec != val_dec:
                val_dec = red_dec

        return f"{val_int}.{val_dec}"
