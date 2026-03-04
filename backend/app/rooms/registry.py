"""In-memory room domain models and registry."""

from __future__ import annotations

from collections.abc import Callable
from collections.abc import Iterable
from collections.abc import Iterator
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from dataclasses import field
import importlib
from pathlib import Path
import sys
import threading
from typing import Any

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


class GameForbiddenError(RoomError):
    """Raised when user is not a participant of the game."""


class GameVersionConflictError(RoomError):
    """Raised when client_version does not match game version."""


class GameInvalidActionError(RoomError):
    """Raised when an action payload is not valid for current game state."""


class GameStateConflictError(RoomError):
    """Raised when a game exists but cannot serve requested state transition."""


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
    rng_seed: int | None
    seat_to_user_id: dict[int, int]
    user_id_to_seat: dict[int, int]
    version: int
    phase: str
    current_seat: int
    round_index: int
    round_kind: int
    last_combo: dict[str, object] | None
    plays: list[dict[str, object]]
    private_hands_by_seat: dict[int, dict[str, int]]
    engine: Any
    settlement_payload: dict[str, object] | None = None
    settlement_applied: bool = False


def _load_engine_class() -> type:
    try:
        module = importlib.import_module("engine.core")
        return getattr(module, "XianqiGameEngine")
    except ModuleNotFoundError:
        repo_root = Path(__file__).resolve().parents[3]
        repo_root_text = str(repo_root)
        if repo_root_text not in sys.path:
            sys.path.insert(0, repo_root_text)
        module = importlib.import_module("engine.core")
        return getattr(module, "XianqiGameEngine")


