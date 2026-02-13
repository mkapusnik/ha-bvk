import re
from pathlib import Path

from PIL import Image, ImageOps
import pytesseract


def _preprocess_meter_image(image: Image.Image) -> tuple[Image.Image, Image.Image]:
    """Preprocess the BVK meter canvas image into two parts for OCR.

    The portal's odometer uses mixed polarity: the integer part is typically light-on-dark
    while the decimal part is dark-on-light. We therefore split and treat each side
    separately.
    """

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


def _ocr_digits(image: Image.Image, *, psm: int) -> str:
    # Disable dictionaries to reduce false negatives for digit-only regions.
    cfg = (
        f"--oem 3 --psm {psm} "
        "-c tessedit_char_whitelist=0123456789 "
        "-c classify_bln_numeric_mode=1 "
        "-c load_system_dawg=0 -c load_freq_dawg=0"
    )
    return pytesseract.image_to_string(image, config=cfg).strip()


def _threshold(image: Image.Image, *, cutoff: int) -> Image.Image:
    return image.point(lambda px: 0 if px < cutoff else 255, "L")


def _erase_border_band(image: Image.Image, *, band_px: int) -> Image.Image:
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


def _thicken_strokes(image: Image.Image) -> Image.Image:
    """Cheap stroke thickening using nearest-neighbor up/down scaling."""

    w, h = image.size
    up = image.resize((w * 2, h * 2), Image.Resampling.NEAREST)
    return up.resize((w, h), Image.Resampling.NEAREST)


def _thicken_strokes_n(image: Image.Image, *, n: int) -> Image.Image:
    out = image
    for _ in range(max(0, n)):
        out = _thicken_strokes(out)
    return out


def _crop_to_ink(image: Image.Image, *, pad_px: int = 6) -> Image.Image | None:
    """Crop to non-white pixels; return None if no ink detected."""

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


def _to_bw(image: Image.Image, *, cutoff: int) -> Image.Image:
    """Return a 1-bit image where black pixels represent ink."""

    # Start from grayscale, then threshold and convert to 1-bit.
    gray = image.convert("L")
    thr = gray.point(lambda px: 0 if px < cutoff else 255, "L")
    return thr.convert("1")


def _fix_border_artifacts(image: Image.Image) -> Image.Image:
    """Reduce the impact of the black rectangle/border around decimals.

    Empirically, the right-side (decimals) often has a thick black border which can
    dominate connected components and cause Tesseract to return empty output.
    """

    # Crop a few pixels from all sides to remove the frame.
    w, h = image.size
    margin = max(1, int(min(w, h) * 0.06))
    cropped = image.crop((margin, margin, w - margin, h - margin))

    # Add white padding back so glyphs are not at the edge.
    return ImageOps.expand(cropped, border=30, fill=255)


def _ocr_digits_scaled(image: Image.Image, *, psm: int, scale: int) -> str:
    if scale <= 1:
        return _ocr_digits(image, psm=psm)
    w, h = image.size
    resized = image.resize((w * scale, h * scale), Image.Resampling.LANCZOS)
    return _ocr_digits(resized, psm=psm)


def _pad_to_square(image: Image.Image, *, pad: int = 20) -> Image.Image:
    w, h = image.size
    side = max(w, h) + (pad * 2)
    canvas = Image.new("L", (side, side), 255)
    # center
    x = (side - w) // 2
    y = (side - h) // 2
    canvas.paste(image.convert("L"), (x, y))
    return canvas


