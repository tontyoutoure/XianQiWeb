# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI()

# CORS settings (we might not need this anymore since frontend and backend are served from same origin)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class PlayerName(BaseModel):
    name: str

@app.post("/api/player/name")
async def set_player_name(player: PlayerName):
    print(f"Received player name: {player.name}")
    return {"status": "success", "message": f"Hello, {player.name}!"}

# Mount the static files from your Vue build
app.mount("/", StaticFiles(directory="../FrontEnd/dist", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)