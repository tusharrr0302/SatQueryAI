"""
backend/tests/test_data_discovery.py
─────────────────────────────────────────────────────────────────────────────
Comprehensive Test Suite for SatQuery AI's Satellite Data Discovery & Acquisition Layer.

21 Tests covering:
  1. DataRequirement creation & validation
  2. Optical -> Sentinel-2 dataset discovery
  3. AOI -> provider STAC search
  4. Candidate asset deterministic ranking
  5. Cloud filtering (cloud_cover <= cloud_cover_max)
  6. Required band validation (B02, B03, B04, B08, VV, VH)
  7. Temporal asset selection (4 distinct windows)
  8. Missing temporal slot -> status='needs_data' (no silent duplication)
  9. SAR + optical dual-modality requirement
  10. Co-registration & temporal pair delta matching (<= 5 days)
  11. Unsupported historical period (1890 -> unsupported_data_period)
  12. Provider unavailable handling
  13. Mock provider deterministic fixtures
  14. Real vs Mock explicit provenance
  15. Search without premature download
  16. Multi-turn context -> data discovery
  17. ToolPlan -> DataRequirement integration
  18. DataAsset -> Tool input integration
  19. End-to-end: "Show optical imagery of Delhi" (Milestone 1 vertical slice)
  20. End-to-end: "What changed in Delhi between 2020 and 2025?" (Milestone 2 temporal slice)
  21. End-to-end: "Show possible flooding using SAR and optical imagery" (Milestone 3 multimodal slice)
"""
import pytest
import asyncio
import datetime
from typing import Dict, Any, List

from app.schemas.analysis_request import (
    AnalysisRequest,
    Intent,
    AOI,
    DataRequirements,
    ModelSelection,
    Analysis,
    Outputs,
    Execution,
    TemporalScope,
    ToolPlan,
)
from app.schemas.data_asset import DataAsset
from app.schemas.data_requirement import (
    DataRequirement,
    LocalAsset,
    DataDiscoveryResult,
    TemporalWindow,
)
from app.dataset.data_requirement_mapper import map_analysis_request_to_requirement
from app.dataset.providers import (
    MockSatelliteDataProvider,
    Sentinel2STACProvider,
    Sentinel1STACProvider,
    get_data_provider,
)
from app.dataset.asset_selector import (
    score_asset,
    rank_candidate_assets,
    select_best_asset,
    select_temporal_assets,
    match_sar_optical_pair,
)
from app.dataset.discovery_service import (
    SatelliteDataDiscoveryService,
    data_discovery_service,
)
from app.services.tool_registry import tool_registry
from app.graph.nodes import (
    validate_request,
    execute_unknown_analysis,
    _extract_geographic_entity,
    _classify_intent_deterministic,
    _generate_fallback_request,
)
from app.services.visualization_registry import build_data_layers


# ==============================================================================
# TEST 1: DataRequirement Creation & Validation
# ==============================================================================
def test_01_data_requirement_creation():
    req = DataRequirement(
        aoi_name="Delhi",
        bbox=[76.84, 28.40, 77.34, 28.88],
        temporal={"start": "2023-01-01", "end": "2024-01-01"},
        modalities=["optical"],
        preferred_datasets=["sentinel-2"],
        cloud_cover_max=15.0,
        required_bands=["B02", "B03", "B04", "B08"],
        acquisition_strategy="single",
    )
    assert req.aoi_name == "Delhi"
    assert req.cloud_cover_max == 15.0
    assert "B08" in req.required_bands
    assert req.acquisition_strategy == "single"


