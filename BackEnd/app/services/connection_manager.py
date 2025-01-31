from fastapi import WebSocket
from typing import Dict, Set, Callable, Any
import json
import asyncio
from datetime import datetime, timedelta


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.player_names: Set[str] = set()
        self.last_heartbeat: Dict[str, datetime] = {}
        self.disconnected_players: Set[str] = set()
        self.message_handlers: Dict[str, Callable] = {}
        
    def register_handler(self, message_type: str, handler: Callable):
        """Register a handler for a specific message type"""
        self.message_handlers[message_type] = handler
        
    async def handle_message(self, player_name: str, message: dict) -> Any:
        """Route message to appropriate handler"""
        message_type = message.get("type")
        
        if message_type == "heartbeat":
            await self.heartbeat(player_name)
            return
            
        if message_type in self.message_handlers:
            return await self.message_handlers[message_type](player_name, message)
        else:
            print(f"No handler for message type: {message_type}")
            
    async def connect(self, websocket: WebSocket, player_name: str) -> bool:
        await websocket.accept()
        
        if player_name in self.disconnected_players:
            self.disconnected_players.remove(player_name)
            await self.broadcast(
                {"type": "player_reconnected", "player_name": player_name},
                {player_name}
            )
        elif player_name in self.player_names:
            await websocket.close(code=4000, reason="Player name already taken")
            return False
            
        self.active_connections[player_name] = websocket
        self.player_names.add(player_name)
        self.last_heartbeat[player_name] = datetime.now()
        return True
    
    async def disconnect(self, player_name: str, temporary: bool = True):
        if player_name in self.active_connections:
            self.active_connections.pop(player_name)
            if temporary:
                self.disconnected_players.add(player_name)
            else:
                self.player_names.remove(player_name)
                self.last_heartbeat.pop(player_name, None)
    
    async def check_connections(self):
        """Check for stale connections every 5 seconds"""
        while True:
            now = datetime.now()
            for player_name, last_beat in self.last_heartbeat.items():
                if now - last_beat > timedelta(seconds=10):  # No heartbeat for 10 seconds
                    await self.handle_disconnection(player_name)
            await asyncio.sleep(5)
    
    async def handle_disconnection(self, player_name: str):
        await self.disconnect(player_name, temporary=True)
        await self.broadcast(
            {"type": "player_disconnected", "player_name": player_name}
        )
    
    async def heartbeat(self, player_name: str):
        """Update last heartbeat time for a player"""
        self.last_heartbeat[player_name] = datetime.now()
    
    async def send_personal_message(self, message: dict, player_name: str):
        if player_name in self.active_connections:
            await self.active_connections[player_name].send_json(message)
    
    async def broadcast(self, message: dict, exclude: Set[str] = None):
        exclude = exclude or set()
        for player_name, connection in self.active_connections.items():
            if player_name not in exclude:
                await connection.send_json(message)