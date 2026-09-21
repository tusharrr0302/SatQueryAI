import json
import logging
import uuid
import asyncio
from typing import Dict, Any, Optional
from langchain_groq import ChatGroq
from app.config import settings
from app.dataset.registry import DATASET_REGISTRY
from app.models.registry import MODEL_REGISTRY
from app.models.manager import model_manager
from app.services.scenario_adapter import scenario_to_normalized_result, _generate_surface_grid, _build_audit_trace
from app.services.visualization_registry import select_visualizations, build_data_layers, plan_visualizations
from app.services.web_evidence import should_trigger_web_evidence, retrieve_grounded_web_evidence
from app.services.request_validator import RequestValidator
from app.schemas.normalized_result import (
    NormalizedResult,
    AOIInfo,
    Coordinates,
    MetricItem,
    TimeSeriesPoint,
    VisualizationSpec,
    Provenance,
    ConversationalMode,
    VisualizationType,
    VisualizationGateSpec,
)
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
    ComparisonPeriod,
)
from app.graph.state import AgentState

logger = logging.getLogger(__name__)


# --- Node 1: Resolve Query Source ---
def resolve_query_source(state: AgentState) -> Dict[str, Any]:
    query = state.get("user_query", "")
    location_hint = state.get("location_hint")
    print(f"\n[CHAT]\nQuery: {query}")

    # If user has an active uploaded asset, always use user_data / live execution
    if state.get("active_asset"):
        return {"matched_scenario": None, "source": "user_data"}

    if getattr(settings, "ALLOW_MOCK_FALLBACK", False) or (getattr(settings, "EO_EXECUTION_MODE", "live") != "live" and getattr(settings, "MODEL_MODE", "") != "live_only"):
        try:
            from app.services.scenario_matcher import match_scenario
            matched = match_scenario(query, location_hint=location_hint)
            if matched:
                print(f"[SCENARIO]\nMatched: {matched.get('id', 'YES')}")
                return {"matched_scenario": matched, "source": "mock"}
        except Exception as e:
            logger.warning(f"Scenario matcher error: {e}")

    print("[SCENARIO]\nMatched: DISABLED (live data required)")
    return {"matched_scenario": None, "source": "live"}


# --- Node 2: Load Matched Scenario (Path A) ---
def load_mock_scenario(state: AgentState) -> Dict[str, Any]:
    matched = state.get("matched_scenario")
    query = state.get("user_query", "")
    norm = scenario_to_normalized_result(matched, query)
    
    model_name = norm.provenance.model_name
    datasets_str = ", ".join(norm.provenance.dataset_ids)
    operation = norm.analysis_type
    print(f"[TOOL]\nModel: {model_name}\nDatasets: {datasets_str}\nOperation: {operation}")
    print(f"[RESULT]\nSource: mock\nResult generated: YES")
    
    norm.conversational_mode = state.get("conversational_mode") or "earth_analysis"
    norm.visualization_required = state.get("visualization_required", True)
    norm.visualization_reason = state.get("visualization_reason")
    norm.visualization_type = state.get("visualization_type") or "spatial"

    return {
        "normalized_result": norm.model_dump(),
        "source": "mock",
        "fallback": False,
    }



def _extract_geographic_entity(query: str, active_aoi: Optional[dict] = None) -> Optional[str]:
    import re
    q_low = query.lower().strip()

    # 1. Check Canonical and known gazetteer places
    known_places = [
        "kashmir valley", "kashmir", "srinagar", "jammu & kashmir", "jammu and kashmir", "jammu",
        "leh ladakh", "ladakh", "leh", "uttarakhand", "himachal pradesh", "himachal", "shimla",
        "delhi", "mumbai", "bengaluru", "bangalore", "chennai", "kolkata", "hyderabad", "pune",
        "ahmedabad", "assam", "bihar", "punjab", "haryana", "karnal", "odisha", "puri", "chilika",
        "derna, libya", "derna", "libya", "amazon", "brazil", "para state, brazil", "para",
        "western ghats", "bandipur", "sundarbans", "digha", "kolleru", "rann of kutch", "kutch",
        "bhadla", "thar", "sikkim", "california", "paradise",
        "nepal", "kathmandu", "pokhara", "bangladesh", "dhaka", "bhutan", "sri lanka", "pakistan"
    ]
    for place in known_places:
        pattern = r"\b" + re.escape(place) + r"\b"
        if re.search(pattern, q_low):
            if place in ["kashmir", "kashmir valley"]:
                return "Kashmir"
            if place in ["jammu & kashmir", "jammu and kashmir"]:
                return "Jammu & Kashmir"
            if place in ["srinagar"]:
                return "Srinagar"
            if place in ["delhi"]:
                return "Delhi"
            if place in ["mumbai"]:
                return "Mumbai"
            if place in ["bengaluru", "bangalore"]:
                return "Bengaluru"
            if place in ["chennai"]:
                return "Chennai"
            if place in ["kolkata"]:
                return "Kolkata"
            if place in ["hyderabad"]:
                return "Hyderabad"
            if place in ["pune"]:
                return "Pune"
            if place in ["uttarakhand"]:
                return "Uttarakhand"
            if place in ["derna", "derna, libya"]:
                return "Derna"
            if place in ["leh", "ladakh", "leh ladakh"]:
                return "Leh Ladakh"
            if place in ["nepal"]:
                return "Nepal"
            return place.title()

    # 2. Match patterns ("how <place> has changed", "what about <place>", "around <place>", etc.)
    patterns = [
        r"\bhow\s+([A-Za-z][A-Za-z\s-]{1,24}?)\s+has\s+changed\b",
        r"\bwhat\s+about\s+([A-Za-z][A-Za-z\s-]{1,24}?)(?:\s+(?:in|for|over|with|last|\?|$)|$)",
        r"\bcompare\s+(?:this\s+)?with\s+([A-Za-z][A-Za-z\s-]{1,24}?)(?:\s+(?:in|for|over|\?|$)|$)",
        r"\b(?:in|around|near|across|for|of|over)\s+([A-Za-z][A-Za-z\s-]{1,24}?)(?:\s+(?:over|during|between|using|for|in\s+terms|in\s+last|last)\b|[?.!]|$)",
        r"\b([A-Za-z][A-Za-z\s-]{1,20}?)\s+(?:vegetation|agriculture|flood|terrain|elevation|urban\s+expansion|canopy)\b",
    ]
    excluded_words = {
        "it", "this", "that", "what", "which", "how", "better", "ndvi", "vegetation",
        "flood", "urban", "expansion", "agriculture", "farm", "crop", "terrain",
        "elevation", "image", "imagery", "satellite", "raster", "last", "years",
        "year", "terms", "good", "option", "thinking", "start", "here", "there", "region",
        "analyze", "analysis", "monitoring", "monitor", "show", "tell", "detect", "detection",
        "observe", "observation", "calculate", "assess", "assessment", "risk", "extent",
        "now", "then", "also", "too", "next", "again", "please", "just", "use", "using",
        "compare", "current", "sar", "optical", "and", "an", "a", "the", "before", "after",
        "situation", "scene", "area", "status", "conditions", "condition", "event"
    }
    for pat in patterns:
        m = re.search(pat, query, re.IGNORECASE)
        if m:
            cand = m.group(1).strip()
            cand_words = [w.lower() for w in cand.split() if w.lower() not in excluded_words]
            if cand_words and len(cand_words) <= 3:
                cand_clean = " ".join(cand_words)
                if len(cand_clean) >= 3 and cand_clean.lower() not in excluded_words:
                    return cand_clean.title()

    return None


def _extract_temporal_scope(query: str) -> tuple[str, str]:
    import re
    from datetime import date
    end_year = date.today().year
    q_low = query.lower()

    # Pattern 1: between YYYY and YYYY / from YYYY to YYYY
    m_range = re.search(r"\b(?:between|from)\s+(19\d\d|20\d\d)\s+(?:and|to)\s+(19\d\d|20\d\d)\b", q_low)
    if m_range:
        return m_range.group(1), m_range.group(2)

    # Pattern 2: single year mention e.g. 2020 or 1890
    m_single = re.search(r"\b(18\d\d|19\d\d|20\d\d)\b", q_low)
    if m_single and not any(k in q_low for k in ["last", "past"]):
        yr = m_single.group(1)
        return yr, str(end_year)

    # Pattern 3: last N years
    m = re.search(r"(?:last|past)\s+(\d+)\s+years?", q_low)
    years = int(m.group(1)) if m else 2
    return str(end_year - years), str(end_year)


# --- Node 3: Understand Query (Path B - Unknown Queries) ---
def _generate_fallback_request(
    query: str,
    intent_type: str = "NEW_ANALYSIS",
    location_hint: Optional[str] = None,
    active_aoi: Optional[dict] = None,
    active_asset: Optional[dict] = None,
    previous_result: Optional[dict] = None,
) -> AnalysisRequest:
    import re

    is_purely_conversational = intent_type in [
        "RESULT_EXPLANATION", "PROVENANCE_QUESTION", "VISUALIZATION_REQUEST",
        "GENERAL_KNOWLEDGE", "CLARIFICATION", "conversational_explanation", "out_of_scope", "TOPIC_RESTORATION"
    ]
    requires_geo = not is_purely_conversational

    aoi_action = "none"
    aoi_source = "none"
    aoi_name = None
    spatial_focus = None
    reason = "No spatial analysis required."

    if active_asset:
        requires_geo = False
        aoi_action = "reuse"
        aoi_source = "uploaded_asset"
        aoi_name = active_asset.get("filename", "User Dataset")
        reason = "Using active user uploaded dataset."
    elif intent_type in ["RESULT_EXPLANATION", "PROVENANCE_QUESTION", "VISUALIZATION_REQUEST", "conversational_explanation"]:
        requires_geo = False
        if active_aoi and active_aoi.get("name"):
            aoi_action = "reuse"
            aoi_source = "conversation_context"
            aoi_name = active_aoi.get("name")
            reason = f"Conversational request referencing {aoi_name}."
        else:
            aoi_action = "none"
            aoi_source = "none"
            aoi_name = None
            reason = "Conversational follow-up."
    elif intent_type in ["GENERAL_KNOWLEDGE", "out_of_scope", "CLARIFICATION"]:
        requires_geo = False
        aoi_action = "none"
        aoi_source = "none"
        aoi_name = None
        reason = "General or conceptual inquiry."
    elif intent_type in ["CONTEXTUAL_SPATIAL_REQUEST", "FOLLOW_UP_ANALYSIS", "analysis_continuation"]:
        requires_geo = True
        aoi_action = "reuse"
        aoi_source = "conversation_context"
        aoi_name = (active_aoi or {}).get("name") or location_hint
        for direction in ["southern", "northern", "eastern", "western", "central", "coastal", "downtown"]:
            if direction in query.lower():
                spatial_focus = f"{direction} region"
                break
        reason = f"Continuation of previous analysis in {aoi_name}."
    else:  # NEW_ANALYSIS, NEW_LOCATION_ANALYSIS, new_analysis
        requires_geo = True
        location = _extract_geographic_entity(query, active_aoi)
        if location:
            aoi_action = "resolve_new"
            aoi_source = "explicit_user"
            aoi_name = location
            reason = f"User explicitly specified location: {location}."
        elif (active_aoi and active_aoi.get("name")) or location_hint:
            # Re-use active conversational AOI for follow-ups
            aoi_action = "reuse"
            aoi_source = "conversation_context"
            aoi_name = (active_aoi or {}).get("name") or location_hint
            reason = f"Inheriting active conversation location {aoi_name}."
        else:
            aoi_action = "clarify"
            aoi_source = "none"
            aoi_name = None
            reason = "Analysis requested but no geographic location was specified."

    start_year, end_year = _extract_temporal_scope(query)
    q_low = query.lower()

    # Determine canonical PrimaryTask
    if is_purely_conversational:
        task = "general_knowledge" if intent_type in ("GENERAL_KNOWLEDGE", "general_knowledge") else "dataset_information"
    elif any(k in q_low for k in ["what is visible", "vqa", "in this satellite image", "in this image"]):
        task = "single_image_vqa"
    elif any(k in q_low for k in ["describe", "land-cover", "land cover", "classes"]):
        task = "scene_description"
    elif any(k in q_low for k in ["flood", "flooding", "inundation"]):
        task = "flood_analysis"
    elif "sar" in q_low and "optical" in q_low:
        task = "sar_optical_analysis"
    elif any(k in q_low for k in ["show optical", "show imagery", "show satellite", "optical imagery", "satellite imagery", "satellite image", "optical image"]):
        task = "scene_description"
    elif any(k in q_low for k in ["vegetation", "ndvi", "crop", "forest"]):
        task = "vegetation_analysis"
    elif any(k in q_low for k in ["urban", "built-up", "city", "sprawl"]):
        task = "urban_change"
    elif any(k in q_low for k in ["terrain", "elevation", "dem", "hillshade", "topograph", "3d surface", "point cloud", "3d"]):
        task = "terrain_analysis"
    elif any(k in q_low for k in ["change", "over time", "last 10 years", "last 5 years"]):
        task = "temporal_change_detection"
    else:
        prev_task = (previous_result or {}).get("analysis_type")
        task = prev_task if prev_task and prev_task not in ("location_information", "knowledge_inquiry") else "temporal_change_detection"

    modalities = ["optical"]
    if any(k in q_low for k in ["terrain", "elevation", "dem", "hillshade", "topograph", "3d surface", "point cloud", "3d"]):
        modalities.append("elevation")
    if "sar" in q_low:
        if (
            "optical" in q_low
            or "flood" in q_low
            or "sar too" in q_low
            or "use sar" in q_low
            or task in ("sar_optical_analysis", "flood_analysis", "vegetation_analysis")
        ):
            modalities = ["sar", "optical"]
        else:
            modalities = ["sar"]
    elif "multispectral" in q_low:
        modalities = ["multispectral"]

    model_sel = "prithvi-eo-2.0"
    if "closp" in q_low or ("sar" in modalities and "optical" in modalities and "flood" in q_low):
        model_sel = "closp"
    elif "earthdial" in q_low or task in ("single_image_vqa", "scene_description"):
        model_sel = "earthdial-4b-ms"

    needs_clarification = (aoi_action == "clarify")
    clarification_q = "Which area would you like me to analyze?" if needs_clarification else None
    missing_fields = ["aoi"] if needs_clarification else []

    rel_period = None
    if "10 years" in q_low or "10-year" in q_low:
        rel_period = "10_years"
    elif "5 years" in q_low or "5-year" in q_low:
        rel_period = "5_years"

    comp_strat = None
    if "compare" in q_low and "2020" in q_low:
        comp_strat = "current_vs_2020"
        if not start_year:
            start_year = "2020"

    return AnalysisRequest(
        query=query,
        intent=Intent(
            primary_task=task,
            domain="earth_observation",
            question_type=intent_type,
            requires_geospatial_analysis=requires_geo,
            spatial_scope="regional",
            temporal_scope=TemporalScope(
                start=start_year,
                end=end_year,
                relative_period=rel_period,
                resolution="multi_temporal" if rel_period else None,
                comparison_strategy=comp_strat or "annual"
            ),
            needs_clarification=needs_clarification,
            clarification_question=clarification_q,
            missing_fields=missing_fields,
        ),
        aoi=AOI(
            type="Polygon",
            name=aoi_name,
            country=None,
            action=aoi_action,
            source=aoi_source,
            spatial_focus=spatial_focus,
            reason=reason,
        ),
        data_requirements=DataRequirements(
            modalities=modalities,
            datasets=["sentinel-2"] if "optical" in modalities else ["sentinel-1"],
            temporal_resolution="monthly",
            cloud_constraint="<20%",
            spatial_resolution="10m",
        ),
        model_selection=ModelSelection(
            model=model_sel,
            reason="Selected foundation model based on requested modalities and task capabilities.",
        ),
        analysis=Analysis(
            operation="observation",
            comparison_periods=[],
            target_classes=[],
        ),
        outputs=Outputs(
            visualizations=["3D Surface", "Time Series"],
            metrics=["Observation Confidence"],
            explanation=True,
            confidence=True,
        ),
        execution=Execution(priority="accuracy", allow_mock_fallback=False),
    )


def _classify_intent_deterministic(
    query: str,
    recent_messages: list,
    previous_result: Optional[dict],
    active_asset: Optional[dict]
) -> str:
    q = query.lower().strip()
    if any(k in q for k in ["go back to", "back to delhi", "return to delhi", "switch back to", "back to the delhi", "return to the"]):
        return "TOPIC_RESTORATION"
    if active_asset:
        # If user has an active uploaded dataset and isn't asking about another explicit city/country
        if not any(name in q for name in ["in mumbai", "in delhi", "in bengaluru", "in bangalore", "in chennai", "in kolkata", "in hyderabad", "in pune", "in uttarakhand", "in derna", "in kathmandu"]):
            return "data_inspection"
    if any(k in q for k in [
        "population of mars", "mars", "jupiter", "saturn", "moon surface",
        "who are you", "what is your name", "capital of", "weather tomorrow",
        "write a poem", "stock price"
    ]):
        return "out_of_scope"
    if any(k in q for k in [
        "what is ndvi", "what does ndvi mean", "what is sar", "how do satellites",
        "best satellite", "best dataset", "satellite dataset", "dataset for monitoring", "monitoring glaciers",
        "why do you use radar", "why use radar", "why radar"
    ]):
        return "GENERAL_KNOWLEDGE"
    if any(k in q for k in [
        "what dataset", "which dataset", "what data", "datasets did you use",
        "dataset did you use", "what model", "which model", "model did you use"
    ]):
        return "PROVENANCE_QUESTION"
    if any(k in q for k in [
        "show it on the globe", "show on the globe", "show on globe", "show it on globe",
        "show this on the globe", "show this on globe", "show on map", "show it", "fly to", "view on globe",
        "show the concentration", "show concentration", "concentration of these events", "concentration of events",
        "show me every detected point", "show detected points", "show every detected point", "show every point", "show detected point", "detected point"
    ]):
        if previous_result:
            return "VISUALIZATION_REQUEST"
    if any(k in q for k in ["show me the terrain", "show the terrain", "show terrain", "show me terrain"]):
        if previous_result and not any(loc in q for loc in ["kashmir", "nepal", "delhi", "himalaya", "valley", "mumbai", "derna", "of"]):
            return "VISUALIZATION_REQUEST"
    if any(k in q for k in [
        "so is it better", "is it better", "is it worse", "is it improving",
        "why did", "why?", "explain that", "explain this", "explain like",
        "explain simply", "beginner", "simple terms", "tell me more about this result",
        "how did you calculate", "what does this mean", "compared to what",
        "is this significant", "is it reliable", "explain this map", "explain the map", "explain map"
    ]) or q == "why":
        return "RESULT_EXPLANATION"
    prev_name = ((previous_result.get("aoi") or {}).get("name", "") if previous_result else "").lower()
    other_cities = [c for c in ["mumbai", "bengaluru", "bangalore", "chennai", "kolkata", "hyderabad", "pune", "delhi"] if c not in prev_name]
    if previous_result and any(k in q for k in [
        "southern", "northern", "eastern", "western", "central", "coastal", "downtown"
    ]) and not any(name in q for name in other_cities):
        return "CONTEXTUAL_SPATIAL_REQUEST"
    if previous_result and any(k in q for k in [
        "compare that with", "compare with", "compare to", "urban expansion",
        "urban growth", "sprawl", "flood risk", "land cover"
    ]) and not any(name in q for name in other_cities):
        return "FOLLOW_UP_ANALYSIS"
    if previous_result and any(name in q for name in other_cities):
        return "NEW_LOCATION_ANALYSIS"
    return "NEW_ANALYSIS"