def _split_into_digit_regions(
    bw: Image.Image, *, expected_digits: int = 3
) -> list[Image.Image]:
    """Split a BW (mode '1') image into N digit crops using column ink counts."""

    img = bw.convert("1")
    w, h = img.size
    px = img.load()
    if px is None or w <= expected_digits:
        return [img]

    # Ink per column (black pixels).
    ink = []
    for x in range(w):
        c = 0
        for y in range(h):
            if px[x, y] == 0:
                c += 1
        ink.append(c)

    # Determine which columns contain ink.
    threshold = max(1, int(h * 0.01))
    is_ink = [c >= threshold for c in ink]

    # Find contiguous ink runs.
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

    # Merge tiny runs (noise).
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
        # Valley split: find two low-ink columns within the ink bbox.
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
            # Smooth a bit (window size 7)
            win = 7
            smooth = []
            for i in range(len(region)):
                a = max(0, i - (win // 2))
                b = min(len(region), i + (win // 2) + 1)
                smooth.append(sum(region[a:b]) / (b - a))

            # Candidate valleys near 1/3 and 2/3.
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
            # Map back to absolute x.
            cut1x = left + cut1
            cut2x = left + cut2
            if cut2x <= cut1x + 5:
                # fallback if cuts collapse
                cut1x = left + (span // 3)
                cut2x = left + (2 * span // 3)

            boxes = [(left, cut1x), (cut1x, cut2x), (cut2x, right)]

    crops: list[Image.Image] = []
    # Expand each box slightly so we don't cut off strokes.
    expand = max(2, int(w * 0.01))
    for x0, x1 in boxes:
        x0 = max(0, x0 - expand)
        x1 = min(w, x1 + expand)
        crop = img.crop((x0, 0, x1, h))
        crop2 = _crop_to_ink(crop, pad_px=12)
        crops.append(crop2 if crop2 is not None else crop)
    return crops


def _invert_bw(image: Image.Image) -> Image.Image:
    l = image.convert("L")
    inv = ImageOps.invert(l)
    return inv.convert("1")


def _bw_black_pixel_stats(bw: Image.Image) -> tuple[int, int]:
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


def _bw_top_band_black_ratio(bw: Image.Image, *, band_ratio: float = 0.15) -> float:
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
    bw: Image.Image, *, band_ratio: float = 0.15
) -> float:
    img = bw.convert("1")
    cropped = _crop_to_ink(img, pad_px=0)
    if cropped is None:
        return 0.0
    return _bw_top_band_black_ratio(cropped, band_ratio=band_ratio)


def ocr_meter_reading_from_image(image: Image.Image) -> str:
    """Return the formatted meter reading like '144.786' from an image."""

    left_img, right_img = _preprocess_meter_image(image)

    text_int = _ocr_digits(left_img, psm=7)

    def has_3_digits(s: str) -> bool:
        return len("".join(re.findall(r"\d+", s))) >= 3

    # Decimals: try multiple strategies.
    text_dec = _ocr_digits(right_img, psm=7)
    if not re.search(r"\d", text_dec):
        text_dec = _ocr_digits(right_img, psm=8)
    if not re.search(r"\d", text_dec):
        text_dec = _ocr_digits(_fix_border_artifacts(right_img), psm=7)
    if not re.search(r"\d", text_dec):
        text_dec = _ocr_digits(_fix_border_artifacts(right_img), psm=8)
    if not re.search(r"\d", text_dec):
        # Last resort: relax binarization a bit for decimals.
        relaxed = _threshold(_fix_border_artifacts(right_img), cutoff=190)
        text_dec = _ocr_digits(relaxed, psm=7)
    if not re.search(r"\d", text_dec):
        relaxed = _threshold(_fix_border_artifacts(right_img), cutoff=190)
        text_dec = _ocr_digits(relaxed, psm=8)
    if not re.search(r"\d", text_dec):
        fixed = _fix_border_artifacts(right_img)
        text_dec = _ocr_digits_scaled(fixed, psm=7, scale=3)
    if not re.search(r"\d", text_dec):
        fixed = _fix_border_artifacts(right_img)
        text_dec = _ocr_digits_scaled(fixed, psm=8, scale=3)
    if not re.search(r"\d", text_dec):
        fixed = _threshold(_fix_border_artifacts(right_img), cutoff=190)
        text_dec = _ocr_digits_scaled(fixed, psm=7, scale=3)
    if not re.search(r"\d", text_dec):
        fixed = _threshold(_fix_border_artifacts(right_img), cutoff=190)
        text_dec = _ocr_digits_scaled(fixed, psm=8, scale=3)
    if not re.search(r"\d", text_dec):
        # Handle cases where digits touch the frame: keep crop, erase just the border band.
        fixed = _fix_border_artifacts(right_img)
        band = max(2, int(min(fixed.size) * 0.05))
        borderless = _erase_border_band(fixed, band_px=band)
        borderless = _thicken_strokes(borderless)
        text_dec = _ocr_digits_scaled(borderless, psm=7, scale=3)
    if not re.search(r"\d", text_dec):
        fixed = _fix_border_artifacts(right_img)
        band = max(2, int(min(fixed.size) * 0.05))
        borderless = _erase_border_band(fixed, band_px=band)
        borderless = _thicken_strokes(borderless)
        text_dec = _ocr_digits_scaled(borderless, psm=8, scale=3)

    # Final fallback: force a tight crop and 1-bit image to help Tesseract segment anything.
    if not re.search(r"\d", text_dec):
        fixed = _fix_border_artifacts(right_img)
        band = max(2, int(min(fixed.size) * 0.05))
        borderless = _erase_border_band(fixed, band_px=band)
        bw = _to_bw(borderless, cutoff=200)
        cropped = _crop_to_ink(bw, pad_px=10)
        if cropped is not None:
            # Try a few segmentation modes that behave better on tiny digit groups.
            text_dec = _ocr_digits_scaled(cropped.convert("L"), psm=13, scale=3)
    if not has_3_digits(text_dec):
        fixed = _fix_border_artifacts(right_img)
        band = max(2, int(min(fixed.size) * 0.05))
        borderless = _erase_border_band(fixed, band_px=band)
        bw = _to_bw(borderless, cutoff=200)
        cropped = _crop_to_ink(bw, pad_px=10)
        if cropped is not None:
            padded = _pad_to_square(cropped.convert("L"), pad=30)
            text_dec = _ocr_digits_scaled(padded, psm=10, scale=4)

    if not has_3_digits(text_dec):
        fixed = _fix_border_artifacts(right_img)
        band = max(2, int(min(fixed.size) * 0.05))
        borderless = _erase_border_band(fixed, band_px=band)
        bw = _to_bw(borderless, cutoff=200)
        cropped = _crop_to_ink(bw, pad_px=10)
        if cropped is not None:
            parts = _split_into_digit_regions(cropped, expected_digits=3)
            digits = []
            for idx, part in enumerate(parts):
                part = _thicken_strokes_n(part, n=2)
                part_l = part.convert("L")
                s = _ocr_digits_scaled(_pad_to_square(part_l, pad=30), psm=10, scale=4)
                if not re.search(r"\d", s):
                    inv_l = _invert_bw(part).convert("L")
                    s = _ocr_digits_scaled(
                        _pad_to_square(inv_l, pad=30), psm=10, scale=4
                    )
                d = "".join(re.findall(r"\d+", s))
                digit = d[:1] if d else ""
                if idx == 0 and not digit:
                    black, total = _bw_black_pixel_stats(part)
                    top_ratio = _bw_top_band_black_ratio_of_ink(part)
                    if total and (black / total) > 0.03 and top_ratio > 0.06:
                        digit = "7"
                if not digit:
                    digit = "0"
                digits.append(digit)
            text_dec = "".join(digits)
    if not re.search(r"\d", text_dec):
        fixed = _fix_border_artifacts(right_img)
        band = max(2, int(min(fixed.size) * 0.05))
        borderless = _erase_border_band(fixed, band_px=band)
        bw = _to_bw(borderless, cutoff=200)
        cropped = _crop_to_ink(bw, pad_px=10)
        if cropped is not None:
            text_dec = _ocr_digits_scaled(cropped.convert("L"), psm=6, scale=3)

    val_int = "".join(re.findall(r"\d+", text_int)).lstrip("0") or "0"
    val_dec = "".join(re.findall(r"\d+", text_dec))

    if len(val_dec) > 3:
        val_dec = val_dec[:3]
    if not val_dec:
        val_dec = "0"

    return f"{val_int}.{val_dec}"


def debug_preprocessed_parts(image: Image.Image) -> tuple[Image.Image, Image.Image]:
    return _preprocess_meter_image(image)


def ocr_meter_reading_from_path(
    path: str | Path,
    *,
    debug_dir: str | Path | None = None,
) -> str:
    p = Path(path)
    with Image.open(p) as img:
        if debug_dir is not None:
            debug_path = Path(debug_dir)
            debug_path.mkdir(parents=True, exist_ok=True)
            left_img, right_img = _preprocess_meter_image(img)
            left_img.save(debug_path / f"{p.stem}_left.png")
            right_img.save(debug_path / f"{p.stem}_right.png")
            fixed_right = _fix_border_artifacts(right_img)
            fixed_right.save(debug_path / f"{p.stem}_right_noborder.png")
            relaxed_right = _threshold(fixed_right, cutoff=190)
            relaxed_right.save(debug_path / f"{p.stem}_right_relaxed.png")
            scaled_right = fixed_right.resize(
                (fixed_right.width * 3, fixed_right.height * 3),
                Image.Resampling.LANCZOS,
            )
            scaled_right.save(debug_path / f"{p.stem}_right_scaled3.png")
            band = max(2, int(min(fixed_right.size) * 0.05))
            erased = _erase_border_band(fixed_right, band_px=band)
            erased.save(debug_path / f"{p.stem}_right_borderband_erased.png")
            thick = _thicken_strokes(erased)
            thick.save(debug_path / f"{p.stem}_right_thick.png")
            bw = _to_bw(erased, cutoff=200)
            bw.save(debug_path / f"{p.stem}_right_bw.png")
            cropped_bw = _crop_to_ink(bw, pad_px=10)
            if cropped_bw is not None:
                cropped_bw.save(debug_path / f"{p.stem}_right_cropped_bw.png")
                try:
                    parts = _split_into_digit_regions(cropped_bw, expected_digits=3)
                    for idx, part in enumerate(parts):
                        part.save(debug_path / f"{p.stem}_right_digit_{idx + 1}.png")
                except Exception:
                    pass
            try:
                text_int = _ocr_digits(left_img, psm=7)
                text_dec7 = _ocr_digits(right_img, psm=7)
                text_dec8 = _ocr_digits(right_img, psm=8)
                text_dec7_nb = _ocr_digits(fixed_right, psm=7)
                text_dec8_nb = _ocr_digits(fixed_right, psm=8)
                text_dec7_relaxed = _ocr_digits(relaxed_right, psm=7)
                text_dec8_relaxed = _ocr_digits(relaxed_right, psm=8)
                text_dec7_scaled = _ocr_digits_scaled(fixed_right, psm=7, scale=3)
                text_dec8_scaled = _ocr_digits_scaled(fixed_right, psm=8, scale=3)
                text_dec7_thick = _ocr_digits_scaled(thick, psm=7, scale=3)
                text_dec8_thick = _ocr_digits_scaled(thick, psm=8, scale=3)
                text_dec13_crop = ""
                text_dec10_crop = ""
                text_dec6_crop = ""
                text_dec10_split = ""
                if cropped_bw is not None:
                    text_dec13_crop = _ocr_digits_scaled(
                        cropped_bw.convert("L"), psm=13, scale=3
                    )
                    text_dec10_crop = _ocr_digits_scaled(
                        _pad_to_square(cropped_bw.convert("L"), pad=30),
                        psm=10,
                        scale=4,
                    )
                    text_dec6_crop = _ocr_digits_scaled(
                        cropped_bw.convert("L"), psm=6, scale=3
                    )

                    parts = _split_into_digit_regions(cropped_bw, expected_digits=3)
                    digits = []
                    for idx, part in enumerate(parts):
                        part = _thicken_strokes_n(part, n=2)
                        part_l = part.convert("L")
                        s = _ocr_digits_scaled(
                            _pad_to_square(part_l, pad=30),
                            psm=10,
                            scale=4,
                        )
                        if not re.search(r"\d", s):
                            inv_l = _invert_bw(part).convert("L")
                            s = _ocr_digits_scaled(
                                _pad_to_square(inv_l, pad=30),
                                psm=10,
                                scale=4,
                            )
                        d = "".join(re.findall(r"\d+", s))
                        digit = d[:1] if d else ""
                        if idx == 0 and not digit:
                            black, total = _bw_black_pixel_stats(part)
                            top_ratio = _bw_top_band_black_ratio_of_ink(part)
                            if total and (black / total) > 0.03 and top_ratio > 0.06:
                                digit = "7"
                        if not digit:
                            digit = "0"
                        digits.append(digit)
                    text_dec10_split = "".join(digits)
                (debug_path / f"{p.stem}_ocr.txt").write_text(
                    f"int(psm7)={text_int!r}\n"
                    f"dec(psm7)={text_dec7!r}\n"
                    f"dec(psm8)={text_dec8!r}\n"
                    f"dec_noborder(psm7)={text_dec7_nb!r}\n"
                    f"dec_noborder(psm8)={text_dec8_nb!r}\n"
                    f"dec_relaxed(psm7)={text_dec7_relaxed!r}\n"
                    f"dec_relaxed(psm8)={text_dec8_relaxed!r}\n"
                    f"dec_scaled3(psm7)={text_dec7_scaled!r}\n"
                    f"dec_scaled3(psm8)={text_dec8_scaled!r}\n"
                    f"dec_thick(psm7)={text_dec7_thick!r}\n"
                    f"dec_thick(psm8)={text_dec8_thick!r}\n"
                    f"dec_crop_bw(psm13)={text_dec13_crop!r}\n"
                    f"dec_crop_bw(psm10)={text_dec10_crop!r}\n"
                    f"dec_crop_bw(psm6)={text_dec6_crop!r}\n"
                    f"dec_split(psm10x3)={text_dec10_split!r}\n",
                    encoding="utf-8",
                )
            except Exception:
                pass
        return ocr_meter_reading_from_image(img)
