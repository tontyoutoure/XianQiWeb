# M2 阶段测试列表（房间大厅）

> 依据文档：`memory-bank/implementation-plan.md`（M2）、`memory-bank/interfaces/frontend-backend-interfaces.md`（Rooms/WS）、`memory-bank/design/backend_design.md`（2.1~2.9）。
> 目标：先固化 M2 TDD 测试清单，再按“人类指定用例 -> 编写测试 -> 红绿推进”执行。

## 0) 测试运行环境与当前执行策略

- 建议环境：conda `XQB`。
- 常规执行（默认）：`conda run -n XQB pytest backend/tests -q`（按测试文件或测试ID分批执行）。
- 当前阶段决策（暂不真实服务）：M2 红绿循环阶段优先使用 TestClient/进程内集成测试，不阻塞在服务拉起、端口与外部环境问题。
- 必须真实服务的用例：`M2-CC-01`、`M2-CC-02`、`M2-CC-03`、`M2-WS-06`（并发与心跳时序）。
- 里程碑收口策略：在 M2 进入验收前，补充一轮真实服务联调（参考 M1 的 real-service 文档模式）验证 Rooms API 与 WS 主链路。

## 1) 单元测试（RoomRegistry / 业务规则）

| 测试ID | 测试描述 | 通过条件 |
|---|---|---|
| M2-UT-01 | 预设房间初始化（`room_id=0..N-1`） | `XQWEB_ROOM_COUNT=N` 时初始化得到 N 个房间，默认 `status=waiting`、`owner_id=null`、`current_game_id=null` |
| M2-UT-02 | seat 分配与回收（最小空位优先） | 连续加入占用 seat `0/1/2`；中间成员离开后，下一个加入复用最小空闲 seat |
| M2-UT-03 | owner 归属与转移 | 首个加入者成为 owner；owner 离开后转移给“剩余成员中最早加入者”；房间空后 owner 置空 |
| M2-UT-04 | ready 计数与成员状态一致性 | 成员 ready true/false 变更后，`ready_count` 与成员 ready 状态一致；离开成员不再计入 ready |
| M2-UT-05 | 同房重复 join 幂等 | 同一用户重复加入同一房间不新增成员，不改变 seat，返回当前房间快照 |
| M2-UT-06 | 跨房自动迁移成功 | 用户在 A 房调用 B 房 join 成功后：A 房移除该成员、B 房新增该成员，用户任一时刻仅在一个房间 |
| M2-UT-07 | 跨房迁移原子性（目标房满） | A 房用户尝试迁移到满员 B 房失败时，仍保留 A 房成员身份与原 seat/ready，不发生“先离后失” |
| M2-UT-08 | 冷结束状态重置 | `playing` 房间成员 leave 后：`status->waiting`、`current_game_id=null`、剩余成员 `ready=false`、`chips` 不变 |

## 2) API 测试（Rooms REST）

| 测试ID | 测试描述 | 通过条件 |
|---|---|---|
| M2-API-01 | `GET /api/rooms` 返回大厅摘要 | 返回按 `room_id` 可排序的 `room_summary[]`，字段含 `room_id/status/player_count/ready_count` |
| M2-API-02 | `GET /api/rooms/{room_id}` 房间详情与 404 | 合法 `room_id` 返回 `room_detail`；非法 `room_id` 返回 `404 + ROOM_NOT_FOUND` |
| M2-API-03 | `POST /join` 首次加入 | 成功加入后返回 `200 + room_detail`，成员 seat/chips 正确，首成员为 owner |
| M2-API-04 | `POST /join` 满员冲突 | 第 4 人加入同房返回 `409 + ROOM_FULL` |
| M2-API-05 | `POST /join` 同房幂等 | 已在目标房间再次 join 返回 `200`，成员数量与 seat 不变化 |
| M2-API-06 | `POST /join` 跨房自动迁移 | 用户从 A 房 join B 房后，A 房人数-1、B 房人数+1，用户在 B 房可见 |
| M2-API-07 | `POST /join` 跨房迁移失败回滚 | 目标房间满员时返回 `409`，并保持用户仍在原房间 |
| M2-API-08 | `POST /leave` 成功与 owner 转移 | 成员 leave 返回 `{"ok":true}`；若离开者是 owner，owner 正确转移 |
| M2-API-09 | `POST /leave` 非成员拒绝 | 非房间成员调用返回 `403 + ROOM_NOT_MEMBER` |
| M2-API-10 | `POST /ready` 正常变更 | waiting 状态下成员可切换 ready，返回更新后的 `room_detail` |
| M2-API-11 | `POST /ready` 非成员拒绝 | 非成员调用 ready 返回 `403 + ROOM_NOT_MEMBER` |
| M2-API-12 | `POST /ready` 非 waiting 拒绝 | `playing/settlement` 状态下 ready 变更返回 `409 + ROOM_NOT_WAITING` |
| M2-API-13 | 三人全 ready 的开局钩子 | 第 3 名成员 ready=true 后触发 `start_game` 预留钩子（可通过 mock 断言只触发一次） |
| M2-API-14 | `playing` 中 leave 触发冷结束 | leave 后房间回 waiting，`current_game_id` 清空，剩余成员 ready 清零，chips 不变 |

