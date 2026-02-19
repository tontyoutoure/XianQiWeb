## 当前进度
- M0 文档基线已冻结：架构、规则、接口、后端设计均完成。
- M1 鉴权能力已完成：Auth REST + WS 鉴权链路可用。
- 真实服务联调（2026-02-14）已全绿：REST 01-13、WS 01-06、E2E 01-03 全部通过。
- M3 设计文档补充（2026-02-15）：已新增 `memory-bank/design/engine_design.md`，明确对局引擎各对外接口实现逻辑与状态推进口径。
- M3 逻辑引擎 TDD 完成（2026-02-18）：UT/CB/LA/ACT/CLI/RF/BF 全套测试已绿，正在向收口测试推进。
- M3 规则补充（2026-02-19）：收轮后新增“提前结算”判定（任一玩家瓷或两名玩家够即进入 settlement），并完成 `M3-ACT-11~14` 测试落地。
- M5 CLI 结算接入（2026-02-20）：`engine/cli.py` 在 `phase=settlement` 自动触发 `settle` 并输出按 seat 拆分的结算明细（含 `sum(delta)` 守恒提示），`M5-CLI-01~04` 已通过。
- M3 CLI 交互优化（2026-02-20）：cover-only 场景跳过 `action_idx`，改为手牌索引输入（如 `01`）选择垫牌，降低 `cover_list` 输入复杂度。
- M3 CLI 显示修复（2026-02-20）：玩家柱数在缺失 `captured_pillar_count` 字段时改为从 `pillar_groups` 本地推导，避免显示为 `-`。
- M3 CLI 柱数统计修复（2026-02-20）：柱数推导统一改为按 `pillar_groups[*].round_kind` 累计，修复对子/三牛回合仅加 1 的问题。
- M3 轻量日志能力（2026-02-19）：`init_game` 新增可选 `log_path`；按版本落盘 `state_v{version}.json`，成功动作追加 `action.json`，`settle()` 覆盖写 `settle.json`；CLI 已支持 `--log-path` 直连测试。
- M3 引擎状态 SSOT 收敛（2026-02-20）：移除 `pillar_groups.pillars` 冗余缓存字段；`load_state` 对旧字段立即不兼容；reducer/settlement/CLI 柱数口径统一为 `sum(round_kind)`；相关回归测试通过。
- M2（房间大厅）进展（2026-02-15）：
  - 已完成：主链路全绿（`M2-API-01~14`、`M2-WS-01~06`、`M2-CC-01~03`）。
  - 已完成：真实服务收口全链路通过（`M2-RS-REST-01~15,18`、`M2-RS-WS-01~10`、`M2-RS-CC-01~03`）。
  - 待补：`M2-RS-REST-16~17` 因 M3 开局未接入暂时 skip。

## 当前阶段
- M3（逻辑引擎核心规则）已基本收口：`M3-UT-01~08`、`M3-CB-01~14`、`M3-LA-01~22`、`M3-ACT-01~14`、`M3-CLI-01~08`、`M3-RF-01~03`、`M3-BF-01~10` 已通过。
- M5（结算与继续下一局）推进中：引擎与 CLI 结算链路已打通（`M5-UT-01~13`、`M5-CLI-01~04` 通过），接口层 `/settlement`、`/continue` 待后续里程碑接入。
- 当前全量引擎测试为 `107 passed`（`pytest engine/tests -q`）。
- M3 轻量日志已接入引擎与 CLI：可按局输出状态/动作/结算日志用于本地排查与回放。
- M2（房间大厅）收口中：仅剩 `M2-RS-REST-16~17` 待 M3 开局能力接入后回补。
