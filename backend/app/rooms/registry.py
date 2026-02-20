"""In-memory room domain models and registry for M2."""

from __future__ import annotations

from collections.abc import Iterable
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from dataclasses import field
import threading

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


class GameNotFoundError(RoomError):
    """Raised when game_id does not exist in in-memory registry."""


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


@dataclass(slots=True)
class GameSession:
    """In-memory game session metadata mapped to one room."""

    game_id: int
    room_id: int
    status: str
    seat_to_user_id: dict[int, int]
    user_id_to_seat: dict[int, int]


class RoomRegistry:
    """In-memory registry for all preset rooms."""

    def __init__(self, room_count: int, initial_chips: int = DEFAULT_CHIPS) -> None:
        if room_count < 1:
            raise ValueError("room_count must be >= 1")

        self._rooms: dict[int, Room] = {
            room_id: Room(room_id=room_id) for room_id in range(room_count)
        }
        self._room_locks: dict[int, threading.RLock] = {
            room_id: threading.RLock() for room_id in self._rooms
        }
        self._user_locks: dict[int, threading.RLock] = {}
        self._user_locks_guard = threading.Lock()
        self._member_room: dict[int, int] = {}
        self._join_sequence: int = 0
        self._initial_chips = initial_chips
        self._games_by_id: dict[int, GameSession] = {}
        self._next_game_id: int = 1

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

    def get_game(self, game_id: int) -> GameSession:
        """Return game session snapshot by game id."""
        game = self._games_by_id.get(game_id)
        if game is None:
            raise GameNotFoundError(f"game_id={game_id} not found")
        return game

    def mark_game_settlement(self, game_id: int) -> None:
        """Move an in-progress game to settlement and reset room ready flags."""
        game = self.get_game(game_id)
        with self.lock_room(game.room_id):
            game = self.get_game(game_id)
            game.status = "settlement"
            room = self.get_room(game.room_id)
            if room.current_game_id == game_id:
                room.status = "settlement"
                for member in room.members:
                    member.ready = False

    @contextmanager
    def lock_room(self, room_id: int) -> Iterator[None]:
        """Acquire one room write lock."""
        self.get_room(room_id)
        with self._room_locks[room_id]:
            yield

    @contextmanager
    def lock_rooms(self, room_ids: Iterable[int]) -> Iterator[None]:
        """Acquire multiple room write locks in room_id order to avoid deadlock."""
        lock_room_ids = sorted(set(room_ids))
        for room_id in lock_room_ids:
            self.get_room(room_id)

        locks = [self._room_locks[room_id] for room_id in lock_room_ids]
        for lock in locks:
            lock.acquire()

        try:
            yield
        finally:
            for lock in reversed(locks):
                lock.release()

    @contextmanager
    def _lock_user(self, user_id: int) -> Iterator[None]:
        with self._user_locks_guard:
            user_lock = self._user_locks.setdefault(user_id, threading.RLock())
        with user_lock:
            yield

    def join(self, room_id: int, user_id: int, username: str) -> Room:
        """Join a target room, with same-room idempotency and cross-room migration."""
        with self._lock_user(user_id):
            target_room = self.get_room(room_id)
            current_room_id = self._member_room.get(user_id)
            lock_room_ids = [room_id]
            if current_room_id is not None and current_room_id != room_id:
                lock_room_ids.append(current_room_id)

            with self.lock_rooms(lock_room_ids):
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
        with self.lock_room(room_id):
            room = self.get_room(room_id)
            idx = self._find_member_index(room, user_id)
            if idx is None:
                raise RoomNotMemberError(f"user_id={user_id} not in room_id={room_id}")

            leaving_member = room.members.pop(idx)
            self._member_room.pop(leaving_member.user_id, None)

            if room.owner_id == user_id:
                room.owner_id = self._pick_next_owner(room)

            if room.status == "playing":
                if room.current_game_id is not None:
                    game = self._games_by_id.get(room.current_game_id)
                    if game is not None:
                        game.status = "aborted"
                room.status = "waiting"
                room.current_game_id = None
                for member in room.members:
                    member.ready = False

            return room

    def set_ready(self, room_id: int, user_id: int, ready: bool) -> Room:
        """Update member ready flag when room is in waiting/settlement state."""
        with self.lock_room(room_id):
            room = self.get_room(room_id)
            if room.status not in {"waiting", "settlement"}:
                raise RoomNotWaitingError(
                    f"room_id={room_id} status={room.status} does not allow ready updates"
                )

            idx = self._find_member_index(room, user_id)
            if idx is None:
                raise RoomNotMemberError(f"user_id={user_id} not in room_id={room_id}")

            was_all_ready = (
                len(room.members) == MAX_ROOM_MEMBERS
                and all(member.ready for member in room.members)
            )
            room.members[idx].ready = ready
            is_all_ready = (
                len(room.members) == MAX_ROOM_MEMBERS
                and all(member.ready for member in room.members)
            )
            if is_all_ready and not was_all_ready:
                self._start_game(room)
            return room

    def _start_game(self, room: Room) -> None:
        game_id = self._next_game_id
        self._next_game_id += 1

        seat_to_user_id = {member.seat: member.user_id for member in room.members}
        user_id_to_seat = {user_id: seat for seat, user_id in seat_to_user_id.items()}
        self._games_by_id[game_id] = GameSession(
            game_id=game_id,
            room_id=room.room_id,
            status="in_progress",
            seat_to_user_id=seat_to_user_id,
            user_id_to_seat=user_id_to_seat,
        )
        room.current_game_id = game_id
        room.status = "playing"

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
    "GameNotFoundError",
    "GameSession",
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
