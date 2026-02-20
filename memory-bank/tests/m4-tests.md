# M4 阶段测试列表（后端-引擎集成与动作接口）

> 依据文档：`memory-bank/implementation-plan.md`（M4/M6）、`memory-bank/interfaces/frontend-backend-interfaces.md`（Games/WS）、`memory-bank/interfaces/backend-engine-interface.md`、`memory-bank/design/backend_design.md`（第 3 节）。
> 目标：先冻结 M4（含 M6 对局推送）测试清单，再按“人类指定测试ID -> 编写测试 -> Red/Green”推进。

## 0) 测试运行环境与执行约定

- 建议环境：conda `XQB`。
- 建议命令：`conda run -n XQB pytest backend/tests -q`（按测试ID分批执行）。
- 测试分层：优先 API/WS 契约 + 轻量单元（game session 编排），避免在后端重复验证引擎规则细节。
- 本文档用于记录 M4 用例设计与每条用例 Red/Green 结果。

## 1) 单元测试（后端 game 编排层）

| 测试ID | 测试描述 | 通过条件 |
|---|---|---|
| M4-UT-01 | 全员 ready 触发开局 | 第 3 名成员 ready=true 后创建 `game_id`，房间 `status=playing` 且 `current_game_id` 非空 |
| M4-UT-02 | seat 映射一致性 | `seat_to_user_id` 与 `user_id_to_seat` 双向可逆，且覆盖 0/1/2 |
| M4-UT-03 | 冷结束 game 状态迁移 | playing 中 leave 后 game 标记 `aborted`，房间 `current_game_id=null`、`status=waiting` |
| M4-UT-04 | 结算后 ready 重置 | 对局进入结算时房间三名成员 `ready` 全部变为 `false` |
| M4-UT-05 | 重新 ready 开局一次性 | `status=settlement` 且从“非全员 ready”变为“全员 ready”时仅触发一次开局 |

## 2) API 测试（Games REST）

| 测试ID | 测试描述 | 通过条件 |
|---|---|---|
| M4-API-01 | `GET /api/games/{id}/state` 成功 | 房间成员拿到 `game_id/self_seat/public_state/private_state/legal_actions` |
| M4-API-02 | `/state` 非成员拒绝 | 非房间成员访问返回 `403`（统一错误体） |
| M4-API-03 | `/state` game 不存在 | 返回 `404 + GAME_NOT_FOUND` |
| M4-API-04 | `POST /actions` 成功推进 | 返回 `204`，且后续 `/state` 看到 `public_state.version + 1` |
| M4-API-05 | `/actions` 版本冲突 | 传旧 `client_version` 返回 `409 + GAME_VERSION_CONFLICT` |
| M4-API-06 | `/actions` 非当前行动位拒绝 | 返回 `409 + GAME_INVALID_ACTION` |
| M4-API-07 | `/actions` 非法 `cover_list` 拒绝 | 返回 `409 + GAME_INVALID_ACTION`（或 `GAME_INVALID_COVER_LIST`，按实现映射） |
| M4-API-08 | `/actions` 非成员拒绝 | 返回 `403` |
| M4-API-09 | `/actions` game 不存在 | 返回 `404` |
| M4-API-10 | `GET /settlement` phase 门禁 | 非 `settlement/finished` 返回 `409 + GAME_STATE_CONFLICT` |
| M4-API-11 | `GET /settlement` 成功 | 结算阶段返回 `chip_delta_by_seat` 且 seat 覆盖 0/1/2 |
| M4-API-12 | 结算后 ready 已清零 | 进入结算后查询 `room_detail`，三名成员 `ready=false` |
| M4-API-13 | 结算阶段三人重新 ready 开新局 | 三名成员在结算后再次 ready=true，立即创建新 `game_id` 并切 `status=playing` |
| M4-API-14 | 结算后未全员 ready 不开局 | 仅 1~2 人 ready 时保持 `status=settlement` 且 `current_game_id` 不变 |

## 3) WebSocket 测试（房间通道游戏事件）

| 测试ID | 测试描述 | 通过条件 |
|---|---|---|
| M4-WS-01 | 房间 WS 初始快照（无局） | 仅收到 `ROOM_UPDATE`，不下发 `GAME_PUBLIC_STATE/GAME_PRIVATE_STATE` |
| M4-WS-02 | 房间 WS 初始快照（有局） | 连接后按顺序收到 `ROOM_UPDATE -> GAME_PUBLIC_STATE -> GAME_PRIVATE_STATE(私发)` |
| M4-WS-03 | 动作后公共态推送 | 成功动作后房间连接收到新的 `GAME_PUBLIC_STATE` |
| M4-WS-04 | 动作后私有态私发 | 每个连接仅收到自己 seat 的 `GAME_PRIVATE_STATE`，不泄露他人私有态 |
| M4-WS-05 | 进入结算推送 | phase 进入 settlement 时收到 `SETTLEMENT` |
| M4-WS-06 | 冷结束推送 | playing 中 leave 后房间收到 `ROOM_UPDATE`，状态回 waiting 且无 settlement |

## 4) 并发与一致性测试

| 测试ID | 测试描述 | 通过条件 |
|---|---|---|
| M4-CC-01 | 并发动作互斥 | 同一版本并发提交两个动作，仅一个成功，另一个返回冲突 |
| M4-CC-02 | 结算后并发 ready 一致性 | 三人近同时提交 ready，最终仅创建一个新 `game_id` 且状态一致 |
| M4-CC-03 | ready 临界并发仅开一局 | 同时触发“第三人 ready”场景时，只创建一个 `game_id` |

## 5) 阶段通过判定（M4）

- Games 三接口（`/state`、`/actions`、`/settlement`）契约全部可测。
- 房间与对局状态联动完整：开局、动作、结算、重新 ready 开下一局、冷结束闭环成立。
- 房间 WS 的 `GAME_PUBLIC_STATE/GAME_PRIVATE_STATE/SETTLEMENT` 推送时机稳定且无私有信息泄露。
- 并发场景下不出现重复开局、重复决议或多动作并发写穿透。

## 6) TDD 执行记录（进行中）

> 说明：按“人类指定测试ID -> 编写测试 -> 执行 Red/Green”推进；当前已完成 `M4-UT-01~05` 红测落地与执行。

| 测试ID | 当前状态 | TDD阶段 | 备注 |
|---|---|---|---|
| M4-UT-01 ~ M4-UT-05 | 🟢 Green 已执行 | Green 已完成 | 2026-02-20：先执行 Red（`5 failed`）；随后在 `app.rooms.registry` 实现 game session 编排（全员 ready 开局、seat 映射、leave 冷结束标记 aborted、进入 settlement 清空 ready、settlement 再 ready 仅开一局）后，执行 `pytest backend/tests/unit/test_m4_red_ut_01_05_room_game_orchestration.py -q`，结果 `5 passed`。 |
| M4-API-01 ~ M4-API-14 | ⏳ 待执行 | 未开始 | 待指定 |
| M4-WS-01 ~ M4-WS-06 | ⏳ 待执行 | 未开始 | 待指定 |
| M4-CC-01 ~ M4-CC-03 | ⏳ 待执行 | 未开始 | 待指定 |
