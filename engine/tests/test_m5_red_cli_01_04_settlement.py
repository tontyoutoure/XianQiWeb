"""M5 Red tests: M5-CLI-01~04 settlement display contracts for engine.cli."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _load_cli_module():
    try:
        import engine.cli as cli  # type: ignore
    except ModuleNotFoundError as exc:
        pytest.fail(f"M5-CLI: missing engine.cli module: {exc}")
    return cli


def test_m5_cli_01_settlement_phase_auto_settles_and_prints_settlement_block() -> None:
    """M5-CLI-01: settlement phase should auto-settle and print settlement section header."""

    cli = _load_cli_module()

    class FakeEngine:
        def __init__(self) -> None:
            self.phase = "settlement"
            self.version = 20
            self.settle_calls = 0

        def init_game(self, _config, rng_seed=None) -> None:  # noqa: ANN001, ANN002
            _ = rng_seed

        def get_public_state(self):
            return {
                "version": self.version,
                "phase": self.phase,
                "turn": {"current_seat": None},
                "players": [
                    {"seat": 0, "hand_count": 0, "captured_pillar_count": 3},
                    {"seat": 1, "hand_count": 0, "captured_pillar_count": 2},
                    {"seat": 2, "hand_count": 0, "captured_pillar_count": 1},
                ],
            }

        def settle(self):
            self.settle_calls += 1
            self.phase = "finished"
            self.version += 1
            return {
                "new_state": {"phase": self.phase, "version": self.version},
                "settlement": {
                    "chip_delta_by_seat": [
                        {"seat": 0, "delta": 2, "delta_enough": 2, "delta_reveal": 0, "delta_ceramic": 0},
                        {"seat": 1, "delta": -1, "delta_enough": -1, "delta_reveal": 0, "delta_ceramic": 0},
                        {"seat": 2, "delta": -1, "delta_enough": -1, "delta_reveal": 0, "delta_ceramic": 0},
                    ]
                },
            }

    outputs: list[str] = []

    def fake_output(line: str) -> None:
        outputs.append(line)

    fake_engine = FakeEngine()
    cli.XianqiGameEngine = lambda: fake_engine
    cli.run_cli(seed=20260220, input_fn=lambda _prompt: "0", output_fn=fake_output)

    assert fake_engine.settle_calls == 1
    assert any("=== Settlement ===" in line for line in outputs)


def test_m5_cli_02_settlement_rows_include_delta_breakdown() -> None:
    """M5-CLI-02: settlement output should include per-seat delta breakdown fields."""

    cli = _load_cli_module()

    class FakeEngine:
        def __init__(self) -> None:
            self.phase = "settlement"
            self.version = 30

        def init_game(self, _config, rng_seed=None) -> None:  # noqa: ANN001, ANN002
            _ = rng_seed

        def get_public_state(self):
            return {
                "version": self.version,
                "phase": self.phase,
                "turn": {"current_seat": None},
                "players": [
                    {"seat": 0, "hand_count": 0, "captured_pillar_count": 3},
                    {"seat": 1, "hand_count": 0, "captured_pillar_count": 2},
                    {"seat": 2, "hand_count": 0, "captured_pillar_count": 1},
                ],
            }

        def settle(self):
            self.phase = "finished"
            self.version += 1
            return {
                "new_state": {"phase": self.phase, "version": self.version},
                "settlement": {
                    "chip_delta_by_seat": [
                        {"seat": 0, "delta": 4, "delta_enough": 1, "delta_reveal": 0, "delta_ceramic": 3},
                        {"seat": 1, "delta": -2, "delta_enough": -1, "delta_reveal": -1, "delta_ceramic": 0},
                        {"seat": 2, "delta": -2, "delta_enough": 0, "delta_reveal": 1, "delta_ceramic": -3},
                    ]
                },
            }

    outputs: list[str] = []

    def fake_output(line: str) -> None:
        outputs.append(line)

    cli.XianqiGameEngine = FakeEngine
    cli.run_cli(seed=20260220, input_fn=lambda _prompt: "0", output_fn=fake_output)

    joined = "\n".join(outputs)
    assert "seat0" in joined and "delta_enough" in joined and "delta_reveal" in joined and "delta_ceramic" in joined
    assert "seat1" in joined and "seat2" in joined


def test_m5_cli_03_settlement_output_prints_sum_delta_invariant() -> None:
    """M5-CLI-03: settlement output should print a sum(delta)=0 invariant hint."""

    cli = _load_cli_module()

    class FakeEngine:
        def __init__(self) -> None:
            self.phase = "settlement"
            self.version = 40

        def init_game(self, _config, rng_seed=None) -> None:  # noqa: ANN001, ANN002
            _ = rng_seed

        def get_public_state(self):
            return {
                "version": self.version,
                "phase": self.phase,
                "turn": {"current_seat": None},
                "players": [
                    {"seat": 0, "hand_count": 0, "captured_pillar_count": 2},
                    {"seat": 1, "hand_count": 0, "captured_pillar_count": 2},
                    {"seat": 2, "hand_count": 0, "captured_pillar_count": 2},
                ],
            }

        def settle(self):
            self.phase = "finished"
            self.version += 1
            return {
                "new_state": {"phase": self.phase, "version": self.version},
                "settlement": {
                    "chip_delta_by_seat": [
                        {"seat": 0, "delta": 0, "delta_enough": 0, "delta_reveal": 0, "delta_ceramic": 0},
                        {"seat": 1, "delta": 0, "delta_enough": 0, "delta_reveal": 0, "delta_ceramic": 0},
                        {"seat": 2, "delta": 0, "delta_enough": 0, "delta_reveal": 0, "delta_ceramic": 0},
                    ]
                },
            }

    outputs: list[str] = []

    def fake_output(line: str) -> None:
        outputs.append(line)

    cli.XianqiGameEngine = FakeEngine
    cli.run_cli(seed=20260220, input_fn=lambda _prompt: "0", output_fn=fake_output)

    assert any("sum(delta)=0" in line for line in outputs)


def test_m5_cli_04_settlement_not_implemented_keeps_fallback_message() -> None:
    """M5-CLI-04: NotImplemented settle should keep the existing fallback message contract."""

    cli = _load_cli_module()

    class FakeEngine:
        def init_game(self, _config, rng_seed=None) -> None:  # noqa: ANN001, ANN002
            _ = rng_seed

        def get_public_state(self):
            return {
                "version": 50,
                "phase": "settlement",
                "turn": {"current_seat": None},
                "players": [
                    {"seat": 0, "hand_count": 0, "captured_pillar_count": 0},
                    {"seat": 1, "hand_count": 0, "captured_pillar_count": 0},
                    {"seat": 2, "hand_count": 0, "captured_pillar_count": 0},
                ],
            }

        def settle(self):
            raise NotImplementedError("settle is not implemented in this stage")

    outputs: list[str] = []

    def fake_output(line: str) -> None:
        outputs.append(line)

    cli.XianqiGameEngine = FakeEngine
    exit_code = cli.run_cli(seed=20260220, input_fn=lambda _prompt: "0", output_fn=fake_output)

    assert exit_code == 0
    assert any("结算阶段已到达，当前版本未实现 settle" in line for line in outputs)