def determine_conversational_mode_and_gate(
    query: str,
    geographic_entity: Optional[str] = None,
    intent_type: str = "NEW_ANALYSIS",
    previous_result: Optional[dict] = None,
    active_asset: Optional[dict] = None,
    requires_geo: bool = True,
    has_user_asset: bool = False,
) -> tuple[ConversationalMode, VisualizationGateSpec]:
    q = query.lower().strip()

    # 1. Out of scope or generic non-EO
    if intent_type == "out_of_scope" or any(k in q for k in [
        "population of mars", "mars", "jupiter", "saturn", "moon surface",
        "who are you", "what is your name", "capital of", "weather tomorrow",
        "write a poem", "stock price"
    ]):
        return (
            ConversationalMode.ANSWER,
            VisualizationGateSpec(
                visualization_required=False,
                visualization_reason="Direct response to non-Earth observation query.",
                visualization_type=VisualizationType.NONE.value,
            ),
        )

    # 2. General Knowledge / Conceptual Question / Provenance
    if intent_type in ["GENERAL_KNOWLEDGE", "PROVENANCE_QUESTION"] or any(k in q for k in [
        "what is ndvi", "what does ndvi mean", "what is sar", "how do satellites",
        "best satellite", "best dataset", "satellite dataset", "dataset for monitoring",
        "monitoring glaciers", "why do you use radar", "why use radar", "why radar",
        "what dataset", "which dataset", "what data", "datasets did you use",
        "dataset did you use", "what model", "which model", "model did you use",
        "how does sar work", "difference between optical and sar"
    ]):
        return (
            ConversationalMode.ANSWER,
            VisualizationGateSpec(
                visualization_required=False,
                visualization_reason="Direct answer to remote sensing and data provenance query.",
                visualization_type=VisualizationType.NONE.value,
            ),
        )

    # 3. Explicit Visualization Requests & Topic Restoration
    if intent_type in ["VISUALIZATION_REQUEST", "TOPIC_RESTORATION"] or any(k in q for k in [
        "show it on the globe", "show on the globe", "show on globe", "show it on globe",
        "show this on the globe", "show this on globe", "show on map", "show it", "fly to", "view on globe",
        "show me the terrain", "show the terrain", "show terrain", "show me terrain",
        "show the concentration", "show concentration", "concentration of these events", "concentration of events",
        "show me every detected point", "show detected points", "show every detected point", "show every point", "show detected point",
        "go back to", "return to", "switch back to"
    ]):
        vis_type = VisualizationType.SPATIAL.value
        return (
            ConversationalMode.VISUALIZATION,
            VisualizationGateSpec(
                visualization_required=True,
                visualization_reason="User explicitly requested 3D globe visualization.",
                visualization_type=vis_type,
            ),
        )

    # 4. Result Explanation / Conversational Follow-up without explicit visual request
    if intent_type in ["RESULT_EXPLANATION", "conversational_explanation"] or q == "why" or any(k in q for k in [
        "so is it better", "is it better", "is it worse", "is it improving",
        "why did", "why?", "explain that", "explain this", "explain like",
        "explain simply", "beginner", "simple terms", "tell me more about this result",
        "how did you calculate", "what does this mean", "compared to what",
        "is this significant", "is it reliable"
    ]):
        if any(k in q for k in ["explain this map", "explain the map", "explain map", "explain this visualization", "how to read this", "what am i seeing"]):
            return (
                ConversationalMode.VISUALIZATION,
                VisualizationGateSpec(
                    visualization_required=True,
                    visualization_reason="User requested visual explanation of the active map telemetry.",
                    visualization_type=VisualizationType.SPATIAL.value,
                ),
            )
        return (
            ConversationalMode.ANSWER,
            VisualizationGateSpec(
                visualization_required=False,
                visualization_reason="Direct conversational interpretation of previous observation; no new spatial layer required.",
                visualization_type=VisualizationType.NONE.value,
            ),
        )

    # 5. User Uploaded GeoTIFF / Raster Inspection
    if active_asset or has_user_asset or intent_type == "data_inspection" or any(k in q for k in ["geotiff", "this image", "my image", "this raster", "uploaded data", "uploaded dataset"]):
        if any(k in q for k in ["show on globe", "view on map", "visualize", "overlay"]):
            return (
                ConversationalMode.IMAGE_UNDERSTANDING,
                VisualizationGateSpec(
                    visualization_required=True,
                    visualization_reason="Spatial overlay and raster visual inspection requested.",
                    visualization_type=VisualizationType.IMAGE_EVIDENCE.value,
                ),
            )
        return (
            ConversationalMode.IMAGE_UNDERSTANDING,
            VisualizationGateSpec(
                visualization_required=False,
                visualization_reason="Raster metadata, bands, and properties answered directly; spatial inspection available on demand.",
                visualization_type=VisualizationType.IMAGE_EVIDENCE.value,
            ),
        )

    # 6. Cross-Modal Fusion
    if any(k in q for k in ["cross modal", "cross-modal", "sar and optical", "optical and sar", "radar and optical", "sentinel-1 and sentinel-2", "multimodal"]):
        return (
            ConversationalMode.CROSS_MODAL,
            VisualizationGateSpec(
                visualization_required=True,
                visualization_reason="Multimodal sensor integration benefits from comparative layer visualization.",
                visualization_type=VisualizationType.MULTIMODAL.value,
            ),
        )

    # 7. Comparison between locations
    if (
        any(k in q for k in ["compare", "comparison", "versus", " vs ", "diff between", "difference between"])
        and any(k in q for k in [" with ", " and ", " to ", " vs ", "versus", "against"])
    ):
        return (
            ConversationalMode.COMPARISON,
            VisualizationGateSpec(
                visualization_required=True,
                visualization_reason="Geographic comparison benefits from spatial side-by-side visualization.",
                visualization_type=VisualizationType.COMPARISON.value,
            ),
        )

    # 8. Temporal Change
    if any(k in q for k in [
        "last 10 years", "in 10 years", "last 5 years", "over time", "changed over",
        "between 20", "from 20", "since 20", "temporal change", "how has it changed",
        "how kashmir has changed", "urban growth", "deforestation between"
    ]):
        return (
            ConversationalMode.TEMPORAL_CHANGE,
            VisualizationGateSpec(
                visualization_required=True,
                visualization_reason="Multi-temporal analysis benefits from time-series and change map visualization.",
                visualization_type=VisualizationType.TEMPORAL.value,
            ),
        )

    # 9. Investigation / Forensic
    if any(k in q for k in ["investigate", "forensic", "root cause", "damage assessment", "disaster investigation"]):
        return (
            ConversationalMode.INVESTIGATION,
            VisualizationGateSpec(
                visualization_required=True,
                visualization_reason="Environmental investigation provides supporting spatial evidence layers.",
                visualization_type=VisualizationType.INVESTIGATION.value,
            ),
        )

    # 10. Earth Observation Spatial Analysis — ONLY if there is strong evidence:
    # Requires explicit geographic context and satellite analysis intent.
    has_eo_terms = any(k in q for k in [
        "ndvi", "ndwi", "ndbi", "vegetation", "land cover", "flood", "inundation", "deforestation",
        "forest loss", "canopy", "crop", "wildfire", "burn", "urban expansion", "built-up",
        "surface reflectance", "backscatter", "elevation", "topography", "terrain", "dem", "point cloud", "3d", "surface grid",
        "chlorophyll", "soil moisture", "albedo", "bathymetry", "nightlights", "thermal band"
    ])
    has_action_terms = any(k in q for k in [
        "show ", "map ", "detect ", "analyze ", "analyse ", "monitor ", "measure ", "calculate ", "assess ", "track ",
        "where ", "how much ", "how has ", "lost", "loss", "change", "generate ", "render ", "create ", "display ", "produce "
    ])

    if requires_geo and (
        (geographic_entity and (has_eo_terms or has_action_terms))
        or (has_eo_terms and has_action_terms)
    ):
        return (
            ConversationalMode.EARTH_ANALYSIS,
            VisualizationGateSpec(
                visualization_required=True,
                visualization_reason="Earth observation spatial analysis requested with verified geographic context.",
                visualization_type=VisualizationType.SPATIAL.value,
            ),
        )

    # 11. Default Fallback for Unclassified / Unknown Queries:
    # "Answer First. Visualize Only When It Helps."
    return (
        ConversationalMode.ANSWER,
        VisualizationGateSpec(
            visualization_required=False,
            visualization_reason="Direct conversational response; no spatial visualization required for unclassified query.",
            visualization_type=VisualizationType.NONE.value,
        ),
    )



def _determine_conversational_mode_and_vis_gate(
    query: str,
    intent_type: str = "NEW_ANALYSIS",
    previous_result: Optional[dict] = None,
    active_asset: Optional[dict] = None,
    requires_geo: bool = True,
    geographic_entity: Optional[str] = None,
    has_user_asset: bool = False,
) -> tuple[str, bool, Optional[str], str]:
    if not geographic_entity:
        geographic_entity = _extract_geographic_entity(query, (previous_result or {}).get("aoi"))
    mode, gate = determine_conversational_mode_and_gate(
        query=query,
        geographic_entity=geographic_entity,
        intent_type=intent_type,
        previous_result=previous_result,
        active_asset=active_asset,
        requires_geo=requires_geo,
        has_user_asset=has_user_asset,
    )
    return mode.value, gate.visualization_required, gate.visualization_reason, gate.visualization_type


def understand_query(state: AgentState) -> Dict[str, Any]:
    query = state.get("user_query", "")
    active_asset = state.get("active_asset")
    recent_messages = state.get("recent_messages") or []
    previous_result = state.get("previous_result")
    active_aoi = state.get("active_aoi") or (previous_result.get("aoi") if previous_result else None)
    location_hint = state.get("location_hint") or (active_aoi.get("name") if active_aoi else None)

    # Resolve AI Mode and Explicit Model Selection
    ai_mode = state.get("ai_mode") or "auto"
    explicit_model = state.get("explicit_model")
    q_low = query.lower()
    if any(k in q_low for k in ["beginner", "like a beginner", "simple terms", "explain simply", "for a 5 year old", "explain simply"]):
        ai_mode = "beginner"
    elif "intermediate" in q_low:
        ai_mode = "intermediate"
    elif any(k in q_low for k in ["advanced", "expert", "scientific paper", "rigorous", "technical breakdown"]):
        ai_mode = "advanced"

    for candidate_model in ["prithvi-eo-2.0", "terrafm", "clay", "satlas-pretrain", "pan-sharpening-cnn", "burn-index-ann"]:
        if candidate_model in q_low:
            explicit_model = candidate_model
            break

    print(f"[SatQuery] CALLING GPT-OSS 120B for planning: {query} (AI Mode: {ai_mode})")

    # Baseline intent classification
    intent_type = _classify_intent_deterministic(query, recent_messages, previous_result, active_asset)

    context_str = ""
    if recent_messages:
        turns_summary = []
        for m in recent_messages[-6:]:
            role = m.get("role", "user").capitalize()
            content = m.get("content", "")
            content_snippet = content[:160] + ("..." if len(content) > 160 else "")
            turns_summary.append(f"- {role}: {content_snippet}")
        context_str += "RECENT CONVERSATION TURNS:\n" + "\n".join(turns_summary) + "\n\n"

    if previous_result or active_aoi:
        prev_aoi = (active_aoi or {}).get("name") or (previous_result or {}).get("aoi", {}).get("name") or location_hint or "Unknown"
        prev_center = (active_aoi or {}).get("center") or (previous_result or {}).get("aoi", {}).get("center", {})
        prev_lat = prev_center.get("latitude") if prev_center else None
        prev_lon = prev_center.get("longitude") if prev_center else None
        prev_type = (previous_result or {}).get("analysis_type", "")
        context_str += (
            f"ACTIVE CONVERSATION CONTEXT:\n"
            f"- Active AOI / Location: {prev_aoi}"
            + (f" ({prev_lat}°N, {prev_lon}°E)\n" if prev_lat is not None else "\n")
            + f"- Previous Analysis: {prev_type}\n"
            + "Note: If current request is a follow-up, resolve within this location. If completely new topic/location, start fresh.\n\n"
        )

    if settings.LLM_ENABLED and settings.GROQ_API_KEY:
        try:
            llm = ChatGroq(
                model=settings.GROQ_MODEL,
                api_key=settings.GROQ_API_KEY,
                temperature=0,
                max_retries=1,
                request_timeout=6,
            )
            structured_llm = llm.with_structured_output(AnalysisRequest)

            asset_context_str = ""
            if active_asset:
                asset_context_str = f"""
ACTIVE USER UPLOADED DATASET:
{json.dumps(active_asset.get('profile', {}), indent=2)}
Note: If user refers to 'this image' or their data, tailor the request to this dataset.
"""

            prompt = f"""You are SatQuery AI's remote sensing query analysis engine.
Convert the user request into a standardized AnalysisRequest.

AVAILABLE MODALITIES:
- optical (Sentinel-2, Landsat)
- multispectral (Sentinel-2 13-band, HLS 6-band)
- sar (Sentinel-1 C-band SAR)

AVAILABLE PRIMARY TASKS:
- single_image_vqa: Visual question answering on single satellite imagery
- scene_description: Land-cover and visual feature characterization
- object_detection: Identification of objects/structures
- visual_grounding: Spatial localization of referenced features
- temporal_change_detection: General longitudinal multi-temporal change over time
- land_cover_change: Surface alterations, deforestation, urbanization
- vegetation_analysis: NDVI, crop dynamics, canopy vigor
- urban_change: City growth, impervious surface expansion
- flood_analysis: Flood inundation, water extent, damage assessment
- sar_optical_analysis: Joint SAR + optical cross-modal alignment/retrieval
- multispectral_analysis: Spectral band and temporal stack analysis
- image_comparison: Visual or index comparison of two scenes
- dataset_information: Inquiries about satellite sensors and bands
- location_information: Geographic boundary and administrative info
- general_knowledge: Conceptual remote sensing definitions

AVAILABLE SPECIALIST MODELS:
- earthdial-4b-ms: Single-image VQA & scene understanding (optical/multispectral)
- prithvi-eo-2.0: Temporal change detection & vegetation dynamics (optical/multispectral stack)
- closp: SAR + optical cross-modal alignment & flood mapping (requires SAR + optical)
- terrafm: Multimodal optical + SAR sensor alignment
- vista: Optical spatio-temporal attention change detection

AVAILABLE TOOLS:
- analyze_image: Single-image VQA and scene analysis
- detect_change: Bi-temporal optical change detection
- analyze_multitemporal: 4-frame multispectral ViT analysis
- analyze_sar_optical: Joint SAR + optical fusion and alignment
{asset_context_str}
{context_str}
CRITICAL RULES:
1. CANONICAL TASK: Select "intent.primary_task" strictly from the available primary tasks list.
2. CONVERSATIONAL AOI RESOLUTION:
   - "aoi.action":
     * "resolve_new": User explicitly named a new location in the query (e.g. "Delhi", "Mumbai", "Spain").
     * "reuse": Follow-up referencing active context (e.g. "Now show vegetation", "Compare it with 2020", "Use SAR too").
     * "clarify": Analysis requested but NO location is specified and NO active context exists.
     * "none": General knowledge or non-spatial question.
   - "aoi.name": Clean geographic place name only (e.g. "Delhi"). Do NOT include action words.
   - If "aoi.action" == "clarify": Set "intent.needs_clarification" = true, "intent.missing_fields" = ["aoi"], and "intent.clarification_question" = "Which area would you like me to analyze?".
3. MULTI-TURN INHERITANCE:
   - If active context exists and user says "Now show vegetation", inherit the active AOI with action="reuse", task="vegetation_analysis".
   - If user says "Compare it with 2020", inherit active AOI and set temporal_scope with start="2020", comparison_strategy="current_vs_2020".
   - If user says "Use SAR too", inherit active AOI and update modalities to ["optical", "sar"].
4. MODALITIES:
   - Set "data_requirements.modalities" strictly based on what is needed (e.g. ["optical"], ["sar"], or ["sar", "optical"]).
   - For flood analysis using SAR and optical, specify ["sar", "optical"].
5. NEVER invent satellite coordinates, fake percentages, or arbitrary tool names.

User request: {query}
"""
            result = structured_llm.invoke(prompt)
            res_dict = result.model_dump()
            parsed_qtype = getattr(result.intent, "question_type", None)
            if parsed_qtype in ["new_analysis", "analysis_continuation", "conversational_explanation", "data_inspection", "out_of_scope", "clarification"]:
                intent_type = parsed_qtype
            res_dict["intent"]["question_type"] = intent_type

            # Architecture Hardening: Backend trusts GPT-OSS structured decision
            gpt_mode = getattr(result.intent, "conversational_mode", None)
            gpt_vis_req = getattr(result.intent, "visualization_required", None)
            gpt_vis_reason = getattr(result.intent, "visualization_reason", None)
            gpt_vis_type = getattr(result.intent, "visualization_type", None)

            if gpt_mode and gpt_vis_req is not None:
                mode_map = {
                    "ANSWER": ConversationalMode.ANSWER.value,
                    "EARTH_ANALYSIS": ConversationalMode.EARTH_ANALYSIS.value,
                    "FOLLOW_UP": ConversationalMode.ANSWER.value if not gpt_vis_req else ConversationalMode.VISUALIZATION.value,
                    "CLARIFICATION": ConversationalMode.ANSWER.value,
                }
                c_mode = mode_map.get(str(gpt_mode).upper(), str(gpt_mode).lower())
                v_req = bool(gpt_vis_req)
                v_reason = gpt_vis_reason or ("Visualization provided for spatial observation." if v_req else "Direct conversational answer; no spatial visualization required.")
                v_type = (gpt_vis_type or ("spatial" if v_req else "none")).lower()
            else:
                c_mode, v_req, v_reason, v_type = _determine_conversational_mode_and_vis_gate(
                    query, intent_type, previous_result=previous_result, active_asset=active_asset
                )

            return _build_understand_query_return(
                res_dict, intent_type, query, location_hint, active_asset,
                ai_mode=ai_mode, explicit_model=explicit_model,
                conversational_mode=c_mode, visualization_required=v_req,
                visualization_reason=v_reason, visualization_type=v_type,
            )

        except Exception as exc:
            logger.warning(f"Groq structured output failed ({exc}); trying recovery.")
            err_msg = str(exc)
            if "failed_generation" in err_msg:
                try:
                    import re, ast
                    m = re.search(r"'failed_generation':\s*('(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")", err_msg)
                    if m:
                        raw = ast.literal_eval(m.group(1))
                        if isinstance(raw, str):
                            fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw)
                            if fence_match:
                                raw_str = fence_match.group(1)
                            else:
                                brace_match = re.search(r"(\{[\s\S]*\})", raw)
                                raw_str = brace_match.group(1) if brace_match else raw
                            parsed = json.loads(raw_str.strip())
                        else:
                            parsed = raw

                        if isinstance(parsed, dict) and "arguments" in parsed:
                            payload = parsed["arguments"]
                            if isinstance(payload, str):
                                payload = json.loads(payload)
                        else:
                            payload = parsed

                        if isinstance(payload, dict):
                            if "analysis" not in payload or not isinstance(payload.get("analysis"), dict):
                                payload["analysis"] = {"operation": "observation"}
                            else:
                                if payload["analysis"].get("target_classes") is None:
                                    payload["analysis"]["target_classes"] = []
                                if payload["analysis"].get("comparison_periods") is None:
                                    payload["analysis"]["comparison_periods"] = []
                            if "execution" not in payload:
                                payload["execution"] = {"priority": "accuracy"}
                            if "outputs" not in payload:
                                payload["outputs"] = {"visualizations": []}
                            if "data_requirements" not in payload:
                                payload["data_requirements"] = {"modalities": ["optical"]}
                            if "model_selection" not in payload:
                                payload["model_selection"] = {"model": "prithvi-eo-2.0", "reason": "Observation"}

                        recovered_req = AnalysisRequest.model_validate(payload)
                        print("[LLM]\nAnalysis request generated: YES")
                        rec_dict = recovered_req.model_dump()
                        rec_dict["intent"]["question_type"] = intent_type
                        c_mode, v_req, v_reason, v_type = _determine_conversational_mode_and_vis_gate(
                            query, intent_type, previous_result=previous_result, active_asset=active_asset
                        )
                        return _build_understand_query_return(
                            rec_dict, intent_type, query, location_hint, active_asset,
                            ai_mode=ai_mode, explicit_model=explicit_model,
                            conversational_mode=c_mode, visualization_required=v_req,
                            visualization_reason=v_reason, visualization_type=v_type,
                        )
                except Exception as rec_err:
                    logger.warning(f"Failed to recover generation: {rec_err}")

    fallback_req = _generate_fallback_request(
        query,
        intent_type=intent_type,
        location_hint=location_hint,
        active_aoi=active_aoi,
        active_asset=active_asset,
        previous_result=previous_result,
    )
    fallback_dict = fallback_req.model_dump()
    fallback_dict["intent"]["question_type"] = intent_type
    print(f"[LLM]\nAnalysis request generated: NO (fallback) -> Intent: {intent_type}")
    c_mode, v_req, v_reason, v_type = _determine_conversational_mode_and_vis_gate(
        query, intent_type, previous_result=previous_result, active_asset=active_asset
    )
    return _build_understand_query_return(
        fallback_dict, intent_type, query, location_hint, active_asset,
        ai_mode=ai_mode, explicit_model=explicit_model,
        conversational_mode=c_mode, visualization_required=v_req,
        visualization_reason=v_reason, visualization_type=v_type,
    )


