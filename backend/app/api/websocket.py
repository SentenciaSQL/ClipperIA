"""WebSocket connection manager and endpoint."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["websocket"])


class ConnectionManager:
    """Tracks connected desktop clients and broadcasts events."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.append(websocket)
        logger.info("websocket_connected", clients=len(self._connections))

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            if websocket in self._connections:
                self._connections.remove(websocket)
        logger.info("websocket_disconnected", clients=len(self._connections))

    async def broadcast(self, event: dict[str, Any]) -> None:
        async with self._lock:
            targets = list(self._connections)
        stale: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_json(event)
            except Exception:
                stale.append(ws)
        for ws in stale:
            await self.disconnect(ws)


manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str | None = Query(default=None),
) -> None:
    settings = get_settings()
    if token != settings.api_token:
        await websocket.close(code=4401)
        return

    await manager.connect(websocket)
    await websocket.send_json(
        {
            "type": "connected",
            "payload": {
                "app": settings.app_name,
                "version": settings.app_version,
            },
        }
    )
    try:
        while True:
            message = await websocket.receive_json()
            msg_type = message.get("type")
            if msg_type == "ping":
                await websocket.send_json({"type": "pong", "payload": {}})
            elif msg_type == "subscribe":
                await websocket.send_json(
                    {
                        "type": "subscribed",
                        "payload": {"channels": message.get("channels", ["jobs"])},
                    }
                )
            else:
                await websocket.send_json(
                    {
                        "type": "ack",
                        "payload": {"received": msg_type},
                    }
                )
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception as exc:
        logger.warning("websocket_error", error=str(exc))
        await manager.disconnect(websocket)
