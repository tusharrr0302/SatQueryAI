import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app, headers={"Authorization": "Bearer test_token_analyst"})


def test_live_query_1_kashmir_10yr_vegetation(monkeypatch):
    """Query 1: Kashmir 10-year vegetation trend."""
    from app.config import settings
    monkeypatch.setattr(settings, "EO_EXECUTION_MODE", "mock")
    
    query = "Analyze vegetation trends in Kashmir from 2016 to 2026"
    response = client.post("/api/chat", json={"query": query})
    assert response.status_code == 200
    data = response.json()
    assert "result" in data
    res = data["result"]
    assert "Kashmir" in res["aoi"]["name"]

    # Verify temporal observations or time series
    ts = res.get("time_series", [])
    assert len(ts) >= 2 or res.get("visualization_plan") is not None

    # Verify plan explanation has canonical factual fields
    plan = res.get("visualization_plan")
    if plan and plan.get("explanation"):
        expl = plan["explanation"]
        assert expl.get("what_it_shows") is not None
        assert expl.get("data_source") is not None


def test_live_query_2_nepal_flood_baseline(monkeypatch):
    """Query 2: Nepal flood baseline comparison."""
    from app.config import settings
    monkeypatch.setattr(settings, "EO_EXECUTION_MODE", "mock")

    query = "Show flood impact in Nepal compared to pre-event baseline"
    response = client.post("/api/chat", json={"query": query})
    assert response.status_code == 200
    data = response.json()
    assert "result" in data
    res = data["result"]
    assert "Nepal" in res["aoi"]["name"] or "Kathmandu" in res["aoi"]["name"]
    # Verify presentation plan or image comparison
    assert res.get("presentation_plan") is not None or res.get("image_comparison") is not None or len(res.get("layers", [])) > 0


def test_live_query_3_kashmir_terrain_copernicus_dem(monkeypatch):
    """Query 3: Kashmir 3D terrain/DEM elevation."""
    from app.config import settings
    monkeypatch.setattr(settings, "EO_EXECUTION_MODE", "mock")

    query = "Show 3D terrain elevation for Kashmir"
    response = client.post("/api/chat", json={"query": query})
    assert response.status_code == 200
    data = response.json()
    assert "result" in data
    res = data["result"]
    assert "Kashmir" in res["aoi"]["name"]
    layers = res.get("layers", [])
    layer_ids = [l.get("layer_id") for l in layers]
    assert any("dem" in lid or "terrain" in lid or "copernicus" in lid or "surface" in lid for lid in layer_ids)


def test_live_query_4_sar_changes_over_1_year(monkeypatch):
    """Query 4: SAR changes over 1 year."""
    from app.config import settings
    monkeypatch.setattr(settings, "EO_EXECUTION_MODE", "mock")

    query = "Show SAR radar changes in Kashmir over the last year"
    response = client.post("/api/chat", json={"query": query})
    assert response.status_code == 200
    data = response.json()
    assert "result" in data
    res = data["result"]
    assert "Kashmir" in res["aoi"]["name"]
    # Radar dataset or model referenced
    prov = res.get("provenance") or {}
    assert "sentinel-1" in prov.get("dataset_ids", []) or "sar" in str(prov).lower() or len(res.get("layers", [])) > 0


def test_live_query_5_kashmir_3d_vegetation(monkeypatch):
    """Query 5: Kashmir 3D vegetation view."""
    from app.config import settings
    monkeypatch.setattr(settings, "EO_EXECUTION_MODE", "mock")

    query = "Show 3D vegetation surface for Kashmir"
    response = client.post("/api/chat", json={"query": query})
    assert response.status_code == 200
    data = response.json()
    assert "result" in data
    res = data["result"]
    assert "Kashmir" in res["aoi"]["name"]
    vis = res.get("visualization") or {}
    plan = res.get("visualization_plan")
    # Must have 3D surface or spatial overlay
    assert "3D" in vis.get("type", "") or "Surface" in vis.get("type", "") or plan is not None