# ==============================================================================
# TEST 2: Optical -> Sentinel-2 Dataset Discovery
# ==============================================================================
def test_02_optical_to_sentinel2_mapping():
    ar = AnalysisRequest(
        query="Show optical imagery of Delhi",
        intent=Intent(primary_task="scene_description", question_type="new_analysis"),
        aoi=AOI(name="Delhi"),
        data_requirements=DataRequirements(modalities=["optical"]),
        model_selection=ModelSelection(model="earthdial-4b-ms", reason="Scene analysis"),
        analysis=Analysis(operation="observation"),
        outputs=Outputs(),
        execution=Execution(),
    )
    data_req = map_analysis_request_to_requirement(ar)
    assert "optical" in data_req.modalities
    assert "sentinel-2" in data_req.preferred_datasets
    assert data_req.acquisition_strategy == "single"
    assert set(["B02", "B03", "B04", "B08"]).issubset(set(data_req.required_bands))


# ==============================================================================
# TEST 3: AOI -> Provider STAC Search
# ==============================================================================
def test_03_aoi_stac_search():
    provider = MockSatelliteDataProvider()
    req = DataRequirement(
        aoi_name="Delhi",
        bbox=[76.84, 28.40, 77.34, 28.88],
        temporal={"start": "2020-01-01", "end": "2025-01-01"},
        modalities=["optical"],
        cloud_cover_max=20.0,
    )
    candidates = provider.search_sync(req)
    assert len(candidates) > 0
    assert all(c.dataset_id == "sentinel-2" for c in candidates)
    assert all(c.cloud_cover <= 20.0 for c in candidates)


# ==============================================================================
# TEST 4: Candidate Asset Deterministic Ranking
# ==============================================================================
def test_04_candidate_asset_ranking():
    req = DataRequirement(
        aoi_name="Delhi",
        cloud_cover_max=20.0,
        required_bands=["B02", "B03", "B04", "B08"],
    )
    c1 = DataAsset(
        asset_id="c1",
        cloud_cover=18.0,
        bands=["B02", "B03", "B04", "B08"],
        spatial_resolution=10.0,
    )
    c2 = DataAsset(
        asset_id="c2",
        cloud_cover=2.0,
        bands=["B02", "B03", "B04", "B08"],
        spatial_resolution=10.0,
    )
    ranked = rank_candidate_assets([c1, c2], req)
    assert len(ranked) == 2
    # c2 has significantly lower cloud cover, so must rank first
    assert ranked[0][0].asset_id == "c2"
    assert ranked[0][1] > ranked[1][1]


# ==============================================================================
# TEST 5: Cloud Filtering
# ==============================================================================
def test_05_cloud_filtering():
    req = DataRequirement(
        aoi_name="Delhi",
        cloud_cover_max=10.0,
        required_bands=["B02", "B03", "B04", "B08"],
    )
    low_cloud = DataAsset(
        asset_id="low_cloud",
        cloud_cover=5.0,
        bands=["B02", "B03", "B04", "B08"],
    )
    high_cloud = DataAsset(
        asset_id="high_cloud",
        cloud_cover=45.0,
        bands=["B02", "B03", "B04", "B08"],
    )
    ranked = rank_candidate_assets([low_cloud, high_cloud], req)
    assert len(ranked) == 1
    assert ranked[0][0].asset_id == "low_cloud"


# ==============================================================================
# TEST 6: Required Band Completeness
# ==============================================================================
def test_06_band_completeness_validation():
    req = DataRequirement(
        aoi_name="Delhi",
        cloud_cover_max=20.0,
        required_bands=["B02", "B03", "B04", "B08"],
    )
    complete = DataAsset(
        asset_id="complete",
        cloud_cover=5.0,
        bands=["B02", "B03", "B04", "B08"],
    )
    missing_nir = DataAsset(
        asset_id="missing_nir",
        cloud_cover=2.0,
        bands=["B02", "B03", "B04"],  # Missing B08
    )
    score_comp, _ = score_asset(complete, req)
    score_miss, rationale = score_asset(missing_nir, req)
    assert score_comp > 0.0
    assert score_miss == 0.0
    assert "Missing required bands" in rationale


