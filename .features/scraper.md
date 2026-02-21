# Goal
Module sources the data from BVK portal, retrieves the smart meter readings, parses and stores them.

## Tech stack
- Docker
- Python
- Selenium + Tesseract OCR

## Implementation

Docker container which per periodically runs the service to scrape data from BVK portal

Workflow:
- Opens the BVK portal and logs in
- Navigates to the page with the smart meter readings
- Downloads the raw image of the meter readings
- Uses OCR to extract the readings from the retrieved raw image
- Stores the extracted readings and the raw image (in `data` folder)

### Selenium/OCR scraper conventions

- Any interaction with the BVK portal may change; keep selectors and waits defensive.
- Prefer `WebDriverWait` over `time.sleep`, except for known animation delays (currently 15s).
- When changing OCR:
  - Save diagnostic artifacts under `data/` (already writes `raw_meter.png`, `debug_left.png`, `debug_right.png`).
  - Keep preprocessing steps deterministic to reduce flakiness.
- Keep validation conservative; the goal is to reject obvious OCR errors, not to overfit.
- Format of the meter value is always `XXXXXX.YYY` where `XXXXXX` is the integer part of the value, left-padded with zeroes. `YYY` is the decimal part.

## Quick Commands

- Copy env template and edit credentials:
  - `copy .env.example .env` (Windows) or `cp .env.example .env` (macOS/Linux)
- Start services:
  - `docker compose up -d --build`
- View logs:
  - `docker compose logs -f scraper`
  - `docker compose logs -f api`
- Verify API:
  - `curl http://localhost:8100/latest`

## Guidelines

After every change, verify the lint checks are passing