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


@pytest.mark.parametrize("image_path", _resource_images(), ids=lambda p: p.name)
def test_ocr_matches_filename(image_path: Path) -> None:
    try:
        pytesseract.get_tesseract_version()
    except Exception as err:
        raise RuntimeError("tesseract is required for scraper tests") from err
    expected = _expected_from_filename(image_path)
    algorithm = os.environ.get("OCR_ALGORITHM", "tesseract_v1")
    actual = ocr_meter_reading_from_path(
        image_path,
        debug_dir="/app/data/ocr_debug",
        config=OcrConfig(algorithm=algorithm),
    )
    assert actual == expected
