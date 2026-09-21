import pytest
from app.geo.resolver import resolve_aoi
from app.dataset.discovery import (
    infer_data_requirement_plan,
    discover_active_layers_plan,
)
from app.graph.nodes import (
    _extract_geographic_entity,
    _extract_temporal_scope,
    _format_unknown_markdown_fallback,
    _classify_intent_deterministic,
    generate_final_response,
)
from app.services.visualization_registry import plan_visualizations, build_data_layers


def test_scenario_1_kashmir_apple_farm_natural_query():
    """
    Scenario 1: Complex natural query with application intent
    'how kashmir has changed in last 10 years in terms of vegetation, i am thinking to start an apple farm there, will it be good option'
    """
    query = "how kashmir has changed in last 10 years in terms of vegetation, i am thinking to start an apple farm there, will it be good option"

    # 1. Geographic extraction
    loc = _extract_geographic_entity(query)
    assert loc is not None
    assert "kashmir" in loc.lower()

    # 2. AOI resolution
    aoi_info = resolve_aoi(loc)
    assert aoi_info is not None
    assert "kashmir" in aoi_info.name.lower()
    assert len(aoi_info.bbox) == 4

    # 3. Temporal scope
    start_y, end_y = _extract_temporal_scope(query)
    assert int(end_y) - int(start_y) >= 9

    # 4. Data requirement inference
    req_plan = infer_data_requirement_plan(query, loc)
    assert req_plan.user_intent == "agricultural investigation"
    assert req_plan.primary_domain in ["vegetation", "agriculture"]
    assert "optical" in req_plan.recommended_data_modalities
    assert "terrain" in req_plan.recommended_data_modalities

    # 5. Active layer plan includes multi-factor supporting layers
    layer_plan = discover_active_layers_plan(req_plan)
    active_layers = layer_plan["active_layers"]
    assert len(active_layers) >= 3
    roles = [l.role for l in active_layers]
    assert "primary_analysis" in roles
    assert "reference" in roles

    # 6. Fallback markdown output contains required sections and caveats
    norm_dict = {
        "analysis_type": "agricultural_investigation",
        "key_finding": "Multi-temporal satellite telemetry indicates favorable environmental baseline conditions.",
        "aoi": {"name": aoi_info.name},
        "provenance": {
            "model_name": "Deterministic Spectral Analysis & Topographic Screening",
            "dataset_ids": ["sentinel-2-l2a", "copernicus-dem-30m", "worldcover-10m"],
            "source": "mock",
        },
        "metrics": [
            {"label": "Mean Canopy NDVI (2015-2025)", "value": "0.54"},
            {"label": "Tree Canopy & Orchard Cover", "value": "42.1%"},
            {"label": "Basin Elevation", "value": "1,580 m"},
            {"label": "Mean Slope Gradient", "value": "4.2°"},
        ],
    }
    md = _format_unknown_markdown_fallback(query, norm_dict)
    assert "### Summary" in md
    assert "### Satellite Evidence & Multi-Factor Telemetry" in md
    assert "### Environmental Interpretation for Orchard Siting" in md
    assert "### Critical Limitations & In-Situ Agronomic Validation" in md
    assert "Soil Chemistry" in md
    assert "Winter Chilling Hours" in md
    assert "Please specify a geographic location" not in md


def test_scenario_2_optical_and_sar_valencia_floods():
    """
    Scenario 2: Optical + SAR cross-modal co-observation
    'show optical and sar for flood in Valencia'
    """
    query = "show optical and sar for flood in Valencia"
    loc = _extract_geographic_entity(query)
    assert loc is not None
    assert "valencia" in loc.lower()

    req_plan = infer_data_requirement_plan(query, loc)
    assert req_plan.primary_domain in ["multimodal", "hydrology"]
    assert "optical" in req_plan.recommended_data_modalities
    assert "sar" in req_plan.recommended_data_modalities

    layer_plan = discover_active_layers_plan(req_plan)
    datasets = [l.dataset_id for l in layer_plan["active_layers"]]
    assert "sentinel-2-l2a" in datasets
    assert "sentinel-1-grd" in datasets


def test_scenario_3_bitemporal_earthquake_turkey():
    """
    Scenario 3: Bi-temporal change detection
    'compare pre and post earthquake imagery for Turkey'
    """
    query = "compare pre and post earthquake imagery for Turkey"
    loc = _extract_geographic_entity(query)
    assert loc is not None
    assert "turkey" in loc.lower()

    req_plan = infer_data_requirement_plan(query, loc)
    assert req_plan.primary_domain == "change_detection"
    assert req_plan.user_intent == "bitemporal_change"

    layer_plan = discover_active_layers_plan(req_plan)
    assert any("diff" in l.layer_id or "change" in l.layer_id for l in layer_plan["active_layers"])


