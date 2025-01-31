from typing import Dict, Optional, List
from datetime import datetime, timedelta
from fastapi import HTTPException
from app.models.player import Player, PlayerState
import json
import asyncio
from app.services.settings_manager import settings

class PlayerManager:
    def __init__(self):
        self.players: Dict[str, Player] = {}
        self.disconnect_times: Dict[str, datetime] = {}
        
    def register_player(self, player_name: str) -> Player:
        """Register a new player or get existing one."""
        if player_name in self.players:
            player = self.players[player_name]
            player.set_status(PlayerState.IDLE)
            # Remove from disconnect times if present
            self.disconnect_times.pop(player_name, None)
            return player
            
        player = Player(_name=player_name)
        self.players[player_name] = player
        return player
        
    def mark_disconnected(self, player_name: str) -> None:
        """Mark a player as disconnected and record the time."""
        if player_name in self.players:
            self.players[player_name].set_status(PlayerState.DISCONNECTED)
            self.disconnect_times[player_name] = datetime.now()
        
    def remove_player(self, player_name: str) -> None:
        """Remove a player completely from the system."""
        if player_name in self.players:
            del self.players[player_name]
            self.disconnect_times.pop(player_name, None)
            
    def get_player(self, player_name: str) -> Optional[Player]:
        """Get a player by name."""
        return self.players.get(player_name)
        
    def update_player_state(self, player_name: str, state: PlayerState) -> Player:
        """Update a player's state."""
        player = self.get_player(player_name)
        if not player:
            raise HTTPException(status_code=404, detail="Player not found")
            
        player.set_status(state)
        return player
        
    async def cleanup_disconnected_players(self):
        """Periodically clean up disconnected players."""
        while True:
            try:
                await self._cleanup_players()
            except Exception as e:
                print(f"Error in cleanup: {e}")
            
            cleanup_interval = settings.get_setting('player', 'cleanup_interval')
            await asyncio.sleep(cleanup_interval)
            
    async def _cleanup_players(self):
        """Remove players who have been disconnected for too long."""
        now = datetime.now()
        disconnect_timeout = settings.get_setting('player', 'disconnect_timeout')
        timeout_delta = timedelta(seconds=disconnect_timeout)
        
        for player_name, disconnect_time in list(self.disconnect_times.items()):
            if now - disconnect_time > timeout_delta:
                self.remove_player(player_name)
                print(f"Cleaned up disconnected player: {player_name}")
        
    def serialize_players(self) -> str:
        """Serialize all players to JSON string."""
        player_data = {}
        for name, player in self.players.items():
            player_data[name] = {
                "status": player.status.name,
                "current_lobby": player.current_lobby,
            }
        return json.dumps(player_data, indent=2)

# Create a global instance
player_manager = PlayerManager()