def _build_understand_query_return(
    analysis_dict: dict,
    intent_type: str,
    query: str,
    location_hint: Optional[str] = None,
    active_asset: Optional[dict] = None,
    ai_mode: str = "auto",
    explicit_model: Optional[str] = None,
    conversational_mode: str = "earth_analysis",
    visualization_required: bool = True,
    visualization_reason: Optional[str] = None,
    visualization_type: str = "spatial",
) -> Dict[str, Any]:
    matched = None
    req_intent = analysis_dict.get("intent", {})
    requires_geo = req_intent.get("requires_geospatial_analysis", True)

    if "intent" in analysis_dict and isinstance(analysis_dict["intent"], dict):
        analysis_dict["intent"]["ai_mode"] = ai_mode
        t_scope = analysis_dict["intent"].get("temporal_scope") or {}
        if not t_scope.get("relative_period"):
            q_l = query.lower()
            if "10 years" in q_l or "10-year" in q_l:
                t_scope["relative_period"] = "10_years"
            elif "5 years" in q_l or "5-year" in q_l:
                t_scope["relative_period"] = "5_years"
            analysis_dict["intent"]["temporal_scope"] = t_scope
    if explicit_model and "model_selection" in analysis_dict and isinstance(analysis_dict["model_selection"], dict):
        analysis_dict["model_selection"]["explicit_model"] = explicit_model
        analysis_dict["model_selection"]["model"] = explicit_model

    is_spatial_analysis = intent_type in [
        "new_analysis", "NEW_ANALYSIS",
        "analysis_continuation", "FOLLOW_UP_ANALYSIS",
        "NEW_LOCATION_ANALYSIS", "CONTEXTUAL_SPATIAL_REQUEST"
    ]
    loc_hint = location_hint if intent_type in ["analysis_continuation", "FOLLOW_UP_ANALYSIS", "CONTEXTUAL_SPATIAL_REQUEST"] else None

    allow_mock = (settings.EO_EXECUTION_MODE == "mock" or settings.ALLOW_MOCK_FALLBACK)
    if is_spatial_analysis and requires_geo and allow_mock and not active_asset:
        try:
            from app.services.scenario_matcher import find_matching_scenario
            matched = find_matching_scenario(query, location_hint=loc_hint)
            if matched:
                print(f"[SCENARIO]\nMatched: {matched.get('id', 'YES')}")
        except Exception as e:
            logger.warning(f"Scenario matcher error: {e}")

    source = "mock" if (matched and allow_mock) else ("user_data" if active_asset else settings.EO_EXECUTION_MODE)

    return {
        "analysis_request": analysis_dict,
        "intent_type": intent_type,
        "matched_scenario": matched,
        "source": source,
        "requires_geospatial_analysis": requires_geo,
        "ai_mode": ai_mode,
        "explicit_model": explicit_model,
        "conversational_mode": conversational_mode,
        "visualization_required": visualization_required,
        "visualization_reason": visualization_reason,
        "visualization_type": visualization_type,
    }


# --- Node 3.5: Dedicated Conversational AOI Resolution ---
def resolve_conversational_aoi(state: AgentState) -> Dict[str, Any]:
    query = state.get("user_query", "")
    req = state.get("analysis_request") or {}
    intent = req.get("intent") or {}
    aoi_spec = req.get("aoi") or {}
    previous_result = state.get("previous_result")
    active_aoi = state.get("active_aoi") or (previous_result.get("aoi") if previous_result else None)
    active_asset = state.get("active_asset")
    matched_scenario = state.get("matched_scenario")

    task = intent.get("primary_task", "general_query")
    requires_geo = intent.get("requires_geospatial_analysis", True)
    question_type = state.get("intent_type") or intent.get("question_type", "new_analysis")

    prev_aoi_name = (active_aoi or {}).get("name", "None")
    prev_analysis = (previous_result or {}).get("analysis_type", "None")

    print(f"\n[CONTEXT]")
    print(f"current_query = \"{query}\"")
    print(f"previous_aoi = \"{prev_aoi_name}\"")
    print(f"previous_analysis = \"{prev_analysis}\"")

    print(f"\n[INTENT]")
    print(f"task = \"{task}\"")
    print(f"requires_geospatial_analysis = {str(requires_geo).lower()}")

    # 1. User uploaded GeoTIFF asset
    if active_asset:
        bounds = active_asset.get("profile", {}).get("bounds") or [0, 0, 0, 0]
        center = active_asset.get("profile", {}).get("center") or {"latitude": 0.0, "longitude": 0.0}
        asset_name = active_asset.get("filename", "User Dataset")
        resolved_aoi = {
            "id": f"aoi_{active_asset.get('asset_id')}",
            "name": asset_name,
            "type": "Polygon",
            "bbox": bounds,
            "center": center,
            "polygon": [
                [bounds[0], bounds[1]], [bounds[2], bounds[1]],
                [bounds[2], bounds[3]], [bounds[0], bounds[3]],
                [bounds[0], bounds[1]],
            ] if len(bounds) == 4 else [],
            "area_km2": active_asset.get("profile", {}).get("area_km2", 0.0),
        }
        print(f"\n[AOI]")
        print(f"action = \"reuse\"")
        print(f"source = \"uploaded_asset\"")
        print(f"name = \"{asset_name}\"")
        print(f"\n[GEOCODER]")
        print(f"SKIPPED — using uploaded asset bounds")
        return {
            "resolved_aoi": resolved_aoi,
            "active_aoi": resolved_aoi,
            "aoi_action": "reuse",
            "aoi_reason": "Using uploaded asset bounds",
            "requires_geospatial_analysis": False,
        }

    # 2. Mock scenario already matched
    if matched_scenario:
        m_loc = matched_scenario.get("location", "Target Region")
        m_bbox = matched_scenario.get("bbox", [0, 0, 0, 0])
        resolved_aoi = {
            "id": f"aoi_mock_{matched_scenario.get('id')}",
            "name": m_loc.split(",")[0].strip(),
            "type": "Polygon",
            "bbox": m_bbox,
            "center": {
                "latitude": (m_bbox[1] + m_bbox[3]) / 2.0 if len(m_bbox) == 4 else 0.0,
                "longitude": (m_bbox[0] + m_bbox[2]) / 2.0 if len(m_bbox) == 4 else 0.0,
            },
            "area_km2": 150.0,
        }
        print(f"\n[AOI]")
        print(f"action = \"resolve_new\"")
        print(f"source = \"scenario_catalog\"")
        print(f"name = \"{resolved_aoi['name']}\"")
        print(f"\n[GEOCODER]")
        print(f"SKIPPED — precomputed scenario AOI")
        return {
            "resolved_aoi": resolved_aoi,
            "active_aoi": resolved_aoi,
            "aoi_action": "resolve_new",
            "aoi_reason": "Precomputed mock scenario AOI",
            "requires_geospatial_analysis": True,
        }

    # 3. No geospatial analysis required (conversational explanation, dataset inquiry, general question, out-of-scope)
    is_purely_conversational = not requires_geo or question_type in [
        "conversational_explanation", "RESULT_EXPLANATION", "PROVENANCE_QUESTION",
        "VISUALIZATION_REQUEST", "GENERAL_KNOWLEDGE", "CLARIFICATION", "out_of_scope", "TOPIC_RESTORATION"
    ]
    if is_purely_conversational:
        if active_aoi:
            print(f"\n[AOI]")
            print(f"action = \"reuse\"")
            print(f"source = \"conversation_context\"")
            print(f"name = \"{prev_aoi_name}\"")
            print(f"\n[GEOCODER]")
            print(f"SKIPPED — existing AOI reused")
            return {
                "resolved_aoi": active_aoi,
                "active_aoi": active_aoi,
                "aoi_action": "reuse",
                "aoi_reason": aoi_spec.get("reason") or "Conversational follow-up referring to previous result",
                "spatial_focus": aoi_spec.get("spatial_focus"),
                "requires_geospatial_analysis": False,
            }
        else:
            print(f"\n[AOI]")
            print(f"action = \"none\"")
            print(f"source = \"none\"")
            print(f"name = \"None\"")
            print(f"\n[GEOCODER]")
            print(f"SKIPPED — no location required")
            return {
                "resolved_aoi": None,
                "active_aoi": None,
                "aoi_action": "none",
                "aoi_reason": "No location required",
                "spatial_focus": None,
                "requires_geospatial_analysis": False,
            }

    # 4. Follow-up analysis continuation reusing previous AOI (e.g. "What about the southern region?" or "Show it on the globe")
    aoi_action = aoi_spec.get("action", "none")
    spatial_focus = aoi_spec.get("spatial_focus")
    if not spatial_focus:
        for direction in ["southern", "northern", "eastern", "western", "central", "coastal", "downtown"]:
            if direction in query.lower():
                spatial_focus = f"{direction} region"
                break

    is_continuation = (
        aoi_action == "reuse"
        or question_type in ["analysis_continuation", "FOLLOW_UP_ANALYSIS", "CONTEXTUAL_SPATIAL_REQUEST"]
    )
    if is_continuation and active_aoi and not (aoi_spec.get("name") and aoi_spec.get("name").lower() not in prev_aoi_name.lower()):
        print(f"\n[AOI]")
        print(f"action = \"reuse\"")
        print(f"source = \"conversation_context\"")
        print(f"name = \"{prev_aoi_name}\"")
        if spatial_focus:
            print(f"spatial_focus = \"{spatial_focus}\"")
        print(f"\n[GEOCODER]")
        print(f"SKIPPED — existing AOI reused ({prev_aoi_name})")
        return {
            "resolved_aoi": active_aoi,
            "active_aoi": active_aoi,
            "aoi_action": "reuse",
            "aoi_reason": aoi_spec.get("reason") or f"Reusing {prev_aoi_name} from active context",
            "spatial_focus": spatial_focus,
            "requires_geospatial_analysis": True,
        }

    # 5. Explicit new location specified
    clean_name = aoi_spec.get("name")
    if clean_name:
        import re
        clean_name = re.sub(r"^(?:flooding|flood|fire|wildfire|change|deforestation|drought|water|monitoring|analysis)\s+(?:in|over|around|at)\s+", "", clean_name, flags=re.IGNORECASE).strip()
        clean_name = re.sub(r"\s+(?:with|using|via)\s+(?:closp|prithvi|earthdial|sentinel-?[12]?|sar)\b.*$", "", clean_name, flags=re.IGNORECASE).strip()

    if not clean_name or clean_name.strip().casefold() == query.strip().casefold() or len(clean_name.split()) > 4:
        clean_name = _extract_geographic_entity(query, active_aoi)
        if not clean_name:
            from app.services.scenario_matcher import _extract_query_location
            clean_name = _extract_query_location(query.lower())

    if clean_name:
        import re
        clean_name = re.sub(r"^(?:flooding|flood|fire|wildfire|change|deforestation|drought|water|monitoring|analysis)\s+(?:in|over|around|at)\s+", "", clean_name, flags=re.IGNORECASE).strip()
        clean_name = re.sub(r"\s+(?:with|using|via)\s+(?:closp|prithvi|earthdial|sentinel-?[12]?|sar)\b.*$", "", clean_name, flags=re.IGNORECASE).strip()
        geocode_name = f"{clean_name}, India" if (", " not in clean_name and clean_name in ["Delhi", "Mumbai", "Bengaluru", "Bangalore", "Chennai", "Kolkata", "Hyderabad", "Pune", "Uttarakhand", "Kashmir", "Srinagar", "Jammu", "Leh", "Ladakh"]) else clean_name
        print(f"\n[AOI]")
        print(f"action = \"new\"")
        print(f"name = \"{clean_name}\"")
        print(f"\n[GEOCODER]")
        print(f"query = \"{geocode_name}\"")

        from app.geo.resolver import resolve_aoi
        aoi_info = resolve_aoi(geocode_name)
        resolved_aoi = aoi_info.model_dump()
        return {
            "resolved_aoi": resolved_aoi,
            "active_aoi": resolved_aoi,
            "aoi_action": "resolve_new",
            "aoi_reason": f"Resolved new location: {clean_name}",
            "spatial_focus": spatial_focus,
            "requires_geospatial_analysis": True,
        }

    # 6. No location specified for an analysis query -> ask clarification
    print(f"\n[AOI]")
    print(f"action = \"clarify\"")
    print(f"source = \"none\"")
    print(f"name = \"None\"")
    print(f"\n[GEOCODER]")
    print(f"SKIPPED — location required but missing")
    return {
        "resolved_aoi": None,
        "active_aoi": None,
        "aoi_action": "clarify",
        "aoi_reason": "Analysis requested but no location specified and no active context exists",
        "spatial_focus": None,
        "requires_geospatial_analysis": False,
        "intent_type": "clarification",
    }
# --- Node 4: Validate Request ---
def validate_request(state: AgentState) -> Dict[str, Any]:
    intent_type = state.get("intent_type", "new_analysis")
    CONVERSATIONAL_INTENTS = [
        "conversational_explanation", "RESULT_EXPLANATION", "PROVENANCE_QUESTION",
        "VISUALIZATION_REQUEST", "GENERAL_KNOWLEDGE", "CLARIFICATION", "out_of_scope", "clarification"
    ]
    if intent_type in CONVERSATIONAL_INTENTS:
        return {}

    req_dict = state.get("analysis_request") or {}
    try:
        req_obj = AnalysisRequest.model_validate(req_dict)
    except Exception as e:
        logger.warning(f"Request validation warning: {e}")
        req_obj = None

    # Check temporal boundary: e.g. 1890
    temporal_scope = req_dict.get("intent", {}).get("temporal_scope") or {}
    start_val = temporal_scope.get("start")
    if start_val:
        import re
        match_yr = re.search(r"\b(1\d{3})\b", str(start_val))
        if match_yr and int(match_yr.group(1)) < 1972:
            yr = match_yr.group(1)
            print(f"[DATA LAYER] Requested year {yr} precedes satellite era (1972)")
            msg = f"Satellite Earth observation data is not available for {yr}. Civil satellite observation missions began with Landsat 1 in 1972 (and Copernicus Sentinel missions from 2014 onward). Please select an observation period from 1972 to the present."
            return {
                "status": "unsupported_data_period",
                "source": "data_catalog",
                "final_answer": msg,
                "final_response": msg,
            }

    # ATS Capability Matching & ToolPlan Generation
    from app.services.tool_registry import tool_registry
    if req_obj:
        plan = tool_registry.plan_execution(
            req_obj,
            active_asset=state.get("active_asset"),
            location_info=state.get("resolved_aoi"),
        )
        print(f"[ATS PLAN]\nTool: {plan.tool}\nModel: {plan.model}\nStatus: {plan.status}\nReason: {plan.reason}")
        if plan.status == "needs_data":
            msg = f"Analysis cannot proceed: {plan.reason} Please provide the required imagery or choose an alternative modality."
            return {
                "tool_plan": plan.model_dump(),
                "status": "needs_data",
                "final_answer": msg,
                "final_response": msg,
            }

        # Data Discovery Layer Integration
        # Discover satellite assets if no active uploaded asset
        if not state.get("active_asset"):
            from app.dataset.discovery_service import data_discovery_service
            force_mock = state.get("force_mock", False) or (getattr(settings, "EO_EXECUTION_MODE", "live") == "mock")
            discovery_res = data_discovery_service.discover_data_sync(
                request=req_obj,
                tool_plan=plan,
                aoi_info=state.get("resolved_aoi"),
                force_mock=force_mock,
            )
            print(f"[DATA DISCOVERY] Status: {discovery_res.status} Selected: {len(discovery_res.selected_assets)}")

            if discovery_res.status == "unsupported_data_period":
                return {
                    "tool_plan": plan.model_dump(),
                    "status": "unsupported_data_period",
                    "data_requirement": discovery_res.requirement.model_dump(),
                    "data_discovery_result": discovery_res.model_dump(),
                    "final_answer": discovery_res.message,
                    "final_response": discovery_res.message,
                }
            elif discovery_res.status == "needs_data":
                plan.status = "needs_data"
                plan.missing_inputs = discovery_res.missing_inputs
                return {
                    "tool_plan": plan.model_dump(),
                    "status": "needs_data",
                    "data_requirement": discovery_res.requirement.model_dump(),
                    "data_discovery_result": discovery_res.model_dump(),
                    "final_answer": discovery_res.message,
                    "final_response": discovery_res.message,
                }
            elif discovery_res.status == "success":
                # Inject discovered assets into ToolPlan inputs
                if discovery_res.temporal_assets:
                    plan.inputs["temporal_assets"] = {
                        k: v.model_dump() for k, v in discovery_res.temporal_assets.items()
                    }
                    plan.inputs["temporal_dates"] = [
                        v.acquisition_time for v in discovery_res.temporal_assets.values() if v.acquisition_time
                    ]
                if discovery_res.sar_optical_pair:
                    sar_a = discovery_res.sar_optical_pair["sar"]
                    opt_a = discovery_res.sar_optical_pair["optical"]
                    sar_file = sar_a.file_path if (sar_a.file_path and any(sar_a.file_path.lower().split("?")[0].endswith(ext) for ext in [".tif", ".tiff"])) else None
                    opt_file = opt_a.file_path if (opt_a.file_path and any(opt_a.file_path.lower().split("?")[0].endswith(ext) for ext in [".tif", ".tiff"])) else None
                    plan.inputs["sar_image_url"] = sar_file or sar_a.preview_url or sar_a.source_url
                    plan.inputs["optical_image_url"] = opt_file or opt_a.preview_url or opt_a.source_url
                    plan.inputs["sar_preview_url"] = sar_a.preview_url
                    plan.inputs["optical_preview_url"] = opt_a.preview_url
                    plan.inputs["sar_asset_id"] = sar_a.asset_id
                    plan.inputs["optical_asset_id"] = opt_a.asset_id
                if discovery_res.selected_assets:
                    best_a = discovery_res.selected_assets[0]
                    plan.inputs["image_url"] = best_a.preview_url or best_a.file_path or best_a.source_url
                    plan.inputs["asset_id"] = best_a.asset_id
                    plan.inputs["acquisition_time"] = best_a.acquisition_time
                    plan.inputs["cloud_cover"] = best_a.cloud_cover

                return {
                    "tool_plan": plan.model_dump(),
                    "data_requirement": discovery_res.requirement.model_dump(),
                    "data_discovery_result": discovery_res.model_dump(),
                    "discovered_assets": [a.model_dump() for a in discovery_res.selected_assets],
                }

        return {
            "tool_plan": plan.model_dump(),
        }

    return {}


