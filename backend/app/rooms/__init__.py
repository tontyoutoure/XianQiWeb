"""Room domain package for M2."""

from app.rooms.registry import DEFAULT_CHIPS
from app.rooms.registry import MAX_ROOM_MEMBERS
from app.rooms.registry import Room
from app.rooms.registry import RoomError
from app.rooms.registry import RoomFullError
from app.rooms.registry import RoomMember
from app.rooms.registry import RoomNotFoundError
from app.rooms.registry import RoomNotMemberError
from app.rooms.registry import RoomNotWaitingError
from app.rooms.registry import RoomRegistry
from app.rooms.models import ReadyRequest

__all__ = [
    "DEFAULT_CHIPS",
    "MAX_ROOM_MEMBERS",
    "Room",
    "RoomError",
    "RoomFullError",
    "RoomMember",
    "RoomNotFoundError",
    "RoomNotMemberError",
    "RoomNotWaitingError",
    "RoomRegistry",
    "ReadyRequest",
]
