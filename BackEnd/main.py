from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import asyncio
from fastapi import APIRouter
from pydantic import BaseModel

from app.services.connection_manager import ConnectionManager
# from app.services.lobby_manager import lobby_manager

app = FastAPI()
connection_manager = ConnectionManager()

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

@app.websocket("/ws/{player_name}")
async def websocket_endpoint(websocket: WebSocket, player_name: str):
    success = await connection_manager.connect(websocket, player_name)
    if not success:
        return
    
    try:
        # Send connection established message
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
router_lobby = APIRouter(
    prefix="/lobby",
    responses={404: {"description": "Not found"}}
)
app.include_router(router_lobby)
# lobby_manager.register_router(router_lobby)

router_player = APIRouter(
    prefix="/player",
    responses={404: {"description": "Not found"}}
)
app.include_router(router_player)

# Serve static files
# app.mount("/", StaticFiles(directory="../frontend/dist", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)