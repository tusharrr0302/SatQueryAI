import asyncio
import json
import logging
from typing import Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

ws_router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def broadcast_event(self, event_type: str, data: dict):
        payload = json.dumps({"event": event_type, "data": data})
        for connection in list(self.active_connections):
            try:
                await connection.send_text(payload)
            except Exception as e:
                logger.warning(f"Error sending ws payload: {e}")
                self.disconnect(connection)


ws_manager = ConnectionManager()


@ws_router.websocket("/ws/chat")
async def websocket_chat_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        # Send initial connected greeting
        await websocket.send_text(
            json.dumps({
                "event": "connected",
                "data": {"message": "SatQuery AI WebSocket stream active"}
            })
        )
        while True:
            # Keep-alive or handle client telemetry
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
        logger.warning(f"WebSocket error: {exc}")
        ws_manager.disconnect(websocket)
