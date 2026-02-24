from __future__ import annotations

from dataclasses import dataclass

from PIL import Image


@dataclass(frozen=True, slots=True)
class OcrConfig:
    """Configuration for OCR reading extraction."""


class OcrEngine:
    name: str

    def read_meter(self, image: Image.Image) -> str:  # pragma: no cover
        raise NotImplementedError
