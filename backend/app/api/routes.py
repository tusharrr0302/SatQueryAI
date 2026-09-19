import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.db.models import User, Conversation, Message, InvestigationRecord, DataAssetRecord
from app.api.auth import get_current_user
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
    active_asset_id: Optional[str] = None


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
async def chat_query(
    req: ChatQueryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    now_str = datetime.utcnow().isoformat()

    # Verify or create conversation owned by user
    conv = None
    if req.conversation_id:
        conv = db.query(Conversation).filter(Conversation.id == req.conversation_id).first()
        if conv and conv.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to access this conversation")

    if not conv:
        conv_id = req.conversation_id or str(uuid.uuid4())
        conv = Conversation(
            id=conv_id,
            user_id=current_user.id,
            title=req.query[:45] + ("..." if len(req.query) > 45 else ""),
            created_at=datetime.utcnow(),
            last_message_at=datetime.utcnow(),
            active_asset_id=req.active_asset_id,
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)
    else:
        conv_id = conv.id

    user_ws_id = current_user.clerk_user_id

    # Step 1: Broadcast planning event scoped to user
    await ws_manager.broadcast_event(
        "planning",
        {"query": req.query, "stage": "UNDERSTANDING REQUEST", "timestamp": now_str},
        user_id=user_ws_id,
        conversation_id=conv_id,
    )

    norm_dict = None
    final_answer = ""
    globe_actions = []
    visualizations = []
    source = "unknown"
    fallback = False
    matched_scenario = None

    active_asset = None
    if req.active_asset_id:
        from app.api.data_routes import _ASSET_CATALOG
        if req.active_asset_id in _ASSET_CATALOG:
            active_asset = _ASSET_CATALOG[req.active_asset_id].model_dump()
        else:
            asset_rec = (
                db.query(DataAssetRecord)
                .filter(DataAssetRecord.id == req.active_asset_id, DataAssetRecord.user_id == current_user.id)
                .first()
            )
            if asset_rec:
                active_asset = asset_rec.profile_json

    # Step 2: Load bounded conversation context for ATS
    recent_db_msgs = (
        db.query(Message)
        .filter(Message.conversation_id == conv_id)
        .order_by(Message.created_at.desc())
        .limit(6)
        .all()
    )
    recent_messages = [
        {"role": m.role, "content": m.content}
        for m in reversed(recent_db_msgs)
    ]
    previous_result = None
    location_hint = None
    for m in reversed(recent_db_msgs):
        if m.role == "assistant" and m.result_json:
            previous_result = m.result_json
            aoi_info = previous_result.get("aoi", {})
            location_hint = aoi_info.get("name")
            break

    # Step 3: Execute workflow via LangGraph dual-path graph
    try:
        graph = build_graph()
        user_scope_id = current_user.clerk_user_id or str(current_user.id)
        graph_res = await graph.ainvoke({
            "user_query": req.query,
            "conversation_id": conv_id,
            "user_id": user_scope_id,
            "active_asset": active_asset,
            "recent_messages": recent_messages,
            "previous_result": previous_result,
            "location_hint": location_hint,
        })
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

    # Broadcast source status scoped to user
    if source == "mock" and matched_scenario:
        await ws_manager.broadcast_event(
            "scenario_matched",
            {"scenario_id": matched_scenario.get("id"), "location": matched_scenario.get("location")},
            user_id=user_ws_id,
            conversation_id=conv_id,
        )
    else:
        await ws_manager.broadcast_event(
            "gpt_started",
            {"model": "llama-3.3-70b-versatile", "mode": "analysis_and_synthesis"},
            user_id=user_ws_id,
            conversation_id=conv_id,
        )

    # Step 3: Broadcast tool and globe events scoped to user
    await ws_manager.broadcast_event(
        "tool_started",
        {"model": prov.get("model_name"), "datasets": prov.get("dataset_ids", [])},
        user_id=user_ws_id,
        conversation_id=conv_id,
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

    await ws_manager.broadcast_event(
        "globe_action",
        primary_fly_to,
        user_id=user_ws_id,
        conversation_id=conv_id,
    )

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
            {"type": first_vis.get("type"), "title": first_vis.get("title")},
            user_id=user_ws_id,
            conversation_id=conv_id,
        )
    await ws_manager.broadcast_event(
        "completed",
        {"result_id": norm_dict.get("result_id")},
        user_id=user_ws_id,
        conversation_id=conv_id,
    )

    assistant_content = final_answer if final_answer else norm_dict.get("key_finding", "")

    # Persist turns in PostgreSQL
    user_msg_db = Message(
        id=f"msg_{uuid.uuid4().hex[:8]}",
        conversation_id=conv_id,
        user_id=current_user.id,
        role="user",
        content=req.query,
        created_at=datetime.utcnow(),
    )
    assistant_msg_db = Message(
        id=f"msg_{uuid.uuid4().hex[:8]}",
        conversation_id=conv_id,
        user_id=current_user.id,
        role="assistant",
        content=assistant_content,
        result_json=norm_dict,
        model_name=prov.get("model_name"),
        datasets=prov.get("dataset_ids", []),
        visualizations=visualizations,
        globe_actions=globe_actions,
        source=source,
        created_at=datetime.utcnow(),
    )
    conv.last_message_at = datetime.utcnow()
    conv.updated_at = datetime.utcnow()
    if req.active_asset_id:
        conv.active_asset_id = req.active_asset_id

    db.add(user_msg_db)
    db.add(assistant_msg_db)
    db.commit()

    user_msg = {
        "id": user_msg_db.id,
        "role": "user",
        "content": req.query,
        "timestamp": user_msg_db.created_at.isoformat(),
    }
    layers = norm_dict.get("layers", [])

    assistant_msg = {
        "id": assistant_msg_db.id,
        "role": "assistant",
        "content": assistant_content,
        "result": norm_dict,
        "source": source,
        "model": prov.get("model_name"),
        "datasets": prov.get("dataset_ids", []),
        "visualizations": visualizations,
        "layers": layers,
        "globe_actions": globe_actions,
        "timestamp": assistant_msg_db.created_at.isoformat(),
    }

    return {
        "conversation_id": conv_id,
        "user_message": user_msg,
        "assistant_message": assistant_msg,
        "result": norm_dict,
        "layers": layers,
        "globe_actions": globe_actions,
        "globe_action": primary_fly_to,
        "visualizations": visualizations,
        "source": source,
        "fallback": fallback
    }


# --- GEOSPATIAL DATA LAYERS (PHASE 3) ---

@api_router.get("/layers")
async def list_registered_layers(
    conversation_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns data layers associated with the current conversation or user session.
    Enforces ownership/access isolation for private user-uploaded raster layers.
    """
    if not conversation_id:
        conv = (
            db.query(Conversation)
            .filter(Conversation.user_id == current_user.id)
            .order_by(Conversation.last_message_at.desc())
            .first()
        )
    else:
        conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if conv and conv.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to access layers for this conversation")

    if not conv:
        return {"layers": [], "conversation_id": None}

    last_assistant_msg = (
        db.query(Message)
        .filter(Message.conversation_id == conv.id, Message.role == "assistant")
        .order_by(Message.created_at.desc())
        .first()
    )
    if not last_assistant_msg or not last_assistant_msg.result_json:
        return {"layers": [], "conversation_id": conv.id}

    layers = last_assistant_msg.result_json.get("layers", [])
    user_scope_id = current_user.clerk_user_id or str(current_user.id)
    authorized_layers = [
        l for l in layers
        if not l.get("access", {}).get("is_private") or l.get("access", {}).get("user_id") in [user_scope_id, current_user.id, current_user.clerk_user_id]
    ]
    return {"layers": authorized_layers, "conversation_id": conv.id}


@api_router.get("/layers/{layer_id}")
async def get_layer_specification(
    layer_id: str,
    conversation_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Fetch authoritative specification for a single geospatial data layer by layer_id.
    """
    res = await list_registered_layers(conversation_id=conversation_id, current_user=current_user, db=db)
    layers = res.get("layers", [])
    layer = next((l for l in layers if l.get("layer_id") == layer_id), None)
    if not layer:
        raise HTTPException(status_code=404, detail=f"Layer '{layer_id}' not found in active analysis session")
    return layer



@api_router.post("/agent/plan")
async def agent_plan(req: ChatQueryRequest, current_user: User = Depends(get_current_user)):
    return {"query": req.query, "plan": {"task": "live Sentinel-2 analysis", "model": "prithvi-eo-2.0", "datasets": ["sentinel-2"]}}


@api_router.post("/agent/execute")
async def agent_execute(
    req: ChatQueryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return await chat_query(req, current_user=current_user, db=db)


@api_router.get("/test-pipeline/delhi")
def test_delhi_pipeline(current_user: User = Depends(get_current_user)):
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
def get_agent_tools(current_user: User = Depends(get_current_user)):
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
def list_datasets(current_user: User = Depends(get_current_user)):
    return {
        "datasets": [
            {"id": k, **v} for k, v in DATASET_REGISTRY.items()
        ]
    }


@api_router.get("/datasets/{dataset_id}")
def get_dataset(dataset_id: str, current_user: User = Depends(get_current_user)):
    key = dataset_id.lower()
    if key not in DATASET_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")
    return {"id": key, **DATASET_REGISTRY[key]}


@api_router.get("/models")
def list_models(current_user: User = Depends(get_current_user)):
    return {
        "models": [
            {"id": k, **v} for k, v in MODEL_REGISTRY.items()
        ]
    }


@api_router.get("/models/{model_id}")
def get_model(model_id: str, current_user: User = Depends(get_current_user)):
    key = model_id.lower()
    if key not in MODEL_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
    return {"id": key, **MODEL_REGISTRY[key]}


# --- AOI ENDPOINTS ---

@api_router.get("/aoi")
def list_aois(current_user: User = Depends(get_current_user)):
    return {"aois": list(_AOI_CATALOG.values())}


@api_router.post("/aoi")
def create_aoi(aoi_data: Dict[str, Any], current_user: User = Depends(get_current_user)):
    aoi_id = aoi_data.get("id") or f"aoi_{uuid.uuid4().hex[:8]}"
    aoi_data["id"] = aoi_id
    aoi_data["created_at"] = datetime.utcnow().isoformat()
    _AOI_CATALOG[aoi_id] = aoi_data
    return {"status": "created", "aoi": aoi_data}


@api_router.delete("/aoi/{aoi_id}")
def delete_aoi(aoi_id: str, current_user: User = Depends(get_current_user)):
    if aoi_id in _AOI_CATALOG:
        del _AOI_CATALOG[aoi_id]
        return {"status": "deleted", "id": aoi_id}
    raise HTTPException(status_code=404, detail="AOI not found")


# --- CONVERSATIONS / PERSISTENCE ---

@api_router.get("/conversations")
def list_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    convs = (
        db.query(Conversation)
        .filter(Conversation.user_id == current_user.id)
        .order_by(Conversation.last_message_at.desc())
        .all()
    )
    result = []
    for c in convs:
        last_msg = (
            db.query(Message)
            .filter(Message.conversation_id == c.id)
            .order_by(Message.created_at.desc())
            .first()
        )
        msg_count = db.query(Message).filter(Message.conversation_id == c.id).count()
        result.append({
            "id": c.id,
            "title": c.title,
            "created_at": c.created_at.isoformat(),
            "last_active": c.last_message_at.isoformat(),
            "message_count": msg_count,
            "active_asset_id": c.active_asset_id,
            "last_result": last_msg.result_json if last_msg and last_msg.role == "assistant" else None,
            "model": last_msg.model_name if last_msg else None,
            "datasets": last_msg.datasets if last_msg else [],
            "visualizations": last_msg.visualizations if last_msg else [],
            "globe_actions": last_msg.globe_actions if last_msg else [],
        })
    return {"conversations": result}


@api_router.get("/conversations/{conv_id}")
def get_conversation(
    conv_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    c = (
        db.query(Conversation)
        .filter(Conversation.id == conv_id, Conversation.user_id == current_user.id)
        .first()
    )
    if not c:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conv_id)
        .order_by(Message.created_at.asc())
        .all()
    )

    formatted_msgs = []
    last_result = None
    model_name = None
    datasets = []
    visualizations = []
    globe_actions = []
    source = None

    for m in messages:
        msg_obj = {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "timestamp": m.created_at.isoformat(),
        }
        if m.role == "assistant":
            msg_obj["result"] = m.result_json
            msg_obj["model"] = m.model_name
            msg_obj["datasets"] = m.datasets or []
            msg_obj["visualizations"] = m.visualizations or []
            msg_obj["globe_actions"] = m.globe_actions or []
            msg_obj["source"] = m.source
            last_result = m.result_json
            model_name = m.model_name
            datasets = m.datasets or []
            visualizations = m.visualizations or []
            globe_actions = m.globe_actions or []
            source = m.source
        formatted_msgs.append(msg_obj)

    return {
        "id": c.id,
        "title": c.title,
        "messages": formatted_msgs,
        "created_at": c.created_at.isoformat(),
        "last_active": c.last_message_at.isoformat(),
        "last_result": last_result,
        "layers": last_result.get("layers", []) if (last_result and isinstance(last_result, dict)) else [],
        "model": model_name,
        "datasets": datasets,
        "visualizations": visualizations,
        "globe_actions": globe_actions,
        "source": source,
    }


@api_router.delete("/conversations/{conv_id}")
def delete_conversation(
    conv_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    c = (
        db.query(Conversation)
        .filter(Conversation.id == conv_id, Conversation.user_id == current_user.id)
        .first()
    )
    if not c:
        raise HTTPException(status_code=404, detail="Conversation not found")
    db.delete(c)
    db.commit()
    return {"status": "deleted", "id": conv_id}


# --- INVESTIGATIONS ---

@api_router.get("/investigations")
def list_investigations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    invs = (
        db.query(InvestigationRecord)
        .filter(InvestigationRecord.user_id == current_user.id)
        .order_by(InvestigationRecord.created_at.desc())
        .all()
    )
    return {
        "investigations": [
            {
                "id": inv.id,
                "name": inv.name,
                "query": inv.query,
                "location": inv.location,
                "datasets": inv.datasets or [],
                "analysis_type": inv.analysis_type,
                "visualization_type": inv.visualization_type,
                "summary": inv.summary,
                "saved_at": inv.created_at.isoformat(),
            }
            for inv in invs
        ]
    }


@api_router.post("/investigations")
def save_investigation(
    inv: SaveInvestigationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inv_id = inv.id or f"inv_{uuid.uuid4().hex[:8]}"
    existing = (
        db.query(InvestigationRecord)
        .filter(InvestigationRecord.id == inv_id, InvestigationRecord.user_id == current_user.id)
        .first()
    )
    if existing:
        existing.name = inv.name
        existing.query = inv.query
        existing.location = inv.location
        existing.datasets = inv.datasets
        existing.analysis_type = inv.analysis_type
        existing.visualization_type = inv.visualization_type
        existing.summary = inv.summary
        db.commit()
        db.refresh(existing)
        saved_inv = existing
    else:
        new_inv = InvestigationRecord(
            id=inv_id,
            user_id=current_user.id,
            name=inv.name,
            query=inv.query,
            location=inv.location,
            datasets=inv.datasets,
            analysis_type=inv.analysis_type,
            visualization_type=inv.visualization_type,
            summary=inv.summary,
            created_at=datetime.utcnow(),
        )
        db.add(new_inv)
        db.commit()
        db.refresh(new_inv)
        saved_inv = new_inv

    return {
        "status": "saved",
        "investigation": {
            "id": saved_inv.id,
            "name": saved_inv.name,
            "query": saved_inv.query,
            "location": saved_inv.location,
            "datasets": saved_inv.datasets,
            "analysis_type": saved_inv.analysis_type,
            "visualization_type": saved_inv.visualization_type,
            "summary": saved_inv.summary,
            "saved_at": saved_inv.created_at.isoformat(),
        },
    }


@api_router.get("/investigations/{inv_id}")
def get_investigation(
    inv_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inv = (
        db.query(InvestigationRecord)
        .filter(InvestigationRecord.id == inv_id, InvestigationRecord.user_id == current_user.id)
        .first()
    )
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return {
        "id": inv.id,
        "name": inv.name,
        "query": inv.query,
        "location": inv.location,
        "datasets": inv.datasets or [],
        "analysis_type": inv.analysis_type,
        "visualization_type": inv.visualization_type,
        "summary": inv.summary,
        "saved_at": inv.created_at.isoformat(),
    }


@api_router.delete("/investigations/{inv_id}")
def delete_investigation(
    inv_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inv = (
        db.query(InvestigationRecord)
        .filter(InvestigationRecord.id == inv_id, InvestigationRecord.user_id == current_user.id)
        .first()
    )
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    db.delete(inv)
    db.commit()
    return {"status": "deleted", "id": inv_id}


# --- SETTINGS ---

@api_router.get("/settings")
def get_settings(current_user: User = Depends(get_current_user)):
    return _RUNTIME_SETTINGS


@api_router.post("/settings")
def update_settings(new_settings: Dict[str, Any], current_user: User = Depends(get_current_user)):
    _RUNTIME_SETTINGS.update(new_settings)
    return {"status": "updated", "settings": _RUNTIME_SETTINGS}
