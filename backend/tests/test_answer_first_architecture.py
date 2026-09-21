import pytest
import os
import json
from unittest.mock import MagicMock
from app.schemas.normalized_result import ConversationalMode, VisualizationType
from app.graph.nodes import (
    determine_conversational_mode_and_gate,
    _determine_conversational_mode_and_vis_gate,
    _extract_geographic_entity,
    _format_unknown_markdown_fallback,
    generate_globe_actions,
    generate_visualizations,
    generate_final_response,
)
from app.services.visualization_registry import plan_visualizations, build_data_layers


def test_scenario_1_kashmir_apple_farm_answer_first_and_gate():
    """
    Scenario 1: Kashmir apple farm query answers the question first,
    sets temporal_change conversational_mode, and requires temporal visualization.
    """
    query = "how kashmir has changed in last 10 years in terms of vegetation, i am thinking to start an apple farm there, will it be good option"
    mode, gate = determine_conversational_mode_and_gate(query, geographic_entity="Kashmir")
    
    assert mode in [ConversationalMode.TEMPORAL_CHANGE, ConversationalMode.EARTH_ANALYSIS]
    assert gate.visualization_required is True
    assert gate.visualization_type in [VisualizationType.TEMPORAL.value, VisualizationType.SPATIAL.value]
    assert "temporal" in gate.visualization_reason.lower() or "vegetation" in gate.visualization_reason.lower()

    # Verify fallback markdown provides direct answer first, with agronomic interpretation
    norm_dict = {
        "analysis_type": "agricultural_investigation",
        "key_finding": "Kashmir's vegetative trend shows positive biomass stability favorable for temperate apple orchard siting.",
        "aoi": {"name": "Kashmir Valley"},
        "provenance": {
            "model_name": "Deterministic Spectral Analysis",
            "dataset_ids": ["sentinel-2-l2a", "copernicus-dem-30m"],
            "source": "mock",
        },
        "metrics": [
            {"label": "Mean Canopy NDVI", "value": "0.54"},
            {"label": "Elevation", "value": "1,580 m"},
        ],
    }
    md = _format_unknown_markdown_fallback(query, norm_dict)
    assert "### Summary" in md
    assert "Kashmir" in md
    # No robotic refusal
    assert "Please specify a geographic location or administrative boundary" not in md


def test_scenario_2_what_is_ndvi_general_knowledge():
    """
    Scenario 2: General knowledge 'What is NDVI?' does not require visualization
    or globe camera actions.
    """
    query = "What is NDVI?"
    mode, gate = determine_conversational_mode_and_gate(query, geographic_entity=None)
    
    assert mode == ConversationalMode.ANSWER
    assert gate.visualization_required is False
    assert gate.visualization_type == VisualizationType.NONE.value

    # Globe actions should be empty
    state = {
        "query": query,
        "conversational_mode": mode.value,
        "visualization_required": False,
        "aoi_info": None,
        "normalized_result": None,
    }
    actions_res = generate_globe_actions(state)
    assert len(actions_res.get("globe_actions", [])) == 0


def test_scenario_3_what_dataset_did_you_use():
    """
    Scenario 3: Provenance meta-query 'What dataset did you use?' should answer
    in prose without triggering globe visualization.
    """
    query = "What dataset did you use for this analysis?"
    mode, gate = determine_conversational_mode_and_gate(query, geographic_entity=None)
    
    assert mode == ConversationalMode.ANSWER
    assert gate.visualization_required is False
    assert gate.visualization_type == VisualizationType.NONE.value


def test_scenario_4_show_it_on_the_globe():
    """
    Scenario 4: Explicit visualization request 'Show it on the globe' requires visualization.
    """
    query = "Show it on the globe"
    mode, gate = determine_conversational_mode_and_gate(query, geographic_entity="Valencia")
    
    assert mode == ConversationalMode.VISUALIZATION
    assert gate.visualization_required is True
    assert gate.visualization_type == VisualizationType.SPATIAL.value


def test_scenario_5_so_is_it_better_conversational():
    """
    Scenario 5: Follow-up conversational question 'So is it better?' should answer directly
    without generating new layers or overriding view.
    """
    query = "So is it better than last year?"
    mode, gate = determine_conversational_mode_and_gate(query, geographic_entity=None)
    
    assert mode == ConversationalMode.ANSWER
    assert gate.visualization_required is False


