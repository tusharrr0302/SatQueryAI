"""Verification test suite for SatQuery AI Intelligent Visualization Workstation.

Tests the 18 authoritative visualization planning, multi-modal representation,
AI explanation modes, grounded web evidence attribution, and Cesium 3D layer contracts.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.normalized_result import (
    NormalizedResult, AOIInfo, Coordinates, MetricItem, Provenance,
    SatelliteImagePair, TimeSeriesPoint, VisualizationSpec, VisualizationPlan,
    DataLayerSpec, WebEvidenceItem
)
from app.services.visualization_registry import (
    plan_visualizations, detect_query_intent, build_data_layers
)
from app.services.web_evidence import (
    should_trigger_web_evidence, retrieve_grounded_web_evidence
)

client = TestClient(app, headers={"Authorization": "Bearer test_token_workstation"})


def _create_mock_normalized_result(query="Show vegetation change in Delhi", aoi_name="Delhi"):
    return NormalizedResult(
        query=query,
        analysis_type="vegetation_loss",
        aoi=AOIInfo(
            name=aoi_name,
            bbox=[76.84, 28.40, 77.34, 28.88],
            center=Coordinates(latitude=28.6139, longitude=77.2090),
            area_km2=1484.0,
            polygon=[[76.84, 28.40], [77.34, 28.40], [77.34, 28.88], [76.84, 28.88], [76.84, 28.40]],
        ),
        provenance=Provenance(
            source="planetary_computer",
            fallback=False,
            model_id="prithvi-eo-2.0",
            model_name="Prithvi-EO-2.0",
            dataset_ids=["sentinel-2-l2a"],
            acquisition_dates="2020-01-01 to 2024-01-01",
        ),
        key_finding="Sentinel-2 NDVI dropped by -0.1420 across 143.80 km².",
        scientific_explanation="Bi-temporal NDVI differencing from calibrated Sentinel-2 BOA reflectance.",
        metrics=[
            MetricItem(label="Mean NDVI before", value="0.5412", unit="NDVI"),
            MetricItem(label="Mean NDVI after", value="0.3992", unit="NDVI"),
            MetricItem(label="Mean NDVI change", value="-0.1420", unit="NDVI"),
            MetricItem(label="Changed area", value="143.80", unit="km²"),
            MetricItem(label="Vegetation loss", value="18.42", unit="%"),
        ],
        time_series=[
            TimeSeriesPoint(date="2020-01-01", metric_name="NDVI", value=0.5412),
            TimeSeriesPoint(date="2024-01-01", metric_name="NDVI", value=0.3992),
        ],
    )


# Test 1: Authoritative visualization plan composition
def test_authoritative_visualization_plan_composition():
    res = _create_mock_normalized_result()
    plan = plan_visualizations(res, query="Show vegetation change in Delhi", ai_mode="auto")
    assert isinstance(plan, VisualizationPlan)
    assert plan.primary_visualization is not None
    assert plan.primary_visualization.get("title")
    assert len(plan.active_layers) > 0
    assert plan.explanation is not None
    assert plan.explanation.visual_form
    assert plan.explanation.what_this_represents


# Test 2: AI Mode Beginner vocabulary and structure
def test_ai_mode_beginner_vocabulary_and_structure():
    res = _create_mock_normalized_result()
    plan = plan_visualizations(res, query="Show vegetation loss in Delhi", ai_mode="beginner")
    exp = plan.explanation
    assert exp.plain_language_summary is not None
    assert "easy-to-read" in exp.plain_language_summary or "plain language" in exp.plain_language_summary or "Delhi" in exp.plain_language_summary
    # Beginner explanations use straightforward vocabulary
    assert len(exp.what_this_represents) > 10


# Test 3: AI Mode Intermediate scientific structure
def test_ai_mode_intermediate_scientific_structure():
    res = _create_mock_normalized_result()
    plan = plan_visualizations(res, query="Analyze vegetation index in Delhi", ai_mode="intermediate")
    exp = plan.explanation
    assert exp.primary_metric
    assert "ndvi" in exp.primary_metric.lower() or "sentinel-2" in exp.provenance_and_sensor.lower()


# Test 4: AI Mode Advanced mathematical structure
def test_ai_mode_advanced_mathematical_structure():
    res = _create_mock_normalized_result()
    plan = plan_visualizations(res, query="Model canopy degradation in Delhi", ai_mode="advanced")
    exp = plan.explanation
    assert exp.technical_summary is not None
    # Advanced mode includes mathematical / formula expressions
    assert "\\Delta" in exp.technical_summary or "NDVI" in exp.technical_summary or "NIR" in exp.technical_summary


# Test 5: Point Cloud Visualization Planning
def test_point_cloud_visualization_planning():
    query = "Show 3D LiDAR point cloud and canopy elevation profile for Delhi forest"
    intent = detect_query_intent(query)
    assert intent.get("point_cloud") is True
    res = _create_mock_normalized_result(query=query)
    plan = plan_visualizations(res, query=query, ai_mode="auto")
    assert plan.primary_visualization.get("type") in ["point_cloud", "scatter3D", "bar3d", "aoi"]
    layer_types = [l.type for l in plan.active_layers]
    assert "point_cloud" in layer_types or "3d_surface" in layer_types or "aoi" in layer_types


# Test 6: Heatmap Density Visualization Planning
def test_heatmap_density_visualization_planning():
    query = "Show urban thermal hotspot density heatmap across Delhi"
    intent = detect_query_intent(query)
    assert intent.get("heatmap") is True
    res = _create_mock_normalized_result(query=query)
    plan = plan_visualizations(res, query=query, ai_mode="auto")
    layer_types = [l.type for l in plan.active_layers]
    assert "heatmap" in layer_types or plan.primary_visualization.get("type") == "heatmap"


# Test 7: 3D Continuous Surface Visualization Planning
def test_3d_continuous_surface_visualization_planning():
    query = "Show 3D topographic terrain elevation surface for Delhi ridge"
    intent = detect_query_intent(query)
    assert intent.get("elevation") is True
    res = _create_mock_normalized_result(query=query)
    plan = plan_visualizations(res, query=query, ai_mode="auto")
    layer_types = [l.type for l in plan.active_layers]
    assert "3d_surface" in layer_types or plan.primary_visualization.get("type") in ["surface3D", "3d_surface"]


# Test 8: 3D Extrusion Visualization Planning
def test_3d_extrusion_visualization_planning():
    query = "Show 3D building height volume extrusion for Delhi core"
    intent = detect_query_intent(query)
    assert intent.get("urban") is True
    res = _create_mock_normalized_result(query=query)
    plan = plan_visualizations(res, query=query, ai_mode="auto")
    layer_types = [l.type for l in plan.active_layers]
    assert "3d_extruded_polygon" in layer_types or plan.primary_visualization.get("type") == "bar3d"


# Test 9: Point Detections Visualization Planning
def test_point_detections_visualization_planning():
    query = "Detect individual detected points and grounding points near Mumbai port"
    intent = detect_query_intent(query)
    assert intent.get("point_detections") is True
    res = _create_mock_normalized_result(query=query, aoi_name="Mumbai")
    plan = plan_visualizations(res, query=query, ai_mode="auto")
    layer_types = [l.type for l in plan.active_layers]
    assert "point_detections" in layer_types or plan.primary_visualization.get("type") in ["scatter", "scatter3D"]


# Test 10: Web Evidence Ground Photo Attribution Label
def test_web_evidence_ground_photo_attribution_label():
    evidence = retrieve_grounded_web_evidence("Show ground photo verification of Delhi urban park", "Delhi")
    assert len(evidence) > 0
    ref_photos = [e for e in evidence if getattr(e, "is_reference_photo", False)]
    assert len(ref_photos) > 0
    for photo in ref_photos:
        assert "Ground Reference Photo (Not Satellite Telemetry)" in photo.attribution
        assert photo.source_domain


# Test 11: Web Evidence Retrieval and Triggering
def test_web_evidence_retrieval_and_filtering():
    assert should_trigger_web_evidence("What does the ground reality look like according to news reports in Delhi?")
    assert should_trigger_web_evidence("Show photos and field verification reports of Delhi")
    evidence = retrieve_grounded_web_evidence("news reports about deforestation in Delhi", "Delhi")
    assert len(evidence) >= 1
    assert all(isinstance(e, WebEvidenceItem) for e in evidence)


# Test 12: Active Layers Semantic Roles and Purposes
def test_active_layers_semantic_roles_and_purposes():
    res = _create_mock_normalized_result()
    layers = build_data_layers(res)
    valid_roles = {"primary_analysis", "study_area", "comparison", "reference"}
    for layer in layers:
        assert layer.role in valid_roles, f"Invalid role {layer.role} for layer {layer.layer_id}"
        assert layer.purpose, f"Missing purpose for layer {layer.layer_id}"
        assert len(layer.purpose) > 10


# Test 13: All 10 Facets Present in Explanation
def test_all_10_facets_present_in_explanation():
    res = _create_mock_normalized_result()
    plan = plan_visualizations(res, query="Vegetation delta in Delhi", ai_mode="auto")
    exp = plan.explanation
    required_facets = [
        "visual_form",
        "what_this_represents",
        "primary_metric",
        "baseline_comparison",
        "palette_and_scale",
        "critical_thresholds",
        "spatial_context",
        "provenance_and_sensor",
        "visual_inferences",
        "limitations",
    ]
    for facet in required_facets:
        val = getattr(exp, facet, None)
        assert val, f"Missing explanation facet: {facet}"
        assert isinstance(val, str) and len(val) > 0


# Test 14: Metric Preservation Across All AI Modes
def test_metric_preservation_across_all_ai_modes():
    res = _create_mock_normalized_result()
    for mode in ["beginner", "intermediate", "advanced", "auto"]:
        plan = plan_visualizations(res, query="Vegetation delta in Delhi", ai_mode=mode)
        # Verify primary metric explicitly carries the exact verified value (-0.1420)
        assert "-0.1420" in plan.explanation.primary_metric


# Test 15: Chat Endpoint Returns Visualization Plan and AI Mode
def test_chat_endpoint_returns_visualization_plan_and_ai_mode():
    resp = client.post("/api/chat", json={
        "query": "Show vegetation change in Delhi",
        "ai_mode": "beginner"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "visualization_plan" in data
    assert data["visualization_plan"] is not None
    assert "primary_visualization" in data["visualization_plan"]
    assert "explanation" in data["visualization_plan"]
    assert data.get("ai_mode") == "beginner"


# Test 16: Chat Endpoint Returns Grounded Web Evidence
def test_chat_endpoint_returns_grounded_web_evidence():
    resp = client.post("/api/chat", json={
        "query": "Show news reports and ground photos for deforestation in Delhi",
        "ai_mode": "auto"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "web_evidence" in data
    assert isinstance(data["web_evidence"], list)
    if len(data["web_evidence"]) > 0:
        item = data["web_evidence"][0]
        assert "title" in item
        assert "url" in item


# Test 17: Globe Action Camera Binding From Visualization Plan
def test_globe_action_camera_binding_from_visualization_plan():
    res = _create_mock_normalized_result()
    plan = plan_visualizations(res, query="Show 3D topographic elevation in Delhi", ai_mode="auto")
    assert plan.camera is not None
    assert plan.camera.pitch is not None
    assert plan.camera.destination is not None
    assert len(plan.camera.destination) == 3


# Test 18: Cesium Layer Manager Layer Types Supported
def test_cesium_layer_manager_layer_types_supported():
    res = _create_mock_normalized_result()
    layers = build_data_layers(res, query="Show point cloud LiDAR for Delhi")
    types = {l.type for l in layers}
    assert "point_cloud" in types or "3d_surface" in types
    
    heatmap_layers = build_data_layers(res, query="Show thermal density heatmap for Delhi")
    assert any(l.type == "heatmap" for l in heatmap_layers)

    surface_layers = build_data_layers(res, query="Show 3D topographic surface DEM for Delhi")
    assert any(l.type == "3d_surface" for l in surface_layers)

    extrusion_layers = build_data_layers(res, query="Show 3D building height extrusion for Delhi")
    assert any(l.type == "3d_extruded_polygon" for l in extrusion_layers)

    detections_layers = build_data_layers(res, query="Detect ships and point detections near Mumbai")
    assert any(l.type == "point_detections" for l in detections_layers)
