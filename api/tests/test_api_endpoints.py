import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import api as api_module


@pytest.fixture()
def client(tmp_path: Path):
    # Patch data directory to temp folder for isolated tests
    api_module.DATA_DIR = str(tmp_path)
    return TestClient(api_module.app)


def test_root_ok(client: TestClient):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "service": "bvk-scraper-api"}


def test_latest_404_when_missing(client: TestClient):
    resp = client.get("/latest")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "latest.json not found"


def test_latest_returns_json_when_present(client: TestClient, tmp_path: Path):
    (tmp_path / "latest.json").write_text(
        json.dumps({"timestamp": "2026-01-01T00:00:00", "reading": "123.456"}),
        encoding="utf-8",
    )
    resp = client.get("/latest")
    assert resp.status_code == 200
    assert resp.json()["reading"] == "123.456"


def test_latest_500_when_invalid_json(client: TestClient, tmp_path: Path):
    (tmp_path / "latest.json").write_text("{not json}", encoding="utf-8")
    resp = client.get("/latest")
    assert resp.status_code == 500
    assert resp.json()["detail"] == "Error decoding latest.json"


def test_history_returns_empty_list_when_missing(client: TestClient):
    resp = client.get("/history")
    assert resp.status_code == 200
    assert resp.json() == []


def test_history_returns_json_when_present(client: TestClient, tmp_path: Path):
    (tmp_path / "history.json").write_text(
        json.dumps(
            [
                {"timestamp": "2026-01-01T00:00:00", "reading": "1.000"},
                {"timestamp": "2026-01-02T00:00:00", "reading": "2.000"},
            ]
        ),
        encoding="utf-8",
    )
    resp = client.get("/history")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert resp.json()[-1]["reading"] == "2.000"


def test_history_500_when_invalid_json(client: TestClient, tmp_path: Path):
    (tmp_path / "history.json").write_text("[] trailing", encoding="utf-8")
    resp = client.get("/history")
    assert resp.status_code == 500
    assert resp.json()["detail"] == "Error decoding history.json"
