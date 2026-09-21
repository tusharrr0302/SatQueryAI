import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app, headers={"Authorization": "Bearer test_token_analyst"})


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_list_datasets():
    response = client.get("/api/datasets")
    assert response.status_code == 200
    data = response.json()
    assert "datasets" in data
    assert len(data["datasets"]) >= 7
    ids = [d["id"] for d in data["datasets"]]
    assert "sentinel-2" in ids
    assert "sentinel-1" in ids
    assert "landsat" in ids


def test_list_models():
    response = client.get("/api/models")
    assert response.status_code == 200
    data = response.json()
    assert "models" in data
    assert len(data["models"]) >= 4
    ids = [m["id"] for m in data["models"]]
    assert "geochat-7b" in ids
    assert "prithvi-eo-2.0" in ids
    assert "terrafm" in ids
    assert "closp" in ids


def test_chat_delhi_vegetation(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "EO_EXECUTION_MODE", "mock")
    query = "Show me the vegetation change in Delhi over the last 1 year using Sentinel-2 data."
    response = client.post("/api/chat", json={"query": query})
    assert response.status_code == 200
    data = response.json()
    assert "result" in data
    assert "Delhi" in data["result"]["aoi"]["name"]
    assert data["result"]["visualization"]["type"] in ["3D Surface", "Time Series"]
    assert len(data["result"]["metrics"]) >= 3
    assert len(data["result"]["audit_trace"]) == 6
    assert data["globe_action"]["action"] == "fly_to"


def test_chat_delhi_decadal(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "EO_EXECUTION_MODE", "mock")
    query = "Show me how Delhi changed over the last 10 years"
    response = client.post("/api/chat", json={"query": query})
    assert response.status_code == 200
    data = response.json()
    assert "result" in data
    assert "Urban expansion" in [m["label"] for m in data["result"]["metrics"]]
    assert data["result"]["provenance"]["model_name"] == "Prithvi-EO-2.0"



def test_aoi_crud():
    aoi_payload = {
        "name": "Test Bangalore AOI",
        "country": "India",
        "center": {"latitude": 12.9716, "longitude": 77.5946},
        "area_km2": 741.0,
        "bbox": [77.4, 12.8, 77.8, 13.1]
    }
    create_res = client.post("/api/aoi", json=aoi_payload)
    assert create_res.status_code == 200
    created_id = create_res.json()["aoi"]["id"]

    list_res = client.get("/api/aoi")
    assert list_res.status_code == 200
    assert any(a["id"] == created_id for a in list_res.json()["aois"])

    del_res = client.delete(f"/api/aoi/{created_id}")
    assert del_res.status_code == 200


def test_investigations_crud():
    inv_payload = {
        "name": "Delhi Decadal Study",
        "query": "Show me how Delhi changed over the last 10 years",
        "location": "Delhi, India",
        "datasets": ["sentinel-2", "sentinel-1"],
        "analysis_type": "temporal_change",
        "visualization_type": "Change Map",
        "summary": "134.2 km² urban growth observed"
    }
    save_res = client.post("/api/investigations", json=inv_payload)
    assert save_res.status_code == 200
    inv_id = save_res.json()["investigation"]["id"]

    get_res = client.get(f"/api/investigations/{inv_id}")
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "Delhi Decadal Study"
