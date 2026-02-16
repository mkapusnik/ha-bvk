from __future__ import annotations

import os
import re
from pathlib import Path

import pytesseract
import pytest

from scraper.ocr.api import ocr_meter_reading_from_path
from scraper.ocr.base import OcrConfig

RESOURCES_DIR = Path(__file__).parent / "resources"


def _expected_from_filename(path: Path) -> str:
    stem = path.stem
    m = re.fullmatch(r"(\d+)[_.](\d+)", stem)
    if not m:
        raise ValueError(
            f"Resource filename must look like '144_786.png' or '144.786.png', got: {path.name}"
        )
    return f"{m.group(1)}.{m.group(2)}"


def _resource_images() -> list[Path]:
    if not RESOURCES_DIR.exists():
        return []
    return sorted(
        [p for p in RESOURCES_DIR.iterdir() if p.is_file() and p.suffix.lower() == ".png"]
    )


def test_ocr_matches_all_resources() -> None:
    try:
        pytesseract.get_tesseract_version()
    except Exception as err:
        raise RuntimeError("tesseract is required for scraper tests") from err

    algorithm = os.environ.get("OCR_ALGORITHM", "tesseract_v1").strip() or "tesseract_v1"
    print(f"OCR_ALGORITHM={algorithm}")

    def colorize(s: str, *, ok: bool) -> str:
        color = "32" if ok else "31"
        return f"\x1b[{color}m{s}\x1b[0m"

    images = _resource_images()
    if not images:
        pytest.skip("No OCR resource images found")

    rows: list[tuple[str, str, str, str]] = []
    failed: list[str] = []
    for image_path in images:
        expected = _expected_from_filename(image_path)
        actual = ocr_meter_reading_from_path(
            image_path,
            debug_dir="/app/data/ocr_debug",
            config=OcrConfig(algorithm=algorithm),
        )
        ok = actual == expected
        status = "OK" if ok else "FAIL"
        rows.append((status, image_path.name, expected, actual))
        if not ok:
            failed.append(image_path.name)

    headers = ("STATUS", "IMAGE", "EXPECTED", "ACTUAL")
    widths = [len(h) for h in headers]
    for r in rows:
        for i, cell in enumerate(r):
            widths[i] = max(widths[i], len(cell))

    def fmt_row(values: tuple[str, str, str, str]) -> str:
        return " | ".join(v.ljust(widths[i]) for i, v in enumerate(values))

    sep = "-+-".join("-" * w for w in widths)

    print("")
    print(fmt_row(headers))
    print(sep)
    for r in rows:
        status, image, expected, actual = r
        ok = status == "OK"
        line = fmt_row(r)
        print(colorize(line, ok=ok))
    print("")
    print(f"Total images: {len(images)}")
    passed_cnt = len(images) - len(failed)
    failed_cnt = len(failed)
    print(colorize(f"Passed: {passed_cnt}", ok=True))
    print(colorize(f"Failed: {failed_cnt}", ok=(failed_cnt == 0)))
    if failed:
        pytest.fail(f"OCR failed for: {', '.join(failed)}", pytrace=False)
