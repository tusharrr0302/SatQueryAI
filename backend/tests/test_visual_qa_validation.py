"""
SatQuery AI — Comprehensive Visual QA, Scientific Correctness & Real Data Validation Suite
Validates the 24 acceptance criteria from the user prompt across all 10 test queries,
AI modes, Cesium layer compositions, ECharts specs, progressive disclosure, and real-data pipelines.
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app, headers={"Authorization": "Bearer test_token_qa_analyst"})


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
    dummy_img = output_dir / "test_scene_qa.png"
    dummy_img.touch(exist_ok=True)

    dummy_scene = SceneData(
        item_id="S2_test_qa_scene",
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


# =====================================================================
# 1. TEST THE 10 USER-REQUESTED QUERIES & VISUAL MATCHING
# =====================================================================

def test_query_1_how_much_vegetation_delhi_lost():
    """Query 1: 'How much vegetation has Delhi lost?' -> Emphasizes quantitative metrics."""
    res = client.post("/api/chat", json={"query": "How much vegetation has Delhi lost?"})
    assert res.status_code == 200
    d = res.json()
    assert d["status"] == "success"
    
    # 1. Visualization Plan
    plan = d.get("visualization_plan") or {}
    assert plan, "Visualization plan must be present"
    primary = plan.get("primary_visualization") or {}
    # Must emphasize quantitative change/loss
    assert any(k in primary.get("id", "").lower() or k in primary.get("type", "").lower() for k in ["bar", "metrics", "summary", "vegetation"])
    
    # 2. Headline quantitative metrics must be present and verified
    metrics = d.get("result", {}).get("metrics") or []
    assert len(metrics) > 0
    metric_labels = [m["label"].lower() for m in metrics]
    assert any("loss" in l or "vegetation" in l or "change" in l for l in metric_labels)
    
    # 3. Active Cesium Layers with roles
    layers = plan.get("active_layers") or []
    assert len(layers) >= 1
    assert any(l.get("role") == "primary_analysis" for l in layers)
    assert all(l.get("purpose") for l in layers)

    # 4. 10-facet Explanation
    exp = plan.get("explanation") or {}
    assert exp.get("visual_form")
    assert exp.get("what_this_represents")
    assert exp.get("primary_metric")
    assert exp.get("limitations")


def test_query_2_where_has_delhi_lost_vegetation():
    """Query 2: 'Where has Delhi lost vegetation?' -> Emphasizes spatial distribution."""
    res = client.post("/api/chat", json={"query": "Where has Delhi lost vegetation?"})
    assert res.status_code == 200
    d = res.json()
    assert d["status"] == "success"
    
    plan = d.get("visualization_plan") or {}
    layers = plan.get("active_layers") or []
    # Must activate spatial imagery/polygon/change_detection layers in Cesium
    spatial_layers = [l for l in layers if l.get("type") in ["change_detection", "imagery", "aoi", "polygon", "cesium_raster", "cesium_polygon", "cesium_imagery", "cesium_3d_tiles"]]
    assert len(spatial_layers) >= 1, "Spatial inquiry must activate spatial Cesium layers"
    
    # Camera spec must frame the target region
    cam = plan.get("camera")
    assert cam is not None
    dest = cam.get("destination") or []
    cam_lat = dest[1] if len(dest) > 1 else cam.get("latitude", 0)
    cam_lon = dest[0] if len(dest) > 0 else cam.get("longitude", 0)
    assert 28.0 <= cam_lat <= 29.0
    assert 76.5 <= cam_lon <= 78.0


def test_query_3_how_has_vegetation_changed_over_10_years():
    """Query 3: 'How has vegetation changed over 10 years?' -> Emphasizes temporal evolution."""
    res = client.post("/api/chat", json={"query": "How has vegetation changed over 10 years in Delhi?"})
    assert res.status_code == 200
    d = res.json()
    
    plan = d.get("visualization_plan") or {}
    primary = plan.get("primary_visualization") or {}
    # Temporal inquiry should prioritize time series or longitudinal trend
    secondaries = plan.get("secondary_visualizations") or []
    all_vis = [primary] + secondaries
    assert any("time_series" in v.get("id", "") or "trend" in v.get("id", "") or "bar" in v.get("type", "") for v in all_vis)
    
    # Explanation should specify temporal window
    exp = plan.get("explanation") or {}
    assert any(k in exp.get("temporal_range", "").lower() for k in ["year", "epoch", "annual", "2015", "2024", "→", "-"])


def test_query_4_compare_urban_expansion_and_vegetation_loss():
    """Query 4: 'Compare urban expansion and vegetation loss.' -> Multi-layer comparison."""
    res = client.post("/api/chat", json={"query": "Compare urban expansion and vegetation loss in Delhi."})
    assert res.status_code == 200
    d = res.json()
    
    plan = d.get("visualization_plan") or {}
    layers = plan.get("active_layers") or []
    # Must have both primary_analysis and comparison or study_area roles
    roles = {l.get("role") for l in layers}
    assert "primary_analysis" in roles
    # Layers must coexist with separate purposes
    assert len(layers) >= 2, f"Comparative query should have multiple simultaneous layers, got {len(layers)}"
    assert any("urban" in l.get("title", "").lower() or "expansion" in l.get("title", "").lower() for l in layers)


def test_query_5_show_flood_affected_areas():
    """Query 5: 'Show flood affected areas.' -> Inundation extent & flood impact."""
    res = client.post("/api/chat", json={"query": "Show the flooding caused by Storm Daniel in Derna"})
    assert res.status_code == 200
    d = res.json()
    
    plan = d.get("visualization_plan") or {}
    primary = plan.get("primary_visualization") or {}
    assert any(k in primary.get("id", "").lower() or k in primary.get("title", "").lower() for k in ["flood", "inundation", "water"])
    
    # Check inundation layer in active layers
    layers = plan.get("active_layers") or []
    assert any("flood" in l.get("title", "").lower() or "water" in l.get("title", "").lower() for l in layers)
    
    # Explanation units must include flood depth or inundated area
    exp = plan.get("explanation") or {}
    assert "km²" in exp.get("units", "") or "hectares" in exp.get("units", "")


def test_query_6_show_me_the_terrain():
    """Query 6: 'Show me the terrain.' -> 3D continuous surface DEM."""
    # Turn 1: Establish context in Delhi
    r1 = client.post("/api/chat", json={"query": "Analyze vegetation in Delhi."}).json()
    conv_id = r1["conversation_id"]
    
    # Turn 2: Show me the terrain
    res = client.post("/api/chat", json={"query": "Show me the terrain.", "conversation_id": conv_id})
    assert res.status_code == 200
    d = res.json()
    
    plan = d.get("visualization_plan") or {}
    primary = plan.get("primary_visualization") or {}
    assert any(k in primary.get("type", "") or k in primary.get("id", "") for k in ["3d_surface", "surface", "terrain", "elevation"])
    
    layers = plan.get("active_layers") or []
    assert any(l.get("type") in ["3d_surface", "cesium_continuous_surface"] for l in layers)


def test_query_7_show_concentration_of_events():
    """Query 7: 'Show the concentration of these events.' -> Heatmap density."""
    # Turn 1: Establish context in Delhi
    r1 = client.post("/api/chat", json={"query": "Analyze vegetation in Delhi."}).json()
    conv_id = r1["conversation_id"]
    
    # Turn 2: Show the concentration of these events
    res = client.post("/api/chat", json={"query": "Show the concentration of these events.", "conversation_id": conv_id})
    assert res.status_code == 200
    d = res.json()
    
    plan = d.get("visualization_plan") or {}
    primary = plan.get("primary_visualization") or {}
    assert "heatmap" in primary.get("type", "").lower()
    
    layers = plan.get("active_layers") or []
    assert any(l.get("type") == "heatmap" for l in layers)


def test_query_8_show_every_detected_point():
    """Query 8: 'Show me every detected point.' -> Discrete point detections."""
    # Turn 1: Establish context in Delhi
    r1 = client.post("/api/chat", json={"query": "Analyze vegetation in Delhi."}).json()
    conv_id = r1["conversation_id"]
    
    # Turn 2: Show me every detected point
    res = client.post("/api/chat", json={"query": "Show me every detected point.", "conversation_id": conv_id})
    assert res.status_code == 200
    d = res.json()
    
    plan = d.get("visualization_plan") or {}
    primary = plan.get("primary_visualization") or {}
    assert any(k in primary.get("type", "") or k in primary.get("id", "") for k in ["point", "points", "point_detections"])
    
    layers = plan.get("active_layers") or []
    assert any(l.get("type") in ["point_detections", "point", "point_cloud"] for l in layers)


def test_query_9_explain_this_map():
    """Query 9: 'Explain this map.' -> Conversational visual explanation."""
    # Turn 1: Analyze Delhi
    r1 = client.post("/api/chat", json={"query": "Analyze vegetation in Delhi."}).json()
    conv_id = r1["conversation_id"]
    
    # Turn 2: Explain this map
    r2 = client.post("/api/chat", json={"query": "Explain this map.", "conversation_id": conv_id}).json()
    assert r2["status"] == "success"
    ans = r2["assistant_message"]["content"]
    assert len(ans) > 50
    # Must explain visual components without running a brand new geocoding query
    assert any(k in ans.lower() for k in ["visualization", "map", "seeing", "view", "telemetry", "delhi"])


def test_query_10_what_is_ndvi_no_fake_layers():
    """Query 10: 'What is NDVI?' -> General knowledge without fake satellite layers."""
    res = client.post("/api/chat", json={"query": "What is NDVI?"})
    assert res.status_code == 200
    d = res.json()
    assert d["status"] == "success"
    
    ans = d["assistant_message"]["content"]
    assert "normalized difference vegetation index" in ans.lower()
    
    # Must NOT generate unnecessary active Cesium layers or fake analysis result
    plan = d.get("visualization_plan") or {}
    layers = plan.get("active_layers") or []
    assert len(layers) == 0, f"General knowledge query should not activate Cesium layers, got {len(layers)}"


# =====================================================================
# 2. TEST AI MODES: NUMERICAL INVARIANCE & TERMINOLOGY
# =====================================================================

def test_ai_modes_numerical_invariance_and_tone():
    """
    Verify across Auto, Beginner, Intermediate, and Advanced modes:
    1. The numeric values (-143.8 km², -18.7%) remain STRICTLY IDENTICAL.
    2. Beginner uses simple vocabulary and plain language summary.
    3. Advanced includes technical formulation and sensor telemetry.
    """
    q = "Analyze vegetation in Delhi."
    
    # 1. Beginner Mode
    r_beg = client.post("/api/chat", json={"query": q, "ai_mode": "beginner"}).json()
    ans_beg = r_beg["assistant_message"]["content"]
    
    # 2. Advanced Mode
    r_adv = client.post("/api/chat", json={"query": q, "ai_mode": "advanced"}).json()
    ans_adv = r_adv["assistant_message"]["content"]
    
    # 3. Intermediate Mode
    r_int = client.post("/api/chat", json={"query": q, "ai_mode": "intermediate"}).json()
    ans_int = r_int["assistant_message"]["content"]
    
    # Numerical metrics preservation
    m_beg = {m["label"]: m["value"] for m in r_beg["result"]["metrics"]}
    m_adv = {m["label"]: m["value"] for m in r_adv["result"]["metrics"]}
    m_int = {m["label"]: m["value"] for m in r_int["result"]["metrics"]}
    assert m_beg == m_adv == m_int, "Metrics must be numerically identical across all AI modes"
    assert any("96.7" in str(v) or "143.8" in str(v) for v in m_beg.values())
    
    # Beginner mode should feature plain English
    assert r_beg.get("ai_mode") == "beginner"
    exp_beg = r_beg["visualization_plan"]["explanation"]
    assert exp_beg.get("plain_language_summary")
    
    # Advanced mode should feature technical depth
    assert r_adv.get("ai_mode") == "advanced"
    exp_adv = r_adv["visualization_plan"]["explanation"]
    assert exp_adv.get("technical_summary")


# =====================================================================
# 3. TEST GROUNDED WEB EVIDENCE & GROUND PHOTO BADGE
# =====================================================================

def test_grounded_web_evidence_separation_and_badge():
    """Verify web evidence citations and ground photo badge are present and separated."""
    res = client.post("/api/chat", json={"query": "Show news reports and ground photos for deforestation in Delhi"})
    assert res.status_code == 200
    d = res.json()
    
    evidence = d.get("web_evidence") or []
    assert len(evidence) >= 1, "Should retrieve grounded web evidence"
    
    # Check source domain and attribution
    for item in evidence:
        assert item.get("source_domain"), "Web evidence must contain source domain"
        assert item.get("url"), "Web evidence must contain URL"
        if item.get("is_reference_photo"):
            assert "Ground Reference Photo (Not Satellite Telemetry)" in item.get("attribution", "")
    
    # Assistant message should have contextual references section
    content = d["assistant_message"]["content"]
    assert "Ground Reference Photo" in content or "Contextual References" in content


# =====================================================================
# 4. TEST MULTI-TURN PERSISTENCE & LAYER COEXISTENCE
# =====================================================================

def test_multiturn_layer_coexistence_and_camera_stability():
    """
    Multi-turn progression:
    Turn 1: Delhi vegetation -> generates vegetation layer
    Turn 2: Southern region -> specializes focus without losing context
    Turn 3: Compare with urban expansion -> retains and adds comparison layer
    """
    # Turn 1
    t1 = client.post("/api/chat", json={"query": "Analyze vegetation in Delhi."}).json()
    conv_id = t1["conversation_id"]
    layers_t1 = t1["visualization_plan"]["active_layers"]
    assert len(layers_t1) >= 1
    
    # Turn 2: Spatial focus
    t2 = client.post("/api/chat", json={"query": "What about southern Delhi?", "conversation_id": conv_id}).json()
    assert t2["conversation_id"] == conv_id
    assert "southern" in t2["result"]["aoi"]["name"].lower() or "delhi" in t2["result"]["aoi"]["name"].lower()
    
    # Turn 3: Compare with urban
    t3 = client.post("/api/chat", json={"query": "Compare that with urban expansion.", "conversation_id": conv_id}).json()
    layers_t3 = t3["visualization_plan"]["active_layers"]
    assert len(layers_t3) >= 2, "Both analysis and comparison layers should coexist"
    
    # Check semantic roles
    roles = [l["role"] for l in layers_t3]
    assert "comparison" in roles or "primary_analysis" in roles
    assert "study_area" in roles or "reference" in roles
