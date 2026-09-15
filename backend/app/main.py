from fastapi import FastAPI
from app.agent.groq_client import GroqClient
from app.services.ats import AgenticToolSystem
from app.agent.schema import ANALYSIS_REQUEST_SCHEMA
from app.schemas.analysis_request import AnalysisRequest
from app.models.registry import MODEL_REGISTRY
from app.dataset.registry import DATASET_REGISTRY
from app.agent.tools import EXECUTE_REMOTE_SENSING_ANALYSIS_TOOL


app =FastAPI(title="SatQuery AI")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/test-groq")
def test_groq():
    groq = GroqClient()

    answer = groq.ask("Reply with exactly: GPT-OSS connection working")

    return {"response": answer}

from app.agent.selector import ModelDatasetSelector


@app.get("/test-selector")
def test_selector():
    selector = ModelDatasetSelector()

    return selector.select(
        "Show me how Delhi changed over the last 10 years"
    )

@app.get("/test-analysis")
def test_analysis():

    groq = GroqClient()

    raw_request = groq.create_analysis_request(
    "Show me how Delhi changed over the last 10 years",
    ANALYSIS_REQUEST_SCHEMA,
    MODEL_REGISTRY,
    DATASET_REGISTRY
)

    request = AnalysisRequest.model_validate_json(raw_request)

    ats = AgenticToolSystem()

    result = ats.run(request)

    return result

@app.get("/test-tool-call")
def test_tool_call():

    groq = GroqClient()

    analysis_request = {
        "query": "Show me how Delhi changed over 10 years",
        "model_selection": {
            "model": "prithvi-eo-2.0",
            "reason": "Temporal multispectral analysis"
        },
        "data_requirements": {
            "datasets": ["sentinel-2"]
        },
        "analysis": {
            "operation": "temporal_change"
        }
    }

    message = groq.request_tool_call(
        analysis_request,
        [EXECUTE_REMOTE_SENSING_ANALYSIS_TOOL]
    )

    return {
        "content": message.content,
        "tool_calls": [
            {
                "name": call.function.name,
                "arguments": call.function.arguments
            }
            for call in (message.tool_calls or [])
        ]
    }