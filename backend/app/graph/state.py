from typing import TypedDict, Optional, Annotated

from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):

    user_query: str

    analysis_request: dict

    messages: Annotated[list, add_messages]

    tool_result: dict

    final_response: str

    error: Optional[str]