from typing import TypedDict, Optional, Annotated, Any, List, Dict
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    user_query: str
    conversation_id: Optional[str]
    user_id: Optional[str]
    active_asset: Optional[Dict[str, Any]]
    data_assets: Optional[List[Dict[str, Any]]]
    data_relationships: Optional[List[Dict[str, Any]]]
    data_context: Optional[str]
    matched_scenario: Optional[Dict[str, Any]]
    analysis_request: Optional[Dict[str, Any]]
    messages: Annotated[list, add_messages]
    recent_messages: Optional[List[Dict[str, Any]]]
    previous_result: Optional[Dict[str, Any]]
    location_hint: Optional[str]
    tool_result: Optional[Dict[str, Any]]
    normalized_result: Optional[Dict[str, Any]]
    final_answer: str
    final_response: str
    globe_actions: Optional[List[Dict[str, Any]]]
    visualizations: Optional[List[Dict[str, Any]]]
    layers: Optional[List[Dict[str, Any]]]
    source: str
    fallback: bool
    audit_trace: Optional[List[Dict[str, Any]]]
    error: Optional[str]