import sys
# add cwd
sys.path.append('.')
# sys.path.append()
from app.services.lobby_manager import LobbyManager
from app.services.player_manager import PlayerManager
from app.services.connection_manager import ConnectionManager
import json

def test_create_lobby():
    player_manager = PlayerManager()
    connection_manager = ConnectionManager(player_manager)
    lobby_manager = LobbyManager(player_manager,connection_manager)
    test_player1 = player_manager.register_player("test_player1")
    test_player2 = player_manager.register_player("test_player2")
    test_player3 = player_manager.register_player("test_player3")
    lobby_manager.create_lobby("test_player1", 10)
    lobby_manager.create_lobby("test_player2", 15)
    
    test_lobby1_id = test_player1.get_current_lobby_id()
    test_lobby2_id = test_player2.get_current_lobby_id()
    lobby_manager.join_lobby(test_lobby2_id, "test_player3")
    
    test_lobby1 = lobby_manager.get_lobby(test_lobby1_id)
    test_lobby2 = lobby_manager.get_lobby(test_lobby2_id)
    
    assert test_lobby2.has_player("test_player2")
    assert test_lobby2.has_player("test_player3")
    assert test_player3.get_current_lobby_id() == test_lobby2_id
    
    lobby_manager.leave_lobby(test_lobby2_id, "test_player2")
    assert not test_lobby2.has_player("test_player2")
    assert test_lobby2.get_host() == "test_player3"
    assert test_player2.get_current_lobby_id() == ""
    
    
    lobby_list = lobby_manager.serialize_lobbies()
    player_list = player_manager.serialize_players()
    print("lobby list is:", json.dumps(lobby_list, indent=2))
    print("player list is:", json.dumps(player_list, indent=2))
    
    
def test():
    test_create_lobby()
    
if __name__ == "__main__":
    test()