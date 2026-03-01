# M7 阶段真实后端收口联调测试清单（Frontend Non-game + Real Backend）

> 目标：在真实启动的后端服务上完成 M7 非对局前端收口，验证“登录 -> 大厅 -> 房间（join/ready/leave）”主链路与异常恢复链路在真实 REST/WS 协议下可用。
> 依据文档：`memory-bank/tests/m7-tests.md`、`memory-bank/implementation-plan.md`（M7/M8）、`memory-bank/design/frontend_design.md`、`memory-bank/interfaces/frontend-backend-interfaces.md`。
> 口径声明：本文件是 M7 真实后端联调用例 ID 与执行记录来源（SSOT）。
> 当前状态：`M7-GATE-01~03`、`M7-RS-E2E-01~03` 已完成并通过；`M7-RS-E2E-04~12` 待执行。

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
| M7-RS-E2E-04 | ⏳ 待执行 | 待启动 | - | 待人类指定 |
| M7-RS-E2E-05 | ⏳ 待执行 | 待启动 | - | 待人类指定 |
| M7-RS-E2E-06 | ⏳ 待执行 | 待启动 | - | 待人类指定 |
| M7-RS-E2E-07 | ⏳ 待执行 | 待启动 | - | 待人类指定 |
| M7-RS-E2E-08 | ⏳ 待执行 | 待启动 | - | 待人类指定 |
| M7-RS-E2E-09 | ⏳ 待执行 | 待启动 | - | 待人类指定 |
| M7-RS-E2E-10 | ⏳ 待执行 | 待启动 | - | 待人类指定 |
| M7-RS-E2E-11 | ⏳ 待执行 | 待启动 | - | 待人类指定 |
| M7-RS-E2E-12 | ⏳ 待执行 | 待启动 | - | 待人类指定 |
