from pydantic import BaseModel
import json
from enum import Enum

class PlayerState(Enum):
    DISCONNECTED = -1,
    IDLE = 0,
    IN_LOBBY = 1,
    READY = 1, 
    PLAYING = 2,

class Player(BaseModel):
    _name: str
    status: PlayerState = PlayerState.IDLE
    current_lobby: str = None
    
    def set_status(self, status: PlayerState):
        self.status = status
        
    def get_status(self):
        return self.status
    
    def set_current_lobby(self, lobby_id: str):
        self.current_lobby = lobby_id
    
    def get_current_lobby(self):
        return self.current_lobby
    
    
if __name__ == "__main__":
    player = Player(_name="Alice")