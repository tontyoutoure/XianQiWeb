# M4 阶段测试列表（UT + 收口索引）

> 依据文档：`memory-bank/implementation-plan.md`（M4/M6）、`memory-bank/design/backend_design.md`（第 3 节）。
> 目标：本文件仅保留 M4-UT（后端 game 编排层）与收口索引；M4 的 API/WS/CC 测试清单统一维护在 `memory-bank/tests/m4-tests-real-service.md`。

## 0) 测试运行环境与执行约定

- 建议环境：conda `XQB`。
- 建议命令：`conda run -n XQB pytest backend/tests -q`（按测试ID分批执行）。
- 测试分层：M4-UT 在本文件维护；M4-API/M4-WS/M4-CC 在 real-service 文档维护。
- 本文档用于记录 M4 用例设计与每条用例 Red/Green 结果。

## 1) 单元测试（后端 game 编排层）

| 测试ID | 测试描述 | 通过条件 |
|---|---|---|
| M4-UT-01 | 全员 ready 触发开局 | 第 3 名成员 ready=true 后创建 `game_id`，房间 `status=playing` 且 `current_game_id` 非空 |
| M4-UT-02 | seat 映射一致性 | `seat_to_user_id` 与 `user_id_to_seat` 双向可逆，且覆盖 0/1/2 |
| M4-UT-03 | 冷结束 game 状态迁移 | playing 中 leave 后 game 标记 `aborted`，房间 `current_game_id=null`、`status=waiting` |
| M4-UT-04 | 结算后 ready 重置 | 对局进入结算时房间三名成员 `ready` 全部变为 `false` |
| M4-UT-05 | 重新 ready 开局一次性 | `status=settlement` 且从“非全员 ready”变为“全员 ready”时仅触发一次开局 |

## 2) 阶段通过判定（M4）

- M4-UT-01~05 保持通过（后端 game 编排层）。
- M4 API/WS/并发收口统一以 `memory-bank/tests/m4-tests-real-service.md` 为准。

## 3) TDD 执行记录（进行中）

> 说明：按“人类指定测试ID -> 编写测试 -> 执行 Red/Green”推进；当前已完成 `M4-UT-01~05` 红测落地与执行。

| 测试ID | 当前状态 | TDD阶段 | 备注 |
|---|---|---|---|
| M4-UT-01 ~ M4-UT-05 | 🟢 Green 已执行 | Green 已完成 | 2026-02-20：先执行 Red（`5 failed`）；随后在 `app.rooms.registry` 实现 game session 编排（全员 ready 开局、seat 映射、leave 冷结束标记 aborted、进入 settlement 清空 ready、settlement 再 ready 仅开一局）后，执行 `pytest backend/tests/unit/test_m4_red_ut_01_05_room_game_orchestration.py -q`，结果 `5 passed`。 |
| M4-RS-API/WS/CC（收口） | 🔄 进行中 | API 01~05 Green 已完成 | 2026-02-21：`M4-API-01~05` 已完成 Red->Green（`5 passed, 9 skipped`）；其余 RS 用例仍为 skip，占位详情见 `memory-bank/tests/m4-tests-real-service.md`。 |
