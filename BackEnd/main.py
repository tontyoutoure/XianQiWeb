from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from fastapi import APIRouter

from app.services.connection_manager import ConnectionManager
from app.services.player_manager import player_manager
from app.services.lobby_manager import LobbyManager

app = FastAPI()
connection_manager = ConnectionManager(player_manager)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    # Start connection monitoring
    asyncio.create_task(connection_manager.check_connections())
    # Start player cleanup
    asyncio.create_task(player_manager.cleanup_disconnected_players())

@app.websocket("/ws/{player_name}")
async def websocket_endpoint(websocket: WebSocket, player_name: str):
    success = await connection_manager.connect(websocket, player_name)
    if not success:
        return
    
    try:
        await connection_manager.send_personal_message(
            {"type": "connection_established", "player_name": player_name},
            player_name
        )
        
        while True:
            try:
                data = await websocket.receive_json()
                await connection_manager.handle_message(player_name, data)
            except ValueError as e:
                print(f"Invalid message format from {player_name}: {e}")
                continue
    except WebSocketDisconnect:
        await connection_manager.handle_disconnection(player_name)
    except Exception as e:
        print(f"Error in websocket connection for {player_name}: {e}")
        await connection_manager.handle_disconnection(player_name)

# Router setup
router_player = APIRouter(
    prefix="/player",
    responses={404: {"description": "Not found"}}
)

@router_player.get("/status/{player_name}")
async def get_player_status(player_name: str):
    """Get current status of a player"""
    player = player_manager.get_player(player_name)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    return {
        "status": player.get_status().name,
        "current_lobby": player.get_current_lobby()
    }

app.include_router(router_player)

router_lobby = APIRouter(
    prefix="/lobby",  # Changed from /lobby to /api/lobby
    responses={404: {"description": "Not found"}}
)

lobby_manager = LobbyManager(player_manager)
lobby_manager.register_router(router_lobby)
app.include_router(router_lobby)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)