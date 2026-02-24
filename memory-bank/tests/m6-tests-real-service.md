# M6 阶段真实服务全量测试设计（实时推送 + 断线重连）

> 目标：按“全量后端服务测试”标准完成 M6 收口，覆盖 M1~M5 回归门禁 + M6 增量能力（实时推送一致性、心跳保活、断线重连恢复、并发一致性）。
> 依据文档：`memory-bank/implementation-plan.md`（M6）、`memory-bank/design/backend_design.md`（3.5/3.7）、`memory-bank/interfaces/frontend-backend-interfaces.md`（2.x）、`memory-bank/tests/m4-tests-real-service.md`、`memory-bank/tests/m5-tests-real-service.md`。
> 口径声明：本文件是 M6 真实服务测试 ID 与执行记录的 SSOT。
> 当前状态：`M6-RS-WS-01~08` 已完成首轮 Red 实测（`8 passed`）；`M6-RS-RC-01~08` 已完成 Green 修复回归（`8 passed`）。

## 0) 测试环境与执行约定（真实服务）

- 建议环境：conda `XQB`。
- 启动方式：复用 `backend/tests/integration/real_service/live_server.py` 拉起 uvicorn 进程。
- 数据隔离：每条用例使用独立 sqlite（`tmp_path`）。
- 建议基础环境变量：
  - `XQWEB_ROOM_COUNT=3`
  - `XQWEB_JWT_SECRET=<at-least-32-byte-secret>`
  - `XQWEB_ACCESS_TOKEN_EXPIRE_SECONDS`（常规用例可默认；token 过期用例建议调小并单测隔离）
- 推荐测试文件规划：
  - `backend/tests/integration/real_service/test_m6_rs_ws_01_08_red.py`
  - `backend/tests/integration/real_service/test_m6_rs_rc_01_08_red.py`
  - `backend/tests/integration/real_service/test_m6_rs_hb_01_03_red.py`
  - `backend/tests/integration/real_service/test_m6_rs_cc_01_05_red.py`

## 1) 全量回归门禁（进入 M6 前置）

> 本节是“全量后端服务测试标准”的基线门禁：M6 新增用例执行前，M1~M5 对应真实服务收口需保持通过。

| 门禁ID | 场景 | 通过条件 |
|---|---|---|
| M6-GATE-01 | M1 鉴权真实服务回归 | `test_m1_rs_rest_red.py`、`test_m1_rs_ws_red.py`、`test_m1_rs_e2e_red.py` 全通过 |
| M6-GATE-02 | M2 房间真实服务回归 | `M2-RS-REST-01~18`、`M2-RS-WS-01~10`、`M2-RS-CC-01~03` 全通过 |
| M6-GATE-03 | M4 对局接口/推送回归 | `M4-API-01~14`、`M4-WS-01~06`、`M4-CC-01~03` 全通过 |
| M6-GATE-04 | M5 结算与再开局回归 | `M5-RS-REST-01~08`、`M5-RS-CC-01`、`M5-RS-WS-01` 全通过 |

## 2) M6 实时推送测试映射（M6-RS-WS-01~08）

| 测试ID | 场景 | 通过条件 | 目标测试函数（规划） |
|---|---|---|---|
| M6-RS-WS-01 | 房间 WS 初始快照（有局）顺序稳定 | 建连后按顺序收到 `ROOM_UPDATE -> GAME_PUBLIC_STATE -> GAME_PRIVATE_STATE`，且 `game_id/version` 对齐 | `test_m6_rs_ws_01_room_snapshot_with_game_ordered` |
| M6-RS-WS-02 | 房间 WS 初始快照（无局）最小化 | `current_game_id=null` 时仅收到 `ROOM_UPDATE`，无多余游戏帧 | `test_m6_rs_ws_02_room_snapshot_without_game_only_room_update` |
| M6-RS-WS-03 | 动作后推送顺序与版本单调 | 每次动作后先 `GAME_PUBLIC_STATE`，再 seat 私发 `GAME_PRIVATE_STATE`；`public_state.version` 严格递增 | `test_m6_rs_ws_03_action_push_order_and_version_monotonic` |
| M6-RS-WS-04 | 私有态隔离（无越权泄露） | A 连接只能收到 A 的 `self_seat/private_state/legal_actions`，不得出现 B/C 私有态 | `test_m6_rs_ws_04_private_state_unicast_without_leak` |
| M6-RS-WS-05 | 进入结算推送完整 | 进入 `settlement` 后可观测 `ROOM_UPDATE`（`status=settlement`）与 `SETTLEMENT`，且 `game_id` 一致 | `test_m6_rs_ws_05_settlement_push_with_room_transition` |
| M6-RS-WS-06 | 冷结束推送口径 | `playing` 中 leave 后只收到 `ROOM_UPDATE(waiting,current_game_id=null)`，不发送 `SETTLEMENT` | `test_m6_rs_ws_06_cold_abort_push_without_settlement` |
| M6-RS-WS-07 | 大厅/房间双通道一致性 | 同一事件后 `ROOM_LIST` 与 `ROOM_UPDATE` 的房态、人数、ready 计数一致 | `test_m6_rs_ws_07_lobby_and_room_consistency` |
| M6-RS-WS-08 | 房间多连接广播一致性 | 同房多客户端同时在线，接收的公共帧 `type/game_id/version` 序列一致 | `test_m6_rs_ws_08_multi_client_public_stream_consistent` |

