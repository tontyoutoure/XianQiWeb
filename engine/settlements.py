"""Settlement entrypoint for the engine."""

from __future__ import annotations

from typing import Any


def settle_state(state: dict[str, Any] | None) -> dict[str, Any]:
    """Settle the current game state.

    The real settlement algorithm is intentionally not implemented in this stage.
    """

    raise NotImplementedError("settle is not implemented in this stage")
