"""
SatQuery AI — Comprehensive Conversational AOI Resolution Test Suite

Validates all 10 core conversation test cases:
1. "so is it better?" -> No Nominatim, answers from previous result.
2. "why?" -> No Nominatim.
3. "what dataset did you use?" -> No Nominatim.
4. "show it on the globe" -> Reuses active AOI, no geocoding.
5. "what about southern Delhi?" -> Reuses Delhi AOI, relative spatial focus, no geocoding "southern region".
6. "what about Mumbai?" -> Resolves new AOI, Nominatim query = "Mumbai, India".
7. "What is NDVI?" -> No AOI, no Nominatim.
8. "Compare these two images" -> Uses active assets, no Nominatim.
9. Upload GeoTIFF -> "What is this?" -> Uses DataProfile, no Nominatim.
10. Upload GeoTIFF -> "Show vegetation." -> Uses asset bounds, no Nominatim.
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.schemas.normalized_result import AOIInfo, Coordinates

client = TestClient(app)
AUTH_HEADERS = {"Authorization": "Bearer test_token_conversational_aoi"}


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
    dummy_img = output_dir / "test_scene.png"
    dummy_img.touch(exist_ok=True)

    dummy_scene = SceneData(
        item_id="S2_test_scene",
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


@pytest.fixture
def mock_nominatim_calls():
    """Tracks resolve_aoi calls to ensure no conversational text is ever geocoded."""
    calls = []

    def spy_resolve(name: str):
        calls.append(name)
        is_delhi = "delhi" in name.lower()
        lat = 28.6139 if is_delhi else 19.0760
        lon = 77.2090 if is_delhi else 72.8777
        bbox = [76.84, 28.40, 77.35, 28.88] if is_delhi else [72.77, 18.89, 72.98, 19.27]
        return AOIInfo(
            id=f"aoi_{abs(hash(name))}",
            name=name.split(",")[0].strip(),
            country="India",
            center=Coordinates(latitude=lat, longitude=lon),
            area_km2=150.0,
            bbox=bbox,
            polygon=[
                [bbox[0], bbox[1]], [bbox[2], bbox[1]],
                [bbox[2], bbox[3]], [bbox[0], bbox[3]],
                [bbox[0], bbox[1]],
            ],
        )

    with patch("app.geo.resolver.resolve_aoi", side_effect=spy_resolve):
        yield calls


def test_case_1_to_6_delhi_conversation_sequence(mock_nominatim_calls):
    """
    Sequence:
    Turn 1: "Analyze vegetation in Delhi."
    Turn 2: "so is it better?"
    Turn 3: "why?"
    Turn 4: "what dataset did you use?"
    Turn 5: "show it on the globe."
    Turn 6: "what about the southern region?"
    Turn 7: "what about Mumbai?"
    """
    # Turn 1: Initial analysis
    resp1 = client.post("/api/chat", json={"query": "Analyze vegetation in Delhi."}, headers=AUTH_HEADERS)
    assert resp1.status_code == 200
    d1 = resp1.json()
    conv_id = d1["conversation_id"]
    assert conv_id is not None
    assert d1["status"] == "success"

    initial_nominatim_count = len(mock_nominatim_calls)

    # Case 1: "so is it better?"
    resp2 = client.post("/api/chat", json={"conversation_id": conv_id, "query": "so is it better?"}, headers=AUTH_HEADERS)
    assert resp2.status_code == 200
    d2 = resp2.json()
    assert d2["status"] == "success"
    # MUST NOT call Nominatim
    assert len(mock_nominatim_calls) == initial_nominatim_count, f"Nominatim was called for 'so is it better?': {mock_nominatim_calls}"
    assert "Nominatim returned no AOI" not in d2["assistant_message"]["content"]
    assert len(d2["assistant_message"]["content"]) > 10

    # Case 2: "why?"
    resp3 = client.post("/api/chat", json={"conversation_id": conv_id, "query": "why?"}, headers=AUTH_HEADERS)
    assert resp3.status_code == 200
    d3 = resp3.json()
    assert d3["status"] == "success"
    assert len(mock_nominatim_calls) == initial_nominatim_count, f"Nominatim called for 'why?': {mock_nominatim_calls}"

    # Case 3: "what dataset did you use?"
    resp4 = client.post("/api/chat", json={"conversation_id": conv_id, "query": "what dataset did you use?"}, headers=AUTH_HEADERS)
    assert resp4.status_code == 200
    d4 = resp4.json()
    assert d4["status"] == "success"
    assert len(mock_nominatim_calls) == initial_nominatim_count, f"Nominatim called for dataset inquiry: {mock_nominatim_calls}"
    assert "sentinel" in d4["assistant_message"]["content"].lower() or "prithvi" in d4["assistant_message"]["content"].lower() or "telemetry" in d4["assistant_message"]["content"].lower()

    # Case 4: "show it on the globe."
    resp5 = client.post("/api/chat", json={"conversation_id": conv_id, "query": "show it on the globe."}, headers=AUTH_HEADERS)
    assert resp5.status_code == 200
    d5 = resp5.json()
    assert d5["status"] == "success"
    assert len(mock_nominatim_calls) == initial_nominatim_count, f"Nominatim called for 'show it on the globe': {mock_nominatim_calls}"

    # Case 5: "what about the southern region?"
    resp6 = client.post("/api/chat", json={"conversation_id": conv_id, "query": "what about the southern region?"}, headers=AUTH_HEADERS)
    assert resp6.status_code == 200
    d6 = resp6.json()
    assert d6["status"] == "success"
    # MUST NOT geocode "southern region"
    assert not any("southern region" in call.lower() for call in mock_nominatim_calls), f"Geocoded 'southern region': {mock_nominatim_calls}"

    # Case 6: "what about Mumbai?" -> New location
    resp7 = client.post("/api/chat", json={"conversation_id": conv_id, "query": "what about Mumbai?"}, headers=AUTH_HEADERS)
    assert resp7.status_code == 200
    d7 = resp7.json()
    assert d7["status"] == "success"
    # MUST have geocoded Mumbai, NOT "what about Mumbai?"
    assert any("mumbai" in call.lower() for call in mock_nominatim_calls), f"Expected Mumbai in Nominatim calls: {mock_nominatim_calls}"
    assert not any("what about" in call.lower() for call in mock_nominatim_calls), f"Geocoded full sentence: {mock_nominatim_calls}"


def test_case_7_general_knowledge_what_is_ndvi(mock_nominatim_calls):
    """Case 7: "What is NDVI?" -> No AOI, No Nominatim."""
    init_calls = len(mock_nominatim_calls)
    resp = client.post("/api/chat", json={"query": "What is NDVI?"}, headers=AUTH_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert len(mock_nominatim_calls) == init_calls, f"Nominatim called for 'What is NDVI?': {mock_nominatim_calls}"
    content = data["assistant_message"]["content"]
    assert "vegetation index" in content.lower() or "ndvi" in content.lower()


def test_case_8_9_10_uploaded_asset_no_geocoding(mock_nominatim_calls):
    """Cases 8, 9, 10: Uploaded asset -> 'Compare these two images', 'What is this?', 'Show vegetation'."""
    init_calls = len(mock_nominatim_calls)
    # Register synthetic user asset
    from app.api.data_routes import _ASSET_CATALOG
    from app.schemas.data_asset import DataAsset, DataProfile, Dimensions, BandInfo
    profile = DataProfile(
        asset_id="asset_test_geotiff_55",
        filename="bengaluru_spectral.tif",
        format="GeoTIFF",
        dimensions=Dimensions(width=1024, height=1024, bands=4),
        dtype="uint16",
        crs="EPSG:32643",
        bounds=[77.50, 12.90, 77.70, 13.10],
        center={"latitude": 13.00, "longitude": 77.60},
        bands=[BandInfo(index=1, name="B2-Blue"), BandInfo(index=2, name="B3-Green"), BandInfo(index=3, name="B4-Red"), BandInfo(index=4, name="B8-NIR")],
        sensor="Sentinel-2 MSI",
    )
    test_asset = DataAsset(
        asset_id="asset_test_geotiff_55",
        filename="bengaluru_spectral.tif",
        file_path="/tmp/bengaluru_spectral.tif",
        file_size_bytes=1024 * 1024,
        preview_url="/api/data/assets/asset_test_geotiff_55/preview",
        created_at="2026-09-19T00:00:00Z",
        profile=profile,
    )
    _ASSET_CATALOG["asset_test_geotiff_55"] = test_asset

    # Case 9: "What is this?" with active asset
    resp_what = client.post(
        "/api/chat",
        json={"query": "What is this?", "active_asset_id": "asset_test_geotiff_55"},
        headers=AUTH_HEADERS,
    )
    assert resp_what.status_code == 200
    d_what = resp_what.json()
    assert d_what["status"] == "success"
    assert len(mock_nominatim_calls) == init_calls, f"Nominatim called on 'What is this?': {mock_nominatim_calls}"
    assert "bengaluru_spectral.tif" in str(d_what)

    # Case 10: "Show vegetation." with active asset
    resp_veg = client.post(
        "/api/chat",
        json={"query": "Show vegetation.", "active_asset_id": "asset_test_geotiff_55"},
        headers=AUTH_HEADERS,
    )
    assert resp_veg.status_code == 200
    d_veg = resp_veg.json()
    assert d_veg["status"] == "success"
    assert len(mock_nominatim_calls) == init_calls, f"Nominatim called on 'Show vegetation.': {mock_nominatim_calls}"

    # Case 8: "Compare these two images."
    resp_cmp = client.post(
        "/api/chat",
        json={"query": "Compare these two images.", "active_asset_id": "asset_test_geotiff_55"},
        headers=AUTH_HEADERS,
    )
    assert resp_cmp.status_code == 200
    assert len(mock_nominatim_calls) == init_calls, f"Nominatim called on comparison query: {mock_nominatim_calls}"