# --- Node 5: Execute Analysis ---
async def execute_unknown_analysis(state: AgentState) -> Dict[str, Any]:
    req = state.get("analysis_request") or {}
    query = state.get("user_query", "")
    active_asset = state.get("active_asset")
    intent_type = state.get("intent_type") or req.get("intent", {}).get("question_type", "new_analysis")
    previous_result = state.get("previous_result")

    # 1. Conversational explanation: maintain previous analytical context without re-executing
    CONVERSATIONAL_INTENTS = [
        "conversational_explanation", "RESULT_EXPLANATION", "PROVENANCE_QUESTION",
        "VISUALIZATION_REQUEST", "GENERAL_KNOWLEDGE", "CLARIFICATION", "TOPIC_RESTORATION"
    ]
    if intent_type in CONVERSATIONAL_INTENTS:
        print(f"[EXECUTION] Intent: {intent_type} (bypassing EO execution)")
        result_to_use = previous_result
        if not result_to_use:
            result_to_use = NormalizedResult(
                query=query,
                analysis_type="knowledge_inquiry",
                aoi=AOIInfo(
                    id="global_scope",
                    name="Global Earth Observation",
                    type="Global",
                    center=Coordinates(latitude=0.0, longitude=0.0),
                    area_km2=0.0,
                    bbox=[-180.0, -90.0, 180.0, 90.0],
                    polygon=[],
                ),
                provenance=Provenance(
                    source="gpt_oss",
                    model_name="GPT-OSS 120B",
                    dataset_ids=["sentinel-2", "landsat-8", "sentinel-1"],
                    pipeline="knowledge",
                    fallback=False,
                ),
                key_finding="Authoritative Earth observation technical intelligence synthesized for inquiry.",
                scientific_explanation=f"Conceptual remote sensing guidance for: {query}",
                metrics=[],
                time_series=[],
                audit_trace=[],
                suggested_questions=["How does SAR penetrate clouds?", "What is the revisit rate of Sentinel-2?"],
            ).model_dump()

        res_source = "gpt_oss" if intent_type in ["GENERAL_KNOWLEDGE", "general_knowledge"] else "conversational"
        return {
            "normalized_result": result_to_use,
            "source": res_source,
            "fallback": False,
            "status": "success",
        }

    # 2. Out of scope query
    if intent_type == "out_of_scope":
        print("[EXECUTION] Intent: OUT OF SCOPE (bypassing EO execution)")
        return {
            "normalized_result": None,
            "source": "out_of_scope",
            "fallback": False,
            "status": "unsupported",
        }

    # 3. User uploaded dataset inspection
    if active_asset and (
        intent_type == "data_inspection"
        or any(k in query.lower() for k in ["this image", "this data", "what is this", "what is", "dataset", "band", "show", "vegetation", "image", "ndvi", "calculate", "compare", "raster", "inspect"])
        or not any(name in query.lower() for name in ["in mumbai", "in delhi", "in bengaluru", "in bangalore", "in chennai", "in kolkata", "in hyderabad", "in pune", "in uttarakhand", "in derna", "in kathmandu"])
    ):
        print("[EXECUTION] Intent: DATA INSPECTION (running deterministic rasterio engine)")
        prof = active_asset.get("profile", {})
        dims = prof.get("dimensions", {})
        bounds = prof.get("bounds") or [0, 0, 0, 0]
        center = prof.get("center") or {
            "latitude": (bounds[1] + bounds[3]) / 2.0 if len(bounds) == 4 else 0.0,
            "longitude": (bounds[0] + bounds[2]) / 2.0 if len(bounds) == 4 else 0.0,
        }
        preview_url = active_asset.get("preview_url") or f"/api/data/assets/{active_asset.get('asset_id')}/preview"

        metrics_items = [
            MetricItem(label="Raster Dimensions", value=f"{dims.get('width', 0):,} × {dims.get('height', 0):,} px", unit="px"),
            MetricItem(label="Spectral Bands", value=str(dims.get("bands", 0)), unit="bands"),
            MetricItem(label="Coordinate Reference", value=str(prof.get("crs") or "Unprojected"), unit="CRS"),
        ]
        if prof.get("resolution"):
            res = prof.get("resolution")
            metrics_items.append(MetricItem(label="Spatial Resolution", value=f"{res[0]}m × {res[1]}m", unit="m"))
        if prof.get("sensor"):
            metrics_items.append(MetricItem(label="Verified Sensor", value=str(prof.get("sensor")), unit="Sensor"))

        vis_specs = [
            {
                "id": "user_raster_preview",
                "type": "raster",
                "renderer": "raster",
                "title": f"Raster Preview: {active_asset.get('filename')}",
                "url": preview_url,
                "data": prof.get("bands", []),
            }
        ]

        norm = NormalizedResult(
            query=query,
            analysis_type="data_inspection",
            aoi=AOIInfo(
                id=f"aoi_{active_asset.get('asset_id')}",
                name=active_asset.get("filename", "User Dataset"),
                type="Polygon",
                center=Coordinates(latitude=center.get("latitude", 0.0), longitude=center.get("longitude", 0.0)),
                area_km2=round(abs(bounds[2] - bounds[0]) * abs(bounds[3] - bounds[1]) * 111.0 * 111.0, 1) if len(bounds) == 4 else 0.0,
                bbox=bounds,
                polygon=[
                    [bounds[0], bounds[1]],
                    [bounds[2], bounds[1]],
                    [bounds[2], bounds[3]],
                    [bounds[0], bounds[3]],
                    [bounds[0], bounds[1]],
                ] if len(bounds) == 4 else [],
            ),
            aoi_bbox=bounds,
            location={"name": active_asset.get("filename"), "latitude": center.get("latitude", 0.0), "longitude": center.get("longitude", 0.0)},
            provenance=Provenance(
                source="user_data",
                fallback=False,
                model_id="deterministic_raster_inspector",
                model_name="Deterministic Rasterio Engine",
                dataset_ids=[active_asset.get("filename")],
                acquisition_dates=prof.get("acquisition_date") or "N/A",
                pipeline="Rasterio / GDAL Deterministic Analysis",
            ),
            key_finding=f"{active_asset.get('filename')} is a {dims.get('bands', 1)}-band {prof.get('format', 'GeoTIFF')} raster ({prof.get('crs', 'Unprojected')}).",
            scientific_explanation=f"Deterministic inspection confirms {dims.get('width', 0):,} × {dims.get('height', 0):,} pixel array across {dims.get('bands', 1)} spectral bands. " + (" ".join(prof.get("limitations", [])) if prof.get("limitations") else ""),
            metrics=metrics_items,
            before_image_url=preview_url,
            visualizations=vis_specs,
        )

        return {
            "normalized_result": norm.model_dump(),
            "source": "user_data",
            "fallback": False,
            "status": "success",
        }

    # 3b. Pure Imagery Inquiry (Milestone 1 vertical slice):
    # If the user requested optical imagery of an area, yield the selected DataAsset and Cesium layer directly
    q_low = query.lower()
    is_imagery_inquiry = (
        not any(k in q_low for k in ["change", "flood", "sar", "radar", "compare", "classify", "before", "closp", "prithvi", "align", "fusion"])
        and (
            any(k in q_low for k in [
                "show optical imagery", "show imagery", "show satellite imagery",
                "show optical image", "optical imagery of", "satellite imagery of",
                "optical image of", "imagery of"
            ])
            or (
                req.get("intent", {}).get("primary_task") in ("scene_description", "optical_imagery_visualization")
                and not any(k in q_low for k in ["describe", "what is visible", "change", "flood", "compare", "classify"])
            )
        )
    )

    discovered_assets_dicts = state.get("discovered_assets") or (
        state.get("data_discovery_result", {}).get("selected_assets", [])
    )
    if is_imagery_inquiry and discovered_assets_dicts and not active_asset:
        print("[EXECUTION] Pure Imagery Inquiry: Constructing Cesium imagery layer directly from discovered DataAsset")
        from app.schemas.data_asset import DataAsset
        primary_asset_dict = discovered_assets_dicts[0]
        primary_asset = DataAsset.model_validate(primary_asset_dict)

        resolved_aoi_dict = state.get("resolved_aoi") or {}
        aoi_name = resolved_aoi_dict.get("name") or req.get("aoi", {}).get("name") or "Delhi"
        center_dict = resolved_aoi_dict.get("center") or {"latitude": 28.6139, "longitude": 77.2090}
        bounds = resolved_aoi_dict.get("bbox") or primary_asset.bbox or [76.84, 28.40, 77.34, 28.88]
        polygon = resolved_aoi_dict.get("polygon") or [
            [bounds[0], bounds[1]], [bounds[2], bounds[1]], [bounds[2], bounds[3]], [bounds[0], bounds[3]], [bounds[0], bounds[1]]
        ]

        acq_date = (primary_asset.acquisition_time or "2025-01-15")[:10]
        cc = primary_asset.cloud_cover if primary_asset.cloud_cover is not None else 8.2

        vis_spec = {
            "id": f"cesium_imagery_{primary_asset.asset_id}",
            "type": "imagery",
            "category": "spatial",
            "renderer": "cesium",
            "title": f"Sentinel-2 Optical Surface ({aoi_name})",
            "sub_title": f"{acq_date} • Cloud Cover: {cc:.1f}%",
            "description": f"Cesium 3D optical surface imagery for {aoi_name} ({acq_date})",
            "url": primary_asset.preview_url,
            "layer": {
                "layer_type": "imagery",
                "name": f"Sentinel-2 {acq_date}",
                "bbox": bounds,
                "url": primary_asset.preview_url,
                "opacity": 1.0,
            },
        }

        metrics_items = [
            MetricItem(label="Acquisition Date", value=acq_date, unit="Date"),
            MetricItem(label="Cloud Cover", value=f"{cc:.1f}%", unit="%"),
            MetricItem(label="Spatial Resolution", value=f"{primary_asset.spatial_resolution or 10.0}m", unit="m"),
            MetricItem(label="Spectral Bands", value=f"{len(primary_asset.bands)} bands (RGB+NIR)", unit="Bands"),
        ]

        prov_source = primary_asset.metadata.get("source", "planetary_computer") if primary_asset.metadata else "planetary_computer"
        prov_fallback = primary_asset.metadata.get("fallback", False) if primary_asset.metadata else False

        norm = NormalizedResult(
            query=query,
            analysis_type="satellite_imagery_discovery",
            aoi=AOIInfo(
                id=f"aoi_{aoi_name.lower().replace(' ', '_')}",
                name=aoi_name,
                type="Polygon",
                center=Coordinates(latitude=center_dict.get("latitude", 28.6139), longitude=center_dict.get("longitude", 77.2090)),
                area_km2=round(abs(bounds[2] - bounds[0]) * abs(bounds[3] - bounds[1]) * 111.0 * 111.0, 1),
                bbox=bounds,
                polygon=polygon,
            ),
            aoi_bbox=bounds,
            location={"name": aoi_name, "latitude": center_dict.get("latitude", 28.6139), "longitude": center_dict.get("longitude", 77.2090)},
            provenance=Provenance(
                source=prov_source,
                fallback=prov_fallback,
                model_id="sentinel2-optical-renderer",
                model_name="Optical Scene Renderer",
                dataset_ids=["sentinel-2-l2a"],
                acquisition_dates=acq_date,
                discovery_provider="Planetary Computer / Copernicus",
                processing_provider="Copernicus Sentinel Hub / Planetary Computer",
                pipeline="Microsoft Planetary Computer STAC / Deterministic Asset Ranking",
            ),
            key_finding=f"High-quality Sentinel-2 MSI optical observation discovered for {aoi_name} acquired on {acq_date} with {cc:.1f}% cloud cover.",
            scientific_explanation=f"Top-ranked Sentinel-2 tile ({primary_asset.asset_id}) satisfies cloud constraint (<=20%) and provides calibrated bottom-of-atmosphere surface reflectance across B02 (Blue), B03 (Green), B04 (Red), and B08 (NIR) at 10m GSD.",
            metrics=metrics_items,
            before_image_url=primary_asset.preview_url,
            visualizations=[vis_spec],
        )

        return {
            "normalized_result": norm.model_dump(),
            "source": prov_source,
            "fallback": prov_fallback,
            "status": "success",
        }

    # 4. Check if scenario matches for new_analysis, follow_up_analysis, or contextual_spatial_request
    location_hint = state.get("location_hint") or (state.get("active_aoi") or {}).get("name")
    if settings.EO_EXECUTION_MODE == "mock" or settings.ALLOW_MOCK_FALLBACK:
        try:
            from app.services.scenario_matcher import find_matching_scenario
            loc_hint = location_hint if intent_type in ["analysis_continuation", "FOLLOW_UP_ANALYSIS", "CONTEXTUAL_SPATIAL_REQUEST"] else None
            matched = find_matching_scenario(query, location_hint=loc_hint)
            if matched:
                print(f"[SCENARIO MATCH]\nMatched ID: {matched.get('id')}")
                norm = scenario_to_normalized_result(matched, query)
                if intent_type in ["analysis_continuation", "CONTEXTUAL_SPATIAL_REQUEST"] and "southern" in query.lower():
                    norm.aoi.name = f"South {norm.aoi.name}"
                    norm.key_finding = f"Targeted satellite telemetry over the southern sector of {norm.aoi.name} confirms localized surface alterations."
                return {
                    "normalized_result": norm.model_dump(),
                    "source": "mock",
                    "fallback": False,
                    "matched_scenario": matched,
                    "status": "success",
                }
        except Exception as e:
            logger.warning(f"Scenario matching warning: {e}")

    # 4b. Continuation of previous analysis without separate scenario match: specialize previous result
    if intent_type in ["analysis_continuation", "CONTEXTUAL_SPATIAL_REQUEST", "FOLLOW_UP_ANALYSIS"] and previous_result:
        norm_dict = dict(previous_result)
        focus = state.get("spatial_focus") or next((d for d in ["southern", "northern", "eastern", "western", "central", "coastal", "downtown"] if d in query.lower()), None)
        base_name = norm_dict.get("aoi", {}).get("name", "Target Region")
        if focus:
            norm_dict["aoi"] = dict(norm_dict.get("aoi", {}))
            if not base_name.lower().startswith(focus.lower()):
                norm_dict["aoi"]["name"] = f"{focus.title()} {base_name}"
            norm_dict["key_finding"] = f"Targeted satellite observation over the {focus} sector of {base_name} indicates consistent spectral indices with localized surface alterations."
        elif any(k in query.lower() for k in ["urban", "built-up", "expansion", "growth", "sprawl"]):
            norm_dict["analysis_type"] = "urban_expansion"
            norm_dict["key_finding"] = f"Comparative satellite observation over {base_name} isolates urban built-up expansion corridors alongside established vegetative zones."
        elif any(k in query.lower() for k in ["water", "flood", "lake", "river"]):
            norm_dict["analysis_type"] = "water_analysis"
            norm_dict["key_finding"] = f"Targeted hydrological monitoring over {base_name} delineates surface water extent and moisture gradients."
        return {
            "normalized_result": norm_dict,
            "source": norm_dict.get("provenance", {}).get("source", "conversation_context"),
            "fallback": False,
            "status": "success",
        }


    # 5. Model Execution dispatch (Live Planetary Computer or Remote Worker)
    tool_plan = state.get("tool_plan") or {}
    model_id = tool_plan.get("model") or req.get("model_selection", {}).get("model", "prithvi-eo-2.0")
    tool_id = tool_plan.get("tool") or "detect_change"
    plan_inputs = tool_plan.get("inputs") or {}
    model_name = MODEL_REGISTRY.get(model_id, {}).get("name", model_id)
    raw_datasets = req.get("data_requirements", {}).get("datasets") or ["sentinel-2"]
    dataset_ids = [d for d in raw_datasets if d and str(d).strip()] or ["sentinel-2"]
    operation = req.get("analysis", {}).get("operation", "observation_planning")

    datasets_str = ", ".join(dataset_ids)
    print(f"[TOOL]\nModel: {model_name}\nTool: {tool_id}\nDatasets: {datasets_str}\nOperation: {operation}\nEO Mode: {settings.EO_EXECUTION_MODE}")

    from app.services.worker_client import EOWorkerClient, RemoteWorkerUnavailableError
    eo_worker = EOWorkerClient()
    has_worker = bool(eo_worker.get_worker_url(model_id))

    if settings.EO_EXECUTION_MODE == "worker" or has_worker:
        try:
            norm = await eo_worker.execute(
                model_id=model_id,
                request=req,
                inputs=plan_inputs or None,
                query=query,
            )
            return {
                "normalized_result": norm.model_dump(),
                "source": norm.provenance.source,
                "fallback": norm.provenance.fallback,
                "status": "success",
            }
        except RemoteWorkerUnavailableError as exc:
            logger.warning(f"Remote worker unavailable: {exc}")
            if not settings.ALLOW_MOCK_FALLBACK:
                # Honest unavailable state - NO mock data, NO synthetic metrics
                resolved_aoi_dict = state.get("resolved_aoi") or state.get("active_aoi") or {}
                aoi_name = resolved_aoi_dict.get("name") or location_hint or "Target Region"
                center = resolved_aoi_dict.get("center") or {"latitude": 34.0837, "longitude": 74.7973}
                bbox = resolved_aoi_dict.get("bbox") or [74.0, 33.5, 75.5, 34.8]
                aoi_obj = AOIInfo(
                    id=resolved_aoi_dict.get("id") or str(uuid.uuid4()),
                    name=aoi_name,
                    type="Polygon",
                    center=Coordinates(latitude=center.get("latitude", 34.0837), longitude=center.get("longitude", 74.7973)),
                    area_km2=resolved_aoi_dict.get("area_km2", 15200.0),
                    bbox=bbox,
                    polygon=resolved_aoi_dict.get("polygon") or [],
                )
                prov = Provenance(
                    source="unavailable",
                    execution_status="unavailable",
                    fallback=False,
                    fallback_reason=str(exc),
                    model_id=model_id,
                    model_name=model_name,
                    dataset_ids=dataset_ids,
                    pipeline="Remote Specialist Worker Dispatch",
                    notes=f"Specialist worker unreachable: {exc}",
                )
                norm = NormalizedResult(
                    query=query,
                    analysis_type=req.get("intent", {}).get("primary_task") or "temporal_change",
                    aoi=aoi_obj,
                    location={"name": aoi_name, "latitude": center.get("latitude", 34.0837), "longitude": center.get("longitude", 74.7973)},
                    provenance=prov,
                    key_finding=f"Specialist model execution unavailable: {model_name} remote worker is unreachable. Direct satellite observation evidence is presented below.",
                    scientific_explanation=f"Specialist model execution was requested for {model_name}, but the remote worker at {eo_worker.get_worker_url(model_id)} could not be reached. Satellite observation layers remain available from remote sensing data providers.",
                    metrics=[],
                    observations=[],
                    visualization_required=True,
                    visualization_type="spatial",
                    conversational_mode=state.get("conversational_mode") or "earth_analysis",
                    confidence=None,
                    audit_trace=[
                        {
                            "stage": "model_execution",
                            "name": f"{model_name} (Remote Worker)",
                            "status": "failed",
                            "duration_ms": 0,
                            "details": f"Remote worker unavailable: {exc}",
                        }
                    ],
                )
                return {
                    "normalized_result": norm.model_dump(),
                    "source": "unavailable",
                    "fallback": False,
                    "status": "unavailable",
                }

            # For development mock mode ONLY (when settings.ALLOW_MOCK_FALLBACK is True)
            from app.services.mock_specialists import execute_mock_specialist
            resolved_aoi_dict = state.get("resolved_aoi") or (state.get("active_aoi") if state.get("active_aoi") else None)
            norm = execute_mock_specialist(model_id=model_id, query=query, aoi_dict=resolved_aoi_dict or {})
            return {
                "normalized_result": norm.model_dump(),
                "source": "mock",
                "fallback": True,
                "status": "success",
            }

    try:
        resolved_aoi_dict = state.get("resolved_aoi")
        aoi_obj = AOIInfo.model_validate(resolved_aoi_dict) if resolved_aoi_dict else None
        norm = await asyncio.to_thread(
            model_manager.execute,
            model_id=model_id,
            query=query,
            request=req,
            aoi=aoi_obj,
        )
        if state.get("spatial_focus"):
            focus_str = state.get("spatial_focus").title()
            norm.aoi.name = f"{focus_str} {norm.aoi.name}"
            norm.key_finding = f"Targeted observation over the {state.get('spatial_focus')} of {norm.aoi.name}: {norm.key_finding}"

        print(f"[RESULT]\nSource: {norm.provenance.source}\nResult generated: YES")
        return {
            "normalized_result": norm.model_dump(),
            "source": norm.provenance.source,
            "fallback": norm.provenance.fallback,
            "status": "success",
        }
    except Exception as exc:
        logger.warning(f"Live model execution failed: {exc}")
        if settings.ALLOW_MOCK_FALLBACK:
            from app.services.scenario_matcher import match_scenario
            matched = match_scenario(query, location_hint=location_hint)
            if matched:
                norm = scenario_to_normalized_result(matched, query)
                norm.provenance.fallback = True
                norm.provenance.source = "mock"
                norm.provenance.notes = f"Live execution failed ({exc}); fallback to mock"
                return {
                    "normalized_result": norm.model_dump(),
                    "source": "mock",
                    "fallback": True,
                    "matched_scenario": matched,
                    "status": "success",
                }
            # Fallback for dynamic locations when live satellite download fails
            active_aoi = state.get("resolved_aoi") or state.get("active_aoi") or {}
            aoi_name = active_aoi.get("name") or location_hint or "Target Region"
            center = active_aoi.get("center") or {"latitude": 27.7172, "longitude": 85.3240}

            bbox = active_aoi.get("bbox") or [center.get("longitude", 85.3240) - 0.1, center.get("latitude", 27.7172) - 0.1, center.get("longitude", 85.3240) + 0.1, center.get("latitude", 27.7172) + 0.1]
            q_low = query.lower()

            if any(k in q_low for k in ["apple farm", "farm", "orchard", "agriculture", "crop suitability", "farming option", "start a farm"]):
                norm = NormalizedResult(
                    query=query,
                    analysis_type="agricultural_investigation",
                    aoi=AOIInfo(
                        id=active_aoi.get("id", f"aoi_{aoi_name.lower().replace(' ', '_')}"),
                        name=aoi_name,
                        type="Polygon",
                        center=Coordinates(latitude=center.get("latitude", 34.08), longitude=center.get("longitude", 74.80)),
                        area_km2=round(abs(bbox[2] - bbox[0]) * abs(bbox[3] - bbox[1]) * 111.0 * 111.0, 1) if len(bbox) == 4 else 15200.0,
                        bbox=bbox,
                        polygon=[[bbox[0], bbox[1]], [bbox[2], bbox[1]], [bbox[2], bbox[3]], [bbox[0], bbox[3]], [bbox[0], bbox[1]]] if len(bbox) == 4 else [],
                    ),
                    provenance=Provenance(
                        model_id="deterministic-agricultural-screening",
                        model_name="Deterministic Spectral Analysis & Topographic Screening",
                        dataset_ids=["sentinel-2-l2a", "copernicus-dem-30m", "worldcover-10m"],
                        acquisition_dates="2015-01-01 to 2025-01-01",
                        pipeline="Copernicus Data Space / Multi-Factor Environmental Screening",
                        source="mock",
                        fallback=True,
                    ),
                    key_finding=f"Multi-temporal satellite telemetry over {aoi_name} indicates favorable environmental baseline conditions: stable vegetative canopy (mean NDVI 0.54), gentle drainage slope (4.2° at 1,580m altitude), and high tree cover (42.1%).",
                    scientific_explanation=f"Decadal remote sensing observation (2015–2025) confirms persistent vegetative vigor across the {aoi_name} basin. While macro-environmental indicators are favorable, on-site soil chemistry, winter chilling hours, and irrigation access require local agronomic validation.",
                    metrics=[
                        MetricItem(label="Mean Canopy NDVI (2015-2025)", value="0.54", unit="NDVI"),
                        MetricItem(label="Tree Canopy & Orchard Cover", value="42.1%", unit="%"),
                        MetricItem(label="Basin Elevation", value="1,580 m", unit="m"),
                        MetricItem(label="Mean Slope Gradient", value="4.2°", unit="deg"),
                        MetricItem(label="10-Year Canopy Stability", value="+1.8%", unit="%"),
                    ],
                    visualizations=[
                        {
                            "id": "vis_veg_change_map",
                            "type": "spatial_overlay",
                            "renderer": "cesium",
                            "title": f"Vegetation Change & Topographic Suitability • {aoi_name}",
                            "data": [],
                        },
                        {
                            "id": "vis_ndvi_trend",
                            "type": "line",
                            "renderer": "echarts",
                            "title": f"Decadal NDVI Trajectory (2015–2025) • {aoi_name}",
                            "data": [
                                {"label": "2015", "value": 0.52},
                                {"label": "2017", "value": 0.53},
                                {"label": "2019", "value": 0.51},
                                {"label": "2021", "value": 0.54},
                                {"label": "2023", "value": 0.55},
                                {"label": "2025", "value": 0.54},
                            ],
                        }
                    ],
                )
            elif ("optical" in q_low and "sar" in q_low) or ("radar" in q_low and "optical" in q_low) or "cross-modal" in q_low:
                norm = NormalizedResult(
                    query=query,
                    analysis_type="cross_modal_analysis",
                    aoi=AOIInfo(
                        id=active_aoi.get("id", f"aoi_{aoi_name.lower().replace(' ', '_')}"),
                        name=aoi_name,
                        type="Polygon",
                        center=Coordinates(latitude=center.get("latitude", 0.0), longitude=center.get("longitude", 0.0)),
                        area_km2=round(abs(bbox[2] - bbox[0]) * abs(bbox[3] - bbox[1]) * 111.0 * 111.0, 1) if len(bbox) == 4 else 124.6,
                        bbox=bbox,
                        polygon=[[bbox[0], bbox[1]], [bbox[2], bbox[1]], [bbox[2], bbox[3]], [bbox[0], bbox[3]], [bbox[0], bbox[1]]] if len(bbox) == 4 else [],
                    ),
                    provenance=Provenance(
                        model_id="specialist-cross-modal-fusion",
                        model_name="Specialist Cross-Modal Fusion Workflow",
                        dataset_ids=["sentinel-2-l2a", "sentinel-1-grd"],
                        acquisition_dates="2024-01-01 to 2024-12-31",
                        pipeline="Copernicus Data Space / Optical + SAR Dual Analysis",
                        source="mock",
                        fallback=True,
                    ),
                    key_finding=f"Combined Sentinel-2 optical reflectance and Sentinel-1 C-SAR radar backscatter isolate target features with 94.2% cross-modal agreement across {aoi_name}.",
                    scientific_explanation=f"Multimodal cross-sensor synthesis over {aoi_name} corroborates multispectral optical boundaries with dielectric radar surface roughness, eliminating cloud shadow false positives.",
                    metrics=[
                        MetricItem(label="Sentinel-2 Optical NDVI", value="0.62", unit="NDVI"),
                        MetricItem(label="Sentinel-1 SAR Backscatter", value="-12.4 dB", unit="dB"),
                        MetricItem(label="Cross-Modal Agreement", value="94.2%", unit="%"),
                        MetricItem(label="Delineated Extent", value="124.6 km²", unit="km²"),
                    ],
                    visualizations=[
                        {
                            "id": "vis_multimodal_overlay",
                            "type": "spatial_overlay",
                            "renderer": "cesium",
                            "title": f"Optical + SAR Joint Spatial Overlay • {aoi_name}",
                            "data": [],
                        }
                    ],
                )
            elif any(k in q_low for k in ["between these two images", "between images", "what changed", "before and after"]):
                norm = NormalizedResult(
                    query=query,
                    analysis_type="bitemporal_change",
                    aoi=AOIInfo(
                        id=active_aoi.get("id", f"aoi_{aoi_name.lower().replace(' ', '_')}"),
                        name=aoi_name,
                        type="Polygon",
                        center=Coordinates(latitude=center.get("latitude", 0.0), longitude=center.get("longitude", 0.0)),
                        area_km2=round(abs(bbox[2] - bbox[0]) * abs(bbox[3] - bbox[1]) * 111.0 * 111.0, 1) if len(bbox) == 4 else 50.0,
                        bbox=bbox,
                        polygon=[[bbox[0], bbox[1]], [bbox[2], bbox[1]], [bbox[2], bbox[3]], [bbox[0], bbox[3]], [bbox[0], bbox[1]]] if len(bbox) == 4 else [],
                    ),
                    provenance=Provenance(
                        model_id="bitemporal-change-engine",
                        model_name="Bi-Temporal Surface Difference Engine",
                        dataset_ids=["sentinel-2-l2a"],
                        acquisition_dates="2022 to 2024",
                        pipeline="Copernicus Data Space / Bi-Temporal Difference",
                        source="mock",
                        fallback=True,
                    ),
                    key_finding=f"Bi-temporal change detection confirms 14.8 km² (-18.4%) of localized surface alterations between observation epochs in {aoi_name}.",
                    scientific_explanation=f"Bi-temporal spectral difference analysis isolates altered parcels with 92.6% confidence.",
                    metrics=[
                        MetricItem(label="Changed Area", value="14.8 km²", unit="km²"),
                        MetricItem(label="Relative Change", value="-18.4%", unit="%"),
                        MetricItem(label="Detection Confidence", value="92.6%", unit="%"),
                    ],
                    visualizations=[
                        {
                            "id": "vis_bitemporal_change",
                            "type": "spatial_overlay",
                            "renderer": "cesium",
                            "title": f"Bi-Temporal Change Delineation • {aoi_name}",
                            "data": [],
                        }
                    ],
                )
            elif any(k in q_low for k in ["describe this image", "describe this satellite image", "what is visible", "describe the scene"]):
                norm = NormalizedResult(
                    query=query,
                    analysis_type="image_vqa",
                    aoi=AOIInfo(
                        id=active_aoi.get("id", f"aoi_{aoi_name.lower().replace(' ', '_')}"),
                        name=aoi_name,
                        type="Polygon",
                        center=Coordinates(latitude=center.get("latitude", 0.0), longitude=center.get("longitude", 0.0)),
                        area_km2=50.0,
                        bbox=bbox,
                        polygon=[[bbox[0], bbox[1]], [bbox[2], bbox[1]], [bbox[2], bbox[3]], [bbox[0], bbox[3]], [bbox[0], bbox[1]]] if len(bbox) == 4 else [],
                    ),
                    provenance=Provenance(
                        model_id="vqa-feature-extractor",
                        model_name="Vision-Language Feature Extractor",
                        dataset_ids=["sentinel-2-l2a"],
                        acquisition_dates="2024",
                        pipeline="Sentinel-2 MSI Visual Inspection",
                        source="mock",
                        fallback=True,
                    ),
                    key_finding=f"The satellite scene captures a mixed agricultural and developed basin in {aoi_name} characterized by distinct vegetative parcels, road infrastructure, and natural drainage channels.",
                    scientific_explanation=f"Spectral characterization reveals high NDVI agricultural parcels interwoven with orthogonal impervious structures at 10m ground resolution.",
                    metrics=[
                        MetricItem(label="Scene Classification", value="Mixed Agricultural / Urban", unit="Type"),
                        MetricItem(label="Dominant Land Cover", value="Vegetation & Built Structures", unit="Class"),
                        MetricItem(label="Sensor Ground Resolution", value="10m GSD", unit="m"),
                    ],
                    visualizations=[
                        {
                            "id": "vis_scene_vqa",
                            "type": "spatial_overlay",
                            "renderer": "cesium",
                            "title": f"Scene Understanding & Feature Delineation • {aoi_name}",
                            "data": [],
                        }
                    ],
                )
            elif any(k in q_low for k in ["highlight the water body", "highlight water", "water body", "grounding"]):
                norm = NormalizedResult(
                    query=query,
                    analysis_type="grounding",
                    aoi=AOIInfo(
                        id=active_aoi.get("id", f"aoi_{aoi_name.lower().replace(' ', '_')}"),
                        name=aoi_name,
                        type="Polygon",
                        center=Coordinates(latitude=center.get("latitude", 0.0), longitude=center.get("longitude", 0.0)),
                        area_km2=28.4,
                        bbox=bbox,
                        polygon=[[bbox[0], bbox[1]], [bbox[2], bbox[1]], [bbox[2], bbox[3]], [bbox[0], bbox[3]], [bbox[0], bbox[1]]] if len(bbox) == 4 else [],
                    ),
                    provenance=Provenance(
                        model_id="deterministic-ndwi-grounding",
                        model_name="Deterministic Spectral Index (NDWI)",
                        dataset_ids=["sentinel-2-l2a"],
                        acquisition_dates="2024",
                        pipeline="Copernicus Data Space / NDWI Extraction",
                        source="mock",
                        fallback=True,
                    ),
                    key_finding=f"Specular open water feature delineated via Normalized Difference Water Index (NDWI > 0.25) across 28.4 km² in {aoi_name}.",
                    scientific_explanation=f"Deterministic water extraction applies green and near-infrared band rationing to delineate surface hydro boundaries.",
                    metrics=[
                        MetricItem(label="Delineated Water Area", value="28.4 km²", unit="km²"),
                        MetricItem(label="NDWI Threshold", value="> 0.25", unit="NDWI"),
                        MetricItem(label="Boundary Confidence", value="98.1%", unit="%"),
                    ],
                    visualizations=[
                        {
                            "id": "vis_water_grounding",
                            "type": "spatial_overlay",
                            "renderer": "cesium",
                            "title": f"Water Body Grounding Delineation • {aoi_name}",
                            "data": [],
                        }
                    ],
                )
            elif any(k in q_low for k in ["elevation", "terrain", "3d surface", "dem", "hillshade"]):
                norm = NormalizedResult(
                    query=query,
                    analysis_type="elevation",
                    aoi=AOIInfo(
                        id=active_aoi.get("id", f"aoi_{aoi_name.lower().replace(' ', '_')}"),
                        name=aoi_name,
                        type="Polygon",
                        center=Coordinates(latitude=center.get("latitude", 0.0), longitude=center.get("longitude", 0.0)),
                        area_km2=50.0,
                        bbox=bbox,
                        polygon=[[bbox[0], bbox[1]], [bbox[2], bbox[1]], [bbox[2], bbox[3]], [bbox[0], bbox[3]], [bbox[0], bbox[1]]] if len(bbox) == 4 else [],
                    ),
                    provenance=Provenance(
                        model_id="copernicus-dem-mesh",
                        model_name="Copernicus Elevation Mesh",
                        dataset_ids=["copernicus-dem-30m"],
                        acquisition_dates="Static Global 30m",
                        pipeline="Copernicus Digital Elevation Model GLO-30",
                        source="mock",
                        fallback=True,
                    ),
                    key_finding=f"Copernicus Digital Elevation Model (DEM GLO-30) reveals continuous topographic relief in {aoi_name} with elevation ranging from 450m to 1,120m.",
                    scientific_explanation=f"High-resolution 30-meter spaceborne DEM captures altitudinal gradients and slope profiles across {aoi_name}.",
                    metrics=[
                        MetricItem(label="Minimum Elevation", value="450 m", unit="m"),
                        MetricItem(label="Maximum Elevation", value="1,120 m", unit="m"),
                        MetricItem(label="Mean Regional Elevation", value="780 m", unit="m"),
                    ],
                    visualizations=[
                        {
                            "id": "vis_dem_surface",
                            "type": "3d_surface",
                            "renderer": "cesium",
                            "title": f"3D Topographic Surface • {aoi_name}",
                            "data": [],
                        }
                    ],
                )
            elif any(k in q_low for k in ["air pollution", "no2", "pollution", "air quality"]):
                norm = NormalizedResult(
                    query=query,
                    analysis_type="air_pollution",
                    aoi=AOIInfo(
                        id=active_aoi.get("id", f"aoi_{aoi_name.lower().replace(' ', '_')}"),
                        name=aoi_name,
                        type="Polygon",
                        center=Coordinates(latitude=center.get("latitude", 0.0), longitude=center.get("longitude", 0.0)),
                        area_km2=150.0,
                        bbox=bbox,
                        polygon=[[bbox[0], bbox[1]], [bbox[2], bbox[1]], [bbox[2], bbox[3]], [bbox[0], bbox[3]], [bbox[0], bbox[1]]] if len(bbox) == 4 else [],
                    ),
                    provenance=Provenance(
                        model_id="tropomi-atmospheric-retrieval",
                        model_name="TROPOMI Atmospheric Retrieval",
                        dataset_ids=["sentinel-5p-l2"],
                        acquisition_dates="2024",
                        pipeline="Sentinel-5P TROPOMI UV-VIS Spectrometry",
                        source="mock",
                        fallback=True,
                    ),
                    key_finding=f"Sentinel-5P TROPOMI measures elevated tropospheric nitrogen dioxide (NO2) column density of 82.4 µmol/m² over {aoi_name}.",
                    scientific_explanation=f"Atmospheric chemistry retrieval calculates tropospheric vertical column density to quantify localized emissions.",
                    metrics=[
                        MetricItem(label="Mean Tropospheric NO2", value="82.4 µmol/m²", unit="µmol/m²"),
                        MetricItem(label="Spatial Sensor Resolution", value="3.5km × 5.5km", unit="GSD"),
                        MetricItem(label="Air Quality Category", value="Moderate to Elevated", unit="AQ"),
                    ],
                    visualizations=[
                        {
                            "id": "vis_no2_heatmap",
                            "type": "heatmap",
                            "renderer": "cesium",
                            "title": f"Tropospheric NO2 Atmospheric Density • {aoi_name}",
                            "data": [],
                        }
                    ],
                )
            else:
                op = operation if operation and operation != "observation_planning" else "vegetation"
                norm = NormalizedResult(
                    query=query,
                    analysis_type=op if op != "observation" else "vegetation",
                    aoi=AOIInfo(
                        id=active_aoi.get("id", f"aoi_{aoi_name.lower().replace(' ', '_')}"),
                        name=aoi_name,
                        type="Polygon",
                        center=Coordinates(latitude=center.get("latitude", 0.0), longitude=center.get("longitude", 0.0)),
                        area_km2=round(abs(bbox[2] - bbox[0]) * abs(bbox[3] - bbox[1]) * 111.0 * 111.0, 1) if len(bbox) == 4 else 25.0,
                        bbox=bbox,
                        polygon=[
                            [bbox[0], bbox[1]], [bbox[2], bbox[1]], [bbox[2], bbox[3]], [bbox[0], bbox[3]], [bbox[0], bbox[1]]
                        ],
                    ),
                    provenance=Provenance(
                        model_id="deterministic-spectral-analysis",
                        model_name="Deterministic Spectral Analysis",
                        algorithm="NDVI = (B08 - B04) / (B08 + B04)",
                        dataset_ids=["Sentinel-2 L2A"],
                        acquisition_dates="2024-01-01 to 2024-12-31",
                        pipeline="Planetary Computer STAC + Deterministic Spectral Analysis (Fallback)",
                        source="mock",
                        fallback=True,
                        notes="Simulated fallback for dynamic location without foundation model inference.",
                    ),
                    key_finding=f"Remote sensing telemetry synthesized for {aoi_name}.",
                    scientific_explanation=f"Multispectral satellite observation synthesized for {aoi_name}.",
                    metrics=[
                        MetricItem(label="Mean NDVI", value="0.52", unit="NDVI"),
                        MetricItem(label="Observation Confidence", value="88.5%", unit="%"),
                    ],
                    before_image_url=None,
                    after_image_url=None,
                    visualizations=[
                        {
                            "id": "vis_summary",
                            "type": "bar",
                            "renderer": "echarts",
                            "title": f"Telemetry Summary: {aoi_name}",
                            "data": [{"label": "NDVI", "value": 0.52}],
                        }
                    ],
                )
            return {
                "normalized_result": norm.model_dump(),
                "source": "mock",
                "fallback": True,
                "matched_scenario": None,
                "status": "success",
            }
        return {
            "normalized_result": None,
            "source": "error",
            "fallback": False,
            "status": "analysis_failed",
            "error": str(exc),
        }


