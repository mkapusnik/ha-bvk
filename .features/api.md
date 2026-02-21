# Goal
Module reads the data from shared `data` folder and exposes it via HTTP

## Tech stack
- Docker
- JavaScript (Node.js)

## Implementation

Node.js service that reads `data/latest.json` and `data/history.json` and exposes them via HTTP,
plus a static landing page served from `api/public/index.html`.

Endpoints:
- `/` landing page (HTML)
- `/latest`
- `/history`

### HTTP API conventions (`api/app.js`)

- Return JSON-serializable objects only for API endpoints; `/` serves HTML.
- Use HTTP status codes:
  - `404` when `latest.json` missing
  - `500` when JSON decoding fails
- Keep endpoints stable: `/latest` and `/history` are part of integration contract.

### Static assets

- Landing page files live in `api/public/` and are served as static assets.
- Prefer separate, cacheable files for CSS/JS instead of inline blocks in HTML.
- When updating the landing page, ensure the API Docker image includes `api/public/`.
