from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel
from enum import Enum

class LobbyStatus(Enum):
    WAITING = 1
    PLAYING = 2
    SETTLING = 3
    

class Lobby(BaseModel):
    id: str
    host: str  # player name of the host
    players: List[str]  # player names of all players in the lobby
    max_players: int = 3
    created_at: datetime
    chip_count: Optional[int] = None  # Will be set when game starts
    status: LobbyStatus = LobbyStatus.WAITING

