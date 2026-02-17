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
- M3 基础能力红测推进（2026-02-16）：已新增 `engine/tests/test_m3_red_ut_01_05.py` 并执行，`M3-UT-01~05` 当前按预期 Red（`init_game` 未实现）。
- M3 新增棋柱测试需求（2026-02-16）：测试文档已补充 `M3-ACT-08~10`，覆盖回合结束后棋柱归属与对子/三牛拆柱规则。
- M3 棋柱规则红测推进（2026-02-16）：已新增 `engine/tests/test_m3_red_act_08_10_pillars.py` 并执行，`M3-ACT-08~10` 当前按预期 Red（`apply_action` 未实现）。
- M3 引擎核心推进（2026-02-16）：已在 `engine/core.py` 实现 `init_game` 与最小可用 `apply_action`（含回合收尾与 `pillar_groups.pillars` 拆柱），`M3-UT-01~05` 与 `M3-ACT-08~10` 已转绿。
- M3 牌力编码重构（2026-02-16）：对子牌力改为对齐单张口径（`R_SHI` 对=9、`B_SHI` 对=8、狗脚对=9），移除 `19/18` 特殊编码并回归测试通过。
- M3 动作校验补齐（2026-02-17）：已新增并拉绿 `M3-ACT-01~07`（`engine/tests/test_m3_red_act_01_07.py`），在 `engine/core.py` 实现 `reveal_decision` 下 `REVEAL/PASS_REVEAL` 的 `pending_order` 消费、行动位推进与阶段收尾。
- M3 合法动作枚举补齐（2026-02-17）：已新增 `engine/tests/test_m3_red_la_01_03_07_12.py` 覆盖 `M3-LA-01~03/07~12`，执行 Red 阶段命令后意外全绿（9/9 通过）。
- M3 CLI 设计需求新增（2026-02-17）：已在 `memory-bank/design/engine_design.md` 增补命令行对局接口设计（可选 seed、单人三座次轮流、公共/私有状态展示与合法动作选择）；并在 `memory-bank/tests/m3-tests.md` 新增 `M3-CLI-01~08` 测试清单（待红测）。
- M3 CLI 首批红测（2026-02-17）：已新增 `engine/tests/test_m3_red_cli_01_04.py` 并执行，`M3-CLI-01~04` 当前按预期 Red（缺失 `engine.cli` 模块与核心交互函数）。
- M3 CLI 剩余红测（2026-02-17）：已新增 `engine/tests/test_m3_red_cli_05_08.py` 并执行，`M3-CLI-05~08` 当前按预期 Red（4 failed），覆盖动作列表索引展示、COVER 重试路径、非法索引错误输出与 settlement 终局提示文案。
- M3 CLI 红转绿（2026-02-17）：已在 `engine/cli.py` 完成动作列表 `action_idx/payload_cards` 展示、COVER 失败重试、错误码前缀输出和 settlement 文案修复；`pytest engine/tests/test_m3_red_cli_01_04.py -q` 与 `pytest engine/tests/test_m3_red_cli_05_08.py -q` 均为 `4 passed`。
- M3 引擎重构里程碑（2026-02-17）：已完成 `apply_action` 等效拆分（`engine/core.py` -> `engine/reducer.py`），并新增 `M3-RF-01~03`（`engine/tests/test_m3_refactor_apply_action_reducer.py`）完成红绿闭环；全量引擎测试更新为 `62 passed`（`pytest engine/tests -q`）。
- M3 公共态脱敏补齐（2026-02-17）：已新增并拉绿 `M3-UT-06`（`engine/tests/test_m3_red_ut_06_public_state_masking.py`），在 `engine/core.py` 实现 `get_public_state` 脱敏投影（`hand -> hand_count`、`power=-1 cards -> covered_count`、隐藏仅内部使用字段）；全量引擎测试更新为 `63 passed`（`pytest engine/tests -q`）。
- M3 私有态补齐（2026-02-17）：已新增并拉绿 `M3-UT-07`（`engine/tests/test_m3_red_ut_07_private_state_covered.py`），在 `engine/core.py` 实现 `get_private_state` 返回 `hand + covered`（按 `turn.plays + pillar_groups[*].plays` 中 `power=-1` 的本人垫牌聚合）；全量引擎测试更新为 `64 passed`（`pytest engine/tests -q`）。
- M3 序列化模块拆分（2026-02-17）：已新增 `engine/serializer.py` 并将 `load_state/dump_state/get_public_state/get_private_state` 及相关辅助函数从 `engine/core.py` 抽离，`engine/core.py` 改为调用 serializer；回归测试通过（`pytest engine/tests -q`，`64 passed`）。
- M3 合法动作模块拆分（2026-02-17）：已新增 `engine/actions.py` 并将 `get_legal_actions` 及手牌读取辅助函数从 `engine/core.py` 抽离为函数式实现（state-only）；`engine/core.py` 的同名方法改为转发调用，reducer 依赖链保持兼容；回归测试通过（`pytest engine/tests -q`，`64 passed`）。
- M3 seat 直索引与快速失败策略（2026-02-17）：`actions/reducer/serializer/core` 中多处 seat 手牌读取改为 `players[seat]` 直索引；`load_state` 增加 players 索引一致性断言（`players[i].seat == i`），并新增 `M3-UT-08`（`engine/tests/test_m3_ut_08_load_state_players_indexed_by_seat.py`）锁定契约；全量测试更新为 `65 passed`（`pytest engine/tests -q`）。
- M3 结算入口模块拆分（2026-02-17）：已新增 `engine/settlements.py` 并将 `engine/core.py` 的 `settle` 改为委托 `settlements` 入口，当前结算逻辑仍保持未实现占位；回归测试通过（`pytest engine/tests -q`，`65 passed`）。
- M5 结算测试清单初始化（2026-02-17）：已新增 `memory-bank/tests/m5-tests.md`，先落地“仅引擎结算”`M5-UT-01~13` 设计（含掀时已够未瓷特殊规则、黑棋零增量与全样例守恒断言），待人类指定测试ID后进入 Red/Green。
- M5 首批红测（2026-02-17）：已新增 `engine/tests/test_m5_red_ut_01_04_settlement.py` 并执行 `pytest engine/tests/test_m5_red_ut_01_04_settlement.py -q`，`M5-UT-01~04` 当前按预期 Red（4 failed，`settle` 仍未实现）。
- M5 测试复用与第二批红测（2026-02-17）：已新增 `engine/tests/m5_settlement_testkit.py` 抽离 M5-UT 通用状态构造与结算断言，并新增 `engine/tests/test_m5_red_ut_05_08_settlement.py`；执行 `pytest engine/tests/test_m5_red_ut_05_08_settlement.py -q`，`M5-UT-05~08` 当前按预期 Red（4 failed，`settle` 仍未实现）。
- M5 第三批红测（2026-02-17）：已新增 `engine/tests/test_m5_red_ut_09_12_settlement.py` 并复用 `m5_settlement_testkit`（含 `extract_new_state`）；执行 `pytest engine/tests/test_m5_red_ut_09_12_settlement.py -q`，`M5-UT-09~12` 当前按预期 Red（4 failed，`settle` 仍未实现）。
- M5 第四批红测（2026-02-17）：已新增 `engine/tests/test_m5_red_ut_13_settlement.py` 并复用 `m5_settlement_testkit` 的黑棋 seed 搜索与通用断言；执行 `pytest engine/tests/test_m5_red_ut_13_settlement.py -q`，`M5-UT-13` 当前按预期 Red（1 failed，`settle` 仍未实现）。
- M3 行动位字段收敛（2026-02-17）：已删除 `state.decision` 及 `_advance_decision` 相关调用，动作判定/状态推进/CLI 全部统一为 `turn.current_seat` 单一真源，并同步修正相关引擎测试夹具与断言；回归测试通过（`pytest engine/tests -q`，`65 passed`）。
- M2（房间大厅）进展（2026-02-15）：
  - 已完成：主链路全绿（`M2-API-01~14`、`M2-WS-01~06`、`M2-CC-01~03`）。
  - 已完成：真实服务收口全链路通过（`M2-RS-REST-01~15,18`、`M2-RS-WS-01~10`、`M2-RS-CC-01~03`）。
  - 待补：`M2-RS-REST-16~17` 因 M3 开局未接入暂时 skip。

## 当前阶段
- M3（逻辑引擎核心规则）推进中：`M3-UT-01~08`、`M3-CB-01~14`、`M3-LA-01~22`、`M3-ACT-01~10`、`M3-CLI-01~08`、`M3-RF-01~03` 已通过；当前全量测试为 `65 passed`（`pytest engine/tests -q`）。
- M2（房间大厅）收口中：仅剩 `M2-RS-REST-16~17` 待 M3 开局能力接入后回补。

## 记录位置
- M1 真实服务结果：`memory-bank/tests/m1-tests-real-service.md`。
- M2 用例与红绿记录：`memory-bank/tests/m2-tests.md`。
- M2 真实服务收口清单：`memory-bank/tests/m2-tests-real-service.md`。