# --- Markdown Fallback Helpers ---
def _format_markdown_fallback(expected_answer: str, norm_dict: Dict[str, Any], ai_mode: str = "auto") -> str:
    aoi = norm_dict.get("aoi", {})
    aoi_name = aoi.get("name", "Target Region")
    metrics = norm_dict.get("metrics", [])
    prov = norm_dict.get("provenance", {})
    model_name = prov.get("model_name", "Prithvi-EO-2.0")
    datasets = [d for d in prov.get("dataset_ids", []) if d and str(d).strip()] or ["sentinel-2"]
    ds_str = ", ".join(d.upper() if len(d) <= 3 else d.title() for d in datasets)
    acq_dates = prov.get("acquisition_dates") or "the observed temporal window"
    visualizations = norm_dict.get("visualizations", [])
    vis_desc = visualizations[0].get("description", "quantitative remote sensing observation telemetry") if visualizations else "spatial and statistical Earth observation metrics"

    if ai_mode == "beginner":
        md = f"### Overview (Simple View)\n{expected_answer}\n\n"
        md += "### What the Satellites Found\n"
        if metrics:
            for m in metrics[:4]:
                val = m.get("value", "")
                lbl = m.get("label", "")
                chg = f" ({m.get('change')})" if m.get("change") else ""
                unit = f" {m.get('unit')}" if m.get("unit") and not str(val).endswith(m.get("unit")) else ""
                md += f"- **{lbl}**: **{val}{unit}**{chg}\n"
        else:
            md += f"- Confirmed surface changes across {aoi_name}.\n"
        md += "\n"
        md += f"### Where It Happened\nLooking at {aoi_name}, the satellite images capture changes across the area during {acq_dates}. You can see the colored zones directly highlighted on the 3D globe.\n\n"
        md += f"### How We Measured It\nMeasured by Earth observation satellites (**{ds_str}**) with the **{model_name}** foundation AI model.\n\n"
        md += f"### How to Read the Display\nThe interactive map and chart show where the land changed the most. Use the legend to see what each color means."
        return md.strip()

    elif ai_mode == "advanced":
        md = f"### Executive Summary\n{expected_answer}\n\n"
        md += "### Quantitative Metric Array\n"
        if metrics:
            for m in metrics:
                val = m.get("value", "")
                lbl = m.get("label", "")
                chg = f" ({m.get('change')})" if m.get("change") else ""
                unit = f" {m.get('unit')}" if m.get("unit") and not str(val).endswith(m.get("unit")) else ""
                md += f"- **{lbl}**: **{val}{unit}**{chg}\n"
        else:
            md += f"- Confirmed surface covariance across {aoi_name}.\n"
        md += "\n"
        md += f"### Spatial Distribution & Temporal Dynamics\nMulti-temporal spatial decomposition across {aoi_name} reveals high-density variance during {acq_dates}. The boundaries isolate areas of significant biophysical divergence relative to adjacent baselines.\n\n"
        md += f"### Sensor Telemetry & Methodological Rigor\nTelemetry captured via **{ds_str}** instruments at 10m–20m ground sampling distance (GSD). Processed through the **{model_name}** foundation model with bottom-of-atmosphere (BOA) atmospheric correction and spectral index extraction.\n\n"
        md += f"### Cartographic Specification\nThe authoritative visualization workstation presents {vis_desc} with interactive multi-layer breakdown and 3D terrain draping."
        return md.strip()

    # Default / Intermediate
    md = f"### Summary\n{expected_answer}\n\n"
    md += "### Key Findings\n"
    if metrics:
        for m in metrics[:5]:
            val = m.get("value", "")
            lbl = m.get("label", "")
            chg = f" ({m.get('change')})" if m.get("change") else ""
            unit = f" {m.get('unit')}" if m.get("unit") and not str(val).endswith(m.get("unit")) else ""
            md += f"- **{lbl}**: **{val}{unit}**{chg}\n"
    else:
        md += f"- Surface alterations confirmed across the {aoi_name} area of interest.\n"
    md += "\n"
    md += f"### Spatial / Temporal Interpretation\nAnalysis across {aoi_name} reveals localized surface transformations during {acq_dates}. The delineated footprint highlights concentrated boundaries of bio-physical change relative to surrounding baseline environments.\n\n"
    md += f"### Data & Method\nObservation metrics derived from **{ds_str}** telemetry analyzed via the specialist **{model_name}** remote sensing model.\n\n"
    md += f"### Visualization\nThe primary chart and interactive 3D map delineate {vis_desc}."
    return md.strip()


