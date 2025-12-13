# BVK Water Meter Scraper & Home Assistant Integration

This project provides a complete solution for integrating **Brněnské vodárny a kanalizace (BVK)** smart meter readings into Home Assistant.

It consists of two parts:
1.  **Scraper & API**: A Dockerized service that scrapes the BVK customer portal (Suez Smart Solutions) and exposes the reading via a local REST API.
2.  **Home Assistant Integration**: A HACS-compatible custom component that fetches data from the API.

## Features
-   **Automated Scraping**: Runs periodically to fetch the latest water meter reading.
-   **OCR**: Uses Tesseract OCR with tuned settings to read the meter value from the canvas image.
-   **Validation**: Ensures new readings differ logically from previous ones to prevent bad data.
-   **ARM64 Support**: Works on Raspberry Pi (uses Chromium).
-   **API**: Provides JSON output (`/latest` and `/history`).

## 1. Installation (Scraper Service)

You need a machine capable of running Docker (e.g., Raspberry Pi, NAS, Server) to run the scraper.

1.  **Clone this repository**:
    ```bash
    git clone https://github.com/mkapusnik/ha-bvk
    cd ha-bvk
    ```

2.  **Configure**:
    Create a `.env` file:
    ```bash
    BVK_USERNAME=your_email
    BVK_PASSWORD=your_password
    CHECK_INTERVAL_HOURS=4
    ```

3.  **Run with Docker Compose**:
    ```bash
    docker compose up -d --build
    ```

4.  **Verify**:
    Check if the API is running at `http://YOUR_IP:8000/latest` (it might take a minute to fetch the first reading).

## 2. Installation (Home Assistant Integration)

1.  **HACS**:
    -   Open HACS in Home Assistant.
    -   Go to **Integrations** > **3 dots** > **Custom repositories**.
    -   Add the URL of your repository (where you pushed this code).
    -   Category: **Integration**.
    -   Click **Add**.

2.  **Install**:
    -   Search for "BVK Water Meter" in HACS and install it.
    -   Restart Home Assistant.

3.  **Configure**:
    -   Go to **Settings** > **Devices & Services** > **Add Integration**.
    -   Search for **BVK Water Meter**.
    -   Enter the **API URL** of your scraper service (e.g., `http://192.168.1.50:8000/latest`).

## Sensors
This integration provides a single sensor:
-   `sensor.bvk_reading`: The current water meter reading in m³.
-   Attribute `timestamp`: Time of the last successful scrape.

## Capturing Mockups for Unit Tests
To generate offline mockups of the BVK workflow (Login page, MainInfo page, Suez page, and raw meter canvas) and store them as part of the source code, use the snapshot script. By default, it saves into `scraper/tests/resources/` inside the repository.

1. Ensure your `.env` is configured with `BVK_USERNAME` and `BVK_PASSWORD`.
2. Build and run the stack as usual:
   ```bash
   docker compose up -d --build
   ```
3. Execute the snapshot workflow inside the scraper container (default output: `scraper/tests/resources/`):
   ```bash
   docker compose exec scraper python -m scraper.snapshot_workflow
   ```

What gets saved by default (lightweight set suitable for committing):
- `*_login_page.html`
- `*_main_info_page.html`
- `*_suez_page.html`
- `*_raw_meter_canvas_base64.png` (canvas export)

Optional: include full-page and element screenshots (PNG), which are larger, by passing `--include-screens`:
```bash
docker compose exec scraper python -m scraper.snapshot_workflow --include-screens
```

You can also change the destination with `--out` (inside the container). For example, to save into the Docker volume (not tracked by Git):
```bash
docker compose exec scraper python -m scraper.snapshot_workflow --out /app/data/mockups
```

Commit the curated files under `scraper/tests/resources/` to use them as fixtures for unit tests.