# ==============================================================================
# TEST 7: Temporal Asset Selection (4 Distinct Windows)
# ==============================================================================
def test_07_temporal_asset_selection_4_slots():
    provider = MockSatelliteDataProvider()
    req = DataRequirement(
        aoi_name="Delhi",
        temporal={"start": "2020-01-01", "end": "2025-01-01"},
        modalities=["optical"],
        acquisition_strategy="temporal",
        temporal_count=4,
    )
    candidates = provider.search_sync(req)
    selected_slots, missing = select_temporal_assets(candidates, req, temporal_count=4)
    assert len(missing) == 0
    assert len(selected_slots) == 4
    assert set(selected_slots.keys()) == {"t1", "t2", "t3", "t4"}
    # Each slot must be a unique asset
    chosen_ids = [a.asset_id for a in selected_slots.values()]
    assert len(set(chosen_ids)) == 4


# ==============================================================================
# TEST 8: Missing Temporal Slot -> status='needs_data' Without Silent Duplication
# ==============================================================================
def test_08_missing_temporal_slot_handling():
    # Only supply assets for 2020 and 2021; leave later slots empty
    candidates = [
        DataAsset(
            asset_id="a1",
            acquisition_time="2020-05-01T00:00:00Z",
            cloud_cover=5.0,
            bands=["B02", "B03", "B04", "B08"],
        ),
        DataAsset(
            asset_id="a2",
            acquisition_time="2021-06-01T00:00:00Z",
            cloud_cover=4.0,
            bands=["B02", "B03", "B04", "B08"],
        ),
    ]
    req = DataRequirement(
        aoi_name="Delhi",
        temporal={"start": "2020-01-01", "end": "2025-01-01"},
        modalities=["optical"],
        acquisition_strategy="temporal",
        temporal_count=4,
        temporal_windows=[
            TemporalWindow(slot="t1", start="2020-01-01", end="2021-03-31"),
            TemporalWindow(slot="t2", start="2021-04-01", end="2022-06-30"),
            TemporalWindow(slot="t3", start="2022-07-01", end="2023-09-30"),
            TemporalWindow(slot="t4", start="2023-10-01", end="2025-01-01"),
        ],
    )
    selected_slots, missing = select_temporal_assets(candidates, req, temporal_count=4)
    assert "t3" in missing
    assert "t4" in missing
    # Never duplicate t1 into t3 or t4
    assert "t3" not in selected_slots
    assert "t4" not in selected_slots


# ==============================================================================
# TEST 9: SAR + Optical Dual-Modality Requirement
# ==============================================================================
def test_09_sar_optical_dual_modality():
    ar = AnalysisRequest(
        query="Show possible flooding using SAR and optical imagery in Derna",
        intent=Intent(primary_task="flood_analysis", question_type="new_analysis"),
        aoi=AOI(name="Derna"),
        data_requirements=DataRequirements(modalities=["sar", "optical"]),
        model_selection=ModelSelection(model="closp", reason="Flood alignment"),
        analysis=Analysis(operation="flood_assessment"),
        outputs=Outputs(),
        execution=Execution(),
    )
    plan = tool_registry.plan_execution(ar)
    data_req = map_analysis_request_to_requirement(ar, tool_plan=plan)
    assert data_req.acquisition_strategy == "sar_optical_pair"
    assert "sar" in data_req.modalities
    assert "optical" in data_req.modalities
    assert set(["VV", "VH"]).issubset(set(data_req.required_bands))
    assert set(["B02", "B03", "B04", "B08"]).issubset(set(data_req.required_bands))


