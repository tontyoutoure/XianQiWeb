## 当前进度
- M0 文档基线已冻结：架构、规则、接口、后端设计均完成。
- M1 鉴权能力已完成：Auth REST + WS 鉴权链路可用。
- 真实服务联调（2026-02-14）已全绿：REST 01-13、WS 01-06、E2E 01-03 全部通过。
- M2 首批 Rooms API（M2-API-01~05）已拉绿（2026-02-15）：`GET /api/rooms`、`GET /api/rooms/{room_id}`、`POST /api/rooms/{room_id}/join` 可用，并满足满员冲突与同房幂等契约。
- M2 API 红阶段推进（2026-02-15）：`M2-API-06~10` 用例已编写并执行，结果为 Red 意外全绿（跨房迁移/迁移回滚/leave/ready 契约已满足）。

## 当前阶段
- M2（房间大厅）进行中：下一步推进 `leave/ready` 相关 API、后续 API 06~14、WS 与并发用例。

## 记录位置
- M1 真实服务结果：`memory-bank/tests/m1-tests-real-service.md`。
- M2 用例与红绿记录：`memory-bank/tests/m2-tests.md`。
