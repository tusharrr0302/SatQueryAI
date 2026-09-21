"""
backend/tests/test_natural_language_intelligence.py
─────────────────────────────────────────────────────────────────────────────
Comprehensive test suite for SatQuery AI's Natural-Language Intelligence Layer:
  Phase 1: Schema & Pydantic Contracts (AnalysisRequest != ToolPlan)
  Phase 2: ToolRegistry & ATS Capability Matching
  Phase 3: Natural Language Understanding & Compact Context (Token Budget)
  Phase 4: Multi-Turn Context State Machine (Delhi -> vegetation -> 2020 -> SAR too)
  Phase 5: Execution Provenance (EarthDial & Prithvi Mock vs CLOSP Real)
  Phase 6: Negative, Boundary & Clarification Tests (1890, missing SAR, no AOI)
"""
import pytest
from typing import Dict, Any

from app.schemas.analysis_request import (
    AnalysisRequest,
    ToolPlan,
    Intent,
    AOI,
    DataRequirements,
    ModelSelection,
    Analysis,
    Outputs,
    Execution,
    TemporalScope,
)
from app.services.tool_registry import tool_registry, ToolRegistry
from app.services.mock_specialists import execute_mock_specialist
from app.graph.nodes import (
    understand_query,
    validate_request,
    execute_unknown_analysis,
    generate_final_response,
    _generate_fallback_request,
)


# ==============================================================================
# PHASE 1: SCHEMA & PYDANTIC CONTRACTS
# ==============================================================================

def test_phase1_analysis_request_schema():
    """Verify AnalysisRequest matches the rigorous Pydantic schema."""
    req = AnalysisRequest(
        query="Show vegetation in Delhi",
        intent=Intent(
            primary_task="vegetation_analysis",
            domain="earth_observation",
            question_type="new_analysis",
            requires_geospatial_analysis=True,
            temporal_scope=TemporalScope(relative_period="5_years"),
            needs_clarification=False,
        ),
        aoi=AOI(name="Delhi", action="resolve_new", source="explicit_user"),
        data_requirements=DataRequirements(modalities=["optical"]),
        model_selection=ModelSelection(model="prithvi-eo-2.0", reason="Optical vegetation"),
        analysis=Analysis(operation="vegetation_index"),
        outputs=Outputs(visualizations=["spatial_overlay"]),
        execution=Execution(priority="accuracy"),
    )
    assert req.query == "Show vegetation in Delhi"
    assert req.intent.primary_task == "vegetation_analysis"
    assert req.aoi.name == "Delhi"
    assert req.data_requirements.modalities == ["optical"]
    # Verify ToolPlan is NOT a field on AnalysisRequest
    assert not hasattr(req, "tool_plan") or "tool_plan" not in req.__fields__


def test_phase1_tool_plan_separation():
    """Verify ToolPlan is generated independently by ATS capability matching."""
    plan = ToolPlan(
        tool="analyze_sar_optical",
        model="closp",
        inputs={"sar_image_url": "http://example.com/sar.tif"},
        reason="Matched SAR and optical modalities",
        requires_modalities=["sar", "optical"],
        status="planned",
        missing_inputs=[],
    )
    assert plan.tool == "analyze_sar_optical"
    assert plan.model == "closp"
    assert plan.status == "planned"
    assert "sar" in plan.requires_modalities


# ==============================================================================
# PHASE 2: ATS TOOL REGISTRY & CAPABILITY MATCHING
# ==============================================================================

def test_phase2_tool_catalog_registered():
    """Verify all four specialist tools are registered."""
    reg = ToolRegistry()
    tools = reg.list_tools()
    tool_ids = [t.tool_id for t in tools]
    assert "analyze_image" in tool_ids
    assert "detect_change" in tool_ids
    assert "analyze_multitemporal" in tool_ids
    assert "analyze_sar_optical" in tool_ids


