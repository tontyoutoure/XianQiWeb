# M1 阶段真实服务联调测试清单（REST + WS）

> 目标：将后端服务真实拉起（非 TestClient/非函数直调），通过 HTTP/WS 黑盒交互验证 M1 接口可用性与契约一致性。  
> 依据文档：`memory-bank/implementation-plan.md`（M1）、`memory-bank/interfaces/frontend-backend-interfaces.md`（Auth/WS）、`memory-bank/design/backend_design.md`（1.9 M1 测试设计）。

## 0) 测试环境与约定

- 建议环境：conda `XQB`。
- 服务启动（示例）：
  - `XQWEB_JWT_SECRET=<test-secret>`（必填）
  - `XQWEB_SQLITE_PATH=/tmp/xqweb-m1-real-service.sqlite3`（建议独立测试库）
  - `conda run -n XQB bash scripts/start-backend.sh`
  - 可选：`XQWEB_APP_PORT=18080`、`XQWEB_RELOAD=1` 覆盖端口与热重载。
- 基础地址：`BASE_URL=http://127.0.0.1:18080`
- WS 地址：
  - `ws://127.0.0.1:18080/ws/lobby?token=<access_token>`
  - `ws://127.0.0.1:18080/ws/rooms/0?token=<access_token>`
- 响应校验口径：
  - 成功响应字段符合接口文档。
  - 失败响应统一为 `{code,message,detail}`。
  - REST 未授权状态码为 `401`。
  - WS 未授权关闭码 `4401`，reason=`UNAUTHORIZED`。
- 代理环境注意事项（本次联调已踩坑）：
  - 若本机设置了 `HTTP_PROXY/HTTPS_PROXY`，访问 `127.0.0.1` 可能被代理劫持并返回 `502 Bad Gateway`。
  - 本地健康检查建议使用：`curl --noproxy '*' -i http://127.0.0.1:18080/api/auth/me`（预期 `401`）。
  - 自动化脚本（如 `httpx`）应显式设置 `trust_env=False`，避免读取代理环境变量。

## 1) REST 接口可用性测试

| 测试ID | 场景 | 步骤（真实服务交互） | 预期结果 |
|---|---|---|---|
| M1-RS-REST-01 | register 成功 | `POST /api/auth/register`，body=`{"username":"Alice","password":"123"}` | `200`；返回 `access_token/refresh_token/expires_in/refresh_expires_in/user` |
| M1-RS-REST-02 | register 重复用户名冲突（NFC 等价） | 先注册 `"é"`，再注册 `"é"` | 第二次 `409`；错误体结构正确 |
| M1-RS-REST-03 | username 大小写敏感 | 注册 `"Tom"` 与 `"tom"` | 两次均 `200`，用户不同 |
| M1-RS-REST-04 | 空密码可注册/登录（MVP） | 注册并登录 `{"username":"NoPwd","password":""}` | 注册 `200`，登录 `200` |
| M1-RS-REST-05 | login 成功 | 对已注册用户调用 `POST /api/auth/login` | `200`；返回新的 token 对 |
| M1-RS-REST-06 | login 失败统一 401 | 错误用户名或错误密码登录 | `401`；错误体结构正确 |
| M1-RS-REST-07 | me 成功 | 带 `Authorization: Bearer <valid_access_token>` 调 `GET /api/auth/me` | `200`；返回当前用户信息 |
| M1-RS-REST-08 | me 未授权（缺失/伪造 token） | 不带 token 或带伪造 token 调 `GET /api/auth/me` | `401` |
| M1-RS-REST-09 | me 未授权（过期 token） | 使用已过期 access token 调 `GET /api/auth/me` | `401` |
| M1-RS-REST-10 | refresh 轮换成功 | 用有效 refresh 调 `POST /api/auth/refresh` | `200`；返回新 access+refresh；旧 refresh 后续不可用 |
| M1-RS-REST-11 | refresh 拒绝无效/撤销/随机 token | 分别提交无效、已撤销、随机 refresh token | 全部 `401` |
| M1-RS-REST-12 | logout 幂等 + 撤销生效 | 对同一 refresh token 连续两次 `POST /api/auth/logout` | 两次均 `200`+`{"ok":true}`；该 refresh 再 `refresh` 返回 `401` |
| M1-RS-REST-13 | 登录踢旧登录策略 | 同用户连续两次 login，记录旧/新 refresh 与旧 access | 旧 refresh 失效、新 refresh 可用；旧 access 过期前仍可调用 `/me` |

## 2) WS 接口可用性测试

