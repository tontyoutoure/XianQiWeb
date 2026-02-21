# M4 阶段真实服务收口测试清单（Games REST + Room WS + 并发）

> 目标：在真实启动的后端服务上完成 M4 收口验证（后端-引擎集成与动作接口）。
> 依据文档：`memory-bank/tests/m4-tests.md`、`memory-bank/implementation-plan.md`（M4/M6）、`memory-bank/interfaces/frontend-backend-interfaces.md`（Games/WS）、`memory-bank/design/backend_design.md`（3.x）。
> 当前状态：`M4-API-01~05` 已完成 Red->Green（`5 passed`）；`M4-API-06~10` 已完成红测落地并执行（当前结果 `4 passed, 1 failed`，失败点为 API-10）；其余用例仍为 `skip` 占位。
> 口径声明：本文件是 M4 API/WS/CC 测试ID与执行记录的唯一来源（SSOT）。

## 0) 测试环境与执行约定（真实服务）

- 建议环境：conda `XQB`。
- 运行方式：使用 `backend/tests/integration/real_service/live_server.py` 动态拉起 uvicorn 进程。
- 数据隔离：每条测试使用独立 sqlite 文件（`tmp_path` 下）。
- 推荐执行命令：
  - `conda run -n XQB pytest backend/tests/integration/real_service/test_m4_rs_rest_01_14_red.py -q`
  - `conda run -n XQB pytest backend/tests/integration/real_service/test_m4_rs_ws_01_06_red.py -q`
  - `conda run -n XQB pytest backend/tests/integration/real_service/test_m4_rs_cc_01_03_red.py -q`
- 本阶段约束：
  - 当前 `M4-API-01~10` 已进入测试体阶段（其中 API-10 仍处 Red 失败）。
  - `M4-API-11~14` 与全部 WS/CC 测试 ID 暂保留 `pytest.skip` 占位。

## 1) REST 收口测试映射（M4-API-01~14）

| 测试ID | 场景 | 占位测试函数 |
|---|---|---|
| M4-API-01 | `GET /api/games/{id}/state` 成功 | `test_m4_rs_rest_01_get_state_success` |
| M4-API-02 | `/state` 非成员拒绝 | `test_m4_rs_rest_02_get_state_forbidden_non_member` |
| M4-API-03 | `/state` game 不存在 | `test_m4_rs_rest_03_get_state_game_not_found` |
| M4-API-04 | `POST /actions` 成功推进 | `test_m4_rs_rest_04_post_actions_success_version_increments` |
| M4-API-05 | `/actions` 版本冲突 | `test_m4_rs_rest_05_post_actions_version_conflict` |
| M4-API-06 | `/actions` 非当前行动位拒绝 | `test_m4_rs_rest_06_post_actions_reject_non_turn_player` |
| M4-API-07 | `/actions` 非法 `cover_list` 拒绝 | `test_m4_rs_rest_07_post_actions_reject_invalid_cover_list` |
| M4-API-08 | `/actions` 非成员拒绝 | `test_m4_rs_rest_08_post_actions_forbidden_non_member` |
| M4-API-09 | `/actions` game 不存在 | `test_m4_rs_rest_09_post_actions_game_not_found` |
| M4-API-10 | `GET /settlement` phase 门禁 | `test_m4_rs_rest_10_get_settlement_phase_gate` |
| M4-API-11 | `GET /settlement` 成功 | `test_m4_rs_rest_11_get_settlement_success` |
| M4-API-12 | 结算后 ready 已清零 | `test_m4_rs_rest_12_ready_reset_after_settlement` |
| M4-API-13 | 结算阶段三人重新 ready 开新局 | `test_m4_rs_rest_13_all_ready_in_settlement_starts_new_game` |
| M4-API-14 | 结算后未全员 ready 不开局 | `test_m4_rs_rest_14_partial_ready_in_settlement_not_start` |

## 2) WebSocket 收口测试映射（M4-WS-01~06）

| 测试ID | 场景 | 占位测试函数 |
|---|---|---|
| M4-WS-01 | 房间 WS 初始快照（无局） | `test_m4_rs_ws_01_room_snapshot_without_game_only_room_update` |
| M4-WS-02 | 房间 WS 初始快照（有局） | `test_m4_rs_ws_02_room_snapshot_with_game_ordered_events` |
| M4-WS-03 | 动作后公共态推送 | `test_m4_rs_ws_03_action_pushes_game_public_state` |
| M4-WS-04 | 动作后私有态私发 | `test_m4_rs_ws_04_private_state_is_unicast_per_seat` |
| M4-WS-05 | 进入结算推送 | `test_m4_rs_ws_05_enter_settlement_pushes_settlement_event` |
| M4-WS-06 | 冷结束推送 | `test_m4_rs_ws_06_leave_during_playing_pushes_waiting_without_settlement` |

## 3) 并发收口测试映射（M4-CC-01~03）

| 测试ID | 场景 | 占位测试函数 |
|---|---|---|
| M4-CC-01 | 并发动作互斥 | `test_m4_rs_cc_01_concurrent_actions_single_winner` |
| M4-CC-02 | 结算后并发 ready 一致性 | `test_m4_rs_cc_02_concurrent_ready_after_settlement_single_new_game` |
| M4-CC-03 | ready 临界并发仅开一局 | `test_m4_rs_cc_03_concurrent_third_ready_only_one_game_created` |

## 4) 收口通过标准（M4 Exit Criteria）

- `M4-API-01~14`、`M4-WS-01~06`、`M4-CC-01~03` 全部由真实服务测试通过。
- 游戏接口与房间 WS 事件顺序、权限、错误码口径与接口文档一致。
- 并发场景下无重复开局、无并发写穿透。
- 以上标准将在后续“按 ID 逐条实现测试体”后正式判定；当前仅完成骨架。

## 5) TDD 执行记录（脚手架阶段）

| 测试ID | 当前状态 | TDD阶段 | 执行日期 | 备注 |
|---|---|---|---|---|
| M4-API-01 ~ M4-API-05 | 🟢 Green 已执行 | Green 已完成 | 2026-02-21 | 先执行 Red（`5 failed, 9 skipped`）；补齐后端 `/api/games/{id}/state` 与 `/api/games/{id}/actions` 基础链路（成员鉴权、版本冲突、动作推进）后复测 `pytest backend/tests/integration/real_service/test_m4_rs_rest_01_14_red.py -q`，结果 `5 passed, 9 skipped`。 |
| M4-API-06 ~ M4-API-10 | 🔴 Red 已执行（部分通过） | Red 已完成 | 2026-02-21 | 按指定测试ID补齐测试体并执行 `pytest backend/tests/integration/real_service/test_m4_rs_rest_01_14_red.py -q -k "rest_06 or rest_07 or rest_08 or rest_09 or rest_10"`：结果 `1 failed, 4 passed, 9 deselected`；失败点：`M4-API-10` 期望 `/settlement` 在非结算阶段返回 `409 + GAME_STATE_CONFLICT`，现状返回 `404 Not Found`（路由未实现）。 |
| M4-API-11 ~ M4-API-14 | ⏳ 未开始 | 框架已建（skip） | 2026-02-21 | 对应文件 `test_m4_rs_rest_01_14_red.py`，维持 skip 占位。 |
| M4-WS-01 ~ M4-WS-06 | ⏳ 未开始 | 框架已建（skip） | 2026-02-21 | 对应文件 `test_m4_rs_ws_01_06_red.py`，每条用例仅保留 skip 占位 |
| M4-CC-01 ~ M4-CC-03 | ⏳ 未开始 | 框架已建（skip） | 2026-02-21 | 对应文件 `test_m4_rs_cc_01_03_red.py`，每条用例仅保留 skip 占位 |

## 6) Real-service 收口索引（2026-02-21）

- 收口文档（M4 API/WS/CC 唯一测试ID来源）：`memory-bank/tests/m4-tests-real-service.md`。
- 收口测试文件：
  - `backend/tests/integration/real_service/test_m4_rs_rest_01_14_red.py`
  - `backend/tests/integration/real_service/test_m4_rs_ws_01_06_red.py`
  - `backend/tests/integration/real_service/test_m4_rs_cc_01_03_red.py`
- 公共骨架模块：
  - `backend/tests/integration/real_service/m4_helpers.py`
  - `backend/tests/integration/real_service/m4_ws_helpers.py`
  - `backend/tests/integration/real_service/m4_scenarios.py`
- 当前阶段约束：`M4-API-01~09` 已可执行并通过，`M4-API-10` 已定位 Red 失败点；其余 real-service 用例保持 skip，占位后续按“人类指定测试ID -> 编写测试体 -> Red/Green”推进。
