# M1 阶段测试列表（后端基础与鉴权）

> 依据文档：`memory-bank/implementation-plan.md`（M1）、`memory-bank/interfaces/frontend-backend-interfaces.md`（Auth/WS）、`memory-bank/design/backend_design.md`（1.9 M1 测试设计）。
> 本地执行环境约定：使用 conda 环境 `XQB`（例如：`conda run -n XQB pytest ...`）。
> 红绿循环的进度更新在本文档，不要更新进progress.md，后者仅记录阶段性里程碑完成情况。

## 1) 单元测试（服务与数据层）

| 测试ID | 对应约定 | 预期输入 | 预期输出 |
|---|---|---|---|
| M1-UT-01 | 密码使用 `bcrypt` 哈希；MVP 允许空密码 | 明文密码（如 `"abc"`、`""`）进行哈希与校验 | 哈希值不等于明文；同明文校验通过；错误明文校验失败 |
| M1-UT-02 | Access Token 为 JWT，至少包含 `sub/exp` | 为 user_id=1 签发 access token，并在有效期内/过期后分别校验 | 有效期内校验通过且可取到 `sub=1`；过期后返回 token 过期错误 |
| M1-UT-03 | refresh token 仅存 `token_hash`，refresh 轮换时旧 token 失效 | 创建 refresh token 后执行一次 rotate | 旧 token 写入 `revoked_at` 且不可再用；返回新 refresh token 且可用 |
| M1-UT-04 | SQLite 连接必须 `PRAGMA foreign_keys=ON` | 向 `refresh_tokens` 插入不存在的 `user_id` | 插入失败（外键约束生效） |
| M1-UT-05 | username 处理规则：`trim + NFC`，长度 1-10 个用户可见字符 | 输入 `" é "`、`"é"`、超过 10 个 grapheme 的用户名 | 前两者归一后等价；超长用户名被拒绝（校验错误） |
| M1-UT-06 | 配置约束：`XQWEB_ACCESS_TOKEN_REFRESH_INTERVAL_SECONDS < XQWEB_ACCESS_TOKEN_EXPIRE_SECONDS` | 构造 refresh interval >= access expire 的配置 | 应用启动配置校验失败 |

## 2) API 测试（Auth 闭环）

| 测试ID | 对应约定 | 预期输入 | 预期输出 |
|---|---|---|---|
| M1-API-01 | `POST /api/auth/register` 成功返回登录态并落库 | `{"username":"Alice","password":"123"}` | `200`；返回 `access_token/refresh_token/expires_in/refresh_expires_in/user`；`users` 新增用户且 `refresh_tokens` 新增一条未撤销记录（仅存 `token_hash`） |
| M1-API-02 | username 重复（含 NFC 等价）返回冲突 | 先注册 `"é"`，再注册 `"é"` | 第二次 `409`（用户名冲突）；错误体结构为 `{code,message,detail}` |
| M1-API-03 | username 大小写敏感 | 依次注册 `"Tom"`、`"tom"` | 两次都成功，且为不同用户 |
| M1-API-04 | MVP 允许空密码注册/登录 | 注册与登录都使用 `password=""` | 注册成功且登录成功 |
| M1-API-05 | `POST /api/auth/login` 账号/密码正确可登录 | 已注册用户使用正确密码登录 | `200`；返回新的 token 对与 user |
| M1-API-06 | 登录失败统一 401（不区分账号不存在/密码错误） | 错误用户名或错误密码登录 | `401`；错误结构符合 `{code,message,detail}` |
| M1-API-07 | `GET /api/auth/me` 需 Bearer access token | 携带有效 access token 调用 `/me` | `200`；返回当前用户 `id/username/created_at` |
| M1-API-08 | `/me` 对无效/缺失 token 返回未授权 | 不带 token 或带伪造/过期 token 调用 `/me` | `401` |
| M1-API-09 | `POST /api/auth/refresh` 成功后 refresh 轮换 | 传入有效 refresh token 调用 `/refresh` | `200`；返回新 access+refresh；旧 refresh 立即失效 |
| M1-API-10 | 失效 refresh token 不可复用 | 使用已撤销/已过期/随机 refresh token 调用 `/refresh` | `401` |
| M1-API-11 | `POST /api/auth/logout` 撤销指定 refresh token，且幂等 | 对同一 refresh token 连续调用两次 `/logout` | 两次都返回 `200` + `{"ok":true}`；该 refresh 后续 refresh 调用 `401` |
| M1-API-12 | 登录踢旧登录策略 | 同用户连续两次登录，拿到旧/新 token 对 | 旧 refresh 失效；新 refresh 可用；旧 access 在自身过期前仍可访问 `/me` |

## 3) WebSocket 鉴权测试

| 测试ID | 对应约定 | 预期输入 | 预期输出 |
|---|---|---|---|
| M1-WS-01 | WS 使用 access token 鉴权 | 连接 `/ws/lobby?token=<valid_access_token>`（或房间 WS） | 连接建立成功（不被 4401 关闭） |
| M1-WS-02 | WS 鉴权失败需关闭连接 | 使用无效 token 连接 WS | 连接被关闭，close code=`4401`，reason=`UNAUTHORIZED` |
| M1-WS-03 | 过期 access token 不允许建立 WS | 使用过期 token 连接 WS | 连接被关闭，close code=`4401` |

## 4) 测试通过判定（M1 完成标准）

- Auth 五接口闭环通过：`register -> login -> me -> refresh -> logout`。
- refresh 轮换与撤销行为符合约定：旧 refresh 不可复用。
- REST/WS 未授权行为一致：REST 返回 `401`，WS 关闭码 `4401`。
- 用户名规则（trim/NFC/长度/大小写敏感）与空密码口径与文档一致。

## 5) TDD 执行进度（2026-02-14）

### 5.1 单元测试（UT）

| 测试ID | 当前状态 | TDD阶段 | 备注 |
|---|---|---|---|
| M1-UT-01 | ✅ 已通过 | Red → Green 完成 | `hash_password/verify_password` 已实现，测试 4 项通过 |
| M1-UT-02 | ✅ 已通过 | Red → Green 完成 | `create_access_token/decode_access_token` 已实现，覆盖 `sub/exp` 与过期 |
| M1-UT-03 | ✅ 已通过 | Red → Green 完成 | `RefreshTokenStore issue/validate/rotate` 已实现，旧 token 失效 |
| M1-UT-04 | ✅ 已通过 | Red → Green 完成 | `create_sqlite_connection` 强制 `PRAGMA foreign_keys=ON` |
| M1-UT-05 | ✅ 已通过 | Red → Green 完成 | username `trim + NFC + grapheme(1~10)` 已实现 |
| M1-UT-06 | ✅ 已通过 | Red → Green 完成 | 新增 `app.core.config.Settings` 与约束校验：`refresh_interval < access_expire` |

当前单测汇总（`backend/tests/unit`）：`14 passed`。

### 5.2 API / WS 测试

| 测试组 | 当前状态 | 备注 |
|---|---|---|
| M1-API-01 | ✅ 已通过 | 已实现最小注册链路（`app.main` + register）；断言覆盖响应字段与 `users/refresh_tokens` 落库（`token_hash` 非明文） |
| M1-API-02 | ✅ 已通过 | 新增统一 HTTP 错误处理后，NFC 等价重复注册返回 `409` 且错误体满足 `{code,message,detail}` |
| M1-API-03 | ✅ 已通过 | 绿阶段完成：`Tom/tom` 可分别注册且落库为不同用户；`conda run -n XQB pytest backend/tests/api/auth/test_m1_api_03_case_sensitive.py -q` 通过 |
| M1-API-04 | ✅ 已通过 | 绿阶段完成：新增 `LoginRequest/login` 后空密码注册+登录通过；`conda run -n XQB pytest backend/tests/api/auth/test_m1_api_04_empty_password.py -q` 通过 |
| M1-API-05 | ✅ 已通过 | 红绿完成：新增登录成功契约测试并验证“fresh token 对”；通过在 access token 中加入 `jti` 保证同秒重复签发也不同；`conda run -n XQB pytest backend/tests/api/auth/test_m1_api_05_login_success.py -q` 通过 |
| M1-API-06 | ✅ 已通过 | 红测意外通过后，经人类确认直接认定绿阶段完成；`conda run -n XQB pytest backend/tests/api/auth/test_m1_api_06_login_failure.py -q` 结果 `1 passed` |
| M1-API-07 | ✅ 已通过 | 绿阶段完成：实现 `me`/`GET /api/auth/me` 与 access token 校验链路；`conda run -n XQB pytest backend/tests/api/auth/test_m1_api_07_me_success.py -q` 通过 |
| M1-API-08 | ✅ 已通过 | 红阶段新增了缺失/伪造/过期 access token 三类 401 断言；红测意外通过（当前 `me` 鉴权链路已满足契约） |
| M1-API-09 | ✅ 已通过 | 绿阶段完成：实现 `RefreshRequest`、`refresh_user` 与 `/api/auth/refresh`；`conda run -n XQB pytest backend/tests/api/auth/test_m1_api_09_refresh_rotate.py -q` 通过 |
| M1-API-10 | ✅ 已通过 | 绿阶段完成：实现 refresh token 校验（已撤销/已过期/随机均拒绝）；`conda run -n XQB pytest backend/tests/api/auth/test_m1_api_10_refresh_invalid.py -q` 通过 |
| M1-API-11 | ✅ 已通过 | 绿阶段完成：实现 `LogoutRequest`、`logout_user` 与 `/api/auth/logout` 幂等撤销；`conda run -n XQB pytest backend/tests/api/auth/test_m1_api_11_logout_idempotent.py -q` 通过 |
| M1-API-12 | ✅ 已通过 | 绿阶段完成：实现登录踢旧 refresh（register/login 撤销历史 refresh）；`conda run -n XQB pytest backend/tests/api/auth/test_m1_api_12_login_kick_old_session.py -q` 通过 |
| M1-WS-01 | ✅ 已通过 | 绿阶段完成：实现 `/ws/lobby` 鉴权入口；有效 access token 可通过鉴权并建立连接路径；`conda run -n XQB pytest backend/tests/integration/ws/test_ws_auth.py -q` 通过 |
| M1-WS-02 | ✅ 已通过 | 绿阶段完成：无效 token 鉴权失败时关闭码为 `4401`，reason=`UNAUTHORIZED`；WS 用例通过 |
| M1-WS-03 | ✅ 已通过 | 绿阶段完成：过期 token 鉴权失败时关闭码为 `4401`；WS 用例通过 |

### 5.3 下一步建议

下一步建议执行一次 M1 阶段验收回归（Auth API + WS 鉴权），确认闭环后进入 M2 房间大厅阶段的红测设计。
