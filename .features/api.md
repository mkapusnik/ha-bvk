# Goal
Module reads the data from shared `data` folder and exposes it via HTTP

## Tech stack
- Docker
- Python

## Implementation

FastAPI service that reads `data/latest.json` and `data/history.json` and exposes them via HTTP.

Endpoints:
- `/latest`
- `/history`

### HTTP API conventions (`api/api.py`)

- Return JSON-serializable objects only.
- Use `HTTPException` with correct status codes:
  - `404` when `latest.json` missing
  - `500` when JSON decoding fails
- Keep endpoints stable: `/latest` and `/history` are part of integration contract.