# Project Overview

Purpose of this project is to provide a complete solution for integrating **Brněnské vodárny a kanalizace (BVK)** smart meter readings into Home Assistant.

This repository contains:

## Project Structure
- `scraper`:
  - Data miner that scrapes BVK portal and stores reading in `data/`
  - Detailed implementation described in @.features/scraper.md
  
- `api`:
  - HTTP service which exposes readings from `data` folder.
  - Detailed implementation described in @.features/api.md

- `custom_components/bvk/`:
  - Home Assistant (HACS) custom integration to expose readings from `api` service as a sensor.
  - Detailed implementation described in @.features/ha.md

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

### OCR tests (recommended)

The OCR unit test uses `pytesseract` which calls the `tesseract` binary.
This binary may not be installed on developer machines (especially Windows).
For consistent results, run OCR-related tests inside the `scraper` Docker image.

- Run OCR tests in container:
  - `docker compose build scraper`
  - `docker compose run --rm scraper python -m pytest -q`

Notes:
- The repo path is copied into the scraper image under `/app/scraper`.
- `scraper/tests/resources/*.png` fixtures are used; filenames must match expected readings.

### Running a single test

No active test suite is present in the main tree (`scraper/tests/` only contains `resources/`).
If you create pytest tests, prefer these conventions:
- Run all tests: `pytest`
- Run one file: `pytest path/to/test_file.py`
- Run one test: `pytest path/to/test_file.py -k test_name`
- Run one test node: `pytest path/to/test_file.py::TestClass::test_name`

### Lint/format tooling

Prefer Home Assistant-friendly defaults:
- `ruff` for lint + import sorting
- `black` for formatting (or ruff-format)

## Code Style Guidelines

### General

- Keep changes scoped: this repo has three loosely-coupled services; avoid cross-service entanglement.
- Prefer readability over cleverness; these services run unattended and are debugged via logs.

### Python version / typing

- `pyproject.toml` declares `requires-python = ">=3.14"`, but containers may run older versions.
  - Write code compatible with Python 3.11+ unless you confirm runtime.
- Use type hints for new/modified functions where helpful, but do not introduce heavy typing overhead.
- Prefer built-in collections (`list`, `dict`) and `typing` only when it improves clarity.

### Imports

- Standard library first, then third-party, then local imports.
- One import per line; avoid wildcard imports.

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

### Error handling and logging

- Prefer narrow exceptions when practical; avoid bare `except:` (there is one in `scraper/main.py` for screenshot capture).
- Always log actionable context:
  - For scraper failures: current URL/title, which step failed, and a screenshot where possible.
  - For API failures: which file was missing/invalid.
- Scraper validation intentionally "fails open" on history parsing; preserve this behavior unless you have a safer alternative.

### I/O, paths, and data contracts

- Persisted files:
  - `data/latest.json` is a dict with keys: `timestamp` (ISO string), `reading` (string like `"123.456"`).
  - `data/history.json` is a list of those dicts.
- Keep the schema backward compatible; the Home Assistant sensor expects `reading` and `timestamp`.
- Use `os.path.join` for paths; do not hardcode Windows path separators.

## Testing strategy (recommended structure)
- Prefer `pytest`.
- Put tests under:
  - `api/tests/` for API unit tests
  - `scraper/tests/` for OCR/HTML fixture tests (fixtures under `scraper/tests/resources/`)
  - `custom_components/bvk/tests/` only if using HA test harness
- Keep tests offline/deterministic; use captured HTML/canvas exports as fixtures.

## CI / CD
- `tests.yml` - runs tests and if they pass, builds and pushes nightly Docker images
- `release_ha.yml` bumps `custom_components/bvk/manifest.json` patch version on pushes to `master`, do not manually bump version.

# External File Loading
CRITICAL: When you encounter a file reference (e.g., @.features/general.md), use your Read tool to load it on a need-to-know basis. They're relevant to the SPECIFIC task at hand.

Instructions:
- Do NOT preemptively load all references - use lazy loading based on actual need
- When loaded, treat content as mandatory instructions that override defaults
- Follow references recursively when needed