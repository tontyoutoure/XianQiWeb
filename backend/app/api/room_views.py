"""Room view builders used by REST and WS responses."""

from __future__ import annotations

from app.rooms.registry import Room
from app.rooms.registry import RoomMember


def room_summary(room: Room) -> dict[str, object]:
    return {
        "room_id": room.room_id,
        "status": room.status,
        "player_count": len(room.members),
        "ready_count": sum(1 for member in room.members if member.ready),
    }


def room_member_detail(member: RoomMember) -> dict[str, object]:
    return {
        "user_id": member.user_id,
        "username": member.username,
        "seat": member.seat,
        "ready": member.ready,
        "chips": member.chips,
    }


def room_detail(room: Room) -> dict[str, object]:
    return {
        "room_id": room.room_id,
        "status": room.status,
        "owner_id": room.owner_id,
        "members": [room_member_detail(member) for member in room.members],
        "current_game_id": room.current_game_id,
    }
