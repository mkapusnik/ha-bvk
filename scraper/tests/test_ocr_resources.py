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

    images = _resource_images()
    if not images:
        pytest.skip("No OCR resource images found")

    failed: list[str] = []
    for image_path in images:
        expected = _expected_from_filename(image_path)
        actual = ocr_meter_reading_from_path(
            image_path,
            debug_dir="/app/data/ocr_debug",
            config=OcrConfig(algorithm=algorithm),
        )
        ok = actual == expected
        print(f"{image_path.name}: expected={expected} actual={actual} ok={ok}")
        if not ok:
            failed.append(image_path.name)

    print(f"Total images: {len(images)}, failed: {len(failed)}")
    assert not failed, f"OCR failed for: {', '.join(failed)}"
