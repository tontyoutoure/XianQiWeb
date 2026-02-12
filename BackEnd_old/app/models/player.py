from pydantic import BaseModel
import json
from enum import Enum

class PlayerState(str,Enum):
    DISCONNECTED = 'DISCONNECTED',
    IDLE = 'IDLE',
    IN_LOBBY = 'IN_LOBBY',
    READY = 'READY',
    PLAYING = 'PLAYING'

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
    
    def get_current_lobby_id(self):
        return self.current_lobby
    
    
if __name__ == "__main__":
    player = Player(_name="Alice")