class RoomRegistry:
    """In-memory registry for all preset rooms."""

    def __init__(
        self,
        room_count: int,
        initial_chips: int = DEFAULT_CHIPS,
        next_game_seed_provider: Callable[[], int | None] | None = None,
    ) -> None:
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
        self._next_game_seed_provider = next_game_seed_provider
        self._games_by_id: dict[int, GameSession] = {}
        self._next_game_id: int = 1
        self._engine_cls = _load_engine_class()

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
        """Move one in-progress game to settlement and reset room ready flags."""
        game = self.get_game(game_id)
        with self.lock_room(game.room_id):
            game = self.get_game(game_id)
            if game.phase != "settlement":
                state = game.engine.dump_state()
                if not isinstance(state, dict):
                    raise GameStateConflictError(f"game_id={game_id} has invalid engine state")
                state["phase"] = "settlement"
                game.engine.load_state(state)
                self._sync_game_from_engine(game)
            self._finalize_settlement(game)

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

    @staticmethod
    def _to_card_count_map(value: object) -> dict[str, int]:
        if not isinstance(value, dict):
            return {}

        mapped: dict[str, int] = {}
        for raw_type, raw_count in value.items():
            card_type = str(raw_type).strip()
            if not card_type:
                continue
            try:
                count = int(raw_count)
            except (TypeError, ValueError):
                continue
            if count <= 0:
                continue
            mapped[card_type] = count
        return mapped

    def _sync_game_from_engine(self, game: GameSession) -> None:
        state = game.engine.dump_state()
        if not isinstance(state, dict):
            raise GameStateConflictError(f"game_id={game.game_id} has invalid engine state")

        turn = state.get("turn")
        if not isinstance(turn, dict):
            turn = {}

        game.version = int(state.get("version", 0))
        game.phase = str(state.get("phase", ""))
        game.status = "settlement" if game.phase == "settlement" else "in_progress"
        game.current_seat = int(turn.get("current_seat", 0))
        game.round_index = int(turn.get("round_index", 0))
        game.round_kind = int(turn.get("round_kind", 0))

        last_combo = turn.get("last_combo")
        game.last_combo = deepcopy(last_combo) if isinstance(last_combo, dict) else None

        plays = turn.get("plays")
        if isinstance(plays, list):
            game.plays = [deepcopy(play) for play in plays if isinstance(play, dict)]
        else:
            game.plays = []

        private_hands_by_seat: dict[int, dict[str, int]] = {}
        for seat in sorted(game.seat_to_user_id):
            private_state = game.engine.get_private_state(seat)
            hand = self._to_card_count_map(private_state.get("hand")) if isinstance(private_state, dict) else {}
            private_hands_by_seat[int(seat)] = hand
        game.private_hands_by_seat = private_hands_by_seat

    def _force_settlement_phase(self, game: GameSession) -> None:
        state = game.engine.dump_state()
        if not isinstance(state, dict):
            raise GameStateConflictError(f"game_id={game.game_id} has invalid engine state")
        state["phase"] = "settlement"
        game.engine.load_state(state)
        self._sync_game_from_engine(game)

    def _ensure_progressable_phase(self, game: GameSession) -> None:
        """Force phase convergence when current seat has no legal action."""
        if game.phase == "settlement" or game.status != "in_progress":
            return

        legal_actions = game.engine.get_legal_actions(game.current_seat)
        if not isinstance(legal_actions, dict):
            self._force_settlement_phase(game)
            return
        actions = legal_actions.get("actions")
        if isinstance(actions, list) and actions:
            return
        self._force_settlement_phase(game)

    @staticmethod
    def _map_engine_error(exc: Exception, *, game_id: int) -> RoomError:
        code = str(exc)
        if code == "ENGINE_VERSION_CONFLICT":
            return GameVersionConflictError(f"version conflict on game_id={game_id}")
        if code in {
            "ENGINE_INVALID_ACTION",
            "ENGINE_INVALID_ACTION_INDEX",
            "ENGINE_INVALID_COVER_LIST",
            "ENGINE_INVALID_PHASE",
        }:
            return GameInvalidActionError(f"invalid action on game_id={game_id}: {code}")
        return GameInvalidActionError(f"engine rejected action on game_id={game_id}: {code}")

    def _start_game(self, room: Room) -> None:
        game_id = self._next_game_id
        self._next_game_id += 1

        rng_seed: int | None = None
        if self._next_game_seed_provider is not None:
            injected_seed = self._next_game_seed_provider()
            if injected_seed is not None:
                rng_seed = int(injected_seed)
        if rng_seed is None:
            # Keep default game bootstrap deterministic for stable service-side regression.
            rng_seed = 1

        seat_to_user_id = {member.seat: member.user_id for member in room.members}
        user_id_to_seat = {user_id: seat for seat, user_id in seat_to_user_id.items()}

        engine = self._engine_cls()
        init_kwargs: dict[str, object] = {"config": {"player_count": MAX_ROOM_MEMBERS}}
        init_kwargs["rng_seed"] = rng_seed
        engine.init_game(**init_kwargs)

        game = GameSession(
            game_id=game_id,
            room_id=room.room_id,
            status="in_progress",
            rng_seed=rng_seed,
            seat_to_user_id=seat_to_user_id,
            user_id_to_seat=user_id_to_seat,
            version=1,
            phase="buckle_flow",
            current_seat=0,
            round_index=0,
            round_kind=0,
            last_combo=None,
            plays=[],
            private_hands_by_seat={},
            engine=engine,
        )
        self._sync_game_from_engine(game)

        self._games_by_id[game_id] = game
        room.current_game_id = game_id
        room.status = "playing"

    def _build_legal_actions(self, game: GameSession, seat: int) -> dict[str, object] | None:
        if game.status != "in_progress":
            return None

        legal_actions = game.engine.get_legal_actions(seat)
        if not isinstance(legal_actions, dict):
            return None

        actions = legal_actions.get("actions")
        if not isinstance(actions, list) or not actions:
            return None
        return legal_actions

    @staticmethod
    def _build_public_state(game: GameSession) -> dict[str, object]:
        public_state = game.engine.get_public_state()
        return public_state if isinstance(public_state, dict) else {}

    @staticmethod
    def _build_private_state(game: GameSession, seat: int) -> dict[str, object]:
        private_state = game.engine.get_private_state(seat)
        return private_state if isinstance(private_state, dict) else {"hand": {}, "covered": {}}

    def get_game_state_for_user(self, game_id: int, user_id: int) -> dict[str, object]:
        game = self.get_game(game_id)
        with self.lock_room(game.room_id):
            game = self.get_game(game_id)
            seat = game.user_id_to_seat.get(user_id)
            if seat is None:
                raise GameForbiddenError(f"user_id={user_id} not in game_id={game_id}")

            self._ensure_progressable_phase(game)
            if game.phase == "settlement":
                self._finalize_settlement(game)

            return {
                "game_id": game_id,
                "self_seat": seat,
                "public_state": self._build_public_state(game),
                "private_state": self._build_private_state(game, seat),
                "legal_actions": self._build_legal_actions(game, seat),
            }

    def _apply_chip_delta_to_room_members(self, game: GameSession) -> None:
        if game.settlement_payload is None or game.settlement_applied:
            return

        room = self.get_room(game.room_id)
        seat_to_member = {member.seat: member for member in room.members}
        chip_delta = game.settlement_payload.get("chip_delta_by_seat")
        if not isinstance(chip_delta, list):
            game.settlement_applied = True
            return

        for item in chip_delta:
            if not isinstance(item, dict):
                continue
            seat = int(item.get("seat", -1))
            if seat not in seat_to_member:
                continue
            delta = int(item.get("delta", 0))
            seat_to_member[seat].chips += delta
        game.settlement_applied = True

    def _finalize_settlement(self, game: GameSession) -> None:
        if game.settlement_payload is None:
            try:
                settle_output = game.engine.settle()
            except ValueError as exc:
                raise self._map_engine_error(exc, game_id=game.game_id) from exc
            settlement = settle_output.get("settlement") if isinstance(settle_output, dict) else None
            if not isinstance(settlement, dict):
                raise GameStateConflictError(
                    f"game_id={game.game_id} engine settlement payload is invalid"
                )
            game.settlement_payload = deepcopy(settlement)

        self._sync_game_from_engine(game)
        game.status = "settlement"
        game.phase = "settlement"

        room = self.get_room(game.room_id)
        if room.current_game_id == game.game_id:
            room.status = "settlement"
            for member in room.members:
                member.ready = False

        self._apply_chip_delta_to_room_members(game)

    def get_game_settlement_for_user(self, game_id: int, user_id: int) -> dict[str, object]:
        """Return settlement payload for a game member in settlement phase."""
        game = self.get_game(game_id)
        with self.lock_room(game.room_id):
            game = self.get_game(game_id)
            seat = game.user_id_to_seat.get(user_id)
            if seat is None:
                raise GameForbiddenError(f"user_id={user_id} not in game_id={game_id}")

            self._ensure_progressable_phase(game)
            if str(game.phase) != "settlement":
                raise GameStateConflictError(f"game_id={game_id} not in settlement phase")

            self._finalize_settlement(game)
            if game.settlement_payload is None:
                raise GameStateConflictError(f"game_id={game_id} settlement unavailable")
            return deepcopy(game.settlement_payload)

    def apply_game_action(
        self,
        *,
        game_id: int,
        user_id: int,
        action_idx: int,
        client_version: int | None,
        cover_list: dict[str, int] | None,
    ) -> None:
        game = self.get_game(game_id)
        with self.lock_room(game.room_id):
            game = self.get_game(game_id)
            seat = game.user_id_to_seat.get(user_id)
            if seat is None:
                raise GameForbiddenError(f"user_id={user_id} not in game_id={game_id}")
            self._ensure_progressable_phase(game)
            if game.phase == "settlement":
                self._finalize_settlement(game)
            if game.status != "in_progress":
                raise GameInvalidActionError(f"game_id={game_id} status={game.status} cannot accept actions")
            if seat != game.current_seat:
                raise GameInvalidActionError(f"user_id={user_id} is not current seat")

            try:
                game.engine.apply_action(
                    action_idx=int(action_idx),
                    cover_list=cover_list,
                    client_version=client_version,
                )
            except ValueError as exc:
                raise self._map_engine_error(exc, game_id=game_id) from exc

            self._sync_game_from_engine(game)
            if game.phase == "settlement":
                self._finalize_settlement(game)

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
    "GameForbiddenError",
    "GameInvalidActionError",
    "GameNotFoundError",
    "GameSession",
    "GameStateConflictError",
    "GameVersionConflictError",
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