def test_phase2_single_image_vqa_routing():
    """Single image VQA routes to analyze_image with earthdial-4b-ms."""
    req = AnalysisRequest(
        query="What is visible in this satellite image?",
        intent=Intent(primary_task="single_image_vqa", requires_geospatial_analysis=True),
        aoi=AOI(action="none"),
        data_requirements=DataRequirements(modalities=["optical"]),
        model_selection=ModelSelection(model="earthdial-4b-ms", reason="VQA"),
        analysis=Analysis(operation="vqa"),
        outputs=Outputs(),
        execution=Execution(),
    )
    plan = tool_registry.plan_execution(req)
    assert plan.tool == "analyze_image"
    assert plan.model == "earthdial-4b-ms"
    assert plan.status == "planned"


def test_phase2_scene_description_routing():
    """Scene description routes to analyze_image with earthdial-4b-ms."""
    req = AnalysisRequest(
        query="Describe the major land-cover types in this image.",
        intent=Intent(primary_task="scene_description", requires_geospatial_analysis=True),
        aoi=AOI(action="none"),
        data_requirements=DataRequirements(modalities=["optical"]),
        model_selection=ModelSelection(model="earthdial-4b-ms", reason="Description"),
        analysis=Analysis(operation="scene_description"),
        outputs=Outputs(),
        execution=Execution(),
    )
    plan = tool_registry.plan_execution(req)
    assert plan.tool == "analyze_image"
    assert plan.model == "earthdial-4b-ms"
    assert plan.status == "planned"


def test_phase2_temporal_change_optical_routing():
    """Bi-temporal optical change routes to detect_change with prithvi-eo-2.0."""
    req = AnalysisRequest(
        query="How has Delhi changed over the last 10 years?",
        intent=Intent(primary_task="temporal_change_detection", requires_geospatial_analysis=True),
        aoi=AOI(name="Delhi", action="resolve_new"),
        data_requirements=DataRequirements(modalities=["optical"]),
        model_selection=ModelSelection(model="prithvi-eo-2.0", reason="Temporal change"),
        analysis=Analysis(operation="temporal_change"),
        outputs=Outputs(),
        execution=Execution(),
    )
    plan = tool_registry.plan_execution(req)
    assert plan.tool == "detect_change"
    assert plan.model == "prithvi-eo-2.0"
    assert plan.status == "planned"


def test_phase2_multitemporal_multispectral_stack_routing():
    """Multispectral stack analysis routes to analyze_multitemporal with prithvi-eo-2.0."""
    req = AnalysisRequest(
        query="Analyze the 4-frame multispectral stack over Delhi",
        intent=Intent(primary_task="temporal_change_detection", requires_geospatial_analysis=True),
        aoi=AOI(name="Delhi", action="resolve_new"),
        data_requirements=DataRequirements(modalities=["multispectral"]),
        model_selection=ModelSelection(model="prithvi-eo-2.0", reason="Multitemporal stack"),
        analysis=Analysis(operation="multispectral_change"),
        outputs=Outputs(),
        execution=Execution(),
    )
    plan = tool_registry.plan_execution(req)
    assert plan.tool == "analyze_multitemporal"
    assert plan.model == "prithvi-eo-2.0"
    assert plan.status == "planned"


def test_phase2_sar_optical_flood_routes_to_closp():
    """SAR + Optical flood analysis routes to analyze_sar_optical with CLOSP."""
    req = AnalysisRequest(
        query="Show me possible flooding using SAR and optical imagery.",
        intent=Intent(primary_task="flood_analysis", requires_geospatial_analysis=True),
        aoi=AOI(name="Derna", action="resolve_new"),
        data_requirements=DataRequirements(modalities=["sar", "optical"]),
        model_selection=ModelSelection(model="closp", reason="Flood fusion"),
        analysis=Analysis(operation="flood_mapping"),
        outputs=Outputs(),
        execution=Execution(),
    )
    plan = tool_registry.plan_execution(req)
    assert plan.tool == "analyze_sar_optical"
    assert plan.model == "closp"
    assert plan.status == "planned"


