import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.dataset.registry import DATASET_REGISTRY
from app.models.registry import MODEL_REGISTRY
from app.graph.workflow import build_graph
from app.services.worker_client import WorkerClient
from app.schemas.normalized_result import NormalizedResult, AOIInfo, Coordinates
from app.models.manager import ModelNotImplementedError
from app.geo.resolver import AOIResolutionError
from app.imagery.planetary_computer import ImageryError
from app.models.manager import model_manager
from app.api.websocket import ws_manager

api_router = APIRouter(prefix="/api")

def _build_seeded_conversations() -> Dict[str, Dict[str, Any]]:
    return {}

# In-memory storage for persistence during session (pre-seeded with realistic scenarios)
_CONVERSATIONS: Dict[str, Dict[str, Any]] = _build_seeded_conversations()
_INVESTIGATIONS: Dict[str, Dict[str, Any]] = {}
_AOI_CATALOG: Dict[str, Dict[str, Any]] = {
    "aoi_delhi": {
        "id": "aoi_delhi",
        "name": "Delhi NCR",
        "country": "India",
        "center": {"latitude": 28.6139, "longitude": 77.2090},
        "area_km2": 1483.0,
        "bbox": [76.84, 28.40, 77.34, 28.88],
        "created_at": "2026-09-15T12:00:00Z"
    }
}
_RUNTIME_SETTINGS = {
    "model_mode": settings.MODEL_MODE,
    "allow_mock_fallback": settings.ALLOW_MOCK_FALLBACK,
    "prithvi_worker_url": settings.PRITHVI_WORKER_URL,
    "surface_opacity": 0.85,
    "vertical_exaggeration": 2.2,
    "reverse_depth": False,
    "theme": "dark"
}

worker_client = WorkerClient()


class ChatQueryRequest(BaseModel):
    query: str
    conversation_id: Optional[str] = None
    aoi_override: Optional[Dict[str, Any]] = None


class SaveInvestigationRequest(BaseModel):
    id: Optional[str] = None
    name: str
    query: str
    location: str
    aoi: Optional[Dict[str, Any]] = None
    camera_state: Optional[Dict[str, Any]] = None
    datasets: List[str] = Field(default_factory=list)
    layers: List[str] = Field(default_factory=list)
    analysis_type: str = "vegetation"
    visualization_type: str = "3D Surface"
    summary: str = ""
    confidence: Optional[float] = None
    depth_settings: Optional[Dict[str, Any]] = None


# --- CHAT & AGENT WORKFLOW ---