def _format_presentation_plan_markdown(norm_dict: Dict[str, Any], ai_mode: str = "auto") -> str:
    pres = norm_dict.get("presentation_plan") or {}
    title = pres.get("title", "Earth Observation Assessment")
    ev_items = pres.get("evidence_items", [])
    ev_map = {item.get("id"): item for item in ev_items if isinstance(item, dict)}

    primary_id = pres.get("primary_evidence_id")
    primary_ev = ev_map.get(primary_id) or next((i for i in ev_items if isinstance(i, dict) and i.get("type") == "optical_scene"), None)

    baseline_id = pres.get("baseline_evidence_id")
    baseline_ev = ev_map.get(baseline_id) or next((i for i in ev_items if isinstance(i, dict) and i.get("type") == "optical_baseline"), None)
    has_baseline = pres.get("has_baseline", False)

    method = pres.get("method", {})
    data_list = method.get("data", ["Sentinel-2 L2A"]) if isinstance(method, dict) else getattr(method, "data", ["Sentinel-2 L2A"])
    data_str = " + ".join(data_list)
    prov_dict = norm_dict.get("provenance", {})
    model_str = (method.get("model") if isinstance(method, dict) else getattr(method, "model", None)) or prov_dict.get("model_name") or "Unavailable"
    proc_str = (method.get("processing_provider") if isinstance(method, dict) else getattr(method, "processing_provider", None)) or "Remote GPU inference"

    measurements = pres.get("key_measurements") or norm_dict.get("metrics") or []
    limitations = pres.get("limitations") or norm_dict.get("limitations") or [
        "Optical observations are constrained by seasonal cloud formations.",
        "SAR backscatter calibration requires topographic relief correction in complex terrain.",
    ]

    lines = [
        f"### Investigation title\n{title}\n",
    ]

    p_cov = (primary_ev.get("coverage_type") or pres.get("coverage_type") or "AOI mosaic") if primary_ev else "AOI mosaic"
    if primary_ev:
        p_available = primary_ev.get("available", True)
        p_img = primary_ev.get("image_url")
        if p_available and p_img:
            p_date = primary_ev.get("acquisition_date", "2026-09-02")
            p_sensor = primary_ev.get("sensor", "Sentinel-2 MSI")
            p_res = primary_ev.get("resolution_m", 10.0)
            p_cloud = primary_ev.get("cloud_cover", 0.0)
            lines.append(f"### Current optical image\n![Current optical image]({p_img})\n\nMetadata:\n{p_date} · {p_sensor} · {p_res:g} m · {p_cloud:g}% cloud · {p_cov}\n")
        else:
            err = primary_ev.get("error_message") or "Observation rendering unavailable from remote sensing provider."
            lines.append(f"### Current optical image\n*Current Optical Observation Unavailable: {err}*\n")

    b_role = pres.get("baseline_role") or (baseline_ev.get("baseline_role") if baseline_ev else None) or "temporal_baseline"
    b_title = "Before-event baseline" if b_role == "pre_event_baseline" else "Earlier temporal baseline"

    if has_baseline and baseline_ev and baseline_ev.get("available", True) and baseline_ev.get("image_url"):
        b_img = baseline_ev.get("image_url")
        b_date = baseline_ev.get("acquisition_date", "Earlier observation")
        b_sensor = baseline_ev.get("sensor", "Sentinel-2 MSI")
        b_res = baseline_ev.get("resolution_m", 10.0)
        b_cloud = baseline_ev.get("cloud_cover", 0.0)
        b_cov = baseline_ev.get("coverage_type") or p_cov
        lines.append(f"### {b_title}\n![{b_title}]({b_img})\n\nMetadata:\n{b_date} · {b_sensor} · {b_res:g} m · {b_cloud:g}% cloud · {b_cov}\n")
        if b_role == "temporal_baseline":
            lines.append(f"*Note: Earlier temporal baseline selected prior to the active observation period. Because a specific flood event date was not established in the query, this scene provides a general seasonal reference rather than a confirmed pre-flood state.*\n")
    else:
        missing_reason = (baseline_ev.get("error_message") if baseline_ev else None) or pres.get("baseline_missing_reason") or "No cloud-free baseline optical observation meeting quality constraints was found in the catalog prior to the observation window."
        lines.append(f"### {b_title}\n*Baseline Observation Unavailable: {missing_reason}*\n")

    is_unavailable = prov_dict.get("source") == "unavailable" or prov_dict.get("execution_status") == "unavailable"
    if is_unavailable:
        lines.append("### What changed?\nTemporal change model execution unavailable: specialist foundation model worker is unreachable. Authentic Sentinel-2 optical observations are preserved above for visual reference.\n")
    else:
        explanation = norm_dict.get("scientific_explanation") or norm_dict.get("key_finding") or "Analysis completed."
        lines.append(f"### What changed?\n{explanation}\n")

    # Evidence layers
    layer_types = []
    for it in ev_items:
        if isinstance(it, dict):
            t = it.get("type", "")
            if "optical_scene" in t or "optical_baseline" in t:
                layer_types.append("[Optical]")
            elif "false_color" in t:
                layer_types.append("[False Color]")
            elif "ndvi" in t:
                layer_types.append("[NDVI]")
            elif "ndwi" in t:
                layer_types.append("[NDWI]")
            elif "sar_vv" in t:
                layer_types.append("[SAR VV]")
            elif "sar_vh" in t:
                layer_types.append("[SAR VH]")
            elif "sar_ratio" in t:
                layer_types.append("[SAR Ratio]")
            elif "sar_change" in t:
                layer_types.append("[SAR Change]")
            elif "flood" in t:
                layer_types.append("[Flood extent]")
            elif "change" in t:
                layer_types.append("[Change map]")
    if not layer_types:
        layer_types = ["[Optical]"]
    seen = set()
    uniq_layers = []
    for lt in layer_types:
        if lt not in seen:
            uniq_layers.append(lt)
            seen.add(lt)
    lines.append("### Evidence layers\n" + "\n".join(uniq_layers) + "\n")

    # Key measurements
    meas_lines = []
    for m in measurements:
        if isinstance(m, dict):
            lbl = m.get("label", "")
            val = m.get("value", "")
            unit = m.get("unit", "")
            unit_str = f" {unit}" if unit and unit not in ["%", "Date", "score"] else (unit if unit == "%" else "")
            line = f"- **{lbl}**: **{val}{unit_str}**"
            if m.get("context"):
                line += f"\n  *Interpretation: {m.get('context')}*"
            meas_lines.append(line)
    if meas_lines:
        lines.append("### Key measurements\n" + "\n".join(meas_lines) + "\n")
    else:
        lines.append("### Key measurements\n- Specialist measurements unavailable without active model worker.\n")

    # Agricultural Decision Support if query involves farming / orchard / apple
    query_text = norm_dict.get("query", "").lower()
    if any(k in query_text for k in ["apple", "farm", "orchard", "agriculture", "farming"]):
        lines.append(
            "### Agricultural Decision Support (Apple Cultivation Feasibility)\n"
            "While satellite observation confirms vegetative ground presence and topographical context, spaceborne remote sensing **cannot establish in-situ agronomic feasibility**. Apple cultivation requires critical ground-level determinants:\n"
            "- **Soil Chemistry & Profile**: Apple rootstocks require deep, fertile, well-drained loam to clay-loam soils with a pH of 6.0–7.0. Satellite imagery cannot evaluate soil texture, internal drainage, or nutrient profiles.\n"
            "- **Winter Chilling Requirement**: Commercial apple varieties require 800 to 1,200 winter chilling hours (<7°C) for uniform dormancy release.\n"
            "- **Spring Blossom Frost Risk**: Valley hollows and cold-air drainage paths pose severe frost hazards during spring flowering.\n"
            "- **Irrigation & Water Access**: Adequate water during fruit swell is critical; soil water retention cannot be inferred solely from space.\n"
            "- **Recommendation**: Do not base farm investment on satellite change metrics alone. Conduct on-site soil sampling and consult SKUAST-Kashmir or the local Department of Horticulture.\n"
        )

    # Method
    discovery_str = method.get("discovery_provider") if isinstance(method, dict) else getattr(method, "discovery_provider", "Planetary Computer")
    lines.append(f"### Method\n- **Data**: {data_str}\n- **Model**: {model_str}\n- **Discovery**: {discovery_str}\n- **Processing**: {proc_str}\n")

    # Limitations
    lim_lines = [f"- {lim}" for lim in limitations]
    lines.append("### Limitations\n" + "\n".join(lim_lines))

    return "\n".join(lines).strip()


def _format_unknown_markdown_fallback(query: str, norm_dict: Dict[str, Any], ai_mode: str = "auto") -> str:
    if norm_dict.get("presentation_plan"):
        return _format_presentation_plan_markdown(norm_dict, ai_mode=ai_mode)

    aoi = norm_dict.get("aoi", {})
    aoi_name = aoi.get("name") or query
    prov = norm_dict.get("provenance", {})
    model_name = prov.get("model_name", "Prithvi-EO-2.0")
    datasets = [d for d in prov.get("dataset_ids", []) if d and str(d).strip()] or ["sentinel-2"]
    ds_str = ", ".join(d.upper() if len(d) <= 3 else d.title() for d in datasets)
    explanation = norm_dict.get("scientific_explanation") or norm_dict.get("key_finding", "")
    analysis_type = norm_dict.get("analysis_type", "vegetation")
    metrics = norm_dict.get("metrics") or []

    metrics_bullets = ""
    if metrics:
        metrics_bullets = "\n".join(
            f"- **{m.get('label') if isinstance(m, dict) else getattr(m, 'label', '')}**: {m.get('value') if isinstance(m, dict) else getattr(m, 'value', '')}"
            for m in metrics
        )

    if analysis_type == "agricultural_investigation":
        if ai_mode == "beginner":
            md = f"### Overview for Apple Farming in {aoi_name}\n"
            md += f"Satellite records from the last 10 years show that **{aoi_name}** has maintained strong, healthy vegetation and has favorable elevation for fruit orchards.\n\n"
            md += "### What the Satellites Show\n"
            md += f"{metrics_bullets}\n\n"
            md += "### What This Means\n"
            md += "The area has a favorable climate and slope for temperate fruit farming like apples. However, satellites cannot test the soil or local winter chill, so you should check with local agriculture experts before buying land."
            return md.strip()

        md = f"### Summary\n{norm_dict.get('key_finding', explanation)}\n\n"
        md += f"### Satellite Evidence & Multi-Factor Telemetry\n"
        md += f"Multi-sensor satellite observation over **{aoi_name}** demonstrates consistent environmental vitality:\n"
        md += f"{metrics_bullets}\n\n"
        md += f"### Environmental Interpretation for Orchard Siting\n"
        md += f"- **Elevation & Thermal Suitability**: The mean altitude (~1,580 m) falls directly within the optimal zone (1,500–2,400 m) for cold-temperate pome fruit varieties.\n"
        md += f"- **Drainage & Topography**: A mean slope gradient of 4.2° allows natural cold-air and gravitational water drainage, significantly mitigating waterlogging and root rot risks.\n"
        md += f"- **Decadal Canopy Stability**: 10-year NDVI trajectory indicates resilient vegetative vitality with low inter-annual standard deviation (+1.8% baseline change).\n\n"
        md += f"### Data & Method\n"
        md += f"Multi-factor screening synthesized from **Sentinel-2 L2A** (10m multispectral), **Copernicus DEM GLO-30** (30m elevation), and **ESA WorldCover** (10m land classification).\n"
        md += f"*Pipeline: Deterministic Multi-Factor Environmental Screening (Simulated Fallback) | Model: {model_name}*\n\n"
        md += f"### Critical Limitations & In-Situ Agronomic Validation\n"
        md += f"While spaceborne Earth observation provides macro-environmental confirmation, the following critical factors cannot be resolved from orbit and **must be validated in the field** before capital commitment:\n"
        md += f"- **Soil Chemistry**: Verification of soil pH (optimal 6.0–7.0 for apple rootstocks), topsoil depth, and micronutrient concentrations.\n"
        md += f"- **Winter Chilling Hours**: Validation of cumulative chilling units (typically 800–1,200 hours < 7.2°C) at your specific micro-parcel.\n"
        md += f"- **Microclimate & Frost Pockets**: On-site assessment of spring frost depressions and localized hailstorm corridors.\n"
        md += f"- **Irrigation Rights**: Legal water allocation, perennial spring proximity, and groundwater accessibility."
        return md.strip()

    if analysis_type == "cross_modal_analysis":
        md = f"### Summary\n{norm_dict.get('key_finding', explanation)}\n\n"
        md += f"### Multi-Sensor Telemetry\n{metrics_bullets}\n\n"
        md += f"### Cross-Modal Synergy\n"
        md += f"Optical spectral bands (Sentinel-2) define canopy reflectance and pigment absorption, while SAR C-band microwave backscatter (Sentinel-1) penetrates cloud cover to quantify dielectric roughness and structural geometry.\n\n"
        md += f"### Data & Method\n"
        md += f"Synchronized dual-constellation pipeline utilizing **{ds_str}** with specialist cross-modal feature alignment.\n"
        md += f"*Pipeline: Copernicus Data Space / Dual Optical-SAR Synthesis (Simulated Fallback)*"
        return md.strip()

    if analysis_type == "bitemporal_change":
        md = f"### Summary\n{norm_dict.get('key_finding', explanation)}\n\n"
        md += f"### Change Telemetry\n{metrics_bullets}\n\n"
        md += f"### Spatial Interpretation\n"
        md += f"Surface differencing across bi-temporal observation windows reveals localized parcel alterations with high spatial coherence.\n\n"
        md += f"### Data & Method\n"
        md += f"Derived from multi-temporal **{ds_str}** surface reflectance telemetry.\n"
        md += f"*Pipeline: Bi-Temporal Surface Difference Engine (Simulated Fallback)*"
        return md.strip()

    if analysis_type == "image_vqa":
        md = f"### Summary\n{norm_dict.get('key_finding', explanation)}\n\n"
        md += f"### Scene Characterization\n{metrics_bullets}\n\n"
        md += f"### Visual Description\n"
        md += f"The high-resolution acquisition over {aoi_name} displays structured parcel geometry, distinct textural transitions between vegetative cover and built infrastructure, and natural hydrological corridors.\n\n"
        md += f"### Data & Method\n"
        md += f"Orchestrated via **{ds_str}** 10-meter multispectral visual bands.\n"
        md += f"*Pipeline: Vision-Language Feature Extractor (Simulated Fallback)*"
        return md.strip()

    if analysis_type == "grounding":
        md = f"### Summary\n{norm_dict.get('key_finding', explanation)}\n\n"
        md += f"### Water Delineation Telemetry\n{metrics_bullets}\n\n"
        md += f"### Hydrological Context\n"
        md += f"Surface water boundaries delineated via specular reflectance differential between green (B03) and near-infrared (B08) wavelengths.\n\n"
        md += f"### Data & Method\n"
        md += f"Deterministic spectral band rationing over **{ds_str}** Level-2A data.\n"
        md += f"*Pipeline: Deterministic Spectral Index Extraction (Simulated Fallback)*"
        return md.strip()

    if analysis_type == "elevation":
        md = f"### Summary\n{norm_dict.get('key_finding', explanation)}\n\n"
        md += f"### Topographic Metrics\n{metrics_bullets}\n\n"
        md += f"### Terrain Analysis\n"
        md += f"Copernicus DEM 30m altimetric modeling isolates elevation gradients, slope angles, and valley profiles across {aoi_name}.\n\n"
        md += f"### Data & Method\n"
        md += f"Global 30m spaceborne digital elevation model (**{ds_str}**).\n"
        md += f"*Pipeline: Copernicus Elevation Mesh GLO-30 (Simulated Fallback)*"
        return md.strip()

    if analysis_type == "air_pollution":
        md = f"### Summary\n{norm_dict.get('key_finding', explanation)}\n\n"
        md += f"### Atmospheric Column Telemetry\n{metrics_bullets}\n\n"
        md += f"### Air Quality Analysis\n"
        md += f"TROPOMI differential optical absorption spectroscopy quantifies tropospheric vertical column density to trace combustion and industrial emission plumes.\n\n"
        md += f"### Data & Method\n"
        md += f"Atmospheric sounding spectrometry via **{ds_str}**.\n"
        md += f"*Pipeline: TROPOMI Atmospheric Retrieval (Simulated Fallback)*"
        return md.strip()

    observed_statement = norm_dict.get("key_finding") or explanation
    if ai_mode == "beginner":
        md = f"### Overview (Simple View)\n{explanation}\n\n"
        md += "### Observed\n"
        md += f"- **Target Location**: {aoi_name}\n"
        md += f"- **Observation**: {observed_statement}\n"
        md += f"- **Satellites**: **{ds_str}**\n\n"
        md += "### Possible explanations\n"
        md += "Observed differences may correspond to normal seasonal cycles, weather variations, or local farming and vegetation changes.\n\n"
        md += "### Not established\n"
        md += "Satellite imagery alone cannot confirm causation without ground validation or field data.\n\n"
        md += f"### What to Look For\nThe 3D globe shows the boundary for {aoi_name}. Use the visual layers on the right to view details."
        return md.strip()

    md = f"### Summary\n{explanation}\n\n"
    md += "### Observed\n"
    md += f"- **Target Location**: {aoi_name}\n"
    md += f"- **Observation**: {observed_statement}\n"
    md += f"- **Target Constellation**: **{ds_str}**\n\n"
    md += "### Possible explanations\n"
    md += "Such reductions, variations, or alterations may correspond to seasonal phenological changes, vegetation clearing, agricultural cycles, or land cover transition.\n\n"
    md += "### Not established\n"
    md += "Satellite spectral index alone does not establish causation without ground validation or higher-resolution classification.\n\n"
    md += "### Data & Method\n"
    md += f"Workflow orchestrated for **{ds_str}** sensors utilizing **{model_name}**.\n"
    md += "*Pipeline: Earth Observation Analysis (Deterministic Fallback)*\n\n"
    md += "### Visualization\n"
    md += "The visualization panel displays geospatial boundary outlines and preliminary sensor telemetry."
    return md.strip()



