## 当前进度
- M0 文档基线已冻结：架构、规则、接口、后端设计均完成。
- M1 鉴权能力已完成：Auth REST + WS 鉴权链路可用。
- 真实服务联调（2026-02-14）已全绿：REST 01-13、WS 01-06、E2E 01-03 全部通过。
- M3 设计文档补充（2026-02-15）：已新增 `memory-bank/design/engine_design.md`，明确对局引擎各对外接口实现逻辑与状态推进口径。
- M3 测试清单细化（2026-02-15）：已新增 `memory-bank/tests/m3-tests.md`，补全组合枚举器（M3-CB）与合法动作枚举（M3-LA）核心用例。
- M3 首批红测（2026-02-15）：`M3-CB-01~04` 与 `M3-LA-04~06` 已落地并执行，当前按预期失败（`engine.combos` / `engine.core` 尚未实现）。
- M3 测试审查增强（2026-02-15）：`memory-bank/tests/m3-tests.md` 已补充 CB/LA 全量 mock 输入与预期结果（审查版）。
- M3 首批绿测（2026-02-16）：已新增 `engine/combos.py`、`engine/core.py` 与 `engine/__init__.py`，`M3-CB-01~04`、`M3-LA-04~06` 已转绿（`pytest engine/tests -q` 全部通过）。
- M3 合法动作枚举扩展测试（2026-02-16）：已新增 `M3-LA-13~22` 共 10 个“可行出牌组合”测试场景，测试文件 `engine/tests/test_m3_la_play_enumeration_13_22.py`，当前全部通过。
- M3 组合枚举剩余红测执行（2026-02-16）：已新增 `engine/tests/test_m3_red_cb_05_12.py` 覆盖 `M3-CB-05~12`，执行红阶段命令后意外全绿（8/8 通过）。
- M3 规则口径对齐（2026-02-16）：已修正文档链路中“狗脚对 > 红士对”的错误描述为“狗脚对 = 红士对”，并在 `engine/combos.py` 同步实现。
- M3 牌力等价回归（2026-02-16）：已新增 `engine/tests/test_m3_cb_13_14_gou_che_power.py`，确保 `R_GOU=R_CHE`、`B_GOU=B_CHE`，当前通过。
- M2（房间大厅）进展（2026-02-15）：
  - 已完成：主链路全绿（`M2-API-01~14`、`M2-WS-01~06`、`M2-CC-01~03`）。
  - 已完成：真实服务收口全链路通过（`M2-RS-REST-01~15,18`、`M2-RS-WS-01~10`、`M2-RS-CC-01~03`）。
  - 待补：`M2-RS-REST-16~17` 因 M3 开局未接入暂时 skip。

## 当前阶段
- M3（逻辑引擎核心规则）推进中：组合枚举 `M3-CB-01~14` 已覆盖，后续继续补齐 `M3-LA-01~03/07~12`、`M3-ACT-01~07`。
- M2（房间大厅）收口中：仅剩 `M2-RS-REST-16~17` 待 M3 开局能力接入后回补。

## 记录位置
- M1 真实服务结果：`memory-bank/tests/m1-tests-real-service.md`。
- M2 用例与红绿记录：`memory-bank/tests/m2-tests.md`。
- M2 真实服务收口清单：`memory-bank/tests/m2-tests-real-service.md`。
