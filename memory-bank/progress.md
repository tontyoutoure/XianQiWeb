## 当前进度
- M0 文档基线已冻结：架构、规则、接口、后端设计均完成。
- M1 鉴权能力已完成：Auth REST + WS 鉴权链路可用。
- 真实服务联调（2026-02-14）已全绿：REST 01-13、WS 01-06、E2E 01-03 全部通过。
- M2 首批 Rooms API（M2-API-01~05）已拉绿（2026-02-15）：`GET /api/rooms`、`GET /api/rooms/{room_id}`、`POST /api/rooms/{room_id}/join` 可用，并满足满员冲突与同房幂等契约。
- M2 API 红阶段推进（2026-02-15）：`M2-API-06~10` 用例已编写并执行，结果为 Red 意外全绿（跨房迁移/迁移回滚/leave/ready 契约已满足）。
- M2 API 继续推进（2026-02-15）：`M2-API-11~14` 完成红绿，其中 `M2-API-13` 已修复为“第 3 人 ready 时仅触发一次 start_game hook”；Rooms API `M2-API-01~14` 当前全绿。
- M2 WS 红阶段（2026-02-15）已执行：`M2-WS-01~06` 测试已落地并全部失败，当前阻塞点为缺少大厅/房间增量推送与 PING/PONG 心跳实现。
- M2 WS 绿阶段（2026-02-15）已完成：实现 `/ws/lobby` 与 `/ws/rooms/{room_id}` 初始快照、join/ready/leave 增量推送与心跳；`M2-WS-01~06` 全绿。
- M2 并发红阶段（2026-02-15）已执行：`M2-CC-01~03` 测试已落地并全红，当前阻塞点为缺少按房间串行化写操作与跨房迁移有序双锁机制。

## 当前阶段
- M2（房间大厅）进行中：Rooms API 01~14 与 WS 01~06 已完成，并发进入 Green 实现阶段（M2-CC-01~03）。

## 记录位置
- M1 真实服务结果：`memory-bank/tests/m1-tests-real-service.md`。
- M2 用例与红绿记录：`memory-bank/tests/m2-tests.md`。
