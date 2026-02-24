#!/usr/bin/env bash
set -euo pipefail

echo "Rebuilding scraper image..."
docker compose build scraper

echo "Running OCR tests"
docker compose run --rm \
  scraper \
  python -m pytest -q scraper/tests
