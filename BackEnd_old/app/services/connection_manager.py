from fastapi import WebSocket
from typing import Dict, Set, Callable, Any
from datetime import datetime, timedelta
import json
import asyncio
from app.models.player import PlayerState
from app.services.player_manager import PlayerManager
from app.services.settings_manager import settings
import logging
logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self, player_manager: PlayerManager):
        self.player_manager = player_manager
        self.active_connections: Dict[str, WebSocket] = {}
        self.last_heartbeat: Dict[str, datetime] = {}
        self.message_handlers: Dict[str, Callable] = {}
        
    def register_handler(self, message_type: str, handler: Callable):
        """Register a handler for a specific message type"""
        self.message_handlers[message_type] = handler
        
    async def connect(self, websocket: WebSocket, player_name: str) -> bool:
        """Handle new WebSocket connection and player registration."""
        
        await websocket.accept()
        if player_name in self.active_connections:
            await websocket.send_json({"type": "connection_error_player_already_exist"})
            await websocket.close()
            return False
        else:
            await websocket.send_json({"type": "connection_established"})
            
            
        # Register player
        self.player_manager.register_player(player_name)
        
        # Set up connection
        self.active_connections[player_name] = websocket
        self.last_heartbeat[player_name] = datetime.now()
        
        return True
    
    async def disconnect(self, player_name: str):
        """Handle player disconnection."""
        if player_name in self.active_connections:
            self.active_connections.pop(player_name)
            self.last_heartbeat.pop(player_name, None)
            self.player_manager.mark_disconnected(player_name)
    
    async def check_connections(self):
        """Check for stale connections periodically"""
        while True:
            now = datetime.now()
            heartbeat_timeout = settings.get_setting('websocket', 'heartbeat_timeout')
            
            for player_name, last_beat in list(self.last_heartbeat.items()):
                if now - last_beat > timedelta(seconds=heartbeat_timeout):
                    await self.handle_disconnection(player_name)
            logger.debug("current players: ")
            logger.debug(self.player_manager.serialize_players())                
            heartbeat_interval = settings.get_setting('websocket', 'heartbeat_interval')
            await asyncio.sleep(heartbeat_interval)
    
    async def handle_disconnection(self, player_name: str):
        """Handle unexpected disconnection"""
        await self.disconnect(player_name)
        await self.broadcast("player_disconnected", 
           {"player_name": player_name}
        )
    
    async def heartbeat(self, player_name: str):
        """Update last heartbeat time for a player"""
        self.last_heartbeat[player_name] = datetime.now()
        
    async def handle_message(self, player_name: str, message: dict) -> Any:
        """Route message to appropriate handler"""
        message_type = message.get("type")
        
        if message_type == "heartbeat":
            await self.heartbeat(player_name)
            return
            
        if message_type in self.message_handlers:
            return await self.message_handlers[message_type](player_name, message)
        else:
            logger.error(f"No handler for message type: {message_type}")
    
    async def send_personal_message(self,msg_type:str, content: dict, player_name: str):
        """Send message to specific player"""
        if player_name in self.active_connections:
            message = {"type":msg_type, "content":content}
            await self.active_connections[player_name].send_json(message)
    
    async def broadcast(self, msg_type:str, content: dict, exclude: Set[str] = None):
        """Broadcast message to all connected players"""
        exclude = exclude or set()
        message = {"type":msg_type, "content":content}
        for player_name, connection in self.active_connections.items():
            if player_name not in exclude:
                await connection.send_json(message)