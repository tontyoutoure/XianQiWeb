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
| M8 | 进行中 | 2026-03-03 | 已进入 M8：对局操作区与结算展示前端实现及全链路回归。 |

## 二级进度（当前 Milestone 内部，Milestone 完结时清零）
- 当前 Milestone：`M8`
- 内部进度记录：
  - 2026-03-02：完成 `memory-bank/tests/m8-tests-real-service.md` 初版，冻结 Seed Hunter 流程与 test-only 种子注入协议（仅 `/api/test-tools/rooms/{room_id}/next-game-seed`）；明确“黑棋重发对前端无感”，并落地 `M8-SEED-GATE-01~05` 门禁测试清单。
  - 2026-03-02：Seed 台账迁移到前端 JSON（`frontend/tests/e2e/seed-catalog/m8-seeds.json`），并将 `memory-bank/tests/m8-tests-real-service.md` 调整为流程与字段约束文档（JSON 为 SSOT）。
  - 2026-03-02：新增前端台账读取工具 `frontend/tests/e2e/support/seed-catalog.ts` 与契约单测 `frontend/tests/unit/m8-seed-catalog.test.ts`，执行结果 `4 passed`。
  - 2026-03-02：根据 M8 新讨论重写 `memory-bank/tests/m8-tests-real-service.md`：移除全部既有测试用例/执行记录，仅保留测试设计草案；种子口径改为启动参数方案，并冻结 `seed_requirement={first_turn_seat,hands_at_least_by_seat}`（不包含 phase 与 legal_actions 约束）。
  - 2026-03-02：进一步调整 M8 Seed 设计口径：台账路径改为目录（允许多文件），并从草案中移除 `evidence`、`last_verified_at`、`fallback_policy.max_rounds`、`status` 字段要求。
  - 2026-03-02：将 Seed Hunter 设计主叙事迁移到 `memory-bank/design/backend_design.md`（新增 M8 专章，定义 ENV 接口、目录多台账契约、匹配与 fail-fast 约束）；`memory-bank/tests/m8-tests-real-service.md` 调整为测试关注点并引用后端设计章节。
  - 2026-03-02：新增 `memory-bank/tests/m7.5-test.md`，冻结后端种子能力的 TDD 测试清单（配置路由、离线 seed hunting、REST 注入与“一次性消费”语义）并建立 Red/Green 记录表。
  - 2026-03-02：按指定测试 ID 拉红 `M8-SEED-CFG-01~05`（新增 `backend/tests/integration/real_service/test_m8_rs_cfg_01_05_red.py`），结果 5/5 Red：种子 ENV 配置校验/模式路由与注入 REST 入口均未落地。
  - 2026-03-02：完成 `M8-SEED-CFG-01~05` Green 实现并复测通过（`pytest backend/tests/integration/real_service/test_m8_rs_cfg_01_05_red.py -q` -> `5 passed`）；已落地 seed ENV 校验、catalog 模式启动即退出、`POST /api/games/seed-injection` 入口。
  - 2026-03-02：完成 `M8-SEED-HUNT-01~08` 与 `M8-SEED-API-05~07` 的 Red->Green：新增 `app.seed_hunter`（候选过滤、`seed_requirement` 匹配、`search_range` 搜索、命中回填、失败退出码），并补齐注入 seed 在开局链路的“一次性消费”语义（`RoomRegistry` 新增 `rng_seed` 记录与 `next_game_seed` 消费回调）；验证通过 `pytest backend/tests/unit/test_m8_seed_hunt_01_08.py -q`（8 passed）、`pytest backend/tests/api/games/test_m8_api_seed_injection_05_07.py -q`（3 passed）。
  - 2026-03-03：重写 `memory-bank/design/backend_design.md` 第 4 章结构（重编号并按“配置/契约/判定/流程/写回/接口/错误/冻结口径”聚合），同步更新 `memory-bank/tests/m8-tests-real-service.md` 的章节索引锚点，消除 Seed Hunter 同概念分散描述。
  - 2026-03-03：新增 `memory-bank/tests/m7.5-test.md`，按 `backend_design.md` 第 4 章（4.1~4.9）冻结后端 Seed Hunter 全覆盖测试清单（`M7.5-MODE/CAT/MATCH/HUNT/API` 共 23 条）并初始化 TDD Red/Green 执行记录模板。
  - 2026-03-03：新增红测文件 `backend/tests/integration/real_service/test_m8_rs_mode_01_04_red.py` 并执行 `pytest ... -q`：`M7.5-MODE-01` 拉红（1 failed，`catalog` 模式经 `uvicorn` 启动返回码为 3），`M7.5-MODE-02~04` 直绿（3 passed）。
  - 2026-03-03：完成 `M7.5-MODE-01` Green 修复：新增 `runtime.exit_if_seed_hunting_mode()` 并在 `app.main` 导入阶段执行，使 `XQWEB_SEED_CATALOG_DIR` 场景下走离线 seed hunting 后以 `exit 0` 退出而非 lifespan 启动失败；复测 `pytest backend/tests/integration/real_service/test_m8_rs_mode_01_04_red.py -q` 为 `4 passed`。
  - 2026-03-03：新增 `backend/tests/unit/test_m8_cat_01_05_red.py` 并执行 `pytest ... -q`：`M7.5-CAT-01~04` 直绿、`M7.5-CAT-05` 拉红（`seed_required=false && seed_current!=null` 当前未触发契约错误）。
  - 2026-03-03：完成 `M7.5-CAT-05` Green 修复：在 `run_seed_hunting` 增加全局契约校验（`seed_required=false` 时 `seed_current` 必须为 `null`）；复测 `pytest backend/tests/unit/test_m8_cat_01_05_red.py -q` 为 `5 passed`。
  - 2026-03-03：新增 `backend/tests/unit/test_m8_match_01_03_red.py` 并执行 `pytest ... -q`：`M7.5-MATCH-01~03` 直绿（`3 passed`），已回填 `memory-bank/tests/m7.5-test.md` 执行记录。
  - 2026-03-03：新增 `backend/tests/unit/test_m8_hunt_01_06_red.py` 并执行 `pytest ... -q`：`M7.5-HUNT-01~06` 直绿（`6 passed`），已回填 `memory-bank/tests/m7.5-test.md` 执行记录。
  - 2026-03-03：新增 `backend/tests/api/games/test_m8_api_seed_injection_01_05_red.py` 并执行 `pytest ... -q`：`M7.5-API-01/03/04/05` 直绿，`M7.5-API-02` 拉红（无效请求体当前返回 `422`，与约定 `400` 不一致，`3 failed, 4 passed`）；已回填 `memory-bank/tests/m7.5-test.md` 执行记录。
  - 2026-03-03：完成 `M7.5-API-02` Green 修复：调整 `POST /api/games/seed-injection` 为手动请求体校验并将参数错误统一映射为 `400`（`SEED_INJECTION_BAD_REQUEST`）；复测 `pytest backend/tests/api/games/test_m8_api_seed_injection_01_05_red.py -q` 为 `7 passed`，并回归 `pytest backend/tests/integration/real_service/test_m8_rs_mode_01_04_red.py -q` 为 `4 passed`。
  - 2026-03-03：将 `memory-bank/tests/m8-tests.md` 重命名为 `memory-bank/tests/m7.5-test.md`，并将文档内测试编号统一为 `M7.5-*`；补充“该文档用于 M8 阶段 E2E 测试基础设施”的定位说明，同时同步修正文档引用路径。
  - 2026-03-03：基于 `memory-bank/design/frontend_ingame_design.md` 完成 M8 测试设计文档拆分：新增 `memory-bank/tests/m8-tests.md`（UT/CT/集成）并重写 `memory-bank/tests/m8-tests-real-service.md`（真实后端 E2E），同时为全部测试 ID 初始化 Red/Green 执行记录模板。
  - 2026-03-03：新增 `memory-bank/tests/tdd-subagent-batch-workflow.md`，固化“双 agent、每 4 条测试一波、Red/Green 各一次提交、波末重启 agent、改测争议即停机”的统一执行规范。
  - 2026-03-03：完成 M8 前四项（`M8-UT-01/02/03`、`M8-IT-01`）Red->Green：新增 `frontend/src/stores/ingame-actions.ts`（`mapLegalActionsToButtonTypes`、`buildActionSubmitPayload`），并修正 `frontend/tests/unit/m8-actions-stage-1-red.test.ts` 的模块加载方式为标准 `import('@/stores/ingame-actions')`；验证 `cd frontend && npm run test -- --run tests/unit/m8-actions-stage-1-red.test.ts` 通过（`4 passed`），全量前端单测回归 `26 passed`。
  - 2026-03-04：按 `tdd-subagent-batch-workflow` 完成第 1 波（`M8-IT-02~05`）Red->Green：新增 `frontend/tests/unit/m8-actions-stage-2-red.test.ts` 并在 `frontend/src/stores/ingame-actions.ts` 落地冲突恢复与提交错误处理控制器（`createIngameActionControllerForTest`）；复测 `cd frontend && npm run test -- --run tests/unit/m8-actions-stage-1-red.test.ts tests/unit/m8-actions-stage-2-red.test.ts` 通过（`8 passed`）。
  - 2026-03-04：按 `tdd-subagent-batch-workflow` 完成第 2 波（`M8-CT-01~04`）Red->Green：新增 `frontend/tests/unit/m8-action-bar-stage-3-red.test.ts` 与 `frontend/src/components/ingame/ActionBar.vue`，固化 `buckle_flow/reveal/in_round` 三类阶段的按钮可见性映射；复测 `cd frontend && npm run test -- --run tests/unit/m8-actions-stage-1-red.test.ts tests/unit/m8-actions-stage-2-red.test.ts tests/unit/m8-action-bar-stage-3-red.test.ts` 通过（`12 passed`）。

## 维护规则（执行口径）
- 一级进度：每个 Milestone 永远只保留一条，推进时只更新该 Milestone 对应行。
- 二级进度：只记录“当前 Milestone”的内部推进，随推进逐条追加。
- Milestone 完结时：先把一级进度对应行改为“已完成”，再将二级进度清零并切换到下一个 Milestone。
