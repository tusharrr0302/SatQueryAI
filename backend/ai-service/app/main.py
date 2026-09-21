"""
app/main.py
─────────────────────────────────────────────────────────────────────────────
FastAPI application factory and entry point.

This file:
  1. Creates the FastAPI app
  2. Configures logging (loguru)
  3. Initialises the orchestrator agent at startup
  4. Registers API routers
  5. Provides the entry point to run with uvicorn

RUNNING THE SERVICE:
  From the ai-service/ directory:

  Option 1 — via Python module:
    python -m app.main

  Option 2 — via uvicorn directly:
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  Option 3 — via uvicorn with hot reload (development):
    uvicorn app.main:app --reload

After starting, visit:
  http://localhost:8000/docs          — interactive API documentation
  http://localhost:8000/api/v1/health — health check
"""

import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.config import settings
from app.api.v1.chat import router as chat_router


# ─────────────────────────────────────────────────────────────────────────────
# Logging setup
# loguru intercepts everything, including uvicorn's own logs.
# ─────────────────────────────────────────────────────────────────────────────

def setup_logging() -> None:
    """
    Configure loguru for human-readable development logs.
    Every agent step, tool call, and model result will appear here.
    """
    logger.remove()  # Remove the default handler
    logger.add(
        sys.stdout,
        level=settings.log_level,
        format=(
            "<green>{time:HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{line}</cyan> — "
            "<level>{message}</level>"
        ),
        colorize=True,
    )
    # Also write logs to a file for debugging sessions
    logger.add(
        "logs/satquery.log",
        level="DEBUG",
        rotation="10 MB",
        retention="7 days",
        format="{time} | {level} | {name}:{line} — {message}",
    )
    logger.info("Logging configured")


# ─────────────────────────────────────────────────────────────────────────────
# Application lifespan
# Code in this function runs ONCE at startup and ONCE at shutdown.
# This is where we initialise expensive resources (models, LLM clients).
# ─────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager.

    Everything BEFORE the `yield` runs at startup.
    Everything AFTER the `yield` runs at shutdown.
    """
    # ── Startup ───────────────────────────────────────────────────────────────
    setup_logging()

    logger.info("=" * 60)
    logger.info("  SatQuery AI — Starting up")
    logger.info("=" * 60)
    logger.info(f"  LLM provider : {settings.llm_provider}")
    logger.info(f"  LLM model    : {settings.llm_model}")
    logger.info(f"  Model mode   : {settings.model_mode}")
    logger.info(f"  Log level    : {settings.log_level}")
    logger.info("=" * 60)

    # Initialise the orchestrator agent.
    # This also initialises the LLM client, tool registry, and all specialist
    # model wrappers. In real mode, model weights would be loaded here.
    from app.orchestrator.agent import OrchestratorAgent
    agent = OrchestratorAgent()

    # Store the agent in app.state so all request handlers can access it
    # without re-creating it on every request.
    app.state.agent = agent
    app.state.model_mode = settings.model_mode

    logger.info("SatQuery AI is ready to handle requests")
    logger.info(f"Docs available at: http://{settings.service_host}:{settings.service_port}/docs")

    yield  # Application is running

    # ── Shutdown ──────────────────────────────────────────────────────────────
    logger.info("SatQuery AI shutting down...")


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI Application
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="SatQuery AI",
    description=(
        "Interactive Vision-Language Assistant for Multimodal Remote Sensing "
        "Image Analysis through Natural Language Queries. "
        "Powered by GPT-OSS orchestration and specialist geospatial AI models "
        "(GeoChat-7B, VisTA, Prithvi-EO-2.0, CLOSP, TerraFM)."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS Middleware ───────────────────────────────────────────────────────────
# Allows the Svelte frontend (or any origin during development) to call this API.
# Tighten this for production by listing only your frontend's domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # Change to specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register routers ──────────────────────────────────────────────────────────
app.include_router(chat_router)


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# Allows running with: python -m app.main
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.service_host,
        port=settings.service_port,
        reload=True,   # Auto-reload on code changes (development mode)
        log_level=settings.log_level.lower(),
    )
