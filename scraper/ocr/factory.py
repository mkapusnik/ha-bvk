from __future__ import annotations

from scraper.ocr.base import OcrConfig, OcrEngine
from scraper.ocr.engines.simple_tesseract import SimpleTesseractEngine
from scraper.ocr.engines.tesseract_split_digits import TesseractSplitDigitsEngine
from scraper.ocr.engines.tesseract_v1 import TesseractV1Engine


def create_ocr_engine(cfg: OcrConfig) -> OcrEngine:
    key = (cfg.algorithm or "").strip().lower()
    if key in {"tesseract_v1", "v1", "default"}:
        return TesseractV1Engine()
    if key in {"simple_tesseract", "simple"}:
        return SimpleTesseractEngine()
    if key in {"tesseract_split_digits", "split_digits", "split"}:
        return TesseractSplitDigitsEngine()
    if key in {"tesseract_v1_legacy", "v1_legacy", "legacy"}:
        return TesseractV1Engine()
    raise ValueError(
        "Unknown OCR algorithm. "
        "Use one of: 'tesseract_v1', 'tesseract_v1_legacy', 'simple_tesseract', 'tesseract_split_digits'"
    )