# ==============================================================================
# TEST 10: Co-registration & Temporal Pair Delta Matching (<= 5 days)
# ==============================================================================
def test_10_sar_optical_temporal_pair_matching():
    sar_candidate = DataAsset(
        asset_id="sar_derna",
        dataset_id="sentinel-1",
        acquisition_time="2023-09-11T05:15:32Z",
        bands=["VV", "VH"],
    )
    opt_close = DataAsset(
        asset_id="opt_derna_close",
        dataset_id="sentinel-2",
        acquisition_time="2023-09-13T09:20:41Z",  # 2.17 days later (<= 5 days)
        cloud_cover=4.0,
        bands=["B02", "B03", "B04", "B08"],
    )
    opt_far = DataAsset(
        asset_id="opt_derna_far",
        dataset_id="sentinel-2",
        acquisition_time="2023-09-25T09:20:41Z",  # 14 days later (> 5 days)
        cloud_cover=1.0,
        bands=["B02", "B03", "B04", "B08"],
    )
    pair = match_sar_optical_pair([sar_candidate], [opt_close, opt_far], max_delta_days=5)
    assert pair is not None
    sar_res, opt_res = pair
    assert sar_res.asset_id == "sar_derna"
    assert opt_res.asset_id == "opt_derna_close"


# ==============================================================================
# TEST 11: Unsupported Historical Period (Pre-1972)
# ==============================================================================
def test_11_unsupported_historical_period():
    ar = AnalysisRequest(
        query="Show satellite imagery of Delhi in 1890",
        intent=Intent(
            primary_task="scene_description",
            temporal_scope=TemporalScope(start="1890", end="1890"),
        ),
        aoi=AOI(name="Delhi"),
        data_requirements=DataRequirements(modalities=["optical"]),
        model_selection=ModelSelection(model="earthdial-4b-ms", reason="Historical query"),
        analysis=Analysis(operation="observation"),
        outputs=Outputs(),
        execution=Execution(),
    )
    svc = SatelliteDataDiscoveryService(provider=MockSatelliteDataProvider())
    res = svc.discover_data_sync(ar)
    assert res.status == "unsupported_data_period"
    assert "1890" in res.message
    assert "1972" in res.message


# ==============================================================================
# TEST 12: Provider Unavailable Handling
# ==============================================================================
def test_12_provider_unavailable_handling():
    class FailingProvider(MockSatelliteDataProvider):
        def search_sync(self, req):
            raise ConnectionError("Upstream STAC API timeout")

    svc = SatelliteDataDiscoveryService(provider=FailingProvider())
    ar = AnalysisRequest(
        query="Show optical imagery of Delhi",
        intent=Intent(primary_task="scene_description"),
        aoi=AOI(name="Delhi"),
        data_requirements=DataRequirements(modalities=["optical"]),
        model_selection=ModelSelection(model="earthdial-4b-ms", reason="Scene test"),
        analysis=Analysis(operation="observation"),
        outputs=Outputs(),
        execution=Execution(),
    )
    res = svc.discover_data_sync(ar)
    assert res.status == "provider_unavailable"
    assert "Upstream STAC API timeout" in res.message


# ==============================================================================
# TEST 13: Mock Provider Deterministic Fixtures
# ==============================================================================
def test_13_mock_provider_deterministic_fixtures():
    prov = MockSatelliteDataProvider()
    delhi_req = DataRequirement(
        aoi_name="Delhi",
        temporal={"start": "2024-01-01", "end": "2025-01-31"},
        modalities=["optical"],
    )
    results = prov.search_sync(delhi_req)
    assert len(results) >= 2
    for r in results:
        assert r.metadata.get("source") == "mock"
        assert r.metadata.get("fallback") is True


# ==============================================================================
# TEST 14: Real vs Mock Explicit Provenance
# ==============================================================================
def test_14_real_vs_mock_explicit_provenance():
    mock_prov = MockSatelliteDataProvider()
    mock_assets = mock_prov.search_sync(
        DataRequirement(aoi_name="Delhi", modalities=["optical"])
    )
    assert mock_assets[0].metadata["source"] == "mock"
    assert mock_assets[0].metadata["fallback"] is True

    # Real STAC asset metadata specification contract
    live_prov = Sentinel2STACProvider()
    assert live_prov.COLLECTION == "sentinel-2-l2a"
    assert "planetarycomputer" in live_prov.STAC_ENDPOINT


