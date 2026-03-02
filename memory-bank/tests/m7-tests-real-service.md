# M7 阶段真实后端收口联调测试清单（Frontend Non-game + Real Backend）

> 目标：在真实启动的后端服务上完成 M7 非对局前端收口，验证“登录 -> 大厅 -> 房间（join/ready/leave）”主链路与异常恢复链路在真实 REST/WS 协议下可用。
> 依据文档：`memory-bank/tests/m7-tests.md`、`memory-bank/implementation-plan.md`（M7/M8）、`memory-bank/design/frontend_design.md`、`memory-bank/interfaces/frontend-backend-interfaces.md`。
> 口径声明：本文件是 M7 真实后端联调用例 ID 与执行记录来源（SSOT）。
> 当前状态：`M7-GATE-01~03`、`M7-RS-E2E-01~12` 已完成并通过。

## 0) 测试环境与执行约定（真实服务）

- 建议环境：
  - 后端：conda `XQB`
  - 前端：Node.js `22.x`
- 后端启动（推荐：测试模式，自动临时 sqlite 隔离）：
  - `XQWEB_APP_HOST=127.0.0.1`
  - `XQWEB_APP_PORT=18080`
  - `XQWEB_TEST_DB_DIR=/tmp/xqweb-test`（可选，默认该目录）
  - `XQWEB_TEST_KEEP_DB=1`（可选，调试时保留 sqlite）
  - `XQWEB_JWT_SECRET=<at-least-32-byte-secret>`
  - `bash scripts/start-backend-test.sh`
- 后端启动（兼容旧模式，固定 sqlite）：
  - `XQWEB_SQLITE_PATH=/tmp/xqweb-m7-real-service.sqlite3`
  - `bash scripts/start-backend.sh`
- 前端环境变量（`frontend/.env.test` 或命令行覆盖）：
  - `VITE_API_BASE_URL=http://127.0.0.1:18080`
  - `VITE_WS_BASE_URL=ws://127.0.0.1:18080`
- 前端 E2E 执行建议：
  - `cd frontend && npm run test:e2e -- --project=chromium`
- 账号与数据隔离约定：
  - 每次执行使用唯一前缀账号（如 `m7rs_a_001`）。
  - 使用 `start-backend-test.sh` 时每轮自动生成独立 sqlite，默认退出自动清理。

## 1) 进入收口前门禁（M7-GATE）

| 门禁ID | 场景 | 通过条件 |
|---|---|---|
| M7-GATE-01 | 后端基础能力可用 | `/api/auth/register`、`/api/auth/login`、`/api/rooms` 可成功响应，且 WS 连接可建立 |
| M7-GATE-02 | 前端本地 E2E 可启动 | Playwright 可启动 `frontend` 并成功访问 `/login` |
| M7-GATE-03 | M7 测试级闭环已完成 | `memory-bank/tests/m7-tests.md` 中 `M7-UT/CT/WS/E2E` 保持 Green |

## 2) 主流程与恢复用例映射（M7-RS-E2E-01~12）

