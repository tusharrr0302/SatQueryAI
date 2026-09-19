from langgraph.graph import StateGraph, START, END
from app.graph.state import AgentState
from app.graph.nodes import (
    resolve_query_source,
    load_mock_scenario,
    understand_query,
    validate_request,
    execute_unknown_analysis,
    generate_final_response,
    generate_globe_actions,
    generate_visualizations,
)


def route_scenario(state: AgentState) -> str:
    if state.get("matched_scenario"):
        return "load_mock_scenario"
    return "understand_query"


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("resolve_query_source", resolve_query_source)
    graph.add_node("load_mock_scenario", load_mock_scenario)
    graph.add_node("understand_query", understand_query)
    graph.add_node("validate_request", validate_request)
    graph.add_node("execute_unknown_analysis", execute_unknown_analysis)
    graph.add_node("generate_final_response", generate_final_response)
    graph.add_node("generate_globe_actions", generate_globe_actions)
    graph.add_node("generate_visualizations", generate_visualizations)

    # Entry edge
    graph.add_edge(START, "resolve_query_source")

    # Conditional router
    graph.add_conditional_edges(
        "resolve_query_source",
        route_scenario,
        {
            "load_mock_scenario": "load_mock_scenario",
            "understand_query": "understand_query",
        },
    )

    # Path A: Known Mock Scenario
    graph.add_edge("load_mock_scenario", "generate_visualizations")

    # Path B: Unknown Query (GPT-OSS Planning)
    graph.add_edge("understand_query", "validate_request")
    graph.add_edge("validate_request", "execute_unknown_analysis")
    graph.add_edge("execute_unknown_analysis", "generate_visualizations")

    # Tail: Visualizations -> Globe Actions -> Final Response -> END
    graph.add_edge("generate_visualizations", "generate_globe_actions")
    graph.add_edge("generate_globe_actions", "generate_final_response")
    graph.add_edge("generate_final_response", END)

    return graph.compile()