# backend/app/services/websocket_service.py
import logging
from typing import Dict, Any, Set
import asyncio

logger = logging.getLogger(__name__)

class WebSocketManager:
    """Simple WebSocket manager for deployment updates"""
    
    def __init__(self):
        self.deployment_connections: Dict[str, Set] = {}
        self.active_connections: Set = set()
    
    async def connect(self, websocket, deployment_id: str = None):
        """Connect websocket to deployment"""
        await websocket.accept()
        self.active_connections.add(websocket)
        
        if deployment_id:
            if deployment_id not in self.deployment_connections:
                self.deployment_connections[deployment_id] = set()
            self.deployment_connections[deployment_id].add(websocket)
            
        logger.info(f"WebSocket connected to deployment {deployment_id}")
    
    async def disconnect(self, websocket, deployment_id: str = None):
        """Disconnect websocket from deployment"""
        self.active_connections.discard(websocket)
        
        if deployment_id and deployment_id in self.deployment_connections:
            self.deployment_connections[deployment_id].discard(websocket)
            if not self.deployment_connections[deployment_id]:
                del self.deployment_connections[deployment_id]
                
        logger.info(f"WebSocket disconnected from deployment {deployment_id}")
    
    async def broadcast_to_deployment(self, deployment_id: str, event: Dict[str, Any]):
        """Broadcast event to deployment subscribers"""
        if deployment_id not in self.deployment_connections:
            logger.info(f"No WebSocket connections for deployment {deployment_id}")
            return
        
        connections = self.deployment_connections[deployment_id].copy()
        
        if connections:
            message = {
                "type": event.get("type", "update"),
                "deployment_id": deployment_id,
                "data": event,
                "timestamp": event.get("timestamp")
            }
            
            # Send to all connected clients for this deployment
            disconnected = set()
            for websocket in connections:
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    logger.error(f"Failed to send message to websocket: {e}")
                    disconnected.add(websocket)
            
            # Clean up disconnected websockets
            for websocket in disconnected:
                await self.disconnect(websocket, deployment_id)
            
            logger.info(f"Broadcasted {event.get('type', 'update')} to {len(connections) - len(disconnected)} clients for deployment {deployment_id}")
        else:
            logger.info(f"No active connections for deployment {deployment_id}")
    
    async def broadcast_to_all(self, event: Dict[str, Any]):
        """Broadcast event to all connected clients"""
        if not self.active_connections:
            return
        
        message = {
            "type": event.get("type", "broadcast"),
            "data": event,
            "timestamp": event.get("timestamp")
        }
        
        disconnected = set()
        for websocket in self.active_connections.copy():
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Failed to broadcast to websocket: {e}")
                disconnected.add(websocket)
        
        # Clean up disconnected websockets
        for websocket in disconnected:
            await self.disconnect(websocket)
        
        logger.info(f"Broadcasted {event.get('type', 'update')} to {len(self.active_connections) - len(disconnected)} clients")

# Global WebSocket manager instance
websocket_manager = WebSocketManager()