def test_scenario_4_single_image_vqa():
    """
    Scenario 4: Single-image understanding and VQA
    'describe what you see in this satellite image'
    """
    query = "describe what you see in this satellite image"
    req_plan = infer_data_requirement_plan(query)
    assert req_plan.user_intent in ["single_image_vqa", "grounding"]
    assert req_plan.primary_domain == "image_understanding"
    assert "feature" in str(req_plan.analysis_requirements).lower() or "scene" in str(req_plan.analysis_requirements).lower()


def test_scenario_5_water_body_grounding():
    """
    Scenario 5: Water body grounding and spatial delineation
    'highlight the water body in this scene'
    """
    query = "highlight the water body in this scene"
    req_plan = infer_data_requirement_plan(query)
    assert req_plan.user_intent == "grounding"

    norm_dict = {
        "analysis_type": "grounding",
        "key_finding": "Water body delineated via NDWI.",
        "aoi": {"name": "Study Area"},
        "provenance": {"model_name": "NDWI Extractor", "dataset_ids": ["sentinel-2"]},
        "metrics": [{"label": "Delineated Area", "value": "28.4 km²"}],
    }
    layers = build_data_layers(norm_dict, query=query)
    assert any("water" in l.layer_id for l in layers)


def test_scenario_6_elevation_dem_shimla():
    """
    Scenario 6: Topographic elevation and 3D surface
    'show 3d elevation terrain for Shimla'
    """
    query = "show 3d elevation terrain for Shimla"
    loc = _extract_geographic_entity(query)
    assert loc is not None
    assert "shimla" in loc.lower()

    req_plan = infer_data_requirement_plan(query, loc)
    assert req_plan.primary_domain == "elevation"
    assert "dem" in req_plan.recommended_data_modalities

    norm_dict = {
        "analysis_type": "elevation",
        "aoi": {"name": "Shimla", "bbox": [77.10, 31.05, 77.25, 31.15]},
        "provenance": {"model_name": "Copernicus Elevation Mesh", "dataset_ids": ["copernicus-dem-30m"], "source": "mock"},
    }
    layers = build_data_layers(norm_dict, query=query)
    assert any("surface" in l.layer_id for l in layers)


def test_scenario_7_air_pollution_delhi():
    """
    Scenario 7: Atmospheric pollution and NO2 sounding
    'measure air pollution and no2 in Delhi'
    """
    query = "measure air pollution and no2 in Delhi"
    loc = _extract_geographic_entity(query)
    assert loc is not None
    assert "delhi" in loc.lower()

    req_plan = infer_data_requirement_plan(query, loc)
    assert req_plan.primary_domain == "atmospheric"
    assert req_plan.phenomenon == "atmospheric_pollution"

    norm_dict = {
        "analysis_type": "air_pollution",
        "aoi": {"name": "Delhi", "bbox": [77.0, 28.5, 77.3, 28.8]},
        "provenance": {"model_name": "TROPOMI Retrieval", "dataset_ids": ["sentinel-5p-l2"], "source": "mock"},
    }
    layers = build_data_layers(norm_dict, query=query)
    assert any("no2" in l.layer_id for l in layers)


def test_scenario_8_conversational_zoom_followup():
    """
    Scenario 8: Conversational spatial follow-up
    'zoom into the northern sector'
    """
    query = "zoom into the northern sector"
    active_aoi = {
        "name": "Kashmir",
        "bbox": [73.8, 33.2, 75.8, 34.9],
        "center": {"latitude": 34.08, "longitude": 74.80},
    }
    # _classify_intent_deterministic should detect contextual spatial request
    intent = _classify_intent_deterministic(
        query=query,
        recent_messages=[{"role": "user", "content": "analyze kashmir"}],
        previous_result={"analysis_type": "vegetation", "aoi": active_aoi},
        active_asset=None,
    )
    assert intent in ["CONTEXTUAL_SPATIAL_REQUEST", "VISUALIZATION_REQUEST", "conversational_explanation"]


def test_scenario_9_conversational_general_question():
    """
    Scenario 9: General EO knowledge question
    'why do you use radar for floods?'
    """
    query = "why do you use radar for floods?"
    intent = _classify_intent_deterministic(
        query=query,
        recent_messages=[],
        previous_result=None,
        active_asset=None,
    )
    assert intent in ["GENERAL_KNOWLEDGE", "conversational_explanation"]


def test_scenario_10_ambiguous_query_natural_clarification():
    """
    Scenario 10: Ambiguous analysis without location
    'analyze vegetation'
    SatQuery must respond with a natural clarification, NOT a robotic error.
    """
    state = {
        "user_query": "analyze vegetation",
        "intent_type": "clarification",
        "aoi_action": "clarify",
        "recent_messages": [],
    }
    resp = generate_final_response(state)
    final_text = resp["final_answer"]
    assert "Please specify a geographic location or administrative boundary" not in final_text
    assert "?" in final_text
    assert "which geographic location" in final_text.lower() or "which" in final_text.lower()