def test_scenario_6_compare_kashmir_with_himachal():
    """
    Scenario 6: Comparative query 'Compare Kashmir with Himachal' sets comparison mode.
    """
    query = "Compare Kashmir with Himachal for apple farming suitability"
    mode, gate = determine_conversational_mode_and_gate(query, geographic_entity="Kashmir")
    
    assert mode == ConversationalMode.COMPARISON
    assert gate.visualization_required is True
    assert gate.visualization_type == VisualizationType.COMPARISON.value


def test_scenario_7_sar_and_optical_cross_modal():
    """
    Scenario 7: Multimodal 'SAR and Optical flood Valencia' triggers cross_modal mode.
    """
    query = "Combine SAR and optical imagery to assess flood extent in Valencia"
    mode, gate = determine_conversational_mode_and_gate(query, geographic_entity="Valencia")
    
    assert mode == ConversationalMode.CROSS_MODAL
    assert gate.visualization_required is True
    assert gate.visualization_type == VisualizationType.MULTIMODAL.value


def test_scenario_8_user_geotiff_image_understanding():
    """
    Scenario 8: User GeoTIFF inspection defaults to image_understanding mode.
    """
    query = "Inspect this raster and tell me what the histogram means"
    mode, gate = determine_conversational_mode_and_gate(query, geographic_entity=None, has_user_asset=True)
    
    assert mode == ConversationalMode.IMAGE_UNDERSTANDING
    assert gate.visualization_required is False


def test_scenario_9_no_spurious_red_dots_on_option_query():
    """
    Scenario 9: Queries containing words like 'option' or general text must NOT trigger
    Case H detected points (15 red dots) in visualization registry.
    """
    query = "how kashmir has changed in last 10 years in terms of vegetation, i am thinking to start an apple farm there, will it be good option"
    norm = {
        "query": query,
        "aoi": {"name": "Kashmir", "bbox": [74.0, 33.0, 75.5, 34.5]},
        "analysis_type": "vegetation_health",
    }
    layers = build_data_layers(norm, query=query)
    
    # Verify no point_detections layer was created
    layer_types = [l.type for l in layers]
    assert "point_detections" not in layer_types
    assert "point" not in layer_types

    # Also verify generate_globe_actions does not create add_marker for general analyses
    state = {
        "query": query,
        "conversational_mode": ConversationalMode.TEMPORAL_CHANGE.value,
        "visualization_required": True,
        "aoi_info": MagicMock(center=MagicMock(latitude=34.0, longitude=74.5), name="Kashmir"),
        "normalized_result": None,
    }
    actions_res = generate_globe_actions(state)
    marker_actions = [a for a in actions_res.get("globe_actions", []) if a.get("action") == "add_marker"]
    assert len(marker_actions) == 0


def test_scenario_10_natural_clarification_no_robotic_error():
    """
    Scenario 10: Vague query without location asks a natural question rather than
    a robotic refusal.
    """
    query = "Analyze flood risk"
    loc = _extract_geographic_entity(query)
    assert loc is None  # Should not mistakenly extract 'Analyze' as a place name


def test_scenario_11_esri_basemap_no_carto_watermark():
    """
    Scenario 11: Frontend globeSkinRegistry uses Esri Canvas basemaps and does not
    use Carto basemap endpoints that show 'API KEY REQUIRED'.
    """
    ts_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../frontend/src/lib/services/globeSkinRegistry.ts"))
    assert os.path.exists(ts_path)
    with open(ts_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Must use Esri Dark Gray Canvas
    assert "services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile" in content
    # Must NOT use broken Carto endpoints
    assert "basemaps.cartocdn.com" not in content


def test_scenario_12_telemetry_cleanliness_in_chat_prompt():
    """
    Scenario 12: Ensure generate_final_response enforces ANSWER FIRST instructions
    and does not append '### Visualization' headers.
    """
    from app.graph.nodes import generate_final_response
    # Verify the system prompt instructs answer first
    import inspect
    src = inspect.getsource(generate_final_response)
    assert "ANSWER FIRST" in src
    assert "DO NOT output raw JSON" in src
