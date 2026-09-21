import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.config import settings
from app.db.session import get_db
from app.db.models import User, Conversation, Message, InvestigationRecord, DataAssetRecord
from app.api.auth import get_current_user, get_optional_user
from app.dataset.registry import DATASET_REGISTRY
from app.models.registry import MODEL_REGISTRY
from app.graph.workflow import build_graph
from app.services.worker_client import WorkerClient, check_all_model_workers
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
    request_id: Optional[str] = None
    ai_mode: Optional[str] = "auto"
    explicit_model: Optional[str] = None


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
    req_id = req.request_id or str(uuid.uuid4())

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

    # Structured debug logging (Phase 22)
    print(f"\n[CHAT REQUEST]\nconversation_id: {conv_id}\nrequest_id: {req_id}\nquery: {req.query}")

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
                active_asset = {
                    "asset_id": asset_rec.id,
                    "filename": asset_rec.filename,
                    "file_path": asset_rec.file_path,
                    "preview_url": asset_rec.preview_url,
                    "thumbnail_url": asset_rec.thumbnail_url,
                    "profile": asset_rec.profile_json,
                }

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
    active_aoi = None
    # Check if user explicitly asks to return/go back to an earlier topic in the conversation
    import re
    back_match = re.search(r"\b(?:go\s+back\s+to|return\s+to|switch\s+to|back\s+to)\s+([A-Za-z]+)", req.query, re.IGNORECASE)
    if back_match:
        target_loc = back_match.group(1).lower()
        all_conv_msgs = (
            db.query(Message)
            .filter(Message.conversation_id == conv_id)
            .order_by(Message.created_at.desc())
            .all()
        )
        for m in all_conv_msgs:
            if m.role == "assistant" and m.result_json:
                res_aoi = m.result_json.get("aoi", {})
                res_name = (res_aoi.get("name") or "").lower()
                if target_loc in res_name:
                    previous_result = m.result_json
                    active_aoi = res_aoi
                    location_hint = res_aoi.get("name")
                    break

    if not active_aoi:
        for m in recent_db_msgs:
            if m.role == "assistant" and m.result_json:
                previous_result = m.result_json
                aoi_info = previous_result.get("aoi", {})
                if aoi_info and aoi_info.get("name"):
                    active_aoi = aoi_info
                    location_hint = aoi_info.get("name")
                    break

    print(f"[CHAT CONTEXT]\nmessage_count: {len(recent_messages)}\nactive_asset: {req.active_asset_id}\nactive_aoi: {location_hint}")

    # Broadcast planning event scoped to user & request
    await ws_manager.broadcast_event(
        "planning",
        {"query": req.query, "stage": "UNDERSTANDING REQUEST", "timestamp": now_str},
        user_id=user_ws_id,
        conversation_id=conv_id,
        request_id=req_id,
    )

    norm_dict = None
    final_answer = ""
    globe_actions = []
    visualizations = []
    source = "unknown"
    fallback = False
    matched_scenario = None
    status = "success"
    intent_type = "new_analysis"
    graph_res = {}

    # Step 3: Execute workflow via LangGraph with 100% turn persistence guarantee
    try:
        graph = build_graph()
        user_scope_id = current_user.clerk_user_id or str(current_user.id)
        graph_res = await graph.ainvoke({
            "user_query": req.query,
            "conversation_id": conv_id,
            "request_id": req_id,
            "user_id": user_scope_id,
            "active_asset": active_asset,
            "active_aoi": active_aoi,
            "recent_messages": recent_messages,
            "previous_result": previous_result,
            "location_hint": location_hint,
            "ai_mode": req.ai_mode or "auto",
            "explicit_model": req.explicit_model,
        })
        norm_dict = graph_res.get("normalized_result")
        final_answer = graph_res.get("final_answer") or graph_res.get("final_response") or ""
        globe_actions = graph_res.get("globe_actions") or []
        visualizations = graph_res.get("visualizations") or []
        intent_type = graph_res.get("intent_type", "new_analysis")
        if intent_type in ["GENERAL_KNOWLEDGE", "general_knowledge"]:
            source = "gpt_oss"
        else:
            source = graph_res.get("source", "live")
        fallback = graph_res.get("fallback", False)
        matched_scenario = graph_res.get("matched_scenario")
        status = graph_res.get("status") or ("unsupported" if intent_type == "out_of_scope" else "success")

    except Exception as exc:
        logger.exception(f"Workflow execution exception: {exc}")
        status = "analysis_failed"
        source = "error"
        final_answer = f"I couldn't complete this analysis: {str(exc)}. Please refine your query or choose an alternative region."

    if hasattr(norm_dict, "model_dump"):
        norm_dict = norm_dict.model_dump()

    aoi = norm_dict.get("aoi", {}) if norm_dict else {}
    center = aoi.get("center", {}) if aoi else {}
    prov = norm_dict.get("provenance", {}) if norm_dict else {}

    # Structured ATS & Execution logging (Phase 22)
    print(f"[ATS]\nintent: {graph_res.get('intent_type')}\nanalysis_type: {norm_dict.get('analysis_type') if norm_dict else 'None'}\nselected_model: {prov.get('model_name')}\nselected_dataset: {prov.get('dataset_ids')}")
    print(f"[EXECUTION]\nsource: {source}\nstatus: {status}")

    vis_req = graph_res.get("visualization_required")
    if vis_req is None:
        vis_req = norm_dict.get("visualization_required") if isinstance(norm_dict, dict) else None
    if vis_req is None:
        vis_req = False

    conv_mode = graph_res.get("conversational_mode") or (norm_dict.get("conversational_mode") if isinstance(norm_dict, dict) else "answer")
    vis_reason = graph_res.get("visualization_reason") or (norm_dict.get("visualization_reason") if isinstance(norm_dict, dict) else None)
    raw_vis_type = graph_res.get("visualization_type") or (norm_dict.get("visualization_type") if isinstance(norm_dict, dict) else "none")
    vis_type = str(raw_vis_type).lower()

    primary_fly_to = None
    if vis_req and center.get("latitude") is not None and center.get("longitude") is not None:
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
            request_id=req_id,
        )
        if not globe_actions:
            globe_actions = [primary_fly_to]
    elif not vis_req:
        globe_actions = []

    # Check if conversational response
    is_conversational = graph_res.get("is_conversational", False) or (isinstance(norm_dict, dict) and norm_dict.get("is_conversational", False)) or intent_type in [
        "RESULT_EXPLANATION", "PROVENANCE_QUESTION", "VISUALIZATION_REQUEST",
        "GENERAL_KNOWLEDGE", "CLARIFICATION", "conversational_explanation", "out_of_scope"
    ]

    # Ensure visualizations and location in norm_dict if present
    if norm_dict:
        norm_dict["is_conversational"] = bool(is_conversational)
        norm_dict["question_type"] = intent_type
        norm_dict["conversational_mode"] = conv_mode
        norm_dict["visualization_required"] = vis_req
        norm_dict["visualization_reason"] = vis_reason
        norm_dict["visualization_type"] = vis_type
        if visualizations and vis_req:
            norm_dict["visualizations"] = visualizations
        elif not vis_req:
            norm_dict["visualizations"] = []
            visualizations = []
            norm_dict["visualization_plan"] = None
            norm_dict["layers"] = []
        elif "visualizations" in norm_dict and norm_dict["visualizations"]:
            visualizations = norm_dict["visualizations"]

        if "location" not in norm_dict or not norm_dict["location"]:
            norm_dict["location"] = {
                "name": aoi.get("name"),
                "latitude": center.get("latitude"),
                "longitude": center.get("longitude"),
            }
        norm_dict["source"] = source

    await ws_manager.broadcast_event(
        "completed",
        {"status": status, "result_id": norm_dict.get("result_id") if norm_dict else None},
        user_id=user_ws_id,
        conversation_id=conv_id,
        request_id=req_id,
    )

    # Step 4: Save turn to Database with ACID transaction
    assistant_content = final_answer if final_answer else (norm_dict.get("key_finding", "") if norm_dict else "Analysis complete.")
    print(f"[CHAT RESPONSE]\nassistant_message_length: {len(assistant_content)}\nconversation_id: {conv_id}\n")
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
    layers = norm_dict.get("layers", []) if (norm_dict and vis_req) else []
    vis_plan = (graph_res.get("visualization_plan") or (norm_dict.get("visualization_plan") if norm_dict else None)) if vis_req else None
    web_evidence = graph_res.get("web_evidence") or (norm_dict.get("web_evidence") if norm_dict else [])
    ai_mode_val = graph_res.get("ai_mode") or (norm_dict.get("ai_mode") if norm_dict else req.ai_mode or "auto")

    assistant_msg = {
        "id": assistant_msg_db.id,
        "role": "assistant",
        "content": assistant_content,
        "result": norm_dict,
        "source": source,
        "model": prov.get("model_name"),
        "datasets": prov.get("dataset_ids", []),
        "visualizations": visualizations,
        "visualization_plan": vis_plan,
        "web_evidence": web_evidence,
        "ai_mode": ai_mode_val,
        "layers": layers,
        "globe_actions": globe_actions,
        "is_conversational": bool(is_conversational),
        "question_type": intent_type,
        "conversational_mode": conv_mode,
        "visualization_required": vis_req,
        "visualization_reason": vis_reason,
        "visualization_type": vis_type,
        "timestamp": assistant_msg_db.created_at.isoformat(),
    }

    # Section 9: Answer-First Response Contract
    canonical_mode = str(conv_mode).lower()
    canonical_vis_type = "none" if not vis_req else str(vis_type).lower()

    response_block = {
        "mode": canonical_mode,
        "answer": assistant_content,
        "conversation_id": conv_id,
        "request_id": req_id,
        "status": status,
    }
    visualization_block = {
        "required": bool(vis_req),
        "reason": vis_reason or ("Visualization enabled for spatial analysis." if vis_req else "Direct conversational answer; no spatial visualization required."),
        "type": canonical_vis_type,
    }
    provenance_list = []
    if prov:
        provenance_list.append(prov)
    execution_list = (norm_dict.get("audit_trace") if norm_dict else []) or graph_res.get("audit_trace") or []
    evidence_list = web_evidence if web_evidence else (norm_dict.get("metrics") if norm_dict else [])

    if not vis_req:
        layers = []
        visualizations = []
        globe_actions = []
        primary_fly_to = None
        vis_plan = None

    return {
        "response": response_block,
        "visualization": visualization_block,
        "evidence": evidence_list,
        "provenance": provenance_list,
        "execution": execution_list,
        # Backward-compatible fields
        "conversation_id": conv_id,
        "request_id": req_id,
        "status": status,
        "user_message": user_msg,
        "assistant_message": assistant_msg,
        "analysis_request": graph_res.get("analysis_request"),
        "normalized_result": norm_dict,
        "result": norm_dict,
        "layers": layers,
        "globe_actions": globe_actions,
        "globe_action": primary_fly_to,
        "visualizations": visualizations,
        "visualization_plan": vis_plan,
        "web_evidence": web_evidence,
        "ai_mode": ai_mode_val,
        "source": source,
        "fallback": fallback,
        "is_conversational": bool(is_conversational),
        "question_type": intent_type,
        "conversational_mode": conv_mode,
        "visualization_required": vis_req,
        "visualization_reason": vis_reason,
        "visualization_type": vis_type,
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


@api_router.get("/v1/health/models")
@api_router.get("/health/models")
async def health_models():
    """
    Health check for all specialist remote AI workers.
    Returns reachability and status for Prithvi, EarthDial, GeoChat, VisTA, CLOSP, TerraFM.
    """
    return await check_all_model_workers()


class ModelDebugRequest(BaseModel):
    query: Optional[str] = "Analyze this region for land-cover change"
    inputs: Optional[Dict[str, Any]] = None
    request: Optional[Dict[str, Any]] = None


@api_router.post("/v1/debug/model/{model_id}")
@api_router.post("/debug/model/{model_id}")
async def debug_model(model_id: str, req: Optional[ModelDebugRequest] = None):
    """
    Diagnostic execution endpoint to verify real model execution independently.
    Reports model ID, worker URL, worker status, execution duration, real/mock source,
    fallback state, model result, and errors if any. Never exposes API keys or secrets.
    """
    import time
    start_t = time.time()
    req_data = req.request if (req and req.request) else {}
    inputs_data = dict(req.inputs) if (req and req.inputs) else {}
    query_text = req.query if (req and req.query) else "Diagnostic specialist execution"

    # Provide real verified fixtures if inputs are omitted
    mid = model_id.lower().strip()
    if not inputs_data:
        if mid in ("closp",):
            inputs_data = {
                "sar_image_url": "https://raw.githubusercontent.com/cloudtostreet/Sen1Floods11/master/sample/S1/Spain_7370579_S1Hand.tif",
                "optical_image_url": "https://raw.githubusercontent.com/cloudtostreet/Sen1Floods11/master/sample/S2/Spain_7370579_S2Hand.tif",
            }
        elif mid in ("prithvi", "prithvi-eo-2.0"):
            inputs_data = {
                "image_t1": "https://huggingface.co/ibm-nasa-geospatial/Prithvi-EO-2.0-300M/resolve/main/examples/Mexico_HLS.S30.T13REM.2018026T173609.v2.0_cropped.tif",
                "image_t2": "https://huggingface.co/ibm-nasa-geospatial/Prithvi-EO-2.0-300M/resolve/main/examples/Mexico_HLS.S30.T13REM.2018106T172859.v2.0_cropped.tif",
                "image_t3": "https://huggingface.co/ibm-nasa-geospatial/Prithvi-EO-2.0-300M/resolve/main/examples/Mexico_HLS.S30.T13REM.2018201T172901.v2.0_cropped.tif",
                "image_t4": "https://huggingface.co/ibm-nasa-geospatial/Prithvi-EO-2.0-300M/resolve/main/examples/Mexico_HLS.S30.T13REM.2018266T173029.v2.0_cropped.tif",
            }
        elif mid in ("earthdial", "earthdial-4b-ms"):
            inputs_data = {
                "image_url": "https://raw.githubusercontent.com/open-mmlab/mmcv/master/tests/data/color.jpg",
            }

    try:
        norm = await worker_client.execute(
            model_id=model_id,
            request=req_data,
            inputs=inputs_data,
            query=query_text,
        )
        duration = time.time() - start_t
        return {
            "model": model_id,
            "worker": norm.provenance.worker_url or "local",
            "worker_status": "success",
            "status": "success",
            "execution_time": round(duration, 3),
            "source": norm.provenance.source,
            "fallback": norm.provenance.fallback,
            "request_id": norm.result_id,
            "provenance": norm.provenance.model_dump(),
            "key_finding": norm.key_finding,
            "metrics": [m.model_dump() for m in norm.metrics],
            "result": norm.model_dump(),
            "error": None,
        }
    except Exception as exc:
        duration = time.time() - start_t
        return {
            "model": model_id,
            "worker": worker_client.get_worker_url(model_id) or "not_configured",
            "worker_status": "error",
            "status": "failed",
            "execution_time": round(duration, 3),
            "source": "remote_worker",
            "fallback": False,
            "result": None,
            "error": str(exc),
        }



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


# --- EARTH OBSERVATION DATA & LAYER CATALOG ---

class ValidateCustomLayerRequest(BaseModel):
    dataset_id: str
    spec: Dict[str, Any]
    layer_name: Optional[str] = None


@api_router.get("/catalog/summary")
def get_catalog_summary(current_user: Optional[User] = Depends(get_optional_user)):
    """
    Returns verified summary of the Earth Observation Data and Layer Catalog.
    Strictly reports verified counts according to Section 26.
    """
    from app.dataset.registry import get_all_datasets
    from app.dataset.layer_catalog import get_all_layers

    datasets = get_all_datasets()
    layers = get_all_layers()
    providers = sorted(list({d.provider for d in datasets}))
    modalities = sorted(list({d.modality for d in datasets}))

    return {
        "verified_dataset_count": len(datasets),
        "verified_layer_count": len(layers),
        "providers": providers,
        "modalities": modalities,
        "ecosystem": "Copernicus Data Space Ecosystem & Federated Sensors",
        "verified_note": "SatQuery AI provides verified, authenticated access to 13 satellite & global observation collections and 21+ analytical layer formulations.",
    }


@api_router.get("/catalog/datasets")
def get_catalog_datasets(current_user: Optional[User] = Depends(get_optional_user)):
    """
    Lists all extensible satellite and model dataset metadata in the unified registry.
    """
    from app.dataset.registry import get_all_datasets
    from app.dataset.layer_catalog import get_layers_for_dataset

    datasets = get_all_datasets()
    results = []
    for d in datasets:
        d_dict = d.model_dump()
        layers = get_layers_for_dataset(d.dataset_id)
        d_dict["verified_layer_count"] = len(layers)
        d_dict["layers"] = [l.model_dump() for l in layers]
        results.append(d_dict)

    return {"datasets": results, "total": len(results)}


@api_router.get("/catalog/datasets/{dataset_id}")
def get_catalog_dataset_detail(dataset_id: str, current_user: Optional[User] = Depends(get_optional_user)):
    """
    Retrieves detailed metadata for a single dataset along with all its registered layer definitions.
    """
    from app.dataset.registry import get_dataset
    from app.dataset.layer_catalog import get_layers_for_dataset

    ds = get_dataset(dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found in registry.")

    layers = get_layers_for_dataset(ds.dataset_id)
    result = ds.model_dump()
    result["layers"] = [l.model_dump() for l in layers]
    result["verified_layer_count"] = len(layers)
    return result


@api_router.get("/catalog/layers")
def get_catalog_layers(
    dataset_id: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    current_user: Optional[User] = Depends(get_optional_user),
):
    """
    Query and filter the Earth Observation Layer Catalog by dataset, category, or search term.
    """
    from app.dataset.layer_catalog import get_all_layers, get_layers_for_dataset, search_layers_by_category, search_layers

    if dataset_id:
        layers = get_layers_for_dataset(dataset_id)
    elif category:
        layers = search_layers_by_category(category)
    elif search:
        layers = search_layers(search)
    else:
        layers = get_all_layers()

    return {
        "layers": [l.model_dump() for l in layers],
        "total": len(layers),
    }


@api_router.post("/catalog/custom-layer/validate")
def validate_custom_layer(
    req: ValidateCustomLayerRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Validates a user-defined custom band composite or mathematical index formula without executing arbitrary code.
    """
    from app.schemas.data_catalog import CustomVisualizationSpec
    from app.dataset.custom_expression import validate_custom_visualization_spec, create_custom_layer_definition

    try:
        spec = CustomVisualizationSpec.model_validate(req.spec)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid CustomVisualizationSpec format: {e}")

    is_valid, errors, meta = validate_custom_visualization_spec(spec, req.dataset_id)
    if not is_valid:
        return {
            "is_valid": False,
            "errors": errors,
            "metadata": {},
        }

    try:
        layer_def = create_custom_layer_definition(spec, req.dataset_id, req.layer_name)
        return {
            "is_valid": True,
            "errors": [],
            "metadata": meta,
            "layer_definition": layer_def.model_dump(),
        }
    except Exception as e:
        return {
            "is_valid": False,
            "errors": [str(e)],
            "metadata": {},
        }


@api_router.get("/imagery/rendered/{artifact_id}")
@api_router.get("/imagery/rendered/{artifact_id}.png")
@api_router.head("/imagery/rendered/{artifact_id}")
@api_router.head("/imagery/rendered/{artifact_id}.png")
def get_rendered_imagery(artifact_id: str):
    from pathlib import Path
    from fastapi.responses import FileResponse

    clean_id = artifact_id.removesuffix(".png")
    base_dir = Path(__file__).resolve().parent.parent  # backend/app
    candidate_paths = [
        base_dir / "static" / "generated" / f"{clean_id}.png",
        base_dir / "static" / "images" / f"{clean_id}.png",
        base_dir.parent.parent / "app" / "static" / "generated" / f"{clean_id}.png",
        Path("app/static/generated") / f"{clean_id}.png",
        Path("backend/app/static/generated") / f"{clean_id}.png",
    ]
    target_path = None
    for p in candidate_paths:
        if p.exists() and p.is_file():
            target_path = p
            break

    if not target_path:
        raise HTTPException(status_code=404, detail="Rendered image artifact not found.")

    return FileResponse(
        str(target_path),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )
