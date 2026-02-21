# M5 阶段真实服务收口测试清单（Settlement REST + Re-ready + Room WS/并发）

> 目标：在真实启动的后端服务上完成 M5 收口验证，聚焦“结算查询 + 结算后重新 ready 开局 + WS 首帧推送 + 并发一致性”。
> 依据文档：`memory-bank/tests/m5-tests.md`、`memory-bank/implementation-plan.md`（M5/M6）、`memory-bank/interfaces/frontend-backend-interfaces.md`（Games/Rooms/WS）、`memory-bank/design/backend_design.md`（3.x）。
> 当前状态：本文件为 M5 真实服务测试 ID 与执行记录来源（SSOT）；`M5-RS-REST-01~08`、`M5-RS-CC-01`、`M5-RS-WS-01` 已完成首轮 Red 实测（总计 `10 passed`）。

## 0) 测试环境与执行约定（真实服务）

- 建议环境：conda `XQB`。
- 运行方式：复用 `backend/tests/integration/real_service/live_server.py` 拉起 uvicorn 进程。
- 数据隔离：每条测试用例使用独立 sqlite 文件（`tmp_path`）。
- 建议基础参数：
  - `XQWEB_ROOM_COUNT=3`
  - `XQWEB_JWT_SECRET=<at-least-32-byte-secret>`
- 推荐测试文件规划（供后续实现）：
  - `backend/tests/integration/real_service/test_m5_rs_rest_01_08_red.py`
  - `backend/tests/integration/real_service/test_m5_rs_cc_01_red.py`
  - `backend/tests/integration/real_service/test_m5_rs_ws_01_red.py`

## 1) REST 收口测试映射（M5-RS-REST-01~08）

> 来源：`M5-BE-01~08`（`memory-bank/tests/m5-tests.md`）。

| 测试ID | 场景 | 通过条件 | 目标测试函数（规划） |
|---|---|---|---|
| M5-RS-REST-01 | `GET /api/games/{id}/settlement` 成功 | `phase=settlement` 时返回 `200`，且包含 `final_state + chip_delta_by_seat` | `test_m5_rs_rest_01_get_settlement_success` |
| M5-RS-REST-02 | `/settlement` phase 门禁 | `phase!=settlement` 时返回 `409 + GAME_STATE_CONFLICT` | `test_m5_rs_rest_02_get_settlement_phase_gate` |
| M5-RS-REST-03 | `/settlement` 成员权限 | 非对局成员访问返回 `403 + GAME_FORBIDDEN` | `test_m5_rs_rest_03_get_settlement_forbidden_non_member` |
| M5-RS-REST-04 | `/settlement` 资源不存在 | `game_id` 不存在返回 `404 + GAME_NOT_FOUND` | `test_m5_rs_rest_04_get_settlement_game_not_found` |
| M5-RS-REST-05 | 结算后 ready 自动清零 | 进入结算后 `GET /api/rooms/{room_id}` 的成员 `ready` 全为 `false` | `test_m5_rs_rest_05_ready_reset_after_settlement` |
| M5-RS-REST-06 | 结算后三人重新 ready 开新局 | 第三名成员提交 `ready=true` 后，房间回 `playing` 且 `current_game_id` 变化 | `test_m5_rs_rest_06_all_ready_in_settlement_starts_new_game` |
| M5-RS-REST-07 | 结算后未全员 ready 不开局 | 仅部分成员 `ready=true` 时，房间保持 `settlement` 且 `current_game_id` 不变 | `test_m5_rs_rest_07_partial_ready_in_settlement_not_start` |
| M5-RS-REST-08 | 结算后非成员 ready 拒绝 | 非成员调用 `/api/rooms/{room_id}/ready` 返回 `403 + ROOM_NOT_MEMBER` | `test_m5_rs_rest_08_ready_forbidden_non_member` |

## 2) 并发收口测试映射（M5-RS-CC-01）

> 来源：`M5-BE-09`（`memory-bank/tests/m5-tests.md`）。

| 测试ID | 场景 | 通过条件 | 目标测试函数（规划） |
|---|---|---|---|
| M5-RS-CC-01 | 结算后并发 ready 一致性 | 三人并发 `ready=true` 时仅创建 1 个新局（`current_game_id` 只前进一步） | `test_m5_rs_cc_01_concurrent_ready_after_settlement_single_new_game` |

## 3) WebSocket 收口测试映射（M5-RS-WS-01）

> 来源：`M5-BE-10`（`memory-bank/tests/m5-tests.md`）。

| 测试ID | 场景 | 通过条件 | 目标测试函数（规划） |
|---|---|---|---|
| M5-RS-WS-01 | 重新 ready 开局后的 WS 推送 | 新局创建后房间 WS 至少收到：`ROOM_UPDATE`（新 `current_game_id`）+ 新局 `GAME_PUBLIC_STATE` + 新局 `GAME_PRIVATE_STATE` | `test_m5_rs_ws_01_reopen_pushes_room_update_and_new_game_frames` |

## 4) 收口通过标准（M5 Exit Criteria, Real-service）

- `M5-RS-REST-01~08`、`M5-RS-CC-01`、`M5-RS-WS-01` 全部通过。
- 结算接口的权限、phase 门禁、错误码口径与接口文档一致。
- 结算后重新开局链路在 REST 与 WS 视角均一致可观测。
- 并发 ready 场景下无重复开局、无 `current_game_id` 竞争写穿透。

## 5) TDD 执行记录（待启动）

> 约定：按“人类指定测试 ID -> 编写测试 -> 执行 Red/Green”推进；每条用例先记录 Red，再记录 Green。

| 测试ID | 当前状态 | TDD阶段 | 执行日期 | 备注 |
|---|---|---|---|---|
| M5-RS-REST-01 | ✅ 已通过 | Red（实测通过） | 2026-02-21 | 新增 `backend/tests/integration/real_service/test_m5_rs_rest_01_08_red.py` 后执行 `pytest backend/tests/integration/real_service/test_m5_rs_rest_01_08_red.py -q`，结果 `5 passed`（同批次）。 |
| M5-RS-REST-02 | ✅ 已通过 | Red（实测通过） | 2026-02-21 | 同批次执行通过（`/settlement` 在非结算阶段返回 `409 + GAME_STATE_CONFLICT`）。 |
| M5-RS-REST-03 | ✅ 已通过 | Red（实测通过） | 2026-02-21 | 同批次执行通过（非成员访问 `/settlement` 返回 `403 + GAME_FORBIDDEN`）。 |
| M5-RS-REST-04 | ✅ 已通过 | Red（实测通过） | 2026-02-21 | 同批次执行通过（未知 `game_id` 返回 `404 + GAME_NOT_FOUND`）。 |
| M5-RS-REST-05 | ✅ 已通过 | Red（实测通过） | 2026-02-21 | 同批次执行通过（进入结算后房间三名成员 `ready=false`）。 |
| M5-RS-REST-06 | ✅ 已通过 | Red（实测通过） | 2026-02-21 | 在同文件补充并执行通过（三人在结算后再次 ready 会创建新 `game_id` 且房态回 `playing`）。 |
| M5-RS-REST-07 | ✅ 已通过 | Red（实测通过） | 2026-02-21 | 同批次执行通过（结算后仅部分成员 ready 不开新局，房态保持 `settlement`）。 |
| M5-RS-REST-08 | ✅ 已通过 | Red（实测通过） | 2026-02-21 | 同批次执行通过（结算后非成员调用 ready 返回 `403 + ROOM_NOT_MEMBER`）。 |
| M5-RS-CC-01 | ✅ 已通过 | Red（实测通过） | 2026-02-21 | 新增 `backend/tests/integration/real_service/test_m5_rs_cc_01_red.py` 并执行通过（结算后并发 ready 仅创建一次新局）。 |
| M5-RS-WS-01 | ✅ 已通过 | Red（实测通过） | 2026-02-21 | 新增 `backend/tests/integration/real_service/test_m5_rs_ws_01_red.py` 并执行通过（重新开局后收到 `ROOM_UPDATE + GAME_PUBLIC_STATE + GAME_PRIVATE_STATE` 新局首帧）。 |