| 测试ID | 场景 | 通过条件 | 目标测试函数（规划） |
|---|---|---|---|
| M7-RS-E2E-01 | 登录闭环（真实 REST） | 输入有效账号密码后进入 `/lobby`，且页面展示真实房间列表 | `test_m7_rs_e2e_01_login_to_lobby_with_real_backend` |
| M7-RS-E2E-02 | 注册并登录闭环（真实 REST） | 注册成功后直接进入 `/lobby`，刷新页面会话仍可恢复 | `test_m7_rs_e2e_02_register_then_login_and_hydrate` |
| M7-RS-E2E-03 | 登录失败提示 | 错误密码返回后端错误消息，页面停留 `/login` | `test_m7_rs_e2e_03_login_failure_message` |
| M7-RS-E2E-04 | 入房主流程 | 从大厅点击 join 后进入 `/rooms/{id}`，房间成员信息与后端一致 | `test_m7_rs_e2e_04_join_room_flow` |
| M7-RS-E2E-05 | ready 切换（真实 REST + ROOM_UPDATE） | 点击 ready 后房间 ready 计数实时更新，刷新后保持一致 | `test_m7_rs_e2e_05_ready_toggle_and_room_update` |
| M7-RS-E2E-06 | leave 主流程 | 房间内 leave 后返回 `/lobby`，大厅计数回落并与后端一致 | `test_m7_rs_e2e_06_leave_back_to_lobby` |
| M7-RS-E2E-07 | 大厅实时同步（双端） | A 端 join/leave/ready 时，B 端大厅 `ROOM_UPDATE` 计数同步变化 | `test_m7_rs_e2e_07_lobby_realtime_sync_multi_client` |
| M7-RS-E2E-08 | 房间实时同步（双端） | A 端 ready 切换后，B 端房间成员 ready 状态实时同步 | `test_m7_rs_e2e_08_room_realtime_sync_multi_client` |
| M7-RS-E2E-09 | token 过期自动 refresh | access 过期后用户无感恢复，停留受保护页面且请求成功重放 | `test_m7_rs_e2e_09_access_expire_refresh_and_replay` |
| M7-RS-E2E-10 | WS 断线重连 + 拉态兜底 | 主动断开房间 WS 后可自动恢复，重连后页面状态与后端一致 | `test_m7_rs_e2e_10_ws_reconnect_with_rest_resync` |
| M7-RS-E2E-11 | 服务端重启边界提示 | 后端重启后，前端出现“服务已重置，请重新入房”并引导回大厅 | `test_m7_rs_e2e_11_backend_restart_boundary_prompt` |
| M7-RS-E2E-12 | 冷结束提示 | 对局中成员离房触发 `playing -> waiting` 时，房间页显示“对局结束”提示 | `test_m7_rs_e2e_12_cold_end_message_on_playing_to_waiting` |

### 2.1) M7-RS-E2E-04~08 详细测试清单（本轮修复范围）

| 测试ID | 前置条件 | 操作步骤 | 通过条件 |
|---|---|---|---|
| M7-RS-E2E-04 | 账号注册并登录成功，位于 `/lobby` | 点击任一房间 `join` 按钮 | 页面跳转 `/rooms/{id}`；后端 `GET /api/rooms/{id}` 返回 `200`；`members` 中存在 `user_id == self_user_id` |
| M7-RS-E2E-05 | 用户已在 `/rooms/{id}` 且为成员 | 点击 `room-ready-toggle`；随后刷新页面 | ready 文案从 `ready 0/1` 变 `ready 1/1`（或按实际人数递增）；刷新后 ready 计数保持一致 |
| M7-RS-E2E-06 | 用户已加入某房间 | 在 `/rooms/{id}` 点击 `room-leave-button` | 页面回到 `/lobby`；后端 `/api/rooms` 对应房间 `player_count` 回落到离房前基线值 |
| M7-RS-E2E-07 | A/B 双端均登录并停留大厅 | A 端执行 join -> ready -> leave；B 端观察同一房间行 | B 端 `player_count` 与 `ready_count` 随 A 端动作实时变化并最终回到初始值 |
| M7-RS-E2E-08 | A/B 双端均已加入同一房间并停留房间页 | A 端点击 `room-ready-toggle` | B 端 `room-ready-count` 在轮询窗口内发生变化（可观测到实时同步） |

### 2.2) M7-RS-E2E-09~12 详细测试清单（本轮拉红范围）

| 测试ID | 前置条件 | 操作步骤 | 通过条件 |
|---|---|---|---|
| M7-RS-E2E-09 | 用户已登录并在 `/rooms/{id}`，本地会话含有效 `refresh_token` | 人为将本地 `access_token` 置为无效后触发受保护请求（如 `ready`） | 前端自动触发 refresh，原请求成功重放；页面停留在受保护页且状态更新成功 |
| M7-RS-E2E-10 | A/B 双端均已加入同一房间，A 端在房间页 | 主动中断 A 端房间 WS；B 端修改房态（如切 ready）；观察 A 端 | A 端自动重连 WS，并通过 REST 兜底拉态；最终与后端房态一致 |
| M7-RS-E2E-11 | 用户在 `/rooms/{id}`，服务端发生重启（内存态清空） | 重启后触发页面恢复路径（刷新或继续交互） | 前端出现“服务已重置，请重新入房”提示，并引导回 `/lobby` |
| M7-RS-E2E-12 | 三名玩家已在同房并开局（`status=playing`） | 其中一名玩家离房触发冷结束；观察其余玩家房间页 | 其余玩家收到 `playing -> waiting`，并出现“对局结束”提示 |