## 3) M6 断线重连恢复测试映射（M6-RS-RC-01~08）

| 测试ID | 场景 | 通过条件 | 目标测试函数（规划） |
|---|---|---|---|
| M6-RS-RC-01 | 断线后 HTTP 快照恢复 | 断线期间他人推进动作后，`GET /api/games/{id}/state` 返回最新 `public/private/legal_actions` | `test_m6_rs_rc_01_http_state_recover_after_disconnect` |
| M6-RS-RC-02 | 重连后房间 WS 首帧恢复 | 重连成功后再次收到完整首帧序列，且 `version >= 断线前版本` | `test_m6_rs_rc_02_room_ws_snapshot_after_reconnect` |
| M6-RS-RC-03 | 跨多步缺帧恢复一致 | 离线跨越多步动作，重连后公共态（phase/round/version）与在线玩家一致 | `test_m6_rs_rc_03_multi_step_catchup_consistency` |
| M6-RS-RC-04 | `buckle_flow` 阶段重连恢复 | 重连后当前决策 seat 与 `legal_actions`（`BUCKLE/PASS` 或 `REVEAL/PASS`）正确恢复 | `test_m6_rs_rc_04_buckle_flow_recover_legal_actions` |
| M6-RS-RC-05 | `in_round` 阶段重连恢复 | 重连后 `PLAY/COVER` 可行动作与服务端一致，`action_idx` 顺序稳定 | `test_m6_rs_rc_05_in_round_recover_action_index_stable` |
| M6-RS-RC-06 | `settlement` 阶段重连恢复 | 重连后可恢复到 `phase=settlement`，且 `GET /settlement` 返回结构与房间视图一致 | `test_m6_rs_rc_06_settlement_recover_and_query` |
| M6-RS-RC-07 | token 过期断连后 refresh 重连 | WS 因 token 过期被 `4401` 关闭后，refresh 成功并可重连恢复同房状态 | `test_m6_rs_rc_07_expired_token_refresh_then_reconnect` |
| M6-RS-RC-08 | 服务重启边界（非恢复） | 服务重启后旧 `game_id` 不可恢复（`404/409`），房间重置为空，边界行为符合文档 | `test_m6_rs_rc_08_restart_boundary_no_cross_restart_recover` |

## 4) M6 心跳保活测试映射（M6-RS-HB-01~03）

| 测试ID | 场景 | 通过条件 | 目标测试函数（规划） |
|---|---|---|---|
| M6-RS-HB-01 | PING 周期与 PONG 保活 | 收到服务端 PING 后在 10s 内回 PONG，连接持续存活 | `test_m6_rs_hb_01_ping_pong_keepalive` |
| M6-RS-HB-02 | 超时未回 PONG 断连 | 连续 2 次未按时回 PONG 后服务端断连，关闭行为可观测 | `test_m6_rs_hb_02_missing_pong_leads_disconnect` |
| M6-RS-HB-03 | 大量房间连接心跳稳定 | 多连接并存时，PING/PONG 不互相干扰，无异常断连与消息串房 | `test_m6_rs_hb_03_multi_connection_heartbeat_stable` |

## 5) M6 并发一致性测试映射（M6-RS-CC-01~05）

| 测试ID | 场景 | 通过条件 | 目标测试函数（规划） |
|---|---|---|---|
| M6-RS-CC-01 | 并发动作互斥 + 推送一致 | 同版本并发动作仅 1 个成功，其余冲突；所有在线客户端最终收敛到同一 `version` | `test_m6_rs_cc_01_concurrent_actions_single_winner_consistent_stream` |
| M6-RS-CC-02 | 断线重连与动作并发竞态 | 玩家重连瞬间与他人动作并发时，无重复应用动作、无版本回退 | `test_m6_rs_cc_02_reconnect_action_race_no_duplicate_apply` |
| M6-RS-CC-03 | 多端同账号连接一致性 | 同一账号多个房间 WS 连接均可收到自身私有态，且不互相污染 | `test_m6_rs_cc_03_multi_socket_same_user_private_consistent` |
| M6-RS-CC-04 | 结算后并发 ready + 重连 | 并发 ready 场景仅开 1 局；重连客户端能拿到新 `current_game_id` 首帧 | `test_m6_rs_cc_04_concurrent_ready_with_reconnect_single_new_game` |
| M6-RS-CC-05 | 三端长局一致性 | 连续多手动作 + 中途断连重连后，三端最终 `public_state.version/phase` 一致 | `test_m6_rs_cc_05_long_session_eventual_consistency` |

## 6) 收口通过标准（M6 Exit Criteria, Full Real-service）