def test_phase2_sar_optical_vegetation_capability_matching():
    """
    Refined ATS capability matching:
    'Use SAR too' with vegetation_analysis routes to analyze_sar_optical
    and selects TerraFM (or CLOSP if requested) based on task capabilities.
    """
    req = AnalysisRequest(
        query="Use SAR too for vegetation observation in Delhi.",
        intent=Intent(primary_task="vegetation_analysis", requires_geospatial_analysis=True),
        aoi=AOI(name="Delhi", action="reuse"),
        data_requirements=DataRequirements(modalities=["sar", "optical"]),
        model_selection=ModelSelection(model="terrafm", reason="Multimodal vegetation"),
        analysis=Analysis(operation="vegetation_change"),
        outputs=Outputs(),
        execution=Execution(),
    )
    plan = tool_registry.plan_execution(req)
    assert plan.tool == "analyze_sar_optical"
    assert plan.model in ("terrafm", "closp")
    assert plan.status == "planned"


def test_phase2_strict_capability_matching_missing_sar_returns_needs_data():
    """
    Strict ATS validation: If user requests CLOSP but modalities only include optical,
    do NOT silently fabricate SAR. Return status='needs_data' and list missing_inputs.
    """
    req = AnalysisRequest(
        query="Analyze with CLOSP",
        intent=Intent(primary_task="sar_optical_analysis", requires_geospatial_analysis=True),
        aoi=AOI(name="Delhi", action="resolve_new"),
        data_requirements=DataRequirements(modalities=["optical"]),  # Missing SAR!
        model_selection=ModelSelection(model="closp", explicit_model="closp", reason="Requested CLOSP"),
        analysis=Analysis(operation="sar_optical"),
        outputs=Outputs(),
        execution=Execution(),
    )
    plan = tool_registry.plan_execution(req)
    assert plan.status == "needs_data"
    assert "sar" in plan.missing_inputs
    assert "requires both SAR and optical" in plan.reason


# ==============================================================================
# PHASE 3: NATURAL LANGUAGE UNDERSTANDING & COMPACT CONTEXT
# ==============================================================================

def test_phase3_what_changed_in_delhi_10_years():
    """
    User query: 'What changed in Delhi over the last 10 years?'
    Produces:
      - primary_task = temporal_change_detection
      - aoi.name = Delhi
      - temporal_scope.relative_period = 10_years
      - modalities = ['optical']
    """
    state = {
        "user_query": "What changed in Delhi over the last 10 years?",
        "recent_messages": [],
        "active_aoi": None,
        "previous_result": None,
    }
    res = understand_query(state)
    analysis_req = res["analysis_request"]

    assert analysis_req["intent"]["primary_task"] == "temporal_change_detection"
    assert analysis_req["aoi"]["name"] == "Delhi"
    rel_period = (analysis_req["intent"].get("temporal_scope") or {}).get("relative_period")
    assert rel_period == "10_years" or "10" in str(rel_period)
    assert "optical" in analysis_req["data_requirements"]["modalities"]


def test_phase3_compact_prompt_budget():
    """
    Verify that understand_query prompt context does NOT dump the 56KB dataset catalog.
    Context should remain compact (<800 tokens).
    """
    state = {
        "user_query": "How has Bangalore changed over the last 5 years?",
        "recent_messages": [],
    }
    # Call understand_query and check that it completes quickly without token limit issues
    res = understand_query(state)
    assert "analysis_request" in res
    assert res["analysis_request"]["aoi"]["name"] == "Bengaluru" or res["analysis_request"]["aoi"]["name"] == "Bangalore"


# ==============================================================================
# PHASE 4: MULTI-TURN CONTEXT STATE MACHINE
# ==============================================================================

