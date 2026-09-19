import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.schemas.normalized_result import (
    NormalizedResult, AOIInfo, Coordinates, MetricItem, Provenance,
    DataLayerSpec, LayerSource, LayerSpatial, LayerStyle, LayerLegend, LayerLegendItem,
    LayerTemporal, LayerProvenance, LayerAccess
)
from app.services.visualization_registry import build_data_layers

client = TestClient(app, headers={"Authorization": "Bearer test_token_analyst"})


def test_canonical_layer_schema_contract():
    """Verify DataLayerSpec adheres to the 10-point Phase 2 contract."""
    layer = DataLayerSpec(
        layer_id="layer_test_001",
        type="change_detection",
        title="Vegetation Canopy Disturbance",
        description="Sentinel-2 bi-temporal NDVI delta across test AOI",
        source=LayerSource(
            type="geojson",
            format="geojson",
            data={"type": "Feature", "geometry": {"type": "Polygon", "coordinates": []}},
        ),
        spatial=LayerSpatial(
            bounds=[76.84, 28.40, 77.34, 28.88],
            center=Coordinates(latitude=28.6139, longitude=77.2090),
            polygon=[[76.84, 28.40], [77.34, 28.40], [77.34, 28.88], [76.84, 28.88], [76.84, 28.40]],
        ),
        style=LayerStyle(
            opacity=0.85,
            color="rgba(239, 68, 68, 0.38)",
            outline_color="#ef4444",
            outline_width=2.5,
            color_scale="red",
        ),
        legend=LayerLegend(
            type="continuous",
            title="Canopy Change",
            unit="km²",
            min=-1.0,
            max=0.0,
            items=[LayerLegendItem(label="Canopy Disturbance", color="#ef4444", value="-143.8 km²")],
        ),
        temporal=LayerTemporal(
            start="2020",
            end="2024",
            acquisition_date="2020-2024",
        ),
        provenance=LayerProvenance(
            dataset_id="sentinel-2",
            model_id="prithvi-eo-2.0",
            source="mock",
        ),
        access=LayerAccess(
            is_private=False,
            user_id=None,
            asset_id=None,
        ),
    )

    d = layer.model_dump()
    assert d["layer_id"] == "layer_test_001"
    assert d["type"] == "change_detection"
    assert d["source"]["type"] == "geojson"
    assert len(d["spatial"]["bounds"]) == 4
    assert d["style"]["opacity"] == 0.85
    assert d["legend"]["type"] == "continuous"
    assert d["legend"]["min"] == -1.0
    assert d["temporal"]["start"] == "2020"
    assert d["provenance"]["source"] == "mock"
    assert d["access"]["is_private"] is False


def test_registry_build_data_layers_from_normalized_result():
    """Verify build_data_layers converts NormalizedResult into authoritative layer specs."""
    norm = NormalizedResult(
        result_id="res_test_veg",
        query="Vegetation loss in Uttarakhand",
        analysis_type="vegetation",
        aoi=AOIInfo(
            name="Uttarakhand",
            area_km2=53483.0,
            center=Coordinates(latitude=30.0668, longitude=79.0193),
            bbox=[77.57, 28.71, 81.04, 31.46],
            polygon=[[77.57, 28.71], [81.04, 28.71], [81.04, 31.46], [77.57, 31.46], [77.57, 28.71]],
        ),
        provenance=Provenance(
            source="mock",
            model_id="prithvi-eo-2.0",
            model_name="Prithvi-EO-2.0",
            dataset_ids=["sentinel-2"],
            acquisition_dates="2020 → 2024",
        ),
        key_finding="Confirmed vegetation loss of 143.8 km².",
        scientific_explanation="Bi-temporal NDVI delta reveals localized disturbance.",
        metrics=[MetricItem(label="Vegetation Loss", value="-143.8 km²", unit="km²")],
        before_image_url="/static/images/delhi_2023.jpg",
        after_image_url="/static/images/delhi_2024.jpg",
    )

    layers = build_data_layers(norm, query="Vegetation loss in Uttarakhand")
    assert len(layers) >= 3

    # Layer 1: AOI Footprint
    aoi_layer = next((l for l in layers if l.type == "aoi"), None)
    assert aoi_layer is not None
    assert "Uttarakhand Footprint" in aoi_layer.title
    assert aoi_layer.provenance.source == "mock"

    # Layer 2: Satellite Imagery
    img_layer = next((l for l in layers if l.type == "imagery"), None)
    assert img_layer is not None
    assert img_layer.source.type == "image"
    assert img_layer.source.url == "/static/images/delhi_2024.jpg"

    # Layer 3: Analytical Vegetation Canopy Loss
    veg_layer = next((l for l in layers if l.type == "change_detection"), None)
    assert veg_layer is not None
    assert veg_layer.legend is not None
    assert veg_layer.legend.items[0].value == "-143.8 km²"
    assert veg_layer.style.color_scale == "red"


