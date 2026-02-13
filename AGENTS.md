# Agent Instructions (HA-BVK)

This repository contains:
- `scraper/`: Selenium + Tesseract OCR service that periodically scrapes BVK portal and writes JSON into `data/`.
- `api/`: FastAPI service that reads `data/latest.json` and `data/history.json` and exposes them via HTTP.
- `custom_components/bvk/`: Home Assistant (HACS) custom integration that fetches `/latest` from the API.

## Quick Commands

### Run the stack (recommended)

- Copy env template and edit credentials:
  - `copy .env.example .env` (Windows) or `cp .env.example .env` (macOS/Linux)
- Start services:
  - `docker compose up -d --build`
- View logs:
  - `docker compose logs -f scraper`
  - `docker compose logs -f api`
- Verify API:
  - `curl http://localhost:8100/latest`

### Run locally (no Docker)

API:
- Create venv, install deps:
  - `python -m venv .venv && .venv\\Scripts\\pip install -r api/requirements.txt`
- Run:
  - `python api/api.py` (uses `uvicorn.run(...)`)

Scraper:
- Install deps:
  - `python -m venv .venv && .venv\\Scripts\\pip install -r scraper/requirements.txt`
- Run:
  - `python scraper/main.py`

Notes:
- The scraper container expects Chromium + chromedriver at `/usr/bin/chromium` and `/usr/bin/chromedriver`.
- Both API and scraper assume data directory `/app/data` (mapped to repo `./data/` by compose).

## Tests / Lint

### CI reality check

`.github/workflows/tests.yml` currently builds and pushes Docker images; it does not run unit tests or linters.
If you add tests, consider updating CI to execute them.

### Running a single test

No active test suite is present in the main tree (`scraper/tests/` only contains `resources/`).
If you create pytest tests, prefer these conventions:
- Run all tests: `pytest`
- Run one file: `pytest path/to/test_file.py`
- Run one test: `pytest path/to/test_file.py -k test_name`
- Run one test node: `pytest path/to/test_file.py::TestClass::test_name`

### Lint/format tooling

No formatter/linter config is checked in (no `ruff.toml`, `.flake8`, `pyproject` tool sections, etc.).
If you introduce tooling, prefer Home Assistant-friendly defaults:
- `ruff` for lint + import sorting
- `black` for formatting (or ruff-format)
- `mypy` only if you commit to maintaining it

## Code Style Guidelines

### General

- Keep changes scoped: this repo has three loosely-coupled services; avoid cross-service entanglement.
- Prefer readability over cleverness; these services run unattended and are debugged via logs.
- Avoid breaking Home Assistant integration patterns; follow HA development guidelines when editing `custom_components/`.

### Python version / typing

- `pyproject.toml` declares `requires-python = ">=3.14"`, but containers may run older versions.
  - Write code compatible with Python 3.11+ unless you confirm runtime.
- Use type hints for new/modified functions where helpful, but do not introduce heavy typing overhead.
- Prefer built-in collections (`list`, `dict`) and `typing` only when it improves clarity.

### Imports

- Standard library first, then third-party, then local imports.
- One import per line; avoid wildcard imports.
- In Home Assistant integration, keep imports aligned with HA style (group `homeassistant.*` imports together).

### Formatting

- Use 4-space indentation.
- Prefer single quotes only when needed; otherwise be consistent within the file.
- Keep lines reasonably short (~88-100 chars) unless constrained by HA constants / long selectors.
- JSON written to disk should remain stable and human-readable (keep `indent=2`).

### Naming conventions

- Modules/files: `snake_case.py`.
- Functions/variables: `snake_case`.
- Classes: `PascalCase`.
- Constants: `UPPER_SNAKE_CASE`.
- Home Assistant entities:
  - Stable `unique_id` values (do not bake in volatile values like timestamps).
  - Keep entity name user-friendly; use `_attr_has_entity_name = True` where appropriate.

### Error handling and logging

- Prefer narrow exceptions when practical; avoid bare `except:` (there is one in `scraper/main.py` for screenshot capture).
- Always log actionable context:
  - For scraper failures: current URL/title, which step failed, and a screenshot where possible.
  - For API failures: which file was missing/invalid.
- Scraper validation intentionally "fails open" on history parsing; preserve this behavior unless you have a safer alternative.
- In Home Assistant integration (`custom_components/bvk/`):
  - Raise `UpdateFailed` for coordinator update issues.
  - Do not spam logs on transient failures; rely on coordinator backoff/interval.

### Async vs sync rules

- Home Assistant code must be async-friendly:
  - Do not block the event loop (no `time.sleep`, no long CPU work).
  - Prefer HA helpers and `aiohttp` sessions provided by HA when possible.
- API and scraper are synchronous today; keep them simple unless refactoring with a clear benefit.

### I/O, paths, and data contracts

- Persisted files:
  - `data/latest.json` is a dict with keys: `timestamp` (ISO string), `reading` (string like `"123.456"`).
  - `data/history.json` is a list of those dicts.
- Keep the schema backward compatible; the Home Assistant sensor expects `reading` and `timestamp`.
- Use `os.path.join` for paths; do not hardcode Windows path separators.

### HTTP API conventions (`api/api.py`)

- Return JSON-serializable objects only.
- Use `HTTPException` with correct status codes:
  - 404 when `latest.json` missing
  - 500 when JSON decoding fails
- Keep endpoints stable: `/latest` and `/history` are part of integration contract.

### Selenium/OCR scraper conventions (`scraper/main.py`)

- Any interaction with the BVK portal may change; keep selectors and waits defensive.
- Prefer `WebDriverWait` over `time.sleep`, except for known animation delays (currently 15s).
- When changing OCR:
  - Save diagnostic artifacts under `data/` (already writes `raw_meter.png`, `debug_left.png`, `debug_right.png`).
  - Keep preprocessing steps deterministic to reduce flakiness.
- Keep validation conservative; the goal is to reject obvious OCR errors, not to overfit.

### Home Assistant integration conventions (`custom_components/bvk/`)

- Follow HA guidelines (async setup, coordinators, entities).
- Avoid creating a new `aiohttp.ClientSession()` per update; prefer HA shared session if you refactor.
- Update interval is currently 30 minutes; if you change it, justify why.

## Repository-Specific Notes

- Docker compose maps container port 8000 to host 8100 for the API (`http://localhost:8100/latest`).
- `release_ha.yml` bumps `custom_components/bvk/manifest.json` patch version on pushes to `master`.
  - Do not manually bump version unless you intentionally want a release.

## When Adding New Tests (recommended structure)

- Prefer `pytest`.
- Put tests under:
  - `api/tests/` for API unit tests
  - `scraper/tests/` for OCR/HTML fixture tests (fixtures under `scraper/tests/resources/`)
  - `custom_components/bvk/tests/` only if using HA test harness
- Keep tests offline/deterministic; use captured HTML/canvas exports as fixtures.
