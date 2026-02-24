from __future__ import annotations

from scraper.ocr.base import OcrConfig, OcrEngine
from scraper.ocr.engines.tesseract_v1 import TesseractV1Engine


def create_ocr_engine(_cfg: OcrConfig | None = None) -> OcrEngine:
    return TesseractV1Engine()
