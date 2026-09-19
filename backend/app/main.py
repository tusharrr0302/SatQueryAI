import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.graph.workflow import build_graph
from app.api.routes import api_router
from app.api.websocket import ws_router
from app.api.data_routes import data_router
from app.db.session import engine, Base
from app.db import models

# Ensure all database tables exist
Base.metadata.create_all(bind=engine)

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
app.include_router(data_router)


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


# Serve built frontend web application if dist directory exists
frontend_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist"))
if os.path.isdir(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")