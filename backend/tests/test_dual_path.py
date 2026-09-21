import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app, headers={"Authorization": "Bearer test_token_analyst"})


@pytest.fixture(autouse=True)
def mock_imagery_fetch(monkeypatch):
    import numpy as np
    from pathlib import Path
    from app.imagery.planetary_computer import SceneData
    from app.config import settings

    monkeypatch.setattr(settings, "ALLOW_MOCK_FALLBACK", True)
    monkeypatch.setattr(settings, "PRITHVI_WORKER_URL", None)
    monkeypatch.setattr(settings, "CHANGE_DETECTION_WORKER_URL", None)
    monkeypatch.setattr(settings, "CLOSP_WORKER_URL", None)
    monkeypatch.setattr(settings, "EARTHDIAL_WORKER_URL", None)

    output_dir = Path(__file__).resolve().parents[1] / settings.IMAGE_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    dummy_img = output_dir / "test_dual_scene.png"
    dummy_img.touch(exist_ok=True)

    dummy_scene = SceneData(
        item_id="S2_test_dual_scene",
        date="2024-01-01",
        red=np.full((10, 10), 0.2),
        green=np.full((10, 10), 0.3),
        blue=np.full((10, 10), 0.1),
        nir=np.full((10, 10), 0.5),
        profile={"transform": MagicMock(a=10, e=-10, b=0, d=0)},
        cloud_cover=5.0,
        true_color_path=dummy_img,
        pixel_area_km2=0.0001,
    )

    with patch("app.models.manager.fetch_before_after_and_series", return_value=(dummy_scene, dummy_scene, [dummy_scene])):
        yield


def test_known_scenario_uttarakhand_exact():
    query = "How much vegetation has been lost in Uttarakhand between 2020 and 2024?"
    response = client.post("/api/chat", json={"query": query})
    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "mock"
    assert "Uttarakhand" in data["result"]["aoi"]["name"]
    # Check exact metrics from VEG-001
    labels_to_values = {m["label"]: m["value"] for m in data["result"]["metrics"]}
    assert "Vegetation Loss" in labels_to_values
    assert "-143.8 km²" in labels_to_values["Vegetation Loss"]
    # Check globe action
    assert data["globe_action"]["action"] == "fly_to"
    assert data["globe_action"]["name"] == "Uttarakhand, India"


def test_known_scenario_typo_tolerance():
    query = "vegitation in uttarakhand"
    response = client.post("/api/chat", json={"query": query})
    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "mock"
    assert "Uttarakhand" in data["result"]["aoi"]["name"]


def test_known_scenario_derna_flood():
    query = "Show the flooding caused by Storm Daniel in Derna"
    response = client.post("/api/chat", json={"query": query})
    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "mock"
    assert "Derna" in data["result"]["aoi"]["name"]
    # Check inundation metric
    labels_to_values = {m["label"]: m["value"] for m in data["result"]["metrics"]}
    assert "Inundation Extent" in labels_to_values
    assert "+4.6 km²" in labels_to_values["Inundation Extent"] or "4.6 km²" in labels_to_values["Inundation Extent"]


def test_unknown_query_conceptual():
    query = "What is the best satellite dataset for monitoring glaciers?"
    response = client.post("/api/chat", json={"query": query})
    assert response.status_code == 200
    data = response.json()
    assert data["source"] in ["gpt", "gpt_oss", "mock_fallback"]
    assert "result" in data
    assert len(data["assistant_message"]["content"]) > 0


def test_unknown_query_kathmandu():
    query = "Tell me about vegetation around Kathmandu"
    response = client.post("/api/chat", json={"query": query})
    assert response.status_code == 200
    data = response.json()
    assert "result" in data
    center = data["result"]["aoi"]["center"]
    # Deterministic geocoder should have placed Kathmandu around 27.7°N, 85.3°E
    assert 27.0 <= center["latitude"] <= 28.5
    assert 84.5 <= center["longitude"] <= 86.0
