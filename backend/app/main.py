import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.graph.workflow import build_graph
from app.api.routes import api_router
from app.api.websocket import ws_router

app = FastAPI(title="SatQuery AI", description="Interactive Earth-Observation Intelligence Workstation")

# CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for satellite imagery and overlays
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")
image_output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", settings.IMAGE_OUTPUT_DIR))
os.makedirs(image_output_dir, exist_ok=True)
app.mount("/generated-images", StaticFiles(directory=image_output_dir), name="generated-images")

# Include routers
app.include_router(api_router)
app.include_router(ws_router)


@app.get("/health")
def health():
    return {"status": "ok", "app": "SatQuery AI"}


graph = build_graph()


@app.get("/test-graph")
def test_graph():
    result = graph.invoke({
        "user_query": "Show me how Delhi changed over the last 10 years"
    })
    return result