### 2.3) M7 E2E 稳定性收敛（workers=1）

| 测试ID | 前置条件 | 操作步骤 | 通过条件 |
|---|---|---|---|
| M7-RS-STAB-01 | 使用真实后端执行 `npm run test:e2e`，Playwright 允许并行 worker | 运行全量 E2E 并观察 `M7-RS-E2E-07` | 可复现偶发失败：`Expected "0/0"`、`Received "2/0"`，定位为跨用例共享房间状态污染 |
| M7-RS-STAB-02 | `frontend/playwright.config.ts` 已设置 `workers=1` | 每轮使用全新 `scripts/start-backend-test.sh`，执行 `cd frontend && npm run test:e2e -- --project=chromium` | 连续 2 轮全量 E2E 均通过（`17 passed`），且 `M7-RS-E2E-07` 通过 |

## 3) 收口通过标准（M7 Exit Criteria, Real Backend）

- `M7-GATE-01~03` 全部通过。
- `M7-RS-E2E-01~12` 全部通过。
- 关键语义满足：
  - 鉴权链路正确：登录、刷新、登出与受保护路由行为一致。
  - 房态同步正确：大厅与房间的成员数、ready 数、状态流转一致。
  - 恢复链路正确：token 过期、WS 断线、服务重启三类异常可恢复或可提示。
- 执行稳定性要求：同一环境连续执行 2 轮，无随机失败。

## 4) TDD 执行记录

> 约定：按“人类指定测试 ID -> 编写测试 -> 执行 Red/Green”推进；每条用例先记录 Red，再记录 Green。