def test_registry_user_uploaded_asset_layer_isolation():
    """Verify active_asset generates a private DataLayerSpec scoped to the owner."""
    user_asset = {
        "asset_id": "asset_geotiff_99",
        "filename": "kanpur_sentinel2.tif",
        "bounds": [80.25, 26.40, 80.45, 26.55],
        "center": {"latitude": 26.4499, "longitude": 80.3319},
        "dimensions": {"width": 1024, "height": 1024, "bands": 4},
        "crs": "EPSG:32644",
        "bands": [{"index": 1, "name": "B2-Blue"}, {"index": 2, "name": "B3-Green"}, {"index": 3, "name": "B4-Red"}, {"index": 4, "name": "B8-NIR"}],
    }

    norm = NormalizedResult(
        result_id="res_user_kanpur",
        query="What is in this image?",
        analysis_type="data_inspection",
        aoi=AOIInfo(
            name="kanpur_sentinel2.tif",
            area_km2=240.0,
            center=Coordinates(latitude=26.4499, longitude=80.3319),
            bbox=[80.25, 26.40, 80.45, 26.55],
        ),
        provenance=Provenance(
            source="user_data",
            model_id="deterministic_raster_inspector",
            model_name="Deterministic Rasterio Engine",
            dataset_ids=["kanpur_sentinel2.tif"],
        ),
        key_finding="User raster dataset inspected.",
        scientific_explanation="4-band GeoTIFF array.",
    )

    layers = build_data_layers(norm, query="What is in this image?", user_id="user_test_analyst", active_asset=user_asset)
    user_layer = next((l for l in layers if l.type == "user_asset"), None)
    assert user_layer is not None
    assert user_layer.access.is_private is True
    assert user_layer.access.user_id == "user_test_analyst"
    assert user_layer.access.asset_id == "asset_geotiff_99"
    assert user_layer.provenance.source == "user_data"
    assert "kanpur_sentinel2.tif" in user_layer.title


def test_api_chat_returns_authoritative_layers():
    """Verify /api/chat includes layers in top-level response and assistant_message."""
    query = "How much vegetation has been lost in Uttarakhand between 2020 and 2024?"
    response = client.post("/api/chat", json={"query": query})
    assert response.status_code == 200
    data = response.json()

    # Top-level layers
    assert "layers" in data
    assert isinstance(data["layers"], list)
    assert len(data["layers"]) >= 2

    # Preserves source: mock
    assert data["source"] == "mock"
    assert all(l["provenance"]["source"] == "mock" for l in data["layers"])

    # Contained in assistant_message and result
    assert "layers" in data["assistant_message"]
    assert "layers" in data["result"]
    assert data["layers"] == data["result"]["layers"]

    layer_types = [l["type"] for l in data["layers"]]
    assert "aoi" in layer_types
    assert "change_detection" in layer_types


def test_api_layers_endpoints():
    """Verify GET /api/layers and GET /api/layers/{layer_id}."""
    # First invoke chat to establish active layers in conversation
    chat_resp = client.post("/api/chat", json={"query": "Show the flooding caused by Storm Daniel in Derna"})
    assert chat_resp.status_code == 200
    chat_data = chat_resp.json()
    conv_id = chat_data["conversation_id"]

    # List layers endpoint
    list_resp = client.get(f"/api/layers?conversation_id={conv_id}")
    assert list_resp.status_code == 200
    layers = list_resp.json().get("layers", [])
    assert len(layers) >= 2

    flood_layer = next((l for l in layers if l["type"] == "flood_extent"), None)
    assert flood_layer is not None
    assert flood_layer["style"]["color_scale"] == "blue"

    # Single layer specification endpoint
    layer_id = flood_layer["layer_id"]
    spec_resp = client.get(f"/api/layers/{layer_id}?conversation_id={conv_id}")
    assert spec_resp.status_code == 200
    spec = spec_resp.json()
    assert spec["layer_id"] == layer_id
    assert spec["title"] == "SAR Flood Inundation Extent"
    assert spec["provenance"]["source"] == "mock"
