from langchain_groq import ChatGroq
from app.config import settings
from app.services.request_validator import RequestValidator
from app.schemas.analysis_request import AnalysisRequest
from app.graph.tools import execute_remote_sensing_analysis


def understand_query(state):

    print("UNDERSTAND QUERY NODE")

    llm = ChatGroq(
        model=settings.GROQ_MODEL,
        api_key=settings.GROQ_API_KEY,
        temperature=0,
    )

    structured_llm = llm.with_structured_output(AnalysisRequest)

    result = structured_llm.invoke(
        f"""
You are SatQuery AI's remote sensing query analysis engine.

Convert the user's request into a standardized AnalysisRequest.

Available models:
- geochat-7b
- prithvi-eo-2.0
- closp
- terrafm

Available datasets:
- sentinel-1
- sentinel-2

Never invent a model or dataset.

User request:
{state["user_query"]}
"""
    )

    print("ANALYSIS REQUEST:", result)

    return {
        "analysis_request": result.model_dump()
    }

def validate_request(state):

    print("VALIDATING ANALYSIS REQUEST")

    request = AnalysisRequest.model_validate(
        state["analysis_request"]
    )

    validator = RequestValidator()
    validator.validate(request)

    print("REQUEST VALID")

    return {
        "analysis_request": request.model_dump()
    }


def select_and_call_tool(state):

    print("TOOL SELECTION NODE")

    llm = ChatGroq(
        model=settings.GROQ_MODEL,
        api_key=settings.GROQ_API_KEY,
        temperature=0,
    )

    llm_with_tools = llm.bind_tools(
        [execute_remote_sensing_analysis]
    )

    response = llm_with_tools.invoke(
        f"""
You are the execution planner for SatQuery AI.

You have a validated AnalysisRequest.

Choose and call the appropriate remote sensing tool.

AnalysisRequest:
{state["analysis_request"]}
"""
    )

    print("GPT TOOL CALL:", response.tool_calls)

    return {
        "messages": [response]
    }