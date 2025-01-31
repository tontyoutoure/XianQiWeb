from typing import Dict, List, Optional
from datetime import datetime
import uuid
from fastapi import HTTPException
from app.models.lobby import Lobby, LobbyStatus
from fastapi import APIRouter



class LobbyManager:
    def __init__(self):
        self.lobbies: Dict[str, Lobby] = {}
        self.players: Dict[str, datetime] = {}  # player_name -> last_active

    def register_player(self, player_name: str) -> None:
        """Register a new player or update their last active time."""
        self.players[player_name] = datetime.now()

    def get_active_lobbies(self) -> List[Lobby]:
        """Get all active lobbies."""
        return list(self.lobbies.values())

    def create_lobby(self, player_name: str, initial_chip_count:int) -> Lobby:
        """Create a new lobby with the given player as host."""
        if player_name not in self.players:
            raise HTTPException(status_code=400, detail="Player not found")
        
        lobby_id = str(uuid.uuid4())
        new_lobby = Lobby(
            id=lobby_id,
            host = player_name,
            players=[player_name],
            created_at=datetime.now(),
            chip_count=initial_chip_count
        )
        
        self.lobbies[lobby_id] = new_lobby
        return new_lobby

    def join_lobby(self, lobby_id: str, player_name: str) -> Lobby:
        """Add a player to an existing lobby."""
        if player_name not in self.players:
            raise HTTPException(status_code=400, detail="Player not found")
            
        if lobby_id not in self.lobbies:
            raise HTTPException(status_code=404, detail="Lobby not found")
            
        lobby = self.lobbies[lobby_id]
        
        if len(lobby.players) >= lobby.max_players:
            raise HTTPException(status_code=400, detail="Lobby is full")
            
        if player_name in lobby.players:
            raise HTTPException(status_code=400, detail="Player already in lobby")
        
        lobby.players.append(player_name)
        return lobby

    def leave_lobby(self, lobby_id: str, player_name: str) -> dict:
        """Remove a player from a lobby."""
        if lobby_id not in self.lobbies:
            raise HTTPException(status_code=404, detail="Lobby not found")
            
        lobby = self.lobbies[lobby_id]
        
        if player_name not in lobby.players:
            raise HTTPException(status_code=400, detail="Player not in lobby")
        
        lobby.players.remove(player_name)
        
        # If lobby is empty, remove it
        if len(lobby.players) == 0:
            del self.lobbies[lobby_id]
            return {"status": "success", "message": "Lobby deleted"}
        
        # If host leaves, assign new host
        if player_name == lobby.host and lobby.players:
            lobby.host = lobby.players[0]
        
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
    
    def register_router(self, router:APIRouter):
        

# Create a global instance of the lobby manager
lobby_manager = LobbyManager()