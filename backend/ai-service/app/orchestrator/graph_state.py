"""
app/orchestrator/graph_state.py
─────────────────────────────────────────────────────────────────────────────
LangGraph agent state schema.

This module defines the single typed state that flows through every node
in the SatQuery LangGraph orchestration graph.

WHY A SEPARATE MODULE:
  Keeping AgentState in its own file avoids circular imports between
  agent.py and any node-level helpers that might import it.
"""

from __future__ import annotations

from typing import Annotated, Any
from langgraph.graph.message import add_messages


class AgentState:
    """
    TypedDict-compatible state container for the SatQuery LangGraph graph.

    LangGraph uses Python TypedDicts for state. We define this as a plain
    dict-like class using __annotations__ so it can be used directly with
    StateGraph(AgentState).

    Fields
    ------
    messages:
        The LangChain message history (HumanMessage, AIMessage, ToolMessage, …).
        The `add_messages` reducer automatically appends new messages on each
        node transition rather than overwriting the list.

    request_id:
        UUID string generated at the start of each chat turn for log
        correlation.  Passed through unchanged.

    primary_image:
        Resolved image reference (URL or path) for the main / optical image.
        Derived from image_url (preferred) or image_path from ChatRequest.

    secondary_image:
        Second temporal image (for change detection), derived from
        image_url_t2 / image_path_t2.

    sar_image:
        SAR image reference, derived from sar_image_url / sar_image_path.

    aoi:
        Area-of-interest bounding box [min_lon, min_lat, max_lon, max_lat].

    date_range:
        ISO-8601 date strings ["YYYY-MM-DD", "YYYY-MM-DD"] for temporal queries.

    metadata:
        Arbitrary metadata dict from ChatRequest.metadata.

    tool_call_records:
        Accumulated list of ToolCallRecord dicts built during graph execution.
        Each record has: { tool_name, arguments, result }.

    artifacts:
        Flattened list of SatelliteDataset / artifact dicts produced by
        satellite acquisition tools.

    error:
        Non-None when the graph encounters an unrecoverable error.  The
        FastAPI layer surfaces this to the client.
    """

    # Annotated with add_messages so LangGraph knows to merge, not replace.
    messages: Annotated[list, add_messages]

    request_id: str
    primary_image: str | None
    secondary_image: str | None
    sar_image: str | None
    aoi: list[float] | None
    date_range: list[str] | None
    metadata: dict[str, Any]
    tool_call_records: list[dict[str, Any]]
    artifacts: list[Any]
    error: str | None
