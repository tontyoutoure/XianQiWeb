"""Game REST routes."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi import Header

import app.runtime as runtime
from app.api.deps import require_current_user
from app.api.errors import raise_api_error
from app.rooms.models import GameActionRequest
from app.rooms.registry import GameForbiddenError
from app.rooms.registry import GameInvalidActionError
from app.rooms.registry import GameNotFoundError
from app.rooms.registry import GameStateConflictError
from app.rooms.registry import GameVersionConflictError
from app.ws.broadcast import broadcast_game_progress
from app.ws.broadcast import dispatch_async

router = APIRouter()


@router.get("/api/games/{game_id}/state")
def get_game_state(
    game_id: int,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, object]:
    """Return one game snapshot for a room member."""
    user = require_current_user(authorization)
    user_id = int(user["id"])
    try:
        return runtime.room_registry.get_game_state_for_user(game_id=game_id, user_id=user_id)
    except GameNotFoundError:
        raise_api_error(
            status_code=404,
            code="GAME_NOT_FOUND",
            message="game not found",
            detail={"game_id": game_id},
        )
    except GameForbiddenError:
        raise_api_error(
            status_code=403,
            code="GAME_FORBIDDEN",
            message="user is not a game member",
            detail={"game_id": game_id, "user_id": user_id},
        )


@router.post("/api/games/{game_id}/actions", status_code=204)
def post_game_action(
    game_id: int,
    payload: GameActionRequest,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> None:
    """Apply one action to an in-progress game."""
    user = require_current_user(authorization)
    user_id = int(user["id"])
    try:
        runtime.room_registry.apply_game_action(
            game_id=game_id,
            user_id=user_id,
            action_idx=int(payload.action_idx),
            client_version=payload.client_version,
            cover_list=payload.cover_list,
        )
    except GameNotFoundError:
        raise_api_error(
            status_code=404,
            code="GAME_NOT_FOUND",
            message="game not found",
            detail={"game_id": game_id},
        )
    except GameForbiddenError:
        raise_api_error(
            status_code=403,
            code="GAME_FORBIDDEN",
            message="user is not a game member",
            detail={"game_id": game_id, "user_id": user_id},
        )
    except GameVersionConflictError:
        raise_api_error(
            status_code=409,
            code="GAME_VERSION_CONFLICT",
            message="game version conflict",
            detail={"game_id": game_id},
        )
    except GameInvalidActionError:
        raise_api_error(
            status_code=409,
            code="GAME_INVALID_ACTION",
            message="game action is invalid",
            detail={"game_id": game_id},
        )
    dispatch_async(broadcast_game_progress(game_id))


@router.get("/api/games/{game_id}/settlement")
def get_game_settlement(
    game_id: int,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, object]:
    """Return settlement payload for a room member in settlement phase."""
    user = require_current_user(authorization)
    user_id = int(user["id"])
    try:
        return runtime.room_registry.get_game_settlement_for_user(game_id=game_id, user_id=user_id)
    except GameNotFoundError:
        raise_api_error(
            status_code=404,
            code="GAME_NOT_FOUND",
            message="game not found",
            detail={"game_id": game_id},
        )
    except GameForbiddenError:
        raise_api_error(
            status_code=403,
            code="GAME_FORBIDDEN",
            message="user is not a game member",
            detail={"game_id": game_id, "user_id": user_id},
        )
    except GameStateConflictError:
        raise_api_error(
            status_code=409,
            code="GAME_STATE_CONFLICT",
            message="game state conflict",
            detail={"game_id": game_id},
        )
