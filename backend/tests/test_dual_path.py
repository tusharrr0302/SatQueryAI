import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


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
