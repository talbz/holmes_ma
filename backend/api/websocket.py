from fastapi import WebSocket, WebSocketDisconnect
from typing import List, Dict, Any
import json
import asyncio
from datetime import datetime

class WebSocketManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.crawl_status: Dict[str, Any] = {
            "status": "idle",
            "progress": 0,
            "message": "",
            "timestamp": datetime.now().isoformat()
        }

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        # Send current status to new connection
        await self.broadcast_status()

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast_status(self):
        """Broadcast current crawl status to all connected clients."""
        if self.active_connections:
            message = json.dumps(self.crawl_status)
            await asyncio.gather(
                *[connection.send_text(message) for connection in self.active_connections]
            )

    async def update_status(self, status: str, progress: int = 0, message: str = ""):
        """Update the crawl status and broadcast to all clients."""
        self.crawl_status.update({
            "status": status,
            "progress": progress,
            "message": message,
            "timestamp": datetime.now().isoformat()
        })
        await self.broadcast_status()

    async def handle_websocket(self, websocket: WebSocket):
        """Handle WebSocket connection and messages."""
        await self.connect(websocket)
        try:
            while True:
                # Keep connection alive
                await websocket.receive_text()
        except WebSocketDisconnect:
            self.disconnect(websocket) 