| 测试ID | 当前状态 | TDD阶段 | 执行日期 | 备注 |
|---|---|---|---|---|
| M7-GATE-01 | ✅ Green通过 | Red→Green 完成 | 2026-03-01 | 新增 `backend/tests/integration/real_service/test_m7_rs_gate_01_red.py`；首轮 Red：用户名测试数据超长触发 `400`；修正后执行 `pytest -q backend/tests/integration/real_service/test_m7_rs_gate_01_red.py`，结果 `1 passed`。 |
| M7-GATE-02 | ✅ Green通过 | Green完成 | 2026-03-01 | 新增 `frontend/tests/e2e/m7-gate-02.spec.ts`；执行 `cd frontend && npm run test:e2e -- --project=chromium tests/e2e/m7-gate-02.spec.ts`，结果 `1 passed`。 |
| M7-GATE-03 | ✅ Green通过 | Green完成 | 2026-03-01 | 新增 `frontend/tests/unit/m7-gate-03.test.ts` 校验 `m7-tests.md` 中 `M7-UT/CT/WS/E2E` 为 Green；执行 `cd frontend && npm run test -- --run tests/unit/m7-gate-03.test.ts`，结果 `1 passed`。 |
| M7-RS-E2E-01 | ✅ Green通过 | Red→Green 完成 | 2026-03-01 | 新增 `frontend/tests/e2e/m7-rs-e2e-01-03.spec.ts`；首轮 Red：执行 `cd frontend && npm run test:e2e -- --project=chromium tests/e2e/m7-rs-e2e-01-03.spec.ts` 结果 `3 failed`（前端仍为测试桩，且跨域预检 `OPTIONS` 405）；补齐真实 API 接线（`auth-api`/`rooms-api`/`main`/`LobbyPage`）并增加 Vite 代理后复测，结果 `3 passed`。 |
| M7-RS-E2E-02 | ✅ Green通过 | Red→Green 完成 | 2026-03-01 | 同上，覆盖注册并登录后进入大厅、刷新后会话恢复。 |
| M7-RS-E2E-03 | ✅ Green通过 | Red→Green 完成 | 2026-03-01 | 同上，覆盖错误密码返回后端错误消息并停留 `/login`。 |
| M7-RS-E2E-04 | ✅ Green通过 | Red→Green 完成 | 2026-03-01 | 先前 Red 失败点：入房后后端 `room_detail.members` 未含当前用户；补齐前端真实 `/join` 调用与房间页真实拉态后，执行 `cd frontend && npm run test:e2e -- --project=chromium tests/e2e/m7-rs-e2e-04-08.spec.ts`，该用例通过。 |
| M7-RS-E2E-05 | ✅ Green通过 | Red→Green 完成 | 2026-03-01 | 先前 Red 失败点：点击 ready 后 `room-ready-count` 保持 `0/1`；修复房间页真实 `/ready` 调用、房间 WS `ROOM_UPDATE` 接线与房间 store 响应式更新后，在同批次执行中通过。 |
| M7-RS-E2E-06 | ✅ Green通过 | Red→Green 完成 | 2026-03-01 | 先前 Red 失败点：leave 后后端 `player_count` 未回落；补齐房间页真实 `/leave` 调用并回大厅后，在同批次执行中通过。 |
| M7-RS-E2E-07 | ✅ Green通过 | Red→Green 完成 | 2026-03-01 | 先前 Red 失败点：大厅双端计数未同步；补齐大厅 `/ws/lobby` 订阅与 `ROOM_LIST/ROOM_UPDATE` 应用后，在同批次执行中通过。 |
| M7-RS-E2E-08 | ✅ Green通过 | Red→Green 完成 | 2026-03-01 | 先前 Red 失败点：房间双端 ready 状态未同步；补齐房间 `/ws/rooms/{id}` 订阅与 `ROOM_UPDATE` 应用后，在同批次执行中通过。 |
| M7-RS-E2E-09 | ✅ Green通过 | Red→Green 完成 | 2026-03-02 | 修复前端 `rooms-api` 401 自动 refresh + 原请求重放链路（接入统一 HTTP 拦截器）；在全新测试后端实例执行 `cd frontend && npm run test:e2e -- --project=chromium --workers=1 --grep "M7-RS-E2E-09" tests/e2e/m7-rs-e2e-09-12.spec.ts`，结果 `4 passed`（同批次含 `09~12`）。 |
| M7-RS-E2E-10 | ✅ Green通过 | Red→Green 完成 | 2026-03-02 | 修复房间 WS 自动重连，并在重连开链后追加 REST 房态拉取兜底；同批次执行结果 `4 passed`，A 端在断链后可恢复并与后端房态一致。 |
| M7-RS-E2E-11 | ✅ Green通过 | Red→Green 完成 | 2026-03-02 | 修复房间上下文失效边界（成员不在房间/房间状态失效）统一引导回大厅，并展示“服务已重置，请重新入房”提示（含跨刷新 notice 保留）；同批次执行结果 `4 passed`。 |
| M7-RS-E2E-12 | ✅ Green通过 | Red 已执行（意外全绿） | 2026-03-02 | 执行 `cd frontend && npm run test:e2e -- --project=chromium --workers=1 --grep "M7-RS-E2E-12" tests/e2e/m7-rs-e2e-09-12.spec.ts`，结果 `1 passed`；现有实现已可在 `playing -> waiting` 时展示“对局结束”提示。 |
| M7-RS-STAB-01 | ✅ Green通过 | Red→Green 完成 | 2026-03-02 | Red 现象来自全量 E2E 偶发失败日志：`M7-RS-E2E-07` 在离房后断言超时，期望 `0/0` 实际为 `2/0`；定位为并行 worker 下共享后端房间状态导致的跨用例污染。Green 修复：`frontend/playwright.config.ts` 固定 `workers=1`。 |
| M7-RS-STAB-02 | ✅ Green通过 | Green完成 | 2026-03-02 | 以“每轮全新后端实例”回归 2 轮：`cd frontend && npm run test:e2e -- --project=chromium`，两轮均 `17 passed`；其中 `M7-RS-E2E-07` 稳定通过。 |
