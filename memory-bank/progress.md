## 当前进度
- M0 文档基线已冻结：架构、规则、接口、后端设计均完成。
- M1 鉴权能力已完成：Auth REST + WS 鉴权链路可用。
- 真实服务联调（2026-02-14）已全绿：REST 01-13、WS 01-06、E2E 01-03 全部通过。
- M3 设计文档补充（2026-02-15）：已新增 `memory-bank/design/engine_design.md`，明确对局引擎各对外接口实现逻辑与状态推进口径。
- M3 测试清单细化（2026-02-15）：已新增 `memory-bank/tests/m3-tests.md`，补全组合枚举器（M3-CB）与合法动作枚举（M3-LA）核心用例。
- M3 首批红测（2026-02-15）：`M3-CB-01~04` 与 `M3-LA-04~06` 已落地并执行，当前按预期失败（`engine.combos` / `engine.core` 尚未实现）。
- M3 测试审查增强（2026-02-15）：`memory-bank/tests/m3-tests.md` 已补充 CB/LA 全量 mock 输入与预期结果（审查版）。
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
