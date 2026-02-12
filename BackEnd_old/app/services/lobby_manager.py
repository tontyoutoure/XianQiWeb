from typing import Dict, List, Optional
from datetime import datetime
import uuid
from fastapi import HTTPException
from app.models.lobby import Lobby, LobbyStatus
from fastapi import APIRouter
from pydantic import BaseModel
from app.services.player_manager import PlayerManager
from app.services.connection_manager import ConnectionManager
import logging
logger = logging.getLogger(__name__)

class CreateLobbyRequest(BaseModel):
    player_name: str
    initial_chip_count: int

class LobbyManager:
    def __init__(self, player_manager:PlayerManager, connection_manager:ConnectionManager):
        self.lobbies: Dict[str, Lobby] = {}
        self.player_manager = player_manager
        self.connection_manager = connection_manager

    def get_lobby_list(self) -> List[Lobby]:
        """Get all active lobbies."""
        return list(self.lobbies.values())

    def create_lobby(self, player_name: str, initial_chip_count:int) -> Lobby:
        """Create a new lobby with the given player as host."""
        host_player = self.player_manager.get_player(player_name)
        if host_player is None:
            raise HTTPException(status_code=400, detail="Player not found")
        
        lobby_id = str(uuid.uuid4())
        new_lobby = Lobby(
            id=lobby_id,
            host = player_name,
            players=[player_name],
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            chip_count=initial_chip_count
        )
        
        self.lobbies[lobby_id] = new_lobby
        host_player.set_current_lobby(lobby_id)
        
        return new_lobby

    def join_lobby(self, lobby_id: str, player_name: str) -> Lobby:
        """Add a player to an existing lobby."""
        
        player = self.player_manager.get_player(player_name)
        if player is None:
            raise HTTPException(status_code=400, detail="Player not found")
            
        if lobby_id not in self.lobbies:
            raise HTTPException(status_code=404, detail="Lobby not found")
            
        lobby = self.lobbies[lobby_id]
        
        if len(lobby.players) >= lobby.max_players:
            raise HTTPException(status_code=400, detail="Lobby is full")
            
        if player_name in lobby.players:
            raise HTTPException(status_code=400, detail="Player already in lobby")
        
        lobby.add_player(player_name)
        player.set_current_lobby(lobby_id)
        
        return lobby

    def leave_lobby(self, lobby_id: str, player_name: str) -> dict:
        """Remove a player from a lobby."""
        if lobby_id not in self.lobbies:
            raise HTTPException(status_code=404, detail="Lobby not found")
            
        lobby = self.lobbies[lobby_id]
        
        if player_name not in lobby.players:
            raise HTTPException(status_code=400, detail="Player not in lobby")
        
        lobby.remove_player(player_name)
        self.player_manager.get_player(player_name).set_current_lobby("")
        
        # If lobby is empty, remove it
        if len(lobby.players) == 0:
            del self.lobbies[lobby_id]
            return {"status": "success", "message": "Lobby deleted"}
        
        
        
        return {"status": "success", "lobby": lobby}

    def set_lobby_settings(self, lobby_id: str, chip_count: int) -> Lobby:
        """Update lobby settings."""
        if lobby_id not in self.lobbies:
            raise HTTPException(status_code=404, detail="Lobby not found")
        
        if chip_count not in [10, 15, 20, 25, 30]:
            raise HTTPException(status_code=400, detail="Invalid chip count")
            
        lobby = self.lobbies[lobby_id]
        lobby.chip_count = chip_count
        return lobby

    def get_lobby(self, lobby_id: str) -> Optional[Lobby]:
        """Get a specific lobby by ID."""
        return self.lobbies.get(lobby_id)
    
    def register_router(self, router: APIRouter):
        @router.get("/list")
        async def get_lobbies():
            return self.serialize_lobbies()
            
        @router.post("/create")
        async def create_new_lobby(request: CreateLobbyRequest):
            try:
                lobby = self.create_lobby(request.player_name, request.initial_chip_count)
                return lobby.dict()  # Convert Pydantic model to dict
            except Exception as e:
                print(f"Error creating lobby: {e}")  # Debug print
                raise

        @router.post("/{lobby_id}/join")
        async def join_existing_lobby(lobby_id: str, player_name: str):
            lobby = self.join_lobby(lobby_id, player_name)
            return lobby.dict()
            
        @router.post("/{lobby_id}/leave")
        async def leave_lobby(lobby_id: str, player_name: str):
            result = self.leave_lobby(lobby_id, player_name)
            if "lobby" in result:
                result["lobby"] = result["lobby"].dict()
            return result
            
        @router.put("/{lobby_id}/settings")
        async def update_lobby_settings(lobby_id: str, chip_count: int):
            lobby = self.set_lobby_settings(lobby_id, chip_count)
            return lobby.dict()
        
    def serialize_lobbies(self) -> List[dict]:
        """Serialize lobbies for debugging."""
        
        return [lobby.dict() for lobby in self.get_lobby_list()]
    
    def broadcast_lobbies(self):
        content = {}
        content["lobby_list"] = self.serialize_lobbies()
        self.connection_manager.broadcast("lobby_info",content)