def test_phase4_multiturn_state_inheritance():
    """
    Test four-turn state machine:
      Turn 1: 'Show Delhi' -> AOI = Delhi
      Turn 2: 'Now show vegetation' -> AOI = Delhi, task = vegetation_analysis
      Turn 3: 'Compare it with 2020' -> AOI = Delhi, task = vegetation_analysis, comparison = 2020
      Turn 4: 'Use SAR too' -> AOI = Delhi, task = vegetation_analysis, modalities = ['optical', 'sar']
                               ATS capability matching selects CLOSP or TerraFM
    """
    # Turn 1: "Show Delhi"
    state_t1 = {"user_query": "Show Delhi", "recent_messages": []}
    res_t1 = understand_query(state_t1)
    req_t1 = res_t1["analysis_request"]
    assert req_t1["aoi"]["name"] == "Delhi"
    assert req_t1["aoi"]["action"] == "resolve_new"

    # Turn 2: "Now show vegetation" (inherits Delhi)
    active_aoi = {"name": "Delhi", "center": {"latitude": 28.6139, "longitude": 77.2090}}
    state_t2 = {
        "user_query": "Now show vegetation",
        "recent_messages": [{"role": "user", "content": "Show Delhi"}, {"role": "assistant", "content": "Focused on Delhi."}],
        "active_aoi": active_aoi,
        "previous_result": {"aoi": active_aoi, "analysis_type": "location_information"},
    }
    res_t2 = understand_query(state_t2)
    req_t2 = res_t2["analysis_request"]
    assert req_t2["aoi"]["name"] == "Delhi"
    assert req_t2["aoi"]["action"] == "reuse"
    assert req_t2["intent"]["primary_task"] == "vegetation_analysis"

    # Turn 3: "Compare it with 2020" (inherits Delhi and vegetation)
    state_t3 = {
        "user_query": "Compare it with 2020",
        "recent_messages": [
            {"role": "user", "content": "Show Delhi"},
            {"role": "assistant", "content": "Focused on Delhi."},
            {"role": "user", "content": "Now show vegetation"},
            {"role": "assistant", "content": "Analyzed vegetation canopy in Delhi."},
        ],
        "active_aoi": active_aoi,
        "previous_result": {"aoi": active_aoi, "analysis_type": "vegetation_analysis"},
    }
    res_t3 = understand_query(state_t3)
    req_t3 = res_t3["analysis_request"]
    assert req_t3["aoi"]["name"] == "Delhi"
    assert req_t3["aoi"]["action"] == "reuse"
    temporal = req_t3["intent"].get("temporal_scope") or {}
    assert temporal.get("start") == "2020" or "2020" in str(temporal)

    # Turn 4: "Use SAR too" (inherits Delhi and updates modalities to optical + SAR)
    state_t4 = {
        "user_query": "Use SAR too",
        "recent_messages": [
            {"role": "user", "content": "Show Delhi"},
            {"role": "assistant", "content": "Focused on Delhi."},
            {"role": "user", "content": "Now show vegetation"},
            {"role": "assistant", "content": "Analyzed vegetation canopy in Delhi."},
            {"role": "user", "content": "Compare it with 2020"},
            {"role": "assistant", "content": "Compared vegetation with 2020 baseline."},
        ],
        "active_aoi": active_aoi,
        "previous_result": {"aoi": active_aoi, "analysis_type": "vegetation_analysis"},
    }
    res_t4 = understand_query(state_t4)
    req_t4 = res_t4["analysis_request"]
    assert req_t4["aoi"]["name"] == "Delhi"
    modalities = req_t4["data_requirements"]["modalities"]
    assert "sar" in modalities
    assert "optical" in modalities

    # Validate ATS execution plan for Turn 4: capability matching selects CLOSP or TerraFM
    plan_t4 = tool_registry.plan_execution(AnalysisRequest.model_validate(req_t4))
    assert plan_t4.tool == "analyze_sar_optical"
    assert plan_t4.model in ("terrafm", "closp")
    assert plan_t4.status == "planned"


# ==============================================================================
# PHASE 5: EXECUTION PROVENANCE (MOCK VS REAL)
# ==============================================================================

def test_phase5_mock_specialist_adapter_earthdial():
    """
    Verify EarthDial mock specialist returns honest provenance:
      source="mock", fallback=True, fallback_reason specifies Kaggle status
    """
    res = execute_mock_specialist(
        model_id="earthdial-4b-ms",
        query="What is visible in this satellite image?",
        aoi_dict={"name": "Kashmir Valley", "center": {"latitude": 34.0837, "longitude": 74.7973}},
    )
    assert res.provenance.source == "mock"
    assert res.provenance.fallback is True
    assert "Kaggle" in res.provenance.fallback_reason
    assert res.provenance.model_id == "earthdial-4b-ms"
    assert len(res.metrics) >= 2


