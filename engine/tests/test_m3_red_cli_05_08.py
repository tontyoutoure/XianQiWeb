"""M3 Red tests: M3-CLI-05~08 command-line interaction contracts."""

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
        pytest.fail(f"M3-CLI: missing engine.cli module: {exc}")
    return cli


def test_m3_cli_05_actions_render_with_explicit_action_idx_and_payload_cards() -> None:
    """M3-CLI-05: rendered list should expose action_idx and payload_cards text directly."""

    cli = _load_cli_module()

    rendered = cli._render_actions(  # pylint: disable=protected-access
        [
            {
                "type": "PLAY",
                "payload_cards": [{"type": "R_SHI", "count": 1}],
                "power": 9,
            },
            {
                "type": "COVER",
                "required_count": 1,
            },
        ]
    )

    assert "action_idx=0" in rendered
    assert "payload_cards" in rendered
    assert "action_idx=1" in rendered


def test_m3_cli_06_cover_invalid_then_retry_cover_only() -> None:
    """M3-CLI-06: COVER invalid input should reprompt cover_list directly without re-selecting action_idx."""

    cli = _load_cli_module()

    class FakeEngine:
        def __init__(self) -> None:
            self.version = 7
            self.phase = "in_round"
            self.apply_calls = 0

        def init_game(self, _config, rng_seed=None) -> None:  # noqa: ANN001, ANN002
            _ = rng_seed

        def get_public_state(self):
            return {
                "version": self.version,
                "phase": self.phase,
                "turn": {"current_seat": 0},
                "players": [
                    {"seat": 0, "hand_count": 2},
                    {"seat": 1, "hand_count": 2},
                    {"seat": 2, "hand_count": 2},
                ],
            }

        def get_private_state(self, seat: int):
            return {"hand": {"R_SHI": 1 if seat == 0 else 0}}

        def get_legal_actions(self, seat: int):
            assert seat == 0
            return {"seat": 0, "actions": [{"type": "COVER", "required_count": 1}]}

        def apply_action(self, action_idx: int, cover_list=None, client_version=None):  # noqa: ANN001
            assert action_idx == 0
            assert client_version == self.version
            self.apply_calls += 1
            if self.apply_calls == 1:
                raise ValueError("ENGINE_INVALID_COVER_LIST")
            self.phase = "finished"
            self.version += 1
            return {"new_state": {"phase": self.phase, "version": self.version}}

    prompts: list[str] = []
    outputs: list[str] = []
    scripted_inputs = iter(["0", "R_SHI:2", "0", "R_SHI:1"])

    def fake_input(prompt: str) -> str:
        prompts.append(prompt)
        return next(scripted_inputs)

    def fake_output(line: str) -> None:
        outputs.append(line)

    cli.XianqiGameEngine = FakeEngine
    cli.run_cli(seed=20260217, input_fn=fake_input, output_fn=fake_output)

    assert any("ENGINE_INVALID_COVER_LIST" in line for line in outputs)
    assert prompts.count("请输入 action_idx: ") == 1


def test_m3_cli_07_invalid_action_index_prints_error_code_prefix() -> None:
    """M3-CLI-07: invalid action_idx should print clear code prefix and then allow retry."""

    cli = _load_cli_module()

    class FakeEngine:
        def __init__(self) -> None:
            self.version = 11
            self.phase = "buckle_decision"

        def init_game(self, _config, rng_seed=None) -> None:  # noqa: ANN001, ANN002
            _ = rng_seed

        def get_public_state(self):
            return {
                "version": self.version,
                "phase": self.phase,
                "turn": {"current_seat": 0},
                "players": [
                    {"seat": 0, "hand_count": 2},
                    {"seat": 1, "hand_count": 2},
                    {"seat": 2, "hand_count": 2},
                ],
            }

        def get_private_state(self, seat: int):
            return {"hand": {"R_SHI": 1 if seat == 0 else 0}}

        def get_legal_actions(self, seat: int):
            assert seat == 0
            return {"seat": 0, "actions": [{"type": "PLAY", "payload_cards": [{"type": "R_SHI", "count": 1}], "power": 9}]}

        def apply_action(self, action_idx: int, cover_list=None, client_version=None):  # noqa: ANN001
            assert action_idx == 0
            assert cover_list is None
            assert client_version == self.version
            self.phase = "finished"
            self.version += 1
            return {"new_state": {"phase": self.phase, "version": self.version}}

    outputs: list[str] = []
    scripted_inputs = iter(["99", "0"])

    def fake_input(_prompt: str) -> str:
        return next(scripted_inputs)

    def fake_output(line: str) -> None:
        outputs.append(line)

    cli.XianqiGameEngine = FakeEngine
    cli.run_cli(seed=20260217, input_fn=fake_input, output_fn=fake_output)

    assert any(line.startswith("错误码:") and "ENGINE_INVALID_ACTION_INDEX" in line for line in outputs)


def test_m3_cli_08_settlement_without_settle_prints_contract_message() -> None:
    """M3-CLI-08: settlement phase should print the agreed fallback message when settle is unavailable."""

    cli = _load_cli_module()

    class FakeEngine:
        def init_game(self, _config, rng_seed=None) -> None:  # noqa: ANN001, ANN002
            _ = rng_seed

        def get_public_state(self):
            return {
                "version": 15,
                "phase": "settlement",
                "turn": {"current_seat": None},
                "players": [
                    {"seat": 0, "hand_count": 0},
                    {"seat": 1, "hand_count": 0},
                    {"seat": 2, "hand_count": 0},
                ],
            }

        def settle(self):
            raise NotImplementedError("settle is not implemented in this stage")

    outputs: list[str] = []

    def fake_output(line: str) -> None:
        outputs.append(line)

    cli.XianqiGameEngine = FakeEngine
    exit_code = cli.run_cli(seed=20260217, input_fn=lambda _prompt: "0", output_fn=fake_output)

    assert exit_code == 0
    assert any("结算阶段已到达，当前版本未实现 settle" in line for line in outputs)