# ==============================================================================
# TEST 15: Search Without Premature Download
# ==============================================================================
def test_15_search_without_premature_download():
    prov = MockSatelliteDataProvider()
    req = DataRequirement(aoi_name="Delhi", modalities=["optical"])
    candidates = prov.search_sync(req)
    for c in candidates:
        assert isinstance(c, DataAsset)
        # Search returns DataAsset metadata and urls, not LocalAsset
        assert hasattr(c, "preview_url")
        assert not isinstance(c, LocalAsset)


# ==============================================================================
# TEST 16: Multi-Turn Context -> Data Discovery
# ==============================================================================
def test_16_multiturn_context_data_discovery():
    # Turn 1 established Delhi
    active_aoi = {"name": "Delhi", "bbox": [76.84, 28.40, 77.34, 28.88]}
    # Turn 2 user asks: "Compare it with 2020"
    ar = _generate_fallback_request(
        query="Compare it with 2020",
        intent_type="FOLLOW_UP_ANALYSIS",
        active_aoi=active_aoi,
    )
    assert ar.aoi.name == "Delhi"
    data_req = map_analysis_request_to_requirement(ar, aoi_info=active_aoi)
    assert data_req.aoi_name == "Delhi"
    assert data_req.bbox == [76.84, 28.40, 77.34, 28.88]
    assert data_req.temporal["start"] == "2020-01-01"


# ==============================================================================
# TEST 17: ToolPlan -> DataRequirement Integration
# ==============================================================================
def test_17_toolplan_data_requirement_integration():
    ar = AnalysisRequest(
        query="Analyze vegetation loss over time in Delhi",
        intent=Intent(primary_task="vegetation_analysis"),
        aoi=AOI(name="Delhi"),
        data_requirements=DataRequirements(modalities=["optical"]),
        model_selection=ModelSelection(model="prithvi-eo-2.0", reason="Vegetation"),
        analysis=Analysis(operation="detect_change"),
        outputs=Outputs(),
        execution=Execution(),
    )
    plan = tool_registry.plan_execution(ar)
    data_req = map_analysis_request_to_requirement(ar, tool_plan=plan)
    assert data_req.acquisition_strategy == "temporal"
    assert data_req.temporal_count == 4
    assert len(data_req.temporal_windows) == 4


# ==============================================================================
# TEST 18: DataAsset -> Tool Input Integration
# ==============================================================================
def test_18_data_asset_tool_input_integration():
    ar = AnalysisRequest(
        query="Show possible flooding using SAR and optical imagery in Derna",
        intent=Intent(primary_task="flood_analysis"),
        aoi=AOI(name="Derna", bbox=[22.60, 32.74, 22.68, 32.79]),
        data_requirements=DataRequirements(modalities=["sar", "optical"]),
        model_selection=ModelSelection(model="closp", reason="Flood alignment"),
        analysis=Analysis(operation="flood_assessment"),
        outputs=Outputs(),
        execution=Execution(),
    )
    state = {
        "analysis_request": ar.model_dump(),
        "resolved_aoi": {"name": "Derna", "bbox": [22.60, 32.74, 22.68, 32.79]},
        "force_mock": True,
    }
    val_res = validate_request(state)
    assert val_res.get("status") != "needs_data"
    plan_inputs = val_res.get("tool_plan", {}).get("inputs", {})
    assert "sar_image_url" in plan_inputs
    assert "optical_image_url" in plan_inputs
    assert "S1A" in plan_inputs["sar_asset_id"]
    assert "S2A" in plan_inputs["optical_asset_id"]


