import asyncio
import json
import logging
from datetime import datetime
from typing import Set, Dict, Any
from fastapi import WebSocket
from models.models import WebSocketMessage

# Configure logging
logger = logging.getLogger(__name__)

class WebSocketManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.clients: Dict[WebSocket, Dict[str, Any]] = {}
        self.status = {
            "is_running": False,
            "progress": 0,
            "current_club": None,
            "error": None
        }
        logger.info("WebSocketManager initialized")

    async def connect(self, websocket: WebSocket):
        logger.info("WebSocket connection attempt received")
        await websocket.accept()
        self.active_connections.add(websocket)
        self.clients[websocket] = {"connected_at": datetime.now()}
        logger.info(f"WebSocket client connected. Total clients: {len(self.active_connections)}")
        
        # Send current status to new client
        try:
            status_message = {
                "type": "status",
                "message": "Connected to WebSocket server",
                "data": self.status,
                "timestamp": datetime.now().isoformat()
            }
            await websocket.send_json(status_message)
            logger.info(f"Sent initial status to client: {status_message}")
        except Exception as e:
            logger.error(f"Error sending initial status: {e}")

    def disconnect(self, websocket: WebSocket):
        logger.info("Disconnecting WebSocket client")
        try:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
                logger.info(f"Removed websocket from active connections. Remaining: {len(self.active_connections)}")
            
            if websocket in self.clients:
                duration = datetime.now() - self.clients[websocket].get("connected_at", datetime.now())
                logger.info(f"Client was connected for {duration.total_seconds():.2f} seconds")
                del self.clients[websocket]
                logger.info("Removed client data")
            
            logger.info(f"WebSocket client disconnected. Remaining clients: {len(self.active_connections)}")
        except Exception as e:
            logger.error(f"Error during WebSocket disconnect: {str(e)}")

    async def broadcast(self, message):
        """Broadcast a message to all connected clients"""
        if not self.active_connections:
            logger.info("No active WebSocket connections to broadcast to")
            return
            
        # Convert message to JSON string if it's an object
        if isinstance(message, dict):
            message_json = message
        elif isinstance(message, str):
            # If it's already a JSON string, parse it to validate and then use the object
            try:
                message_json = json.loads(message)
            except json.JSONDecodeError:
                message_json = {"type": "message", "message": message}
        else:
            # If it's a WebSocketMessage model
            try:
                message_json = message.dict()
            except AttributeError:
                message_json = {"type": "message", "message": str(message)}
        
        logger.info(f"Broadcasting message to {len(self.active_connections)} clients: {message_json['type']}")
        
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message_json)
            except Exception as e:
                logger.error(f"Error broadcasting to client: {e}")
                # Remove failed connection
                try:
                    self.disconnect(connection)
                except Exception as disconnect_error:
                    logger.error(f"Error disconnecting client: {disconnect_error}")

    async def send_to_client(self, websocket: WebSocket, message):
        """Send a message to a specific client"""
        # Handle different message types
        if isinstance(message, dict):
            message_json = message
        elif isinstance(message, str):
            try:
                message_json = json.loads(message)
            except json.JSONDecodeError:
                message_json = {"type": "message", "message": message}
        else:
            try:
                message_json = message.dict()
            except AttributeError:
                message_json = {"type": "message", "message": str(message)}
        
        logger.info(f"Sending message to client: {message_json['type']}")
                
        try:
            await websocket.send_json(message_json)
        except Exception as e:
            logger.error(f"Error sending to client: {e}")
            # Remove failed connection
            try:
                self.disconnect(websocket)
            except Exception as disconnect_error:
                logger.error(f"Error disconnecting client: {disconnect_error}")

    def get_connected_clients_count(self) -> int:
        return len(self.active_connections)

    def get_status(self) -> Dict[str, Any]:
        """Get the current crawl status"""
        return self.status

    async def update_status(self, **kwargs):
        """Update the crawl status and broadcast to all clients"""
        changed = False
        for key, value in kwargs.items():
            if key in self.status and self.status[key] != value:
                changed = True
                self.status[key] = value
            elif key not in self.status:
                changed = True
                self.status[key] = value
                
        if changed or kwargs.get('force_update', False):
            logger.info(f"Broadcasting status update: {self.status}")
            message = {
                "type": "status",
                "message": "Crawl status updated",
                "data": self.status,
                "timestamp": datetime.now().isoformat()
            }
            await self.broadcast(message)

# Create a singleton instance
websocket_manager = WebSocketManager() 