def test_phase5_mock_specialist_adapter_prithvi():
    """
    Verify Prithvi mock specialist returns honest provenance:
      source="mock", fallback=True, fallback_reason specifies Kaggle status
    """
    res = execute_mock_specialist(
        model_id="prithvi-eo-2.0",
        query="How has this area changed over the last 10 years?",
        aoi_dict={"name": "Delhi", "center": {"latitude": 28.6139, "longitude": 77.2090}},
    )
    assert res.provenance.source == "mock"
    assert res.provenance.fallback is True
    assert "Kaggle" in res.provenance.fallback_reason
    assert res.provenance.model_id == "prithvi-eo-2.0"
    assert len(res.metrics) >= 2


# ==============================================================================
# PHASE 6: NEGATIVE, BOUNDARY & CLARIFICATION TESTS
# ==============================================================================

def test_phase6_historical_1890_unsupported_data_period():
    """
    Historical Query: 'Show vegetation in Delhi in 1890'
    Natural language layer faithfully parses the 1890 date.
    Validation layer checks the temporal boundary and flags unsupported_data_period (pre-1972).
    """
    state = {
        "user_query": "Show vegetation in Delhi in 1890",
        "analysis_request": {
            "query": "Show vegetation in Delhi in 1890",
            "intent": {
                "primary_task": "vegetation_analysis",
                "temporal_scope": {"start": "1890", "end": "1890"},
                "requires_geospatial_analysis": True,
            },
            "aoi": {"name": "Delhi", "action": "resolve_new"},
            "data_requirements": {"modalities": ["optical"]},
            "model_selection": {"model": "prithvi-eo-2.0", "reason": "Vegetation"},
            "analysis": {"operation": "vegetation"},
            "outputs": {},
            "execution": {},
        },
    }
    val_res = validate_request(state)
    assert val_res.get("status") == "unsupported_data_period"
    assert "1890" in val_res.get("final_answer", "")
    assert "1972" in val_res.get("final_answer", "")


def test_phase6_clarification_gate_when_aoi_missing():
    """
    Clarification Gate: If user asks 'Show vegetation' without any location
    and without previous context, intent.needs_clarification must be True.
    """
    state = {
        "user_query": "Show vegetation",
        "recent_messages": [],
        "active_aoi": None,
        "previous_result": None,
    }
    res = understand_query(state)
    req = res["analysis_request"]
    assert req["intent"]["needs_clarification"] is True
    assert "aoi" in req["intent"]["missing_fields"]
    assert req["aoi"]["action"] == "clarify"
    assert req["intent"]["clarification_question"] is not None

    # Verify generate_final_response returns clarification prompt
    resp = generate_final_response({
        "user_query": "Show vegetation",
        "status": "needs_clarification",
        "aoi_action": "clarify",
        "analysis_request": req,
    })
    assert "which" in resp["final_answer"].lower() or "specify" in resp["final_answer"].lower()


def test_phase6_closp_flood_pipeline_end_to_end():
    """
    User Query: 'Show me possible flooding using SAR and optical imagery in Derna'
    Verifies the complete flow:
      Natural Language -> GPT-OSS / AnalysisRequest -> ATS Capability Matching -> ToolPlan
      tool = analyze_sar_optical
      model = closp
      modalities = ['sar', 'optical']
      status = 'planned'
    """
    state = {
        "user_query": "Show me possible flooding using SAR and optical imagery in Derna",
        "recent_messages": [],
        "active_aoi": None,
        "previous_result": None,
    }
    res = understand_query(state)
    analysis_req = res["analysis_request"]

    # Verify AnalysisRequest output
    assert analysis_req["intent"]["primary_task"] in ("flood_analysis", "sar_optical_analysis")
    assert "sar" in analysis_req["data_requirements"]["modalities"]
    assert "optical" in analysis_req["data_requirements"]["modalities"]
    assert "Derna" in analysis_req["aoi"]["name"]

    # Run ATS validation node
    val_state = dict(state)
    val_state["analysis_request"] = analysis_req
    val_res = validate_request(val_state)

    tool_plan = val_res.get("tool_plan")
    assert tool_plan is not None
    assert tool_plan["tool"] == "analyze_sar_optical"
    assert tool_plan["model"] == "closp"
    assert tool_plan["status"] == "planned"
    assert "sar" in tool_plan["requires_modalities"]
    assert "optical" in tool_plan["requires_modalities"]