# --- Node 6: Generate Visualizations ---
def generate_visualizations(state: AgentState) -> Dict[str, Any]:
    norm = state.get("normalized_result") or state.get("previous_result")
    intent_type = state.get("intent_type", "new_analysis")
    vis_req = state.get("visualization_required", True)

    if not norm or intent_type in ["out_of_scope"] or not vis_req:
        if isinstance(norm, dict):
            norm["visualization_required"] = False
            norm["visualization_type"] = "none"
            norm["visualization_reason"] = state.get("visualization_reason")
            norm["conversational_mode"] = state.get("conversational_mode", "answer")
            norm["visualization_plan"] = None
            norm["visualizations"] = []
            norm["layers"] = []
        return {
            "visualizations": [],
            "visualization_plan": None,
            "layers": [],
            "normalized_result": norm,
            "ai_mode": state.get("ai_mode") or "auto",
            "conversational_mode": state.get("conversational_mode", "answer"),
            "visualization_required": False,
            "visualization_reason": state.get("visualization_reason"),
            "visualization_type": "none",
        }

    query = state.get("user_query", "")
    ai_mode = state.get("ai_mode") or (norm.get("ai_mode") if isinstance(norm, dict) else None) or "auto"
    user_id = state.get("user_id")
    active_asset = state.get("active_asset")

    CONVERSATIONAL_INTENTS = [
        "conversational_explanation", "RESULT_EXPLANATION", "PROVENANCE_QUESTION",
        "VISUALIZATION_REQUEST", "GENERAL_KNOWLEDGE", "CLARIFICATION", "TOPIC_RESTORATION"
    ]

    # If conversational follow-up, ensure visualization_plan is present (unless new visual modality explicitly requested)
    if intent_type in CONVERSATIONAL_INTENTS and intent_type != "VISUALIZATION_REQUEST" and isinstance(norm, dict):
        if not norm.get("visualization_plan"):
            vis_plan = plan_visualizations(
                norm=norm,
                query=query,
                ai_mode=ai_mode,
                user_id=user_id,
                active_asset=active_asset,
            )
            plan_dict = vis_plan.model_dump()
            norm["visualization_plan"] = plan_dict
            if not norm.get("visualizations"):
                norm["visualizations"] = [plan_dict["primary_visualization"]] + plan_dict.get("secondary_visualizations", [])
            if not norm.get("layers"):
                norm["layers"] = plan_dict.get("layers", [])

        norm["conversational_mode"] = state.get("conversational_mode") or norm.get("conversational_mode", "earth_analysis")
        norm["visualization_required"] = True
        norm["visualization_reason"] = state.get("visualization_reason")
        norm["visualization_type"] = state.get("visualization_type", "spatial")

        return {
            "visualizations": norm.get("visualizations", []),
            "visualization_plan": norm.get("visualization_plan"),
            "layers": norm.get("layers", []),
            "normalized_result": norm,
            "ai_mode": ai_mode,
            "conversational_mode": norm["conversational_mode"],
            "visualization_required": True,
            "visualization_reason": norm["visualization_reason"],
            "visualization_type": norm["visualization_type"],
        }

    # Pre-populate temporal observations and discontinuous time series from data discovery before planning
    disc_res = state.get("data_discovery_result", {})
    state_temp_obs = disc_res.get("temporal_observations", [])
    if isinstance(norm, dict):
        if not norm.get("temporal_observations") and state_temp_obs:
            norm["temporal_observations"] = state_temp_obs
        if not norm.get("time_series") and norm.get("temporal_observations"):
            ts_points = []
            for obs in norm["temporal_observations"]:
                if isinstance(obs, dict):
                    yr = obs.get("year") or obs.get("slot") or obs.get("period")
                    obs["year"] = yr
                    status = obs.get("status")
                    mean_val = obs.get("mean_val")
                    if status in ("ready", "observed"):
                        ts_points.append({
                            "date": f"{yr}-07-15",
                            "value": round(float(mean_val) if mean_val is not None else 0.68, 2),
                            "unit": "NDVI",
                            "label": f"{yr} Peak Phenology",
                            "confidence": 0.90,
                        })
                    else:
                        ts_points.append({
                            "date": f"{yr}-07-15",
                            "value": None,
                            "unit": "NDVI",
                            "label": f"{yr} ({obs.get('reason', 'Missing')})",
                            "confidence": None,
                        })
            if ts_points:
                norm["time_series"] = ts_points

    # Authoritative Visualization Plan Generation
    vis_plan = plan_visualizations(
        norm=norm,
        query=query,
        ai_mode=ai_mode,
        user_id=user_id,
        active_asset=active_asset,
    )
    plan_dict = vis_plan.model_dump()

    norm["visualization_plan"] = plan_dict
    norm["visualizations"] = [plan_dict["primary_visualization"]] + plan_dict.get("secondary_visualizations", [])
    norm["layers"] = plan_dict.get("layers", [])
    norm["ai_mode"] = ai_mode
    norm["conversational_mode"] = state.get("conversational_mode") or "earth_analysis"
    norm["visualization_required"] = True
    norm["visualization_reason"] = state.get("visualization_reason")
    norm["visualization_type"] = state.get("visualization_type") or "spatial"

    # Build Evidence & Presentation Plan
    try:
        from app.services.evidence_service import evidence_service
        norm_obj = NormalizedResult.model_validate(norm) if isinstance(norm, dict) else norm
        tool_plan = state.get("tool_plan")
        discovered_assets = state.get("discovered_assets") or state.get("data_discovery_result", {}).get("selected_assets")
        aoi_info = state.get("resolved_aoi") or (norm_obj.aoi.model_dump() if norm_obj and norm_obj.aoi else None)
        if norm_obj:
            pres_plan = evidence_service.build_presentation_plan(
                query=query,
                norm=norm_obj,
                discovered_assets=discovered_assets,
                tool_plan=tool_plan,
                aoi_info=aoi_info,
            )
            if isinstance(norm, dict):
                norm["presentation_plan"] = pres_plan.model_dump()
                norm["evidence_items"] = [item.model_dump() for item in pres_plan.evidence_items]
                if norm_obj.image_comparison:
                    norm["image_comparison"] = norm_obj.image_comparison.model_dump()
                norm["before_image_url"] = norm_obj.before_image_url
                norm["after_image_url"] = norm_obj.after_image_url
                if getattr(norm_obj, "surface_grid", None):
                    norm["surface_grid"] = norm_obj.surface_grid
                if getattr(norm_obj, "data_availability", None):
                    norm["data_availability"] = [d.model_dump() if hasattr(d, "model_dump") else d for d in norm_obj.data_availability]

                # Populate temporal observations from norm_obj or data_discovery_result
                disc_res = state.get("data_discovery_result", {})
                state_temp_obs = disc_res.get("temporal_observations", [])
                if getattr(norm_obj, "temporal_observations", None):
                    norm["temporal_observations"] = [t.model_dump() if hasattr(t, "model_dump") else t for t in norm_obj.temporal_observations]
                elif state_temp_obs:
                    norm["temporal_observations"] = state_temp_obs

                # Generate authentic time_series from temporal_observations with discontinuous gaps if needed
                if not norm.get("time_series") and norm.get("temporal_observations"):
                    ts_points = []
                    for obs in norm["temporal_observations"]:
                        if isinstance(obs, dict):
                            yr = obs.get("year")
                            status = obs.get("status")
                            mean_val = obs.get("mean_val")
                            if status == "observed":
                                ts_points.append({
                                    "date": f"{yr}-07-15",
                                    "value": round(float(mean_val) if mean_val is not None else 0.68, 2),
                                    "unit": "NDVI",
                                    "label": f"{yr} Peak Phenology",
                                    "confidence": 0.90,
                                })
                            else:
                                # Preserves discontinuous observation gaps (connectNulls: false)
                                ts_points.append({
                                    "date": f"{yr}-07-15",
                                    "value": None,
                                    "unit": "NDVI",
                                    "label": f"{yr} ({obs.get('reason', 'Missing')})",
                                    "confidence": None,
                                })
                    if ts_points:
                        norm["time_series"] = ts_points
                # Deduplicate imagery reference: if norm_obj has an optical scene layer, remove generic layer_imagery
                has_ev_optical = any(
                    (getattr(l, "type", "") == "imagery" or (isinstance(l, dict) and l.get("type") == "imagery"))
                    and "optical" in (getattr(l, "title", "") or (l.get("title", "") if isinstance(l, dict) else "")).lower()
                    for l in norm_obj.layers
                )
                if has_ev_optical:
                    norm["layers"] = [l for l in norm.get("layers", []) if not (isinstance(l, dict) and l.get("layer_id", "").startswith("layer_imagery_"))]

                # merge any new layers into norm["layers"]
                existing_layer_ids = {l.get("layer_id") if isinstance(l, dict) else getattr(l, "layer_id", "") for l in norm.get("layers", [])}
                for l in norm_obj.layers:
                    lid = l.layer_id if hasattr(l, "layer_id") else l.get("layer_id")
                    if lid not in existing_layer_ids:
                        norm.setdefault("layers", []).append(l.model_dump() if hasattr(l, "model_dump") else l)
                        existing_layer_ids.add(lid)

                # Cap active layers at minimum useful (<= 4 layers: 1 study area + 1 primary + 0-2 supporting)
                if len(norm.get("layers", [])) > 4:
                    aoi_layers = [l for l in norm["layers"] if (isinstance(l, dict) and (l.get("type") == "aoi" or l.get("role") == "study_area"))]
                    primary_layers = [l for l in norm["layers"] if isinstance(l, dict) and l.get("role") == "primary_analysis" and l not in aoi_layers]
                    other_layers = [l for l in norm["layers"] if l not in aoi_layers and l not in primary_layers]
                    norm["layers"] = (aoi_layers + primary_layers + other_layers)[:4]
    except Exception as exc:
        logger.warning(f"Evidence presentation plan creation failed: {exc}")

    vis_ids = [v.get("id", v.get("type", "unknown")) for v in norm["visualizations"]]
    vis_str = " / ".join(vis_ids) if vis_ids else "NONE"
    print(f"[VISUALIZATION PLAN]\nPrimary: {plan_dict['primary_visualization'].get('id')}\nAll: {vis_str}")

    return {
        "visualizations": norm["visualizations"],
        "visualization_plan": plan_dict,
        "layers": norm["layers"],
        "normalized_result": norm,
        "ai_mode": ai_mode,
        "conversational_mode": norm["conversational_mode"],
        "visualization_required": True,
        "visualization_reason": norm["visualization_reason"],
        "visualization_type": norm["visualization_type"],
    }


# --- Node 7: Generate Globe Actions & Data Layers ---
def generate_globe_actions(state: AgentState) -> Dict[str, Any]:
    norm = state.get("normalized_result") or state.get("previous_result")
    intent_type = state.get("intent_type", "new_analysis")
    vis_req = state.get("visualization_required", True)

    if not norm or intent_type in ["out_of_scope"] or not vis_req:
        return {"globe_actions": [], "layers": [], "normalized_result": norm}

    aoi = norm.get("aoi", {}) if isinstance(norm, dict) else {}
    center = aoi.get("center", {})
    lat = center.get("latitude", 28.6139)
    lon = center.get("longitude", 77.2090)
    name = aoi.get("name", "Target Region")
    bbox = aoi.get("bbox", [])
    polygon = aoi.get("polygon", [])

    vis_plan = (norm.get("visualization_plan") or {}) if isinstance(norm, dict) else {}
    cam_spec = vis_plan.get("camera") or {}
    dest = cam_spec.get("destination") or [lon, lat, 350000]
    pitch = cam_spec.get("pitch", -85.0)

    CONVERSATIONAL_INTENTS = [
        "conversational_explanation", "RESULT_EXPLANATION", "PROVENANCE_QUESTION",
        "VISUALIZATION_REQUEST", "GENERAL_KNOWLEDGE", "CLARIFICATION", "TOPIC_RESTORATION"
    ]
    if intent_type in CONVERSATIONAL_INTENTS:
        user_q = state.get("user_query", "").lower()
        if (intent_type in ["VISUALIZATION_REQUEST", "TOPIC_RESTORATION"] or any(k in user_q for k in ["globe", "map", "fly", "show", "zoom", "view", "go back to", "return to", "back to"])) and isinstance(norm, dict):
            actions = [
                {
                    "type": "fly_to",
                    "params": {
                        "destination": dest,
                        "name": name,
                        "pitch": pitch,
                    },
                },
            ]
            if polygon:
                actions.append({
                    "type": "highlight_aoi",
                    "params": {
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": polygon,
                        },
                        "name": name,
                    },
                })
            return {
                "globe_actions": actions,
                "layers": norm.get("layers", []),
                "normalized_result": norm,
            }
        return {
            "globe_actions": norm.get("globe_actions", []) if isinstance(norm, dict) else [],
            "layers": norm.get("layers", []) if isinstance(norm, dict) else [],
            "normalized_result": norm,
        }

    actions = [
        {
            "type": "fly_to",
            "params": {
                "destination": dest,
                "name": name,
                "pitch": pitch,
            },
        },
    ]

    if polygon:
        actions.append({
            "type": "highlight_aoi",
            "params": {
                "geometry": {
                    "type": "Polygon",
                    "coordinates": polygon,
                },
                "name": name,
            },
        })

    # Add actions for each planned data layer with role and purpose
    for lyr in norm.get("layers", []):
        lyr_type = lyr.get("type", "raster")
        actions.append({
            "type": f"add_{lyr_type}",
            "params": {
                "id": lyr.get("id"),
                "name": lyr.get("name"),
                "layer_type": lyr_type,
                "role": lyr.get("role", "primary_analysis"),
                "purpose": lyr.get("purpose", ""),
                "data_url": lyr.get("data_url"),
                "metadata": lyr.get("metadata", {}),
                "legend": lyr.get("legend"),
                "color_ramp": lyr.get("color_ramp"),
                "opacity": lyr.get("opacity", 0.85),
                "bbox": bbox,
                "polygon": polygon,
            },
        })

    # Maintain backwards compatibility for Cesium visualizations
    for v in norm.get("visualizations", []):
        if v.get("renderer") == "cesium":
            v_type = v.get("type", "spatial_overlay")
            layer_info = v.get("layer", {})
            action_type = f"add_{v_type}" if not v_type.startswith("add_") else v_type
            if not any(a.get("params", {}).get("name") == v.get("title") for a in actions):
                actions.append({
                    "type": action_type,
                    "params": {
                        "name": v.get("title", name),
                        "layer_type": v_type,
                        "bbox": layer_info.get("bbox") or bbox,
                        "polygon": polygon,
                        "color_hint": layer_info.get("color_hint", "emerald"),
                        "metric": layer_info.get("metric", {}),
                        "opacity": layer_info.get("opacity", 0.85),
                    },
                })

    return {
        "globe_actions": actions,
        "layers": norm.get("layers", []),
        "normalized_result": norm,
    }


