from typing import TypedDict, Optional, Annotated, Any, List, Dict
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    user_query: str
    matched_scenario: Optional[Dict[str, Any]]
    analysis_request: Optional[Dict[str, Any]]
    messages: Annotated[list, add_messages]
    tool_result: Optional[Dict[str, Any]]
    normalized_result: Optional[Dict[str, Any]]
    final_answer: str
    final_response: str
    globe_actions: Optional[List[Dict[str, Any]]]
    visualizations: Optional[List[Dict[str, Any]]]
    source: str
    fallback: bool
    error: Optional[str]