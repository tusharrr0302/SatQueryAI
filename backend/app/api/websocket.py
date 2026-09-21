"""
SatQuery AI — WebSocket Connection Manager
Supports authenticated, user-scoped, and conversation-scoped event streaming.
Prevents cross-user telemetry leakage.
"""
import asyncio
import json
import logging
from typing import Dict, Optional, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status

from app.config import settings

logger = logging.getLogger(__name__)

ws_router = APIRouter()


class ConnectionManager:
    def __init__(self):
        # Maps user_id -> Set[WebSocket]
        self.user_connections: Dict[str, Set[WebSocket]] = {}
        # Maps WebSocket instance -> user_id
        self.socket_user_map: Dict[WebSocket, str] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.socket_user_map[websocket] = user_id
        if user_id not in self.user_connections:
            self.user_connections[user_id] = set()
        self.user_connections[user_id].add(websocket)
        logger.info(f"[WS] Connected authenticated socket for user: {user_id}")

    def disconnect(self, websocket: WebSocket):
        user_id = self.socket_user_map.pop(websocket, None)
        if user_id and user_id in self.user_connections:
            self.user_connections[user_id].discard(websocket)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]

    async def broadcast_event(
        self,
        event_type: str,
        data: dict,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ):
        """
        Delivers real-time execution events strictly to authenticated user's sockets.
        Scoped by user_id, conversation_id, and request_id.
        """
        if not user_id or user_id not in self.user_connections:
            return

        payload_dict = {"event": event_type, "data": data}
        if conversation_id:
            payload_dict["conversation_id"] = conversation_id
        if request_id:
            payload_dict["request_id"] = request_id
        payload = json.dumps(payload_dict)

        targets: Set[WebSocket] = set(self.user_connections[user_id])
        for connection in targets:
            try:
                await connection.send_text(payload)
            except Exception as e:
                logger.warning(f"[WS] Error sending payload: {e}")
                self.disconnect(connection)


ws_manager = ConnectionManager()


@ws_router.websocket("/ws/chat")
async def websocket_chat_endpoint(websocket: WebSocket, token: Optional[str] = Query(None)):
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication required")
        return

    try:
        from app.api.auth import verify_clerk_token
        claims = verify_clerk_token(token)
        user_id = claims.get("sub")
        if not user_id:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token claims")
            return
    except Exception as e:
        logger.warning(f"[WS] Token verification error: {e}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized")
        return

    await ws_manager.connect(websocket, user_id=user_id)
    try:
        # Send initial greeting
        await websocket.send_text(
            json.dumps({
                "event": "connected",
                "data": {
                    "message": "SatQuery AI WebSocket stream active",
                    "authenticated": True,
                    "user_id": user_id,
                }
            })
        )
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_text(json.dumps({"event": "pong"}))
            except Exception:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as exc:
        logger.warning(f"[WS] WebSocket error: {exc}")
        ws_manager.disconnect(websocket)
