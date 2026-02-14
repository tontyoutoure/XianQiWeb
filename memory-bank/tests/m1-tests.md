# M1 阶段测试列表（后端基础与鉴权）

> 依据文档：`memory-bank/implementation-plan.md`（M1）、`memory-bank/interfaces/frontend-backend-interfaces.md`（Auth/WS）、`memory-bank/design/backend_design.md`（1.9 M1 测试设计）。

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
| M1-API-01 | `POST /api/auth/register` 成功返回登录态 | `{"username":"Alice","password":"123"}` | `200`；返回 `access_token/refresh_token/expires_in/refresh_expires_in/user` |
| M1-API-02 | username 重复（含 NFC 等价）返回冲突 | 先注册 `"é"`，再注册 `"é"` | 第二次 `409`（用户名冲突） |
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
