from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode

from app.graph.state import AgentState
from app.graph.nodes import (
    understand_query,
    validate_request,
    select_and_call_tool,
)
from app.graph.tools import execute_remote_sensing_analysis


def build_graph():

    graph = StateGraph(AgentState)

    graph.add_node(
        "understand_query",
        understand_query
    )

    graph.add_node(
        "validate_request",
        validate_request
    )

    graph.add_node(
        "select_and_call_tool",
        select_and_call_tool
    )

    tool_node = ToolNode(
        [execute_remote_sensing_analysis]
    )

    graph.add_node(
        "execute_tool",
        tool_node
    )

    graph.add_edge(
        START,
        "understand_query"
    )

    graph.add_edge(
        "understand_query",
        "validate_request"
    )

    graph.add_edge(
        "validate_request",
        "select_and_call_tool"
    )

    graph.add_edge(
        "select_and_call_tool",
        "execute_tool"
    )

    graph.add_edge(
        "execute_tool",
        END
    )

    return graph.compile()