## 3) 并发测试（一致性）

| 测试ID | 测试描述 | 通过条件 |
|---|---|---|
| M2-CC-01 | 并发 join 不超员 | 多请求同时加入同一房间，最终成员数 `<=3`，无重复 seat |
| M2-CC-02 | 并发 ready 计数一致 | 多成员并发切换 ready 后，`ready_count` 与成员 ready 实际值一致 |
| M2-CC-03 | 跨房迁移无死锁 | 两个用户同时互换房间（A->B / B->A）可在超时前完成，无死锁且结果一致 |

## 4) WebSocket 测试（大厅与房间推送）

| 测试ID | 测试描述 | 通过条件 |
|---|---|---|
| M2-WS-01 | `/ws/lobby` 连接即全量快照 | 建连后立即收到 `ROOM_LIST`，内容与 `GET /api/rooms` 一致 |
| M2-WS-02 | `/ws/rooms/{room_id}` 连接即房间快照 | 建连后立即收到 `ROOM_UPDATE`，内容与 `GET /api/rooms/{room_id}` 一致 |
| M2-WS-03 | join 触发双通道更新 | 任一 join 成功后，lobby 收到 `ROOM_LIST`，对应 room 收到 `ROOM_UPDATE` |
| M2-WS-04 | ready 触发双通道更新 | ready 变更后，lobby `ready_count` 更新且 room 成员 ready 状态同步 |
| M2-WS-05 | leave/冷结束推送正确 | playing 房间成员 leave 后，room 推送含 `status=waiting` 与 `current_game_id=null` |
| M2-WS-06 | 心跳机制 | 服务端 `PING` 后客户端回 `PONG` 可保活；超时未回可断开 |

## 5) 阶段通过判定（M2 完成标准）

- Rooms 五接口（list/detail/join/leave/ready）行为与错误码符合契约。
- 房间容量、owner、seat、ready 计数、跨房迁移原子性均通过。
- 冷结束规则完整生效：不结算、不改 chips、`current_game_id` 清空、房间回 waiting。
- 并发下不超员、无 seat 冲突、无死锁。
- WS 的 lobby/room 初始快照与增量推送可用。

## 6) TDD 执行记录（初始）

> 说明：本节用于后续记录每个测试用例的 Red/Green 结果。当前仅完成测试清单整理。

| 测试ID | 当前状态 | TDD阶段 | 备注 |
|---|---|---|---|
| M2-UT-01 | ✅ 已通过 | Red -> Green 完成 | 红阶段：模块缺失导致失败；绿阶段实现 `app.rooms.registry.RoomRegistry` 后通过 |
| M2-UT-02 | ✅ 已通过 | Red -> Green 完成 | 通过断言：seat 初始分配 `0/1/2` 且离房后复用最小空位 |
| M2-UT-03 | ✅ 已通过 | Red -> Green 完成 | 通过断言：首入房为 owner，owner 离开后按最早加入顺序转移 |
| M2-UT-04 ~ M2-UT-08 | ⬜ 未开始 | 待执行 | 等待人类指定优先用例 |
| M2-API-01 ~ M2-API-14 | ⬜ 未开始 | 待执行 | 等待人类指定优先用例 |
| M2-CC-01 ~ M2-CC-03 | ⬜ 未开始 | 待执行 | 等待人类指定优先用例 |
| M2-WS-01 ~ M2-WS-06 | ⬜ 未开始 | 待执行 | 等待人类指定优先用例 |
