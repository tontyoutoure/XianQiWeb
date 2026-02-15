## 当前进度
- M0 文档基线已冻结：架构、规则、接口、后端设计均完成。
- M1 鉴权能力已完成：Auth REST + WS 鉴权链路可用。
- 真实服务联调（2026-02-14）已全绿：REST 01-13、WS 01-06、E2E 01-03 全部通过。
- M2（房间大厅）进展（2026-02-15）：
  - 已完成：Rooms API `M2-API-01~14` 全绿（含幂等 join、跨房迁移/回滚、ready 约束、cold end、start_game hook 单次触发）。
  - 已完成：WS `M2-WS-01~06` 全绿（lobby/room 初始快照、join/ready/leave 推送、PING/PONG 心跳）。
  - 已完成：真实服务收口清单已落地（`memory-bank/tests/m2-tests-real-service.md`）。
  - 已完成：真实服务 REST `M2-RS-REST-01~10` 已编写并实测通过（`backend/tests/integration/real_service/test_m2_rs_rest_01_10_red.py`）。
  - 待完成：并发 `M2-CC-01~03` 仍在 Red（需房间级串行化写操作与跨房迁移有序双锁）。

## 当前阶段
- M2（房间大厅）进行中：API/WS 主链路已完成，当前聚焦并发 Green（`M2-CC-01~03`）。

## 记录位置
- M1 真实服务结果：`memory-bank/tests/m1-tests-real-service.md`。
- M2 用例与红绿记录：`memory-bank/tests/m2-tests.md`。
- M2 真实服务收口清单：`memory-bank/tests/m2-tests-real-service.md`。
