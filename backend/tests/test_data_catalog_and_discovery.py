"""
SatQuery AI — Comprehensive Data & Layer Catalog, Provider Adapters, and Intelligent Discovery Tests
Tests the 10 representative prompt scenarios, extensible registry, safe AST custom formulas, and API endpoints.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.auth import get_current_user
from app.db.models import User
from app.schemas.data_catalog import (
    DatasetMetadata,
    LayerDefinition,
    DataRequirementPlan,
    CustomVisualizationSpec,
)
from app.dataset.registry import (
    get_dataset,
    get_all_datasets,
    list_datasets,
    search_datasets,
    resolve_canonical_dataset_id,
    DATASET_REGISTRY,
)
from app.dataset.layer_catalog import (
    get_layer_definition,
    list_layers_for_dataset,
    search_layer_catalog,
    _LAYER_STORE,
)
from app.dataset.adapters import (
    adapter_registry,
    CopernicusAdapter,
    PlanetaryComputerAdapter,
    UserAssetAdapter,
)
from app.dataset.discovery import (
    infer_data_requirement_plan,
    rank_datasets,
    discover_active_layers_plan,
)
from app.dataset.custom_expression import (
    validate_formula_ast,
    validate_custom_visualization_spec,
    create_custom_layer_definition,
    CustomExpressionValidationError,
)


@pytest.fixture
def auth_client():
    user = User(id="test_usr_catalog", email="catalog_tester@satquery.ai", is_active=True)
    app.dependency_overrides[get_current_user] = lambda: user
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


# ==============================================================================
# 1. UNIFIED EXTENSIBLE DATASET REGISTRY TESTS
# ==============================================================================

def test_dataset_registry_contains_13_verified_datasets():
    datasets = get_all_datasets()
    assert len(datasets) >= 13
    assert len(DATASET_REGISTRY) >= 13

    # Check key mission identifiers
    canonical_ids = {d.dataset_id for d in datasets}
    expected_ids = {
        "sentinel-1-grd",
        "sentinel-2-l2a",
        "sentinel-3-olci",
        "sentinel-5p-tropomi",
        "copernicus-dem-glo30",
        "copernicus-land-cover-100m",
        "copernicus-surface-soil-moisture",
        "copernicus-marine-water-quality",
        "landsat-8-9-c2",
        "cartosat-3-vhr",
        "risat-1a-sar",
        "planetscope",
        "user-asset-raster",
    }
    for eid in expected_ids:
        assert eid in canonical_ids, f"Expected canonical dataset {eid} missing from registry"


def test_dataset_metadata_completeness():
    for ds in get_all_datasets():
        assert ds.dataset_id, "dataset_id cannot be empty"
        assert ds.name, "name cannot be empty"
        assert ds.provider, "provider cannot be empty"
        assert ds.mission, "mission cannot be empty"
        assert ds.sensor, "sensor cannot be empty"
        assert ds.platform, "platform cannot be empty"
        assert ds.modality, "modality cannot be empty"
        assert ds.spatial_resolution, "spatial_resolution cannot be empty"
        assert ds.provenance, "provenance cannot be empty"
        assert ds.limitations, "limitations cannot be empty"
        assert len(ds.products) > 0, f"products empty for {ds.dataset_id}"
        assert len(ds.supported_analyses) > 0, f"supported_analyses empty for {ds.dataset_id}"
        assert len(ds.available_visualizations) > 0, f"available_visualizations empty for {ds.dataset_id}"


def test_dataset_shorthand_aliases():
    assert resolve_canonical_dataset_id("sentinel-2") == "sentinel-2-l2a"
    assert resolve_canonical_dataset_id("sentinel-1") == "sentinel-1-grd"
    assert resolve_canonical_dataset_id("sentinel-5p") == "sentinel-5p-tropomi"
    assert resolve_canonical_dataset_id("dem") == "copernicus-dem-glo30"
    assert resolve_canonical_dataset_id("landsat") == "landsat-8-9-c2"

    # get_dataset handles aliases
    s2 = get_dataset("sentinel-2")
    assert s2 is not None
    assert s2.dataset_id == "sentinel-2-l2a"


# ==============================================================================
# 2. LAYER CATALOG REGISTRY TESTS (DATASET != LAYER)
# ==============================================================================

def test_layer_catalog_contains_21_plus_layers():
    assert len(_LAYER_STORE) >= 21, f"Expected >= 21 layers, found {len(_LAYER_STORE)}"


def test_sentinel2_exposes_multiple_distinct_layers():
    # Sentinel-2 should expose at least RGB, False Color, NDVI, NDWI, NDBI, Red Edge, SWIR
    s2_layers = list_layers_for_dataset("sentinel-2-l2a")
    layer_ids = {l.layer_id for l in s2_layers}
    assert "sentinel2_rgb" in layer_ids
    assert "sentinel2_false_color_nir" in layer_ids
    assert "sentinel2_ndvi" in layer_ids
    assert "sentinel2_ndwi" in layer_ids
    assert "sentinel2_ndbi" in layer_ids
    assert "sentinel2_red_edge" in layer_ids
    assert "sentinel2_swir_urban" in layer_ids


def test_sentinel5p_atmospheric_layers():
    s5p_layers = list_layers_for_dataset("sentinel-5p-tropomi")
    layer_ids = {l.layer_id for l in s5p_layers}
    assert "sentinel5p_no2_density" in layer_ids
    assert "sentinel5p_co_density" in layer_ids
    assert "sentinel5p_aerosol_index" in layer_ids


def test_copernicus_dem_topographic_layers():
    dem_layers = list_layers_for_dataset("copernicus-dem-glo30")
    layer_ids = {l.layer_id for l in dem_layers}
    assert "copernicus_dem_surface" in layer_ids
    assert "copernicus_dem_hillshade" in layer_ids


def test_search_layer_catalog_by_category():
    veg_layers = search_layer_catalog(category="vegetation")
    assert len(veg_layers) >= 3
    for l in veg_layers:
        assert l.category == "vegetation"

    sar_layers = search_layer_catalog(category="sar")
    assert len(sar_layers) >= 2


# ==============================================================================
# 3. PROVIDER ADAPTERS TESTS
# ==============================================================================

def test_adapter_registry_resolves_providers():
    assert isinstance(adapter_registry.get_adapter("copernicus"), CopernicusAdapter)
    assert isinstance(adapter_registry.get_adapter("planetary_computer"), PlanetaryComputerAdapter)
    assert isinstance(adapter_registry.get_adapter("user_asset"), UserAssetAdapter)


def test_copernicus_adapter_metadata():
    adapter = adapter_registry.get_adapter("copernicus")
    collections = adapter.list_available_collections()
    assert "SENTINEL-2" in collections
    assert "SENTINEL-1" in collections
    assert "COP-DEM-GLO-30" in collections

    bands = adapter.get_band_metadata("sentinel-2-l2a")
    assert "B04" in bands
    assert "B08" in bands


def test_user_asset_adapter_generates_dataset_and_layers():
    adapter = adapter_registry.get_adapter("user_asset")
    asset_dict = {
        "asset_id": "test_geotiff_99",
        "filename": "farm_multispectral_sample.tif",
        "dimensions": {"width": 1024, "height": 1024, "bands": 4},
        "bands": [
            {"index": 1, "name": "Red"},
            {"index": 2, "name": "Green"},
            {"index": 3, "name": "Blue"},
            {"index": 4, "name": "NIR"},
        ],
        "bounds": [77.10, 28.50, 77.30, 28.70],
        "crs": "EPSG:4326",
    }
    user_ds = adapter.register_user_asset_dataset(asset_dict, user_id="usr_01")
    assert user_ds.dataset_id == "user_asset_test_geotiff_99"
    assert user_ds.is_user_asset is True

    user_layers = list_layers_for_dataset(user_ds.dataset_id)
    assert len(user_layers) >= 2
    layer_names = [l.name for l in user_layers]
    assert any("True Color" in n for n in layer_names)
    assert any("NDVI" in n for n in layer_names)


# ==============================================================================
# 4. INTELLIGENT DISCOVERY & 10 REPRESENTATIVE QUERIES TESTS
# ==============================================================================

def test_query_1_vegetation_loss_uttarakhand():
    query = "Show vegetation loss in Uttarakhand"
    plan = infer_data_requirement_plan(query)
    assert "optical" in plan.modality

    ranked = rank_datasets(plan)
    assert ranked[0][0].dataset_id == "sentinel-2-l2a"

    active_plan = discover_active_layers_plan(query)
    assert active_plan["selected_dataset"].dataset_id == "sentinel-2-l2a"
    active_layers = active_plan["active_layers"]
    assert len(active_layers) >= 1
    assert any(l.category == "vegetation" for l in active_layers)
    assert active_layers[0].role == "primary_analysis"


def test_query_2_no2_pollution_delhi():
    query = "Check NO2 pollution in Delhi after Diwali"
    plan = infer_data_requirement_plan(query)
    assert "atmospheric" in plan.modality
    assert plan.phenomenon == "atmospheric_pollution"

    ranked = rank_datasets(plan)
    assert "sentinel-5p" in ranked[0][0].dataset_id

    active_plan = discover_active_layers_plan(query)
    assert "sentinel-5p" in active_plan["selected_dataset"].dataset_id
    assert any("no2" in l.layer_id for l in active_plan["active_layers"])


def test_query_3_flood_derna():
    query = "Map flood extent in Derna"
    plan = infer_data_requirement_plan(query)
    assert "sar" in plan.modality
    assert plan.phenomenon == "flood_inundation"

    ranked = rank_datasets(plan)
    assert ranked[0][0].dataset_id == "sentinel-1-grd"

    active_plan = discover_active_layers_plan(query)
    assert active_plan["selected_dataset"].dataset_id == "sentinel-1-grd"
    assert any("flood" in l.layer_id for l in active_plan["active_layers"])


def test_query_4_land_cover_bangalore():
    query = "Classify land cover around Bangalore"
    plan = infer_data_requirement_plan(query)
    assert "land_cover" in plan.modality or "multispectral" in plan.modality

    active_plan = discover_active_layers_plan(query)
    assert active_plan["selected_dataset"].dataset_id in ["copernicus-land-cover-100m", "sentinel-2-l2a"]


def test_query_5_elevation_alps():
    query = "Show elevation profile for Alps"
    plan = infer_data_requirement_plan(query)
    assert "dem" in plan.modality

    ranked = rank_datasets(plan)
    assert "dem" in ranked[0][0].dataset_id

    active_plan = discover_active_layers_plan(query)
    assert "dem" in active_plan["selected_dataset"].dataset_id
    assert any("surface" in l.layer_id or "dem" in l.layer_id for l in active_plan["active_layers"])


def test_query_6_soil_moisture_punjab():
    query = "Monitor soil moisture in Punjab"
    plan = infer_data_requirement_plan(query)
    assert "soil" in plan.modality

    ranked = rank_datasets(plan)
    assert "soil" in ranked[0][0].dataset_id


def test_query_7_water_quality_bay_of_bengal():
    query = "Track ocean chlorophyll in Bay of Bengal"
    plan = infer_data_requirement_plan(query)
    assert "water" in plan.modality

    ranked = rank_datasets(plan)
    top_ids = [r[0].dataset_id for r in ranked[:2]]
    assert any("water" in t or "marine" in t or "olci" in t for t in top_ids)


def test_query_8_comparison_delhi_vegetation_urban():
    query = "Compare vegetation loss and urban expansion in Delhi"
    plan = infer_data_requirement_plan(query)
    active_plan = discover_active_layers_plan(query)

    active_layers = active_plan["active_layers"]
    roles = {l.role for l in active_layers}
    # Should have primary_analysis and comparison
    assert "primary_analysis" in roles
    assert "comparison" in roles


def test_query_9_user_geotiff_raster():
    asset_dict = {
        "asset_id": "test_geotiff_user",
        "filename": "my_drone_field.tif",
        "dimensions": {"width": 500, "height": 500, "bands": 4},
        "bands": [{"name": "Red"}, {"name": "Green"}, {"name": "Blue"}, {"name": "NIR"}],
    }
    active_plan = discover_active_layers_plan("Inspect my uploaded GeoTIFF raster", active_asset=asset_dict)
    assert active_plan["selected_dataset"].is_user_asset is True
    assert any(l.role == "primary_analysis" for l in active_plan["active_layers"])


def test_query_10_aoi_catalog_search():
    delhi_aoi = {"name": "Delhi NCR", "bbox": [76.84, 28.40, 77.34, 28.88]}
    active_plan = discover_active_layers_plan("Find all available data layers over Delhi", aoi=delhi_aoi)
    assert active_plan["selected_dataset"] is not None
    assert len(active_plan["active_layers"]) >= 1


# ==============================================================================
# 5. SAFE AST CUSTOM FORMULA TESTS
# ==============================================================================

def test_ast_safe_formula_validation():
    # Valid expressions
    ok, vars_found, errs = validate_formula_ast("(B08 - B04) / (B08 + B04)")
    assert ok is True
    assert vars_found == {"B08", "B04"}
    assert len(errs) == 0

    ok2, vars2, _ = validate_formula_ast("(NIR - RED) / (NIR + RED)")
    assert ok2 is True
    assert vars2 == {"NIR", "RED"}


def test_ast_rejects_unsafe_code_execution():
    # Attempt function calls
    ok, _, errs = validate_formula_ast("__import__('os').system('rm -rf /')")
    assert ok is False
    assert any("Function calls are strictly forbidden" in e for e in errs)

    # Attempt attribute access
    ok2, _, errs2 = validate_formula_ast("B08.__class__.__bases__")
    assert ok2 is False
    assert any("Attribute access is strictly forbidden" in e for e in errs2)

    # Attempt subscripting
    ok3, _, errs3 = validate_formula_ast("B08[0] + B04[1]")
    assert ok3 is False
    assert any("Subscript indexing is strictly forbidden" in e for e in errs3)


def test_custom_visualization_spec_validation():
    spec = CustomVisualizationSpec(
        type="index",
        formula="(B08 - B04) / (B08 + B04)",
        output_range=[-1.0, 1.0],
        color_map="viridis",
    )
    valid, errors, meta = validate_custom_visualization_spec(spec, "sentinel-2-l2a")
    assert valid is True
    assert len(errors) == 0
    assert meta["resolved_bands"]["B08"] == "B08"
    assert meta["resolved_bands"]["B04"] == "B04"

    layer = create_custom_layer_definition(spec, "sentinel-2-l2a", "My NDVI Layer")
    assert layer.layer_id == "sentinel-2-l2a-custom-my_ndvi_layer"
    assert layer.visualization_type == "single_band_index"
    assert "B08" in layer.required_bands
    assert "B04" in layer.required_bands


def test_custom_band_composite_validation():
    spec = CustomVisualizationSpec(
        type="band_composite",
        bands={"r": "B08", "g": "B04", "b": "B03"},
    )
    valid, errors, meta = validate_custom_visualization_spec(spec, "sentinel-2-l2a")
    assert valid is True
    assert meta["bands"] == {"r": "B08", "g": "B04", "b": "B03"}

    layer = create_custom_layer_definition(spec, "sentinel-2-l2a", "CIR Composite")
    assert layer.visualization_type == "rgb_composite"
    assert set(layer.required_bands) == {"B08", "B04", "B03"}


# ==============================================================================
# 6. REST API ENDPOINTS TESTS
# ==============================================================================

def test_api_catalog_summary(auth_client):
    res = auth_client.get("/api/catalog/summary")
    assert res.status_code == 200
    data = res.json()
    assert data["verified_dataset_count"] >= 13
    assert data["verified_layer_count"] >= 21
    assert "Copernicus / ESA" in data["providers"]
    assert "optical" in data["modalities"]
    assert "sar" in data["modalities"]


def test_api_catalog_datasets(auth_client):
    res = auth_client.get("/api/catalog/datasets")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 13
    ds_names = [d["name"] for d in data["datasets"]]
    assert any("Sentinel-2" in n for n in ds_names)
    assert any("Sentinel-1" in n for n in ds_names)
    assert any("DEM" in n for n in ds_names)


def test_api_catalog_dataset_detail(auth_client):
    res = auth_client.get("/api/catalog/datasets/sentinel-2-l2a")
    assert res.status_code == 200
    data = res.json()
    assert data["dataset_id"] == "sentinel-2-l2a"
    assert data["verified_layer_count"] >= 7
    assert len(data["layers"]) >= 7


def test_api_catalog_layers_filtering(auth_client):
    # Filter by dataset
    res_ds = auth_client.get("/api/catalog/layers?dataset_id=sentinel-5p-tropomi")
    assert res_ds.status_code == 200
    layers = res_ds.json()["layers"]
    assert len(layers) >= 3
    assert all(l["dataset_id"] == "sentinel-5p-tropomi" for l in layers)

    # Filter by category
    res_cat = auth_client.get("/api/catalog/layers?category=sar")
    assert res_cat.status_code == 200
    assert len(res_cat.json()["layers"]) >= 2


def test_api_catalog_custom_layer_validation(auth_client):
    res = auth_client.post(
        "/api/catalog/custom-layer/validate",
        json={
            "dataset_id": "sentinel-2-l2a",
            "spec": {
                "type": "index",
                "formula": "(B08 - B04) / (B08 + B04)",
                "output_range": [-1.0, 1.0],
                "color_map": "turbo",
            },
            "layer_name": "API Custom NDVI",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["is_valid"] is True
    assert body["layer_definition"]["layer_id"] == "sentinel-2-l2a-custom-api_custom_ndvi"
