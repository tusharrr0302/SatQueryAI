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
    request_id: Optional[str]
    intent_type: Optional[str]
    status: Optional[str]
    layers: Optional[List[Dict[str, Any]]]
    source: str
    fallback: bool
    audit_trace: Optional[List[Dict[str, Any]]]
    error: Optional[str]
    active_aoi: Optional[Dict[str, Any]]
    resolved_aoi: Optional[Dict[str, Any]]
    aoi_action: Optional[str]
    aoi_reason: Optional[str]
    spatial_focus: Optional[str]
    requires_geospatial_analysis: Optional[bool]
    ai_mode: Optional[str]
    explicit_model: Optional[str]
    conversational_mode: Optional[str]
    visualization_required: Optional[bool]
    visualization_reason: Optional[str]
    visualization_type: Optional[str]
    visualization_plan: Optional[Dict[str, Any]]
    web_evidence: Optional[List[Dict[str, Any]]]
    tool_plan: Optional[Dict[str, Any]]
    data_requirement: Optional[Dict[str, Any]]
    data_discovery_result: Optional[Dict[str, Any]]
    discovered_assets: Optional[List[Dict[str, Any]]]
    force_mock: Optional[bool]