"""
app/api/v1/chat.py
─────────────────────────────────────────────────────────────────────────────
FastAPI router for the chat endpoint.

This file defines the HTTP interface layer — it only handles HTTP concerns:
  - Parsing the request body
  - Calling the orchestrator
  - Returning a structured response
  - Error handling at the HTTP level

It does NOT contain any AI/ML logic. The orchestrator handles that.

ENDPOINT:
  POST /api/v1/chat

REQUEST BODY: ChatRequest (see app/schemas/requests.py)
RESPONSE:     ChatResponse (see app/schemas/responses.py)
"""

from fastapi import APIRouter, HTTPException, Request
from loguru import logger

from app.schemas.requests import ChatRequest
from app.schemas.responses import ChatResponse, ErrorResponse

# The router is a "mini app" that groups related endpoints.
# It is included in the main FastAPI app in app/main.py.
router = APIRouter(prefix="/api/v1", tags=["Chat"])


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Send a natural-language query to SatQuery AI",
    description=(
        "The main entry point for the SatQuery AI assistant. "
        "Send a natural-language message and optional image paths. "
        "The orchestrator (GPT-OSS) will autonomously select and call "
        "the appropriate specialist geospatial AI tool, then return "
        "a synthesised natural-language answer."
    ),
    responses={
        200: {"model": ChatResponse, "description": "Successful analysis"},
        422: {"description": "Validation error — invalid request body"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def chat(
    request_body: ChatRequest,
    request: Request,  # FastAPI Request object for accessing app state
) -> ChatResponse:
    """
    Main chat endpoint.

    The orchestrator agent is stored in app.state (set in main.py at startup)
    so it is shared across requests and not re-initialised on every call.
    """
    logger.info(
        f"POST /api/v1/chat | "
        f"message='{request_body.message[:80]}...' | "
        f"image={request_body.image_path}"
    )

    # Get the shared orchestrator from app state
    # (set in main.py lifespan — this avoids re-loading models per request)
    agent = request.app.state.agent

    try:
        response = agent.run(
            user_message=request_body.message,
            image_path=request_body.image_path,
            image_url=request_body.image_url,
            image_path_t2=request_body.image_path_t2,
            image_url_t2=request_body.image_url_t2,
            sar_image_path=request_body.sar_image_path,
            sar_image_url=request_body.sar_image_url,
            metadata=request_body.metadata,
            conversation_history=request_body.conversation_history,
            aoi=request_body.aoi,
            date_range=request_body.date_range,
            request_id=request_body.request_id,
        )
        return response

    except Exception as e:
        logger.exception(f"Unhandled error in /api/v1/chat: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}",
        )


@router.get(
    "/health",
    summary="Health check",
    description="Returns the service status and available tools.",
)
async def health(request: Request) -> dict:
    """
    Simple health check endpoint.
    Returns the list of registered tools and the current model mode.
    Useful for verifying the service is running and tools are registered.
    """
    agent = request.app.state.agent
    # ChatOpenAI stores the model name as model_name; fall back gracefully.
    llm_model = getattr(agent._llm, "model_name", None) or "configured"
    return {
        "status": "ok",
        "service": "SatQuery AI",
        "registered_tools": agent._registry.list_tool_names(),
        "llm_model": llm_model,
        "model_mode": request.app.state.model_mode,
    }
