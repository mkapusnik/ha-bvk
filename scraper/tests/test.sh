#!/usr/bin/env bash
set -euo pipefail

ocr_algorithm="${1:-tesseract_v1}"

echo "Rebuilding scraper image..."
docker compose build scraper

echo "Running tests with OCR_ALGORITHM=${ocr_algorithm}"
docker compose run --rm \
  -e OCR_ALGORITHM="${ocr_algorithm}" \
  scraper \
  python -m pytest -q scraper/tests
