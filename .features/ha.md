# Goal
Provide custom component for Home Assistant server.

## Tech stack
- Python
- Home Assistant

## Implementation
Custom component for Home Assistant server that fetches `/latest` from the API and exposes it as a sensor.
The API root (`/`) now serves a landing page, but the integration continues to use `/latest`.

Home Assistant code must be async-friendly:
  - Do not block the event loop (no `time.sleep`, no long CPU work).
  - Prefer HA helpers and `aiohttp` sessions provided by HA when possible.

### Conventions

- Follow HA guidelines (async setup, coordinators, entities).
- Avoid creating a new `aiohttp.ClientSession()` per update; prefer HA shared session if you refactor.
- Update interval is currently 30 minutes; if you change it, justify why.

### Error handling and logging

- Raise `UpdateFailed` for coordinator update issues.
- Do not spam logs on transient failures; rely on coordinator backoff/interval.

## Code Style Guidelines

- Avoid breaking Home Assistant integration patterns; follow HA development guidelines when editing `custom_components/`.
- Keep imports aligned with HA style (group `homeassistant.*` imports together).
- Home Assistant entities:
  - Stable `unique_id` values (do not bake in volatile values like timestamps).
  - Keep entity name user-friendly; use `_attr_has_entity_name = True` where appropriate.
