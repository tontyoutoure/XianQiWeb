"""In-memory room domain models and registry for M2."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field

MAX_ROOM_MEMBERS = 3
DEFAULT_CHIPS = 20


class RoomError(Exception):
    """Base class for room-domain errors."""


class RoomNotFoundError(RoomError):
    """Raised when room_id is out of configured range."""


class RoomFullError(RoomError):
    """Raised when trying to join a full room."""


class RoomNotMemberError(RoomError):
    """Raised when an operation requires existing room membership."""


class RoomNotWaitingError(RoomError):
    """Raised when ready state is changed outside waiting phase."""


@dataclass(slots=True)
class RoomMember:
    """Room member state tracked in memory."""

    user_id: int
    username: str
    seat: int
    ready: bool = False
    chips: int = DEFAULT_CHIPS
    joined_seq: int = 0


@dataclass(slots=True)
class Room:
    """Room aggregate state."""

    room_id: int
    status: str = "waiting"
    owner_id: int | None = None
    members: list[RoomMember] = field(default_factory=list)
    current_game_id: int | None = None


class RoomRegistry:
    """In-memory registry for all preset rooms."""

    def __init__(self, room_count: int, initial_chips: int = DEFAULT_CHIPS) -> None:
        if room_count < 1:
            raise ValueError("room_count must be >= 1")

        self._rooms: dict[int, Room] = {
            room_id: Room(room_id=room_id) for room_id in range(room_count)
        }
        self._member_room: dict[int, int] = {}
        self._join_sequence: int = 0
        self._initial_chips = initial_chips

    def get_room(self, room_id: int) -> Room:
        """Return room snapshot by room id."""
        room = self._rooms.get(room_id)
        if room is None:
            raise RoomNotFoundError(f"room_id={room_id} not found")
        return room

    def list_rooms(self) -> list[Room]:
        """Return all preset rooms sorted by room_id."""
        return [self._rooms[room_id] for room_id in sorted(self._rooms)]

    def find_room_id_by_user(self, user_id: int) -> int | None:
        """Return current room id for user, or None if user is not in any room."""
        return self._member_room.get(user_id)

    def join(self, room_id: int, user_id: int, username: str) -> Room:
        """Join a target room, with same-room idempotency and cross-room migration."""
        target_room = self.get_room(room_id)
        current_room_id = self._member_room.get(user_id)

        if current_room_id == room_id:
            return target_room

        if len(target_room.members) >= MAX_ROOM_MEMBERS:
            raise RoomFullError(f"room_id={room_id} is full")

        if current_room_id is not None:
            self.leave(room_id=current_room_id, user_id=user_id)

        seat = self._pick_min_available_seat(target_room)
        self._join_sequence += 1
        member = RoomMember(
            user_id=user_id,
            username=username,
            seat=seat,
            ready=False,
            chips=self._initial_chips,
            joined_seq=self._join_sequence,
        )
        target_room.members.append(member)
        target_room.members.sort(key=lambda item: item.seat)

        if target_room.owner_id is None:
            target_room.owner_id = user_id

        self._member_room[user_id] = room_id
        return target_room

    def leave(self, room_id: int, user_id: int) -> Room:
        """Leave a room and transfer owner when needed."""
        room = self.get_room(room_id)
        idx = self._find_member_index(room, user_id)
        if idx is None:
            raise RoomNotMemberError(f"user_id={user_id} not in room_id={room_id}")

        leaving_member = room.members.pop(idx)
        self._member_room.pop(leaving_member.user_id, None)

        if room.owner_id == user_id:
            room.owner_id = self._pick_next_owner(room)

        if room.status == "playing":
            room.status = "waiting"
            room.current_game_id = None
            for member in room.members:
                member.ready = False

        return room

    def set_ready(self, room_id: int, user_id: int, ready: bool) -> Room:
        """Update member ready flag when room is in waiting state."""
        room = self.get_room(room_id)
        if room.status != "waiting":
            raise RoomNotWaitingError(
                f"room_id={room_id} status={room.status} does not allow ready updates"
            )

        idx = self._find_member_index(room, user_id)
        if idx is None:
            raise RoomNotMemberError(f"user_id={user_id} not in room_id={room_id}")

        room.members[idx].ready = ready
        return room

    @staticmethod
    def _find_member_index(room: Room, user_id: int) -> int | None:
        for idx, member in enumerate(room.members):
            if member.user_id == user_id:
                return idx
        return None

    @staticmethod
    def _pick_next_owner(room: Room) -> int | None:
        if not room.members:
            return None
        earliest = min(room.members, key=lambda item: item.joined_seq)
        return earliest.user_id

    @staticmethod
    def _pick_min_available_seat(room: Room) -> int:
        used_seats = {member.seat for member in room.members}
        for seat in range(MAX_ROOM_MEMBERS):
            if seat not in used_seats:
                return seat
        raise RoomFullError(f"room_id={room.room_id} is full")


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
]