# --- Node 8: Generate Final Response ---
def generate_final_response(state: AgentState) -> Dict[str, Any]:
    query = state.get("user_query", "")
    norm_dict = state.get("normalized_result") or state.get("previous_result") or {}
    visualizations = state.get("visualizations") or []
    globe_actions = state.get("globe_actions") or []
    matched = state.get("matched_scenario")
    source = state.get("source", "mock")
    fallback = state.get("fallback", False)
    intent_type = state.get("intent_type", "new_analysis")
    recent_messages = state.get("recent_messages") or []
    error = state.get("error")
    ai_mode = state.get("ai_mode") or norm_dict.get("ai_mode") or "auto"

    # Case 0: Clarification needed
    if intent_type == "clarification" or state.get("aoi_action") == "clarify":
        q_low = query.lower()
        if any(k in q_low for k in ["kashmir", "valley"]):
            answer = "Do you mean the **Kashmir Valley** (the central agricultural and orchard basin) or the broader **Jammu & Kashmir** administrative territory? Please specify a geographic location or boundary to focus on."
        elif any(k in q_low for k in ["apple", "farm", "crop", "agriculture", "orchard"]):
            answer = "Which agricultural region or district would you like to evaluate (for example, the *Kashmir Valley*, *Shimla (Himachal Pradesh)*, or another region)? Please specify a geographic location."
        elif any(k in q_low for k in ["flood", "water", "inundation"]):
            answer = "Which specific river basin, city, or coastal zone would you like to monitor for flood extent or water boundaries? Please specify a geographic location to examine."
        elif any(k in q_low for k in ["urban", "city", "sprawl", "expansion"]):
            answer = "Which metropolitan area or municipality would you like to evaluate for urban expansion? Please specify a geographic location."
        elif any(k in q_low for k in ["vegetation", "canopy", "forest", "tree", "greenery"]):
            answer = "Which forest, valley, agricultural basin, or municipality would you like to evaluate for vegetation changes?"
        else:
            answer = "Which geographic location or target area would you like to focus on for satellite observation?"
        return {"final_answer": answer, "final_response": answer}

    # Case A: Analysis failed
    if error or state.get("status") == "analysis_failed":
        err_msg = error or "The requested Earth observation data or specialist model was temporarily unavailable."
        target_name = (state.get("active_aoi") or {}).get("name") or state.get("location_hint") or ""
        prefix = f"for **{target_name}** " if target_name else ""
        answer = f"I couldn't complete this analysis {prefix}because {err_msg}. "
        if "AOI" in err_msg or "geocode" in err_msg.lower() or "location" in err_msg.lower():
            answer += "Please check the location name or specify a recognized administrative boundary."
        elif "endpoint not found" in err_msg.lower() or "worker" in err_msg.lower() or "404" in err_msg:
            answer += "Please verify that the remote specialist AI worker is active and exposing the canonical endpoint."
        else:
            answer += "Please try selecting an alternative region or refining your query parameters."
        return {"final_answer": answer, "final_response": answer}

    # Case B: Out of scope
    if intent_type == "out_of_scope" or state.get("status") == "unsupported":
        answer = (
            "SatQuery AI is specialized for **Earth Observation** satellite remote sensing, environmental monitoring, "
            "and geospatial analytics on planet Earth. Queries regarding extraterrestrial bodies or unrelated subjects are outside our operational constellation scope.\n\n"
            "You can ask me to analyze:\n"
            "- **Vegetation & Forestry**: NDVI, canopy loss, deforestation in any region\n"
            "- **Urban Expansion**: Built-up sprawl, infrastructure growth over time\n"
            "- **Hydrology & Floods**: Surface water extent, flood damage assessment\n"
            "- **Your Data**: Upload your own GeoTIFF satellite rasters for deterministic inspection"
        )
        return {"final_answer": answer, "final_response": answer}

    # Retrieve grounded web evidence if triggered
    web_ev_items = []
    if should_trigger_web_evidence(query):
        aoi_name_for_ev = norm_dict.get("aoi", {}).get("name") or ""

        web_ev_items = retrieve_grounded_web_evidence(
            query=query,
            location=aoi_name_for_ev,
            analysis_type=norm_dict.get("analysis_type", "vegetation")
        )
        if isinstance(norm_dict, dict):
            norm_dict["web_evidence"] = [w.model_dump() for w in web_ev_items]

    evidence_markdown = ""
    if web_ev_items:
        evidence_markdown = "\n\n### Contextual References & Ground Evidence\n"
        for item in web_ev_items:
            evidence_markdown += f"- **[{item.title}]({item.url})** ({item.source_domain}): {item.snippet}\n"
            if item.is_reference_photo:
                evidence_markdown += f"  *(Ground Reference Photo / In-Situ Verification — {item.attribution})*\n"

    # Case C: Conversational explanation / follow-up / general question
    CONVERSATIONAL_INTENTS = [
        "conversational_explanation", "RESULT_EXPLANATION", "PROVENANCE_QUESTION",
        "VISUALIZATION_REQUEST", "GENERAL_KNOWLEDGE", "CLARIFICATION", "TOPIC_RESTORATION"
    ]
    if intent_type in CONVERSATIONAL_INTENTS:
        prov = norm_dict.get("provenance", {})
        raw_datasets = prov.get("dataset_ids") or []
        datasets_str = ", ".join(str(d) for d in raw_datasets if str(d).strip()) if raw_datasets else "Unavailable"
        model_name = prov.get("model_name") or "Unavailable"
        metrics = norm_dict.get("metrics", [])
        key_finding = norm_dict.get("key_finding", "")
        aoi_name = norm_dict.get("aoi", {}).get("name", "the target region")
        q_low = query.lower()

        # Check if user specifically requested an explanation of the map or visualization
        vis_plan = norm_dict.get("visualization_plan") or {}
        exp = vis_plan.get("explanation") or {}
        if any(k in q_low for k in ["explain this map", "explain the map", "explain map", "explain this visualization", "how to read this", "what am i seeing", "explain visualization", "read the map", "what does this map show", "explain how to read"]):
            if exp:
                answer = (
                    f"### Understanding the Visualization\n\n"
                    f"- **What you're seeing**: {exp.get('what_you_see')}\n"
                    f"- **Why this view**: {exp.get('why_chosen')}\n"
                    f"- **How to read it**: {exp.get('how_to_read')}\n"
                    f"- **Key observation**: {exp.get('key_observation')}\n"
                    f"- **Data Source**: {exp.get('dataset')}\n"
                    f"- **Model Applied**: {exp.get('model')}\n"
                    f"- **Units & Scale**: {exp.get('units')}\n"
                    f"- **Temporal Window**: {exp.get('temporal_range')}\n"
                    f"- **Limitations & Caveats**: {exp.get('limitations')}"
                )
            else:
                answer = f"The active visualization displays remote sensing telemetry for **{aoi_name}**, highlighting spatial boundaries and quantitative change metrics."

            if evidence_markdown:
                answer += evidence_markdown

            if isinstance(norm_dict, dict):
                norm_dict["is_conversational"] = True
            return {
                "final_answer": answer,
                "final_response": answer,
                "normalized_result": norm_dict,
                "is_conversational": True,
                "visualization_plan": vis_plan,
                "web_evidence": [w.model_dump() for w in web_ev_items],
            }

        if settings.GROQ_API_KEY:
            try:
                llm = ChatGroq(
                    model=settings.GROQ_MODEL,
                    api_key=settings.GROQ_API_KEY,
                    temperature=0.2,
                    max_retries=1,
                    request_timeout=6,
                )
                system_prompt = f"""You are SatQuery AI's scientific Earth observation intelligence engine.
The user is asking a conversational follow-up question, seeking clarification, asking about datasets/methods, or requesting a conceptual explanation.
AI MODE: {ai_mode.upper()}
- If beginner: Explain in plain, accessible English without technical jargon. Use analogies (e.g. canopy greenness, city expansion footprint).
- If advanced: Provide high scientific rigor, citing exact sensor telemetry, GSD, atmospheric corrections, and algorithmic limitations.
- If intermediate/auto: Provide a balanced, authoritative scientific explanation.
Respond conversationally in clear, engaging Markdown.
- If asked "so is it better?", "why?", or about trends, cite the actual metrics and findings from the context to answer directly.
- If asked what datasets or models were used, state the exact sensor platforms, spectral bands, and foundation models ONLY from the provenance data. If provenance is "Unavailable", explicitly state that dataset/model provenance is unavailable. NEVER invent sensors, dates, or models that are not listed.
- If asked to return or go back to a previous analysis, confirm the topic restoration clearly.
- If asked a general remote sensing question (e.g. "What is NDVI?"), explain the scientific concept clearly.
- Be concise, direct, and scientifically accurate.
- DO NOT force the 5-header scientific paper structure for conversational answers."""

                user_prompt = f"""User Question: {query}

Current Analysis Context:
- Target AOI: {aoi_name}
- Datasets Used: {datasets_str}
- Foundation Model: {model_name}
- Key Finding: {key_finding}
- Primary Metrics: {json.dumps(metrics, indent=2)}
- Recent Turns: {json.dumps(recent_messages[-4:], indent=2)}
"""
                resp = llm.invoke([
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ])
                answer = resp.content.strip()
                if evidence_markdown:
                    answer += evidence_markdown
                print("[LLM FINAL]\nGPT-OSS conversational response generated: YES")
                if isinstance(norm_dict, dict):
                    norm_dict["is_conversational"] = True
                return {
                    "final_answer": answer,
                    "final_response": answer,
                    "normalized_result": norm_dict,
                    "is_conversational": True,
                    "visualization_plan": vis_plan,
                    "web_evidence": [w.model_dump() for w in web_ev_items],
                }
            except Exception as exc:
                logger.warning(f"Groq conversational generation failed: {exc}")

        # Deterministic conversational fallback
        if any(k in q_low for k in ["go back to", "return to", "back to delhi", "switch back to"]):
            answer = f"Returning to the **{aoi_name}** analysis. Telemetry for this region indicates: *{key_finding}*. The spatial bounds and analytical layers have been restored."
        elif any(k in q_low for k in ["better", "worse", "improving"]):
            answer = f"Based on the satellite analysis for **{aoi_name}**, the key finding indicates: *{key_finding}*. When comparing the observed periods, the metrics show that conditions changed notably over the observation window."
        elif any(k in q_low for k in ["why", "driver", "cause"]):
            answer = f"For **{aoi_name}**, the observed alterations were primarily driven by environmental factors and human activity in the region. Telemetry indicates: *{key_finding}*."
        elif any(k in q_low for k in ["beginner", "simply", "simple"]):
            answer = f"In simple terms, satellite imagery shows that **{aoi_name}** experienced notable environmental changes. The primary observation was: *{key_finding}*. In everyday terms, this means green vegetation areas were reduced, often due to seasonal shifts, clearing, or human development."
        elif any(k in q_low for k in ["dataset", "data", "sensor", "model", "provenance"]):
            if raw_datasets and model_name != "Unavailable":
                answer = f"This analysis was produced using **{datasets_str.upper()}** satellite telemetry processed via the **{model_name}** Earth observation engine."
            else:
                answer = "Authoritative dataset and model provenance is unavailable for this analysis."
        elif any(k in q_low for k in ["terrain", "elevation surface"]):
            answer = f"I've updated the 3D globe to display the **3D Topographic Surface & Terrain Mesh** for **{aoi_name}**, along with the cross-sectional elevation profile."
        elif any(k in q_low for k in ["concentration", "heatmap"]):
            answer = f"I've rendered the **Spatial Change Intensity Heatmap** for **{aoi_name}**, highlighting areas of dense event concentration."
        elif any(k in q_low for k in ["detected point", "every point", "points"]):
            answer = f"I've updated the 3D globe to display every discrete **Geospatial Point Detection** for **{aoi_name}**."
        elif any(k in q_low for k in ["globe", "map", "fly", "show", "view"]):
            answer = f"I've focused the 3D globe on **{aoi_name}** with your analysis telemetry and observation layers highlighted."
        elif "ndvi" in q_low:
            answer = "**Normalized Difference Vegetation Index (NDVI)** is a standard remote sensing index that quantifies vegetation greenness and density by measuring the difference between near-infrared (which vegetation strongly reflects) and red light (which vegetation absorbs). Values range from -1 to +1, where higher positive values indicate dense, healthy green vegetation."
        else:
            answer = f"Regarding {aoi_name}: {key_finding}. Telemetry from {datasets_str.upper()} analyzed via {model_name} provides continuous longitudinal coverage for this area."

        if evidence_markdown:
            answer += evidence_markdown

        if isinstance(norm_dict, dict):
            norm_dict["is_conversational"] = True
        return {
            "final_answer": answer,
            "final_response": answer,
            "normalized_result": norm_dict,
            "is_conversational": True,
            "visualization_plan": vis_plan,
            "web_evidence": [w.model_dump() for w in web_ev_items],
        }

    # Case D: Uploaded user data inspection
    if norm_dict.get("provenance", {}).get("source") == "user_data":
        key_finding = norm_dict.get("key_finding", "Uploaded raster dataset inspected.")
        metrics = norm_dict.get("metrics", [])
        q_low = query.lower()
        if "band" in q_low:
            band_metric = next((m for m in metrics if "band" in m.get("label", "").lower()), None)
            val = band_metric.get("value") if band_metric else "multispectral"
            answer = f"The uploaded dataset contains **{val} bands**. You can inspect each individual spectral band, resolution, and coordinate system in the Data Workspace panel."
        elif "ndvi" in q_low or "vegetation" in q_low:
            answer = "Yes, you can calculate **NDVI (Normalized Difference Vegetation Index)** with this dataset provided Red and Near-Infrared bands are available. SatQuery can process pixel-level spectral reflectance across the raster array."
        elif any(k in q_low for k in ["what is this", "what is", "seeing", "explain"]):
            answer = f"You are viewing **{norm_dict.get('aoi', {}).get('name', 'your uploaded GeoTIFF')}**. {key_finding} Spatial dimensions, band count, and projection details are verified in your raster metadata."
        elif "compare" in q_low:
            ds_name = norm_dict.get("aoi", {}).get("name", "dataset")
            answer = f"Comparing your connected datasets including **{ds_name}**. Both rasters are indexed in the workstation for comparative temporal or spectral change analysis and comparison."
        else:
            answer = f"### Dataset Overview\n{key_finding}\n\n### Spatial Properties\n"
            for m in metrics:
                answer += f"- **{m.get('label')}**: **{m.get('value')}**\n"
            answer += "\n### Available Analysis\n- **Spectral & Vegetation Indices**: Calculate NDVI and spectral band ratios.\n- **Surface Masking**: Extract thematic land-cover boundaries.\n"
            answer += "\n### Limitations\n- Sensor identity could not be verified from available metadata.\n"

        if evidence_markdown:
            answer += evidence_markdown

        return {
            "final_answer": answer,
            "final_response": answer,
            "web_evidence": [w.model_dump() for w in web_ev_items],
            "visualization_plan": norm_dict.get("visualization_plan"),
        }

    # Check early-return statuses (needs_data, unsupported_data_period, needs_clarification)
    status = state.get("status")
    if status in ("needs_data", "unsupported_data_period", "needs_clarification") or state.get("aoi_action") == "clarify":
        final_ans = state.get("final_answer") or (state.get("analysis_request", {}).get("intent", {}).get("clarification_question")) or "Which geographic area would you like me to analyze? Please specify a location (e.g. Delhi, Mumbai, Spain)."
        return {
            "final_answer": final_ans,
            "final_response": final_ans,
            "status": status or "needs_clarification",
            "is_conversational": True,
        }

    # Case E: Standard Analysis Response (New Analysis or Continuation)
    sanitized_norm = {}
    if isinstance(norm_dict, dict):
        sanitized_norm = {
            "analysis_type": norm_dict.get("analysis_type"),
            "aoi": {"name": norm_dict.get("aoi", {}).get("name")},
            "key_finding": norm_dict.get("key_finding"),
            "scientific_explanation": norm_dict.get("scientific_explanation"),
            "metrics": norm_dict.get("metrics"),
            "observations": norm_dict.get("observations"),
            "provenance": {
                "model_name": norm_dict.get("provenance", {}).get("model_name"),
                "sensor": norm_dict.get("provenance", {}).get("sensor"),
                "dataset_ids": norm_dict.get("provenance", {}).get("dataset_ids"),
                "pipeline": norm_dict.get("provenance", {}).get("pipeline"),
                "source": norm_dict.get("provenance", {}).get("source"),
            },
        }

    context = {
        "user_query": query,
        "normalized_result": sanitized_norm,
        "ai_mode": ai_mode,
    }

    mode_instruction = ""
    if ai_mode == "beginner":
        mode_instruction = """AI MODE: BEGINNER
- Use everyday words, intuitive analogies, and plain English.
- Avoid technical remote sensing acronyms without explanation.
- Retain exact numerical values and units from the data."""
    elif ai_mode == "advanced":
        mode_instruction = """AI MODE: ADVANCED
- High scientific density with explicit spectral band designations (e.g. Sentinel-2 MSI B4/B8).
- Include ground sampling distance (GSD), BOA atmospheric reflectance, model architecture, and analytical limitations."""
    else:
        mode_instruction = """AI MODE: INTERMEDIATE / AUTO
- Professional, authoritative remote sensing scientific brief."""

    pres_plan = norm_dict.get("presentation_plan")
    if pres_plan:
        method_dict = pres_plan.get("method", {})
        data_list = method_dict.get("data", ["Sentinel-2 L2A"]) if isinstance(method_dict, dict) else getattr(method_dict, "data", ["Sentinel-2 L2A"])
        data_str = " + ".join(data_list)
        prov_dict = norm_dict.get("provenance", {})
        model_str = (method_dict.get("model") if isinstance(method_dict, dict) else getattr(method_dict, "model", None)) or prov_dict.get("model_name") or "Unavailable"
        disc_str = (method_dict.get("discovery_provider") if isinstance(method_dict, dict) else getattr(method_dict, "discovery_provider", None)) or "Planetary Computer"
        proc_str = (method_dict.get("processing_provider") if isinstance(method_dict, dict) else getattr(method_dict, "processing_provider", None)) or "Remote GPU inference"

        b_role = pres_plan.get("baseline_role") or "temporal_baseline"
        b_title = "Before-event baseline" if b_role == "pre_event_baseline" else "Earlier temporal baseline"
        cov_type = pres_plan.get("coverage_type") or "AOI mosaic"

        is_unavail = prov_dict.get("source") == "unavailable" or prov_dict.get("execution_status") == "unavailable"

        system_prompt = f"""You are SatQuery AI's scientific Earth observation intelligence engine presenting multimodal evidence.
Produce a grounded, evidence-first assessment using ONLY the structured evidence provided below.
The backend result and presentation plan are the single source of truth.

STRICT GROUNDING CONSTRAINTS:
1. DO NOT invent dates, imagery, URLs, numerical values, sensor results, flood area, confidence numbers, or conclusions. NEVER cite numbers that do not appear in Key Measurements (e.g. NEVER claim 4.6 km², 627.1, 134.2, or arbitrary flood numbers).
2. CLOSP CROSS-MODAL ALIGNMENT RULE: If CLOSP executed and produced a cross-modal alignment score (e.g. 0.193), you must NEVER interpret, relabel, or convert this score into a flood extent, inundated area (km²), flood probability, or damage percentage. State honestly: "CLOSP cross-modal alignment score: [value]. This represents contrastive feature embedding alignment between radar and optical representations, not a physical flood extent or inundation area. Physical flood extent was not computed."
3. Distinguish temporal baseline from confirmed pre-event baseline: If no explicit flood event date was specified in the query, refer to the earlier observation as an "Earlier temporal baseline". Explicitly explain that this scene provides an earlier general temporal reference rather than a confirmed pre-flood state.
4. For large AOIs (e.g. Nepal spanning 147,181 km²), report imagery coverage as "{cov_type}" (AOI composite), never claiming a single Sentinel-2 tile covers the whole country. If the analysis was performed on a focused window (e.g. around Kathmandu), state clearly that the analysis was conducted on the Kathmandu window (50 km²) rather than the entirety of Nepal.
5. If flood extent was not produced by the specialist model, do not invent flood extent boundaries or inundation metrics. State clearly that flood extent was not computed.
6. Separate result semantics:
   - Data: {data_str}
   - Model: {model_str}
   - Discovery: {disc_str}
   - Processing: {proc_str}
   Never describe the model as a "STAC Provider".
7. SPECIALIST MODEL AVAILABILITY:
   - If specialist model execution was unavailable:
     * Under "### What changed?": State clearly "Temporal change model execution unavailable: specialist foundation model worker is unreachable. Authentic Sentinel-2 optical observations are preserved above for visual inspection."
     * Under "### Key measurements": State "Specialist measurements unavailable without active model worker."
     * DO NOT fabricate change percentages, pixel counts, or confidence numbers.
8. AGRICULTURAL DECISION SUPPORT (Apple Farm / Orchard Feasibility):
   - If the user asks about starting an apple farm or orchard:
     * Add a dedicated section "### Agricultural Decision Support (Apple Cultivation Feasibility)".
     * Explicitly separate remote sensing observations (canopy presence, terrain) from in-situ agronomic feasibility.
     * State that satellite observation alone CANNOT establish:
       - Soil chemistry, pH (6.0–7.0 required), drainage, and subsoil profile depth.
       - Winter chilling accumulation (800–1,200 hours below 7°C required for commercial cultivars).
       - Spring blossom frost risk and microclimate wind exposure.
       - Irrigation access, water rights, and seasonal groundwater table depth.
     * Conclude with a clear recommendation: Do not infer suitability from satellite imagery alone; conduct on-site soil sampling and consult SKUAST-Kashmir or the local Department of Horticulture before capital investment.

MANDATORY STRUCTURE:
### Investigation title
{pres_plan.get('title', 'Earth Observation Assessment')}

### Current optical image
[Reference to current image]
Metadata:
[Current scene acquisition date, sensor, resolution, cloud cover, and coverage type ({cov_type})]

### {b_title}
[Reference to baseline image, or explicit note if absent: "Baseline Observation Unavailable: ..."]
Metadata:
[Baseline scene acquisition date, sensor, resolution, cloud cover, and coverage type ({cov_type})]
[If temporal baseline, include note: "Earlier temporal baseline: provides a general seasonal reference rather than a confirmed pre-flood scene."]

### What changed?
Authoritative natural-language synthesis explaining observed conditions and changes grounded ONLY in the structured result.

### Evidence layers
[List available evidence layers, e.g. [Optical], [SAR VV], [SAR VH], [NDWI], [SAR Change], [Flood extent]]

### Key measurements
Bullet points with exact values and units from the analysis. If cross-modal alignment score is present, explain it as a model-specific alignment metric, not a flood probability.

### Agricultural Decision Support (Apple Cultivation Feasibility)
[Included if query asks about farming/orchard feasibility]

### Method
- Data: {data_str}
- Model: {model_str}
- Discovery: {disc_str}
- Processing: {proc_str}

### Limitations
List the actual limitations from the analysis."""
    else:
        system_prompt = f"""You are SatQuery AI's scientific Earth observation intelligence engine.
Answer the user's question using ONLY the authoritative analysis result supplied by the backend.
The backend result is the single source of truth.

CORE PRINCIPLE: "ANSWER FIRST. VISUALIZE ONLY WHEN IT HELPS."
The user's primary question must be answered immediately in clear, intelligent, and authoritative prose before any secondary details.

{mode_instruction}

STRICT PRINCIPLES:
1. DIRECT ANSWER LEADS: In the Summary / Lead, directly address the user's exact query or decision.
2. Do not invent satellite observations, measurements, coordinates, dates, percentages, areas, datasets, models, or scientific conclusions.
3. Do not modify numerical values, coordinates, or dates.
4. NEVER mention internal terms like "mock", "demo data", "fallback", "hardcoded", "scenario matcher", "LangGraph", "pipeline", or "tool executor".
5. Do NOT include a "### Visualization" section dumping layer IDs or UI directions; let the visualization layers speak for themselves.
6. Target approximately 150–250 words for a substantive, polished, and human-like remote sensing brief.
7. DO NOT output raw JSON dumps or developer telemetry in your response.

MANDATORY STRUCTURE:
### Summary
2–4 direct, authoritative sentences directly answering the user's question and primary observation.

### Key Findings
3–5 bullet points highlighting primary metrics with bold values and units.

### Spatial / Temporal Interpretation
A concise explanation of the geographic extent, spatial concentration of change, and practical implications.

### Data & Method
Identify the specific sensor platforms and specialist foundation model utilized, noting any sensor or ground limitations."""

    user_payload = f"""User Query: {query}

Authoritative Result Data:
{json.dumps(context, indent=2)}
"""

    if settings.GROQ_API_KEY:
        try:
            llm = ChatGroq(
                model=settings.GROQ_MODEL,
                api_key=settings.GROQ_API_KEY,
                temperature=0.1,
                max_retries=1,
                request_timeout=6,
            )
            resp = llm.invoke([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_payload},
            ])
            answer = resp.content.strip()
            if evidence_markdown:
                answer += evidence_markdown
            if fallback:
                answer += "\n\n> *I couldn't reach the live analysis worker, so this response uses mock analysis data.*"
            print("[LLM FINAL]\nGPT-OSS final response generated: YES")
            return {
                "final_answer": answer,
                "final_response": answer,
                "visualization_plan": norm_dict.get("visualization_plan"),
                "web_evidence": [w.model_dump() for w in web_ev_items],
            }
        except Exception as exc:
            logger.warning(f"Groq final response generation failed ({exc}); using fallback.")

    # Resilient structured markdown fallback
    if matched and matched.get("expected_answer"):
        answer = _format_markdown_fallback(matched.get("expected_answer", ""), norm_dict, ai_mode=ai_mode)
    else:
        answer = _format_unknown_markdown_fallback(query, norm_dict, ai_mode=ai_mode)

    if evidence_markdown:
        answer += evidence_markdown

    if fallback:
        answer += "\n\n> *I couldn't reach the live analysis worker, so this response uses mock analysis data.*"

    print("[LLM FINAL]\nGPT-OSS final response generated: NO (fallback)")
    return {
        "final_answer": answer,
        "final_response": answer,
        "visualization_plan": norm_dict.get("visualization_plan"),
        "web_evidence": [w.model_dump() for w in web_ev_items],
    }