@api_router.post("/chat")
async def chat_query(req: ChatQueryRequest):
    conv_id = req.conversation_id or str(uuid.uuid4())
    now_str = datetime.utcnow().isoformat()

    # Step 1: Broadcast planning event
    await ws_manager.broadcast_event(
        "planning",
        {"query": req.query, "stage": "UNDERSTANDING REQUEST", "timestamp": now_str}
    )

    norm_dict = None
    final_answer = ""
    globe_actions = []
    visualizations = []
    source = "unknown"
    fallback = False
    matched_scenario = None

    # Step 2: Execute workflow via LangGraph dual-path graph
    try:
        graph = build_graph()
        graph_res = await graph.ainvoke({"user_query": req.query})
        norm_dict = graph_res.get("normalized_result")
        final_answer = graph_res.get("final_answer") or graph_res.get("final_response") or ""
        globe_actions = graph_res.get("globe_actions") or []
        visualizations = graph_res.get("visualizations") or []
        source = graph_res.get("source", "unknown")
        fallback = graph_res.get("fallback", False)
        matched_scenario = graph_res.get("matched_scenario")
    except (AOIResolutionError, ImageryError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ModelNotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Live analysis failed: {exc}") from exc

    if not norm_dict:
        raise HTTPException(status_code=500, detail="Live analysis returned no result")

    if hasattr(norm_dict, "model_dump"):
        norm_dict = norm_dict.model_dump()

    aoi = norm_dict.get("aoi", {})
    center = aoi.get("center", {})
    prov = norm_dict.get("provenance", {})
    vis = norm_dict.get("visualization", {})

    # Broadcast source status
    if source == "mock" and matched_scenario:
        await ws_manager.broadcast_event(
            "scenario_matched",
            {"scenario_id": matched_scenario.get("id"), "location": matched_scenario.get("location")}
        )
    else:
        await ws_manager.broadcast_event(
            "gpt_started",
            {"model": "llama-3.3-70b-versatile", "mode": "analysis_and_synthesis"}
        )

    # Step 3: Broadcast tool and globe events
    await ws_manager.broadcast_event(
        "tool_started",
        {"model": prov.get("model_name"), "datasets": prov.get("dataset_ids", [])}
    )

    primary_fly_to = {
        "action": "fly_to",
        "latitude": center.get("latitude"),
        "longitude": center.get("longitude"),
        "name": aoi.get("name"),
        "bbox": aoi.get("bbox"),
        "polygon": aoi.get("polygon"),
        "area_km2": aoi.get("area_km2")
    }

    await ws_manager.broadcast_event("globe_action", primary_fly_to)

    if not globe_actions:
        globe_actions = [primary_fly_to]

    # Ensure visualizations in norm_dict
    if visualizations:
        norm_dict["visualizations"] = visualizations
    elif "visualizations" in norm_dict and norm_dict["visualizations"]:
        visualizations = norm_dict["visualizations"]

    # Ensure location in norm_dict
    if "location" not in norm_dict or not norm_dict["location"]:
        norm_dict["location"] = {
            "name": aoi.get("name"),
            "latitude": center.get("latitude"),
            "longitude": center.get("longitude"),
        }
    norm_dict["source"] = source

    if visualizations:
        first_vis = visualizations[0]
        await ws_manager.broadcast_event(
            "visualization_created",
            {"type": first_vis.get("type"), "title": first_vis.get("title")}
        )
    await ws_manager.broadcast_event("completed", {"result_id": norm_dict.get("result_id")})

    assistant_content = final_answer if final_answer else norm_dict.get("key_finding", "")

    user_msg = {
        "id": f"msg_{uuid.uuid4().hex[:8]}",
        "role": "user",
        "content": req.query,
        "timestamp": now_str,
    }
    assistant_msg = {
        "id": f"msg_{uuid.uuid4().hex[:8]}",
        "role": "assistant",
        "content": assistant_content,
        "result": norm_dict,
        "source": source,
        "model": prov.get("model_name"),
        "datasets": prov.get("dataset_ids", []),
        "visualizations": visualizations,
        "globe_actions": globe_actions,
        "timestamp": now_str,
    }

    if conv_id not in _CONVERSATIONS:
        _CONVERSATIONS[conv_id] = {
            "id": conv_id,
            "title": req.query[:45] + ("..." if len(req.query) > 45 else ""),
            "messages": [],
            "created_at": now_str,
            "last_active": now_str,
            "last_result": norm_dict,
            "source": source,
            "model": prov.get("model_name"),
            "datasets": prov.get("dataset_ids", []),
            "visualizations": visualizations,
            "globe_actions": globe_actions,
        }

    _CONVERSATIONS[conv_id]["messages"].extend([user_msg, assistant_msg])
    _CONVERSATIONS[conv_id]["last_active"] = now_str
    _CONVERSATIONS[conv_id]["last_result"] = norm_dict
    _CONVERSATIONS[conv_id]["source"] = source
    _CONVERSATIONS[conv_id]["model"] = prov.get("model_name")
    _CONVERSATIONS[conv_id]["datasets"] = prov.get("dataset_ids", [])
    _CONVERSATIONS[conv_id]["visualizations"] = visualizations
    _CONVERSATIONS[conv_id]["globe_actions"] = globe_actions

    return {
        "conversation_id": conv_id,
        "user_message": user_msg,
        "assistant_message": assistant_msg,
        "result": norm_dict,
        "globe_actions": globe_actions,
        "globe_action": primary_fly_to,
        "visualizations": visualizations,
        "source": source,
        "fallback": fallback
    }



@api_router.post("/agent/plan")
async def agent_plan(req: ChatQueryRequest):
    return {"query": req.query, "plan": {"task": "live Sentinel-2 analysis", "model": "prithvi-eo-2.0", "datasets": ["sentinel-2"]}}


@api_router.post("/agent/execute")
async def agent_execute(req: ChatQueryRequest):
    return await chat_query(req)


@api_router.get("/test-pipeline/delhi")
def test_delhi_pipeline():
    """Run a real two-year Delhi Sentinel-2 check without the chat/LLM layer."""
    today = datetime.utcnow().date()
    request = {
        "aoi": {"name": "Delhi"},
        "intent": {"temporal_scope": {"start": str(today - timedelta(days=730)), "end": today.isoformat()}},
        "data_requirements": {"datasets": ["sentinel-2"]},
        "analysis": {"operation": "temporal_change"},
    }
    try:
        result = model_manager.execute(model_id="prithvi-eo-2.0", query="Delhi two-year live pipeline check", request=request)
    except (AOIResolutionError, ImageryError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {
        "aoi_bbox": result.aoi_bbox,
        "before_image_url": result.before_image_url,
        "after_image_url": result.after_image_url,
        "time_series": [point.model_dump() for point in result.time_series],
        "metrics": [metric.model_dump() for metric in result.metrics],
    }


@api_router.get("/agent/tools")
def get_agent_tools():
    return {
        "tools": [
            {
                "name": "execute_remote_sensing_analysis",
                "description": "Execute specialized remote sensing model analysis over satellite datasets",
                "parameters": ["model_id", "dataset_ids", "analysis_type"]
            }
        ]
    }


# --- REGISTRIES ---

@api_router.get("/datasets")
def list_datasets():
    return {
        "datasets": [
            {"id": k, **v} for k, v in DATASET_REGISTRY.items()
        ]
    }


@api_router.get("/datasets/{dataset_id}")
def get_dataset(dataset_id: str):
    key = dataset_id.lower()
    if key not in DATASET_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")
    return {"id": key, **DATASET_REGISTRY[key]}


@api_router.get("/models")
def list_models():
    return {
        "models": [
            {"id": k, **v} for k, v in MODEL_REGISTRY.items()
        ]
    }


@api_router.get("/models/{model_id}")
def get_model(model_id: str):
    key = model_id.lower()
    if key not in MODEL_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
    return {"id": key, **MODEL_REGISTRY[key]}


# --- AOI ENDPOINTS ---

@api_router.get("/aoi")
def list_aois():
    return {"aois": list(_AOI_CATALOG.values())}


@api_router.post("/aoi")
def create_aoi(aoi_data: Dict[str, Any]):
    aoi_id = aoi_data.get("id") or f"aoi_{uuid.uuid4().hex[:8]}"
    aoi_data["id"] = aoi_id
    aoi_data["created_at"] = datetime.utcnow().isoformat()
    _AOI_CATALOG[aoi_id] = aoi_data
    return {"status": "created", "aoi": aoi_data}


@api_router.delete("/aoi/{aoi_id}")
def delete_aoi(aoi_id: str):
    if aoi_id in _AOI_CATALOG:
        del _AOI_CATALOG[aoi_id]
        return {"status": "deleted", "id": aoi_id}
    raise HTTPException(status_code=404, detail="AOI not found")


# --- CONVERSATIONS / PERSISTENCE ---

@api_router.get("/conversations")
def list_conversations():
    return {
        "conversations": sorted(
            list(_CONVERSATIONS.values()),
            key=lambda x: x.get("last_active", ""),
            reverse=True
        )
    }


@api_router.get("/conversations/{conv_id}")
def get_conversation(conv_id: str):
    if conv_id not in _CONVERSATIONS:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return _CONVERSATIONS[conv_id]


@api_router.delete("/conversations/{conv_id}")
def delete_conversation(conv_id: str):
    if conv_id in _CONVERSATIONS:
        del _CONVERSATIONS[conv_id]
        return {"status": "deleted", "id": conv_id}
    raise HTTPException(status_code=404, detail="Conversation not found")


# --- INVESTIGATIONS ---

@api_router.get("/investigations")
def list_investigations():
    return {"investigations": list(_INVESTIGATIONS.values())}


@api_router.post("/investigations")
def save_investigation(inv: SaveInvestigationRequest):
    inv_id = inv.id or f"inv_{uuid.uuid4().hex[:8]}"
    data = inv.model_dump()
    data["id"] = inv_id
    data["saved_at"] = datetime.utcnow().isoformat()
    _INVESTIGATIONS[inv_id] = data
    return {"status": "saved", "investigation": data}


@api_router.get("/investigations/{inv_id}")
def get_investigation(inv_id: str):
    if inv_id not in _INVESTIGATIONS:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return _INVESTIGATIONS[inv_id]


@api_router.delete("/investigations/{inv_id}")
def delete_investigation(inv_id: str):
    if inv_id in _INVESTIGATIONS:
        del _INVESTIGATIONS[inv_id]
        return {"status": "deleted", "id": inv_id}
    raise HTTPException(status_code=404, detail="Investigation not found")


# --- SETTINGS ---

@api_router.get("/settings")
def get_settings():
    return _RUNTIME_SETTINGS


@api_router.post("/settings")
def update_settings(new_settings: Dict[str, Any]):
    _RUNTIME_SETTINGS.update(new_settings)
    return {"status": "updated", "settings": _RUNTIME_SETTINGS}
