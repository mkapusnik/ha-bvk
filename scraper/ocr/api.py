from __future__ import annotations

from pathlib import Path

from PIL import Image

from scraper.ocr.base import OcrConfig
from scraper.ocr.factory import create_ocr_engine


def ocr_meter_reading_from_image(image: Image.Image, *, config: OcrConfig | None = None) -> str:
    engine = create_ocr_engine(config or OcrConfig())
    return engine.read_meter(image)


def ocr_meter_reading_from_path(
    path: str | Path,
    *,
    debug_dir: str | Path | None = None,
    config: OcrConfig | None = None,
) -> str:
    p = Path(path)
    with Image.open(p) as img:
        engine = create_ocr_engine(config or OcrConfig())
        if debug_dir is not None:
            try:
                engine_debug = getattr(engine, "debug_preprocessed_parts", None)
                if callable(engine_debug):
                    left, right = engine_debug(img)
                    out_dir = Path(debug_dir)
                    out_dir.mkdir(parents=True, exist_ok=True)
                    left.save(out_dir / f"{p.stem}_left.png")
                    right.save(out_dir / f"{p.stem}_right.png")
            except Exception:
                # Debug output must never affect the main reading path.
                pass
        return engine.read_meter(img)
