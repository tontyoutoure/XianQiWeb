from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel
from enum import Enum
import uuid

class LobbyStatus(str, Enum):
    WAITING = 'WAITING'
    PLAYING = 'PLAYING'
    SETTLING = 'SETTLING'
    

class Lobby(BaseModel):
    id: str
    host: str  # player name of the host
    players: List[str]  # player names of all players in the lobby
    max_players: int = 3
    created_at: str
    chip_count: Optional[int] = None  # Will be set when game starts
    status: LobbyStatus = LobbyStatus.WAITING
    
    def add_player(self,player_name) ->None:
        assert(len(self.players) < self.max_players)
        self.players.append(player_name)
        
    def remove_player(self, player_name)->None:
        assert(player_name in self.players)
        self.players.remove(player_name)
        if len(self.players) > 0 and player_name == self.host:
            self.host = self.players[0]
    
    def set_chip_count(self, chip_count)->None:
        self.chip_count = self.chip_count
    
    def get_chip_count(self)->int:
        return self.chip_count
        
    def get_id(self)->str:
        return self.id()

    def get_player_name_list(self) -> List[str]:
        return self.players

    def has_player(self, player_name:str)->bool:
        return player_name in self.players
        
    def get_host(self)->str:
        return self.host
    