| 测试ID | 场景 | 步骤（真实服务交互） | 预期结果 |
|---|---|---|---|
| M1-RS-WS-01 | `/ws/lobby` 有效 token 可连 | 使用有效 access token 建连 `/ws/lobby` | 连接成功，不被 4401 关闭 |
| M1-RS-WS-02 | `/ws/rooms/{room_id}` 有效 token 可连 | 使用有效 access token 建连 `/ws/rooms/0` | 连接成功，不被 4401 关闭 |
| M1-RS-WS-03 | lobby 无 token 拒绝 | 建连 `/ws/lobby`（不带 token） | 连接被关闭：`4401/UNAUTHORIZED` |
| M1-RS-WS-04 | lobby 无效 token 拒绝 | 建连 `/ws/lobby?token=invalid` | 连接被关闭：`4401/UNAUTHORIZED` |
| M1-RS-WS-05 | lobby 过期 token 拒绝 | 使用过期 access token 建连 `/ws/lobby` | 连接被关闭：`4401/UNAUTHORIZED` |
| M1-RS-WS-06 | room 无效/过期 token 拒绝 | 以无效或过期 token 建连 `/ws/rooms/0` | 连接被关闭：`4401/UNAUTHORIZED` |

## 3) REST 与 WS 联动验证

| 测试ID | 场景 | 步骤（真实服务交互） | 预期结果 |
|---|---|---|---|
| M1-RS-E2E-01 | REST 登录产物可用于 WS | register/login 拿 access token 后连接 lobby 与 room WS | 两条 WS 都可建连 |
| M1-RS-E2E-02 | refresh 后 token 切换对 WS 生效 | refresh 前后分别使用旧/新 access token 连 WS | 新 access 可连；旧 access 到期后应被拒绝 |
| M1-RS-E2E-03 | logout 仅影响 refresh，不立即失效 access | logout 后立即用原 access 调 `/me` 与连 WS | 在 access 未过期前仍可用；refresh 已不可用 |

## 4) 执行记录（TDD 红绿循环）

> 约定：每条测试在“红阶段”先验证失败或缺陷，再进入“绿阶段”修复并回归。  
> 该文档记录真实服务测试执行结果；`memory-bank/progress.md` 仅记录里程碑级结论。

| 测试ID | 当前状态 | TDD阶段 | 执行日期 | 备注 |
|---|---|---|---|---|
| M1-RS-REST-01 | ✅ 已通过 | Red（实测通过） | 2026-02-14 | 人类执行 `pytest backend/tests/integration/real_service/test_m1_rs_rest_red.py -q` 通过 |
| M1-RS-REST-02 | ✅ 已通过 | Red（实测通过） | 2026-02-14 | 人类执行 `pytest backend/tests/integration/real_service/test_m1_rs_rest_red.py -q` 通过 |
| M1-RS-REST-03 | ✅ 已通过 | Red（实测通过） | 2026-02-14 | 人类执行 `pytest backend/tests/integration/real_service/test_m1_rs_rest_red.py -q` 通过 |
| M1-RS-REST-04 | ✅ 已通过 | Red（实测通过） | 2026-02-14 | 人类执行 `pytest backend/tests/integration/real_service/test_m1_rs_rest_red.py -q` 通过 |
| M1-RS-REST-05 | ✅ 已通过 | Red（实测通过） | 2026-02-14 | 人类执行 `pytest backend/tests/integration/real_service/test_m1_rs_rest_red.py -q` 通过 |
| M1-RS-REST-06 | ⏳ 待执行 | 未开始 | - | - |
| M1-RS-REST-07 | ⏳ 待执行 | 未开始 | - | - |
| M1-RS-REST-08 | ⏳ 待执行 | 未开始 | - | - |
| M1-RS-REST-09 | ⏳ 待执行 | 未开始 | - | - |
| M1-RS-REST-10 | ⏳ 待执行 | 未开始 | - | - |
| M1-RS-REST-11 | ⏳ 待执行 | 未开始 | - | - |
| M1-RS-REST-12 | ⏳ 待执行 | 未开始 | - | - |
| M1-RS-REST-13 | ⏳ 待执行 | 未开始 | - | - |
| M1-RS-WS-01 | ⏳ 待执行 | 未开始 | - | - |
| M1-RS-WS-02 | ⏳ 待执行 | 未开始 | - | - |
| M1-RS-WS-03 | ⏳ 待执行 | 未开始 | - | - |
| M1-RS-WS-04 | ⏳ 待执行 | 未开始 | - | - |
| M1-RS-WS-05 | ⏳ 待执行 | 未开始 | - | - |
| M1-RS-WS-06 | ⏳ 待执行 | 未开始 | - | - |
| M1-RS-E2E-01 | ⏳ 待执行 | 未开始 | - | - |
| M1-RS-E2E-02 | ⏳ 待执行 | 未开始 | - | - |
| M1-RS-E2E-03 | ⏳ 待执行 | 未开始 | - | - |
