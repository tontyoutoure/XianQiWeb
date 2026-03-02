## 一级进度（Milestone 级，每个 Milestone 仅一条）
| Milestone | 状态 | 最新更新 | 一句话进度 |
| --- | --- | --- | --- |
| M0 | 已完成 | 2026-03-02 | 架构、接口、计划与设计文档基线已冻结并持续维护。 |
| M1 | 已完成 | 2026-03-02 | 鉴权链路（REST + WS）可用。 |
| M2 | 已完成 | 2026-03-02 | 大厅/房间主链路可用（加入、离开、ready、房态流转）。 |
| M3 | 已完成 | 2026-03-02 | 引擎核心规则与 CLI 演示已打通。 |
| M4 | 已完成 | 2026-03-02 | 后端-引擎集成、`/api/games/*` 与房间 WS 游戏事件链路已收口。 |
| M5 | 已完成 | 2026-03-02 | 结算与“结算后重置 ready -> 再次 ready 开新局”流程已收口。 |
| M6 | 已完成 | 2026-03-02 | 增量能力（WS/重连/心跳/并发）与全量门禁通过（M1~M5 真实服务回归 `86 passed`）。 |
| M7 | 已完成 | 2026-03-02 | 前端非对局范围已收口，`M7-GATE-01~03` 与 `M7-RS-E2E-01~12` 全绿（`17 passed`）。 |
| M8 | 进行中 | 2026-03-02 | 已进入 M8：对局操作区与结算展示前端实现及全链路回归。 |

## 二级进度（当前 Milestone 内部，Milestone 完结时清零）
- 当前 Milestone：`M8`
- 内部进度记录：
  - 2026-03-02：完成 `memory-bank/tests/m8-tests-real-service.md` 初版，冻结 Seed Hunter 流程与 test-only 种子注入协议（仅 `/api/test-tools/rooms/{room_id}/next-game-seed`）；明确“黑棋重发对前端无感”，并落地 `M8-SEED-GATE-01~05` 门禁测试清单。
  - 2026-03-02：Seed 台账迁移到前端 JSON（`frontend/tests/e2e/seed-catalog/m8-seeds.json`），并将 `memory-bank/tests/m8-tests-real-service.md` 调整为流程与字段约束文档（JSON 为 SSOT）。
  - 2026-03-02：新增前端台账读取工具 `frontend/tests/e2e/support/seed-catalog.ts` 与契约单测 `frontend/tests/unit/m8-seed-catalog.test.ts`，执行结果 `4 passed`。
  - 2026-03-02：根据 M8 新讨论重写 `memory-bank/tests/m8-tests-real-service.md`：移除全部既有测试用例/执行记录，仅保留测试设计草案；种子口径改为启动参数方案，并冻结 `seed_requirement={first_turn_seat,hands_at_least_by_seat}`（不包含 phase 与 legal_actions 约束）。
  - 2026-03-02：进一步调整 M8 Seed 设计口径：台账路径改为目录（允许多文件），并从草案中移除 `evidence`、`last_verified_at`、`fallback_policy.max_rounds`、`status` 字段要求。
  - 2026-03-02：将 Seed Hunter 设计主叙事迁移到 `memory-bank/design/backend_design.md`（新增 M8 专章，定义 ENV 接口、目录多台账契约、匹配与 fail-fast 约束）；`memory-bank/tests/m8-tests-real-service.md` 调整为测试关注点并引用后端设计章节。
  - 2026-03-02：新增 `memory-bank/tests/m8-test.md`，冻结后端种子能力的 TDD 测试清单（配置路由、离线 seed hunting、REST 注入与“一次性消费”语义）并建立 Red/Green 记录表。
  - 2026-03-02：按指定测试 ID 拉红 `M8-SEED-CFG-01~05`（新增 `backend/tests/integration/real_service/test_m8_rs_cfg_01_05_red.py`），结果 5/5 Red：种子 ENV 配置校验/模式路由与注入 REST 入口均未落地。
  - 2026-03-02：完成 `M8-SEED-CFG-01~05` Green 实现并复测通过（`pytest backend/tests/integration/real_service/test_m8_rs_cfg_01_05_red.py -q` -> `5 passed`）；已落地 seed ENV 校验、catalog 模式启动即退出、`POST /api/games/seed-injection` 入口。

## 维护规则（执行口径）
- 一级进度：每个 Milestone 永远只保留一条，推进时只更新该 Milestone 对应行。
- 二级进度：只记录“当前 Milestone”的内部推进，随推进逐条追加。
- Milestone 完结时：先把一级进度对应行改为“已完成”，再将二级进度清零并切换到下一个 Milestone。
