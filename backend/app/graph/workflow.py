from langgraph.graph import StateGraph, START, END
from app.graph.state import AgentState
from app.graph.nodes import (
    understand_query,
    resolve_conversational_aoi,
    load_mock_scenario,
    validate_request,
    execute_unknown_analysis,
    generate_visualizations,
    generate_globe_actions,
    generate_final_response,
)


def route_after_aoi_resolution(state: AgentState) -> str:
    intent = state.get("intent_type", "new_analysis")
    requires_geo = state.get("requires_geospatial_analysis", True)
    active_asset = state.get("active_asset")

    # If user has an active uploaded asset and inspection is needed, execute analysis
    if active_asset and (intent == "data_inspection" or not state.get("normalized_result")):
        return "validate_request"

    if not requires_geo or intent in [
        "RESULT_EXPLANATION", "PROVENANCE_QUESTION", "VISUALIZATION_REQUEST",
        "GENERAL_KNOWLEDGE", "CLARIFICATION", "conversational_explanation",
        "out_of_scope", "clarification", "TOPIC_RESTORATION"
    ]:
        return "generate_visualizations"
    if state.get("matched_scenario"):
        return "load_mock_scenario"
    return "validate_request"


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("understand_query", understand_query)
    graph.add_node("resolve_conversational_aoi", resolve_conversational_aoi)
    graph.add_node("load_mock_scenario", load_mock_scenario)
    graph.add_node("validate_request", validate_request)
    graph.add_node("execute_unknown_analysis", execute_unknown_analysis)
    graph.add_node("generate_visualizations", generate_visualizations)
    graph.add_node("generate_globe_actions", generate_globe_actions)
    graph.add_node("generate_final_response", generate_final_response)

    # Entry edge: GPT-OSS 120B intent understanding is the single authoritative planner
    graph.add_edge(START, "understand_query")

    # Pass to dedicated Conversational AOI Resolution
    graph.add_edge("understand_query", "resolve_conversational_aoi")

    # Conditional routing after Conversational AOI Resolution
    graph.add_conditional_edges(
        "resolve_conversational_aoi",
        route_after_aoi_resolution,
        {
            "generate_visualizations": "generate_visualizations",
            "load_mock_scenario": "load_mock_scenario",
            "validate_request": "validate_request",
        },
    )

    # Path A: Precomputed Mock Scenario
    graph.add_edge("load_mock_scenario", "generate_visualizations")

    # Path B: Live / Dynamic Remote-Sensing Execution
    graph.add_edge("validate_request", "execute_unknown_analysis")
    graph.add_edge("execute_unknown_analysis", "generate_visualizations")

    # Common Tail: Visualizations -> Globe Actions -> Final Response -> END
    graph.add_edge("generate_visualizations", "generate_globe_actions")
    graph.add_edge("generate_globe_actions", "generate_final_response")
    graph.add_edge("generate_final_response", END)

    return graph.compile()