- 全量门禁通过：`M6-GATE-01~04` 全绿。
- M6 增量通过：`M6-RS-WS-01~08`、`M6-RS-RC-01~08`、`M6-RS-HB-01~03`、`M6-RS-CC-01~05` 全绿。
- 关键一致性满足：
  - 事件顺序一致：`ROOM_UPDATE/GAME_PUBLIC_STATE/GAME_PRIVATE_STATE/SETTLEMENT` 顺序符合协议。
  - 恢复一致：HTTP 恢复与 WS 首帧恢复在同一 `game_id/version` 口径下收敛。
  - 安全隔离：私有态不泄露，鉴权失败可观测（401/403/4401）。
  - 并发稳态：无重复开局、无重复动作应用、无版本倒退。

## 7) TDD 执行记录（执行中）

> 约定：按“人类指定测试 ID -> 编写测试 -> 执行 Red/Green”推进；每条用例先记录 Red，再记录 Green。

| 测试ID | 当前状态 | TDD阶段 | 执行日期 | 备注 |
|---|---|---|---|---|
| M6-GATE-01 ~ M6-GATE-04 | ⏳ 待执行 | Pending | - | 先做全量回归门禁，失败即阻断 M6 增量测试。 |
| M6-RS-WS-01 | ✅ 已通过 | Red（实测通过） | 2026-02-21 | 新增 `backend/tests/integration/real_service/test_m6_rs_ws_01_08_red.py` 后执行 `pytest backend/tests/integration/real_service/test_m6_rs_ws_01_08_red.py -q`，结果 `8 passed`（同批次）。 |
| M6-RS-WS-02 | ✅ 已通过 | Red（实测通过） | 2026-02-21 | 同批次执行通过（无局房间初始快照仅 `ROOM_UPDATE`）。 |
| M6-RS-WS-03 | ✅ 已通过 | Red（实测通过） | 2026-02-21 | 同批次执行通过（动作后 `GAME_PUBLIC_STATE -> GAME_PRIVATE_STATE`，版本单调递增）。 |
| M6-RS-WS-04 | ✅ 已通过 | Red（实测通过） | 2026-02-21 | 同批次执行通过（私有态按连接 seat 私发，无跨 seat 泄露）。 |
| M6-RS-WS-05 | ✅ 已通过 | Red（实测通过） | 2026-02-21 | 同批次执行通过（进入结算收到 `ROOM_UPDATE(settlement)` 与 `SETTLEMENT`）。 |
| M6-RS-WS-06 | ✅ 已通过 | Red（实测通过） | 2026-02-21 | 同批次执行通过（playing 中 leave 冷结束无 `SETTLEMENT`）。 |
| M6-RS-WS-07 | ✅ 已通过 | Red（实测通过） | 2026-02-21 | 同批次执行通过（`ROOM_LIST` 与 `ROOM_UPDATE` 的 status/player_count/ready_count 一致）。 |
| M6-RS-WS-08 | ✅ 已通过 | Red（实测通过） | 2026-02-21 | 同批次执行通过（多连接公共态流 `game_id/version` 序列一致）。 |
| M6-RS-RC-01 | ✅ 已通过 | Green（修复通过） | 2026-02-24 | 修复后执行 `pytest backend/tests/integration/real_service/test_m6_rs_rc_01_08_red.py -q`，结果 `8 passed`（同批次），非当前 seat 的 `legal_actions` 已隐藏。 |
| M6-RS-RC-02 | ✅ 已通过 | Green（修复通过） | 2026-02-24 | 同批次通过：重连首帧非当前 seat 的 `GAME_PRIVATE_STATE.legal_actions` 已隐藏。 |
| M6-RS-RC-03 | ✅ 已通过 | Green（修复通过） | 2026-02-24 | 同批次通过：跨步恢复后公共态一致，非当前 seat 的 `legal_actions` 已隐藏。 |
| M6-RS-RC-04 | ✅ 已通过 | Green（修复通过） | 2026-02-24 | 同批次通过：开局/重连可恢复 `buckle_flow`，当前 seat 合法动作为 `BUCKLE/PASS_BUCKLE`。 |
| M6-RS-RC-05 | ✅ 已通过 | Green（修复通过） | 2026-02-24 | 同批次通过：合法动作索引稳定，非当前 seat 无 `legal_actions`。 |
| M6-RS-RC-06 | ✅ 已通过 | Green（修复通过） | 2026-02-24 | 同批次通过：`settlement` 重连首帧已隐藏 `legal_actions`，且 `/settlement` 与 WS 版本一致。 |
| M6-RS-RC-07 | ✅ 已通过 | Green（修复通过） | 2026-02-24 | 同批次通过：access token 过期后 WS 被 `4401 UNAUTHORIZED` 主动断连，refresh 后可重连。 |
| M6-RS-RC-08 | ✅ 已通过 | Green（回归通过） | 2026-02-24 | 同批次回归通过：服务重启边界行为保持正确（旧 `game_id` 不可恢复，房间重置）。 |
| M6-RS-HB-01 ~ M6-RS-HB-03 | ⏳ 待执行 | Pending | - | 先验证 PING/PONG 正常与超时断连，再做多连接压力。 |
| M6-RS-CC-01 ~ M6-RS-CC-05 | ⏳ 待执行 | Pending | - | 并发用例放在主链路稳定后执行。 |
