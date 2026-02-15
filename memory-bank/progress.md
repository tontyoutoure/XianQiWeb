## 当前进度
- M0 文档基线已冻结：架构、规则、接口、后端设计均完成。
- M1 鉴权能力已完成：Auth REST + WS 鉴权链路可用。
- 真实服务联调（2026-02-14）已全绿：REST 01-13、WS 01-06、E2E 01-03 全部通过。
- M2（房间大厅）进展（2026-02-15）：
  - 已完成：主链路全绿（`M2-API-01~14`、`M2-WS-01~06`、`M2-CC-01~03`）。
  - 已完成：真实服务收口全链路通过（`M2-RS-REST-01~15,18`、`M2-RS-WS-01~10`、`M2-RS-CC-01~03`）。
  - 待补：`M2-RS-REST-16~17` 因 M3 开局未接入暂时 skip。

## 当前阶段
- M2（房间大厅）收口中：仅剩 `M2-RS-REST-16~17` 待 M3 开局能力接入后回补。

## 记录位置
- M1 真实服务结果：`memory-bank/tests/m1-tests-real-service.md`。
- M2 用例与红绿记录：`memory-bank/tests/m2-tests.md`。
- M2 真实服务收口清单：`memory-bank/tests/m2-tests-real-service.md`。