# ==============================================================================
# TEST 19: End-to-End Milestone 1: "Show optical imagery of Delhi"
# ==============================================================================
# TEST 19: End-to-End Milestone 1: "Show optical imagery of Delhi"
# ==============================================================================
def test_19_e2e_show_optical_imagery_delhi():
    """
    Milestone 1 Vertical Slice Acceptance Path:
      "Show optical imagery of Delhi"
              ↓
      AnalysisRequest
              ↓
      ToolPlan
              ↓
      DataRequirement
              ↓
      Sentinel-2 Provider
              ↓
      STAC candidates
              ↓
      Deterministic ranking
              ↓
      Selected DataAsset
              ↓
      Cesium imagery layer
    """
    ar = AnalysisRequest(
        query="Show optical imagery of Delhi",
        intent=Intent(primary_task="scene_description", question_type="new_analysis"),
        aoi=AOI(name="Delhi", bbox=[76.84, 28.40, 77.34, 28.88]),
        data_requirements=DataRequirements(modalities=["optical"], datasets=["sentinel-2"]),
        model_selection=ModelSelection(model="earthdial-4b-ms", reason="Optical visualization"),
        analysis=Analysis(operation="observation"),
        outputs=Outputs(),
        execution=Execution(),
    )
    state = {
        "user_query": "Show optical imagery of Delhi",
        "analysis_request": ar.model_dump(),
        "resolved_aoi": {
            "name": "Delhi",
            "bbox": [76.84, 28.40, 77.34, 28.88],
            "center": {"latitude": 28.6139, "longitude": 77.2090},
            "polygon": [[76.84, 28.4], [77.34, 28.4], [77.34, 28.88], [76.84, 28.88], [76.84, 28.4]],
        },
        "force_mock": True,
    }

    # 1. validate_request derives ToolPlan and discovers DataAssets
    val_out = validate_request(state)
    state.update(val_out)

    assert state.get("tool_plan") is not None
    assert state.get("data_requirement") is not None
    assert state.get("data_discovery_result") is not None
    discovered = state.get("discovered_assets", [])
    assert len(discovered) >= 1
    selected_asset = discovered[0]
    assert selected_asset["dataset_id"] == "sentinel-2"
    assert selected_asset["cloud_cover"] <= 20.0

    # 2. execute_unknown_analysis directly builds Cesium layer without heavy model
    exec_out = asyncio.run(execute_unknown_analysis(state))
    state.update(exec_out)

    norm = state.get("normalized_result")
    assert norm is not None
    assert norm["analysis_type"] == "satellite_imagery_discovery"
    assert norm["provenance"]["model_name"] in ["Sentinel-2 STAC Provider", "Optical Scene Renderer"]
    assert len(norm["visualizations"]) == 1
    assert norm["visualizations"][0]["renderer"] == "cesium"
    assert norm["visualizations"][0]["type"] == "imagery"

    # 3. Verify Cesium layer generation via build_data_layers
    layers = build_data_layers(norm, query=state["user_query"])
    assert len(layers) >= 2
    imagery_layers = [l for l in layers if l.type == "imagery"]
    assert len(imagery_layers) == 1
    assert imagery_layers[0].role == "reference"
    assert imagery_layers[0].dataset == "Sentinel-2 MSI"


# ==============================================================================
# TEST 20: End-to-End Milestone 2: "What changed in Delhi between 2020 and 2025?"
# ==============================================================================
def test_20_e2e_delhi_temporal_change_2020_2025():
    """
    Milestone 2 Acceptance Path:
      "What changed in Delhi between 2020 and 2025?"
              ↓
      4 temporal Sentinel-2 assets
              ↓
      Prithvi / mock
              ↓
      NormalizedResult
              ↓
      Change visualization
    """
    ar = AnalysisRequest(
        query="What changed in Delhi between 2020 and 2025?",
        intent=Intent(
            primary_task="temporal_change_detection",
            temporal_scope=TemporalScope(start="2020", end="2025"),
            question_type="new_analysis",
        ),
        aoi=AOI(name="Delhi", bbox=[76.84, 28.40, 77.34, 28.88]),
        data_requirements=DataRequirements(modalities=["optical"], datasets=["sentinel-2"]),
        model_selection=ModelSelection(model="prithvi-eo-2.0", reason="Change detection"),
        analysis=Analysis(operation="detect_change"),
        outputs=Outputs(),
        execution=Execution(),
    )
    state = {
        "user_query": "What changed in Delhi between 2020 and 2025?",
        "analysis_request": ar.model_dump(),
        "resolved_aoi": {
            "name": "Delhi",
            "bbox": [76.84, 28.40, 77.34, 28.88],
            "center": {"latitude": 28.6139, "longitude": 77.2090},
        },
        "force_mock": True,
    }

    # 1. validate_request resolves 4 temporal slots
    val_out = validate_request(state)
    state.update(val_out)

    plan_inputs = state.get("tool_plan", {}).get("inputs", {})
    temporal_assets = plan_inputs.get("temporal_assets", {})
    assert len(temporal_assets) == 4
    assert set(temporal_assets.keys()) == {"t1", "t2", "t3", "t4"}

    # 2. execute_unknown_analysis executes Prithvi adapter
    exec_out = asyncio.run(execute_unknown_analysis(state))
    state.update(exec_out)

    norm = state.get("normalized_result")
    assert norm is not None
    assert norm["provenance"]["model_id"] == "prithvi-eo-2.0"
    assert norm["provenance"]["source"] in ("mock", "remote_worker", "unavailable")

    # 3. Data layers contain change detection layer
    layers = build_data_layers(norm, query=state["user_query"])
    change_layers = [l for l in layers if l.type in ("change_detection", "aoi")]
    assert len(change_layers) >= 1


# ==============================================================================
# TEST 21: End-to-End Milestone 3: "Show possible flooding using SAR and optical imagery"
# ==============================================================================
def test_21_e2e_sar_optical_flooding_closp():
    """
    Milestone 3 Acceptance Path:
      "Show possible flooding using SAR and optical imagery in Derna"
              ↓
      Sentinel-1 VV/VH + Sentinel-2
              ↓
      Temporal pairing (<= 5 days)
              ↓
      CLOSP execution
              ↓
      NormalizedResult & Cesium overlay
    """
    ar = AnalysisRequest(
        query="Show possible flooding using SAR and optical imagery in Derna",
        intent=Intent(primary_task="flood_analysis", question_type="new_analysis"),
        aoi=AOI(name="Derna", bbox=[22.60, 32.74, 22.68, 32.79]),
        data_requirements=DataRequirements(modalities=["sar", "optical"]),
        model_selection=ModelSelection(model="closp", reason="Cross-modal flood alignment"),
        analysis=Analysis(operation="flood_assessment"),
        outputs=Outputs(),
        execution=Execution(),
    )
    state = {
        "user_query": "Show possible flooding using SAR and optical imagery in Derna",
        "analysis_request": ar.model_dump(),
        "resolved_aoi": {
            "name": "Derna",
            "bbox": [22.60, 32.74, 22.68, 32.79],
            "center": {"latitude": 32.76, "longitude": 22.64},
        },
        "force_mock": True,
    }

    # 1. validate_request pairs SAR and optical assets within 5 days delta
    val_out = validate_request(state)
    state.update(val_out)

    plan_inputs = state.get("tool_plan", {}).get("inputs", {})
    assert "sar_image_url" in plan_inputs
    assert "optical_image_url" in plan_inputs
    assert "S1A" in plan_inputs["sar_asset_id"]
    assert "S2A" in plan_inputs["optical_asset_id"]

    # 2. execute_unknown_analysis dispatches CLOSP (or mock fallback if worker offline)
    exec_out = asyncio.run(execute_unknown_analysis(state))
    state.update(exec_out)

    # In mock test mode, status is success or worker unavailable error is reported honestly
    assert state.get("status") in ("success", "unavailable")
    if state.get("status") == "success":
        norm = state.get("normalized_result")
        assert norm is not None
        assert "closp" in norm["provenance"]["model_id"].lower()
