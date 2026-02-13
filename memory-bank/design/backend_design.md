# 后端详细设计文档

本文档用于沉淀后端实现层面的详细设计，作为 `memory-bank/architecture.md` 与接口文档的实现补充。

## 0. 文档范围与基线
- 当前版本覆盖：M1（后端基础与鉴权）、M2（房间与大厅）。
- 一致性基线：
  - `memory-bank/architecture.md`
  - `memory-bank/interfaces/frontend-backend-interfaces.md`
  - `memory-bank/interfaces/backend-engine-interface.md`
- 安全基线（MVP）：安全性保持基础可用，重点保障鉴权正确与服务稳定；对用户恶意行为暂不做强对抗防护（如复杂风控、反刷、设备指纹、行为审计）。
- 非目标：M3+ 的引擎规则、结算细节与前端实现（仅做接口预留，不做实现展开）。

## 1. M1 后端基础与鉴权设计

### 1.1 目标
- 建立可运行的 FastAPI 服务骨架。
- 完成 `users + refresh_tokens` 持久化模型。
- 完成 Access/Refresh 双 token 鉴权闭环（REST + WS）。

### 1.2 后端目录建议
```text
backend/
  app/
    main.py
    core/
      config.py
      security.py
      logging.py
      errors.py
      db.py
    models/
      user.py
      refresh_token.py
    repositories/
      user_repo.py
      refresh_token_repo.py
    schemas/
      auth.py
      common.py
    services/
      auth_service.py
      token_service.py
    api/
      deps.py
      auth.py
      rooms.py
      games.py
    ws/
      auth.py
      manager.py
  tests/
    auth/
```

### 1.3 配置与环境变量
- 命名空间约定：后端环境变量统一使用 `XQWEB_` 前缀，避免污染系统级命名空间。
- `XQWEB_APP_ENV`：`dev|test|prod`
- `XQWEB_APP_HOST` / `XQWEB_APP_PORT`
- `XQWEB_JWT_SECRET`：Access token 签名密钥。
- `XQWEB_ACCESS_TOKEN_EXPIRE_SECONDS`：默认 3600。
- `XQWEB_REFRESH_TOKEN_EXPIRE_SECONDS`：默认 7776000（90 天）。
- `XQWEB_SQLITE_PATH`：SQLite 文件路径。
- `XQWEB_CORS_ALLOW_ORIGINS`：前端域名白名单。
- `XQWEB_PRESET_ROOM_IDS`：预设房间编号列表（如 `1,2,3,4,5`）。

本地开发/测试约定（无 Docker）：
- 使用项目内 env 文件，不在 shell profile（如 `~/.bashrc`）做全局 `export`。
- 开发环境使用 `.env.dev`。
- 测试环境使用 `.env.test`（与开发隔离，避免误连开发库）。
- 由应用启动参数或测试初始化逻辑按需加载对应 env 文件。
- 配置加载策略：`pydantic-settings` 负责解析与校验；启动命令显式指定 env 文件（开发 `.env.dev`，测试 `.env.test`）。

约束：
- 所有时间使用 UTC。
- secret 缺失时服务启动失败。

### 1.4 数据库设计（SQLite）

#### users
- `id INTEGER PRIMARY KEY`
- `username TEXT NOT NULL UNIQUE`
- `password_hash TEXT NOT NULL`
- `created_at TEXT NOT NULL`（ISO 8601 UTC）

#### refresh_tokens
- `id INTEGER PRIMARY KEY`
- `user_id INTEGER NOT NULL`
- `token_hash TEXT NOT NULL UNIQUE`
- `expires_at TEXT NOT NULL`
- `created_at TEXT NOT NULL`
- `revoked_at TEXT NULL`
- FK：`user_id -> users.id`

索引建议：
- `idx_refresh_tokens_user_id (user_id)`
- `idx_refresh_tokens_expires_at (expires_at)`

### 1.5 安全与鉴权策略
- 密码哈希：`bcrypt`（或 `passlib[bcrypt]`）。
- Access token：JWT，payload 至少含 `sub(user_id)`、`exp`。
- Refresh token：随机高熵字符串，仅存 `token_hash`，不明文落库。
- 会话策略（MVP）：
  - 单账号单活跃会话（以 refresh token 为准）。
  - 每次 `register/login` 成功后，撤销该用户历史全部 refresh token，再签发新 token 对。
  - 旧端 access token 不做立即失效处理，可使用到自身 `exp` 到期（默认 1 小时）。
- Refresh 轮换：
  1. 校验旧 refresh token（存在、未撤销、未过期）。
  2. 旧 token 立即写 `revoked_at`。
  3. 新建 refresh token 记录并返回。
- Logout：撤销指定 refresh token（幂等）。

### 1.6 认证接口实现细节

#### POST `/api/auth/register`
- 输入：`username/password`
- 规则：
  - username 去前后空格，长度建议 3-24。
  - password 最小长度建议 8。
  - username 重复返回 409。
- 输出：登录态（access + refresh + user）。

#### POST `/api/auth/login`
- 使用 username + password 验证。
- 密码错误返回 401（不区分账号不存在/密码错误）。
- 登录成功后撤销该用户历史 refresh token（踢掉旧登录）。
- 输出：登录态（与 register 一致）。

#### GET `/api/auth/me`
- Bearer access token。
- 输出当前用户基础信息。

#### POST `/api/auth/refresh`
- 输入：`refresh_token`。
- 成功：返回新 access + 新 refresh。
- 失败：401（无效、过期、已撤销）。

#### POST `/api/auth/logout`
- 输入：`refresh_token`。
- 成功：`{"ok": true}`。
- 仅注销当前 refresh token，不影响同用户其他会话（若未来支持多会话）。
- 不存在或已撤销按幂等处理，仍可返回成功。

### 1.6.1 Refresh Token 清理任务（运行策略）
- 目标：控制 `refresh_tokens` 体量，避免长期增长。
- 清理范围：仅删除“已过期”或“已撤销”的 refresh token 记录；不删除未过期且未撤销记录。
- 执行时机：
  - 服务启动时执行一次清理。
  - 每天 00:00 再执行一次定时清理（默认按服务器本地时区）。
- 安全性：不会导致当前有效会话失效；被清理记录本身已不可用于 refresh。

### 1.7 鉴权依赖与中间件
- REST：统一 `get_current_user()` 依赖，解析 Bearer JWT。
- WS：在连接阶段读取 query `token` 并校验 access token。
- WS 鉴权失败：直接关闭，code `4401`，reason `UNAUTHORIZED`。

### 1.8 错误响应与日志
- 统一错误结构：`{"code":"", "message":"", "detail":{}}`。
- 典型 code：
  - `AUTH_INVALID_CREDENTIALS`
  - `AUTH_TOKEN_EXPIRED`
  - `AUTH_TOKEN_INVALID`
  - `AUTH_REFRESH_REVOKED`
  - `VALIDATION_ERROR`
- 结构化日志字段：`request_id`, `user_id`, `path`, `status_code`, `latency_ms`。

### 1.9 M1 测试设计
- 测试配置：默认加载 `.env.test`，禁止复用 `.env.dev` 的数据库与密钥。
- 单元测试：
  - 密码哈希/校验。
  - JWT 签发与过期。
  - refresh 轮换时旧 token 失效。
- API 测试：
  - register/login/me/refresh/logout 正常流。
  - 非法 token、过期 token、重复注册、错误密码。
- 集成测试：
  - WS token 鉴权成功/失败。

## 2. M2 房间与大厅设计

### 2.1 目标
- 实现预设房间模型与成员管理。
- 完成大厅列表与房间详情接口。
- 完成 ready 流程与房态流转。
- 实现中途离房冷结束策略。

### 2.2 内存域模型

#### Room
- `room_id: int`
- `status: waiting|playing|settlement`
- `owner_id: int|null`
- `members: list[RoomMember]`
- `current_game_id: int|null`
- `created_at/updated_at`

#### RoomMember
- `user_id: int`
- `seat: 0|1|2`
- `ready: bool`
- `chips: int`（MVP 初始 20，可为负）
- `joined_at`

#### RoomRegistry
- 服务启动时按配置加载预设房间（`XQWEB_PRESET_ROOM_IDS`）。
- 仅内存保存，服务重启全部重置。

### 2.3 并发与一致性
- 每个房间一个 `asyncio.Lock`，同房间写操作串行化：`join/leave/ready`。
- 跨房间无全局锁，避免大厅操作互相阻塞。
- 写操作完成后再广播 WS，保证推送与内存状态一致。

### 2.4 房间业务规则
- 房间最大 3 人，满员时 `join` 返回 409。
- 首个进入者为 `owner_id`。
- 座位采用最小空闲 seat 分配（0→1→2）。
- 成员退出：
  - 从成员列表移除。
  - 若是 owner，owner 转给当前最早加入成员；若无人则置空。
  - 退出后成员 ready 清除（成员已不存在）。
- 房态：
  - 默认 `waiting`。
  - `playing/settlement` 由对局生命周期驱动（M2 先实现 waiting 期逻辑，playing 冷结束规则预留）。

### 2.5 冷结束规则（对齐接口文档）
当 `room.status=playing` 且任一成员调用 `/leave`：
1. 当前对局标记冷结束（不执行结算、不改 chips）。
2. `current_game_id = null`。
3. 所有剩余成员 `ready = false`。
4. `room.status = waiting`。
5. 广播 `ROOM_UPDATE`。

### 2.6 M2 REST 接口落地

#### GET `/api/rooms`
- 返回 `room_summary[]`：`room_id,status,player_count,ready_count`。
- 可按 `room_id` 升序输出。

#### GET `/api/rooms/{room_id}`
- 返回 `room_detail`（含 members、owner、current_game_id）。
- 非法 room_id 返回 404。

#### POST `/api/rooms/{room_id}/join`
- 要求已登录。
- 校验：房间存在、未满、未重复加入。
- 成功返回最新 `room_detail`。

#### POST `/api/rooms/{room_id}/leave`
- 要求房间成员。
- 成功返回 `{"ok": true}` 并触发广播。

#### POST `/api/rooms/{room_id}/ready`
- body: `{"ready": true|false}`。
- 仅房间成员可调用。
- 成功返回最新 `room_detail`。
- 当三人均 `ready=true` 时：
  - 若引擎未接入，先预留 `start_game` 钩子。
  - 引擎接入后切 `playing` 并创建 `current_game_id`。

### 2.7 WS 推送（M2 阶段）

#### `/ws/lobby`
- 连接成功立即下发 `ROOM_LIST`（全量）。
- 任意房间成员/ready/status 变化后推送 `ROOM_LIST`。

#### `/ws/rooms/{room_id}`
- 连接成功下发 `ROOM_UPDATE`（全量房间快照）。
- room 发生变化时广播 `ROOM_UPDATE`。
- 心跳：服务端每 30s 发 `PING`，客户端 10s 内应答 `PONG`。

### 2.8 错误码建议（M2）
- `ROOM_NOT_FOUND`（404）
- `ROOM_FULL`（409）
- `ROOM_ALREADY_JOINED`（409）
- `ROOM_NOT_MEMBER`（403）
- `ROOM_INVALID_READY_TRANSITION`（409，可选）

### 2.9 M2 测试设计
- 单元测试：
  - seat 分配与回收。
  - owner 转移。
  - ready 计数正确性。
- API 测试：
  - list/detail/join/leave/ready 全流程。
  - 房间满员、重复加入、非成员 ready/leave。
- 并发测试：
  - 两请求同时 join 最后不超过 3 人。
- WS 测试：
  - join/leave/ready 后大厅与房间消息正确到达。

## 3. M1-M2 交付检查清单
- [ ] 代码结构与配置文件落地。
- [ ] DB 建表与索引落地。
- [ ] Auth 五个接口通过测试。
- [ ] 登录踢旧会话策略生效（旧 refresh 不可用，旧 access 可用至过期）。
- [ ] refresh token 清理任务（启动一次 + 每天 00:00）生效。
- [ ] 预设房间 CRUD（无创建/解散）能力可用。
- [ ] Lobby/Room WS 推送与心跳可用。
- [ ] 统一错误响应与关键日志字段可观测。

## 4. 已知风险与决策
- 风险：refresh token 无限增长。
  - 决策：服务启动清理一次 + 每天 00:00 清理一次（仅删过期/撤销记录）。
- 风险：房间并发写导致座位冲突。
  - 决策：采用房间级锁。
- 风险：登录踢旧后，旧端 access token 仍短时可用。
  - 决策：MVP 不做 access 立即失效（不做黑名单），接受最多 1 小时自然过期窗口。
- 风险：`client_version` 在文档口径有差异（MVP 是否强校验）。
  - 决策：在 M4 统一为“引擎校验并返回 409”。

## 5. 变更记录
- 2026-02-13：创建文档骨架。
- 2026-02-13：补充 M1-M2 后端详细设计（目录、数据、接口、并发、测试、风险）。
- 2026-02-13：统一环境变量前缀为 `XQWEB_`，补充 `.env.dev/.env.test` 本地约定。
- 2026-02-13：确认登录踢旧、logout 仅当前会话、refresh 清理时机（启动+每日 00:00）、配置加载策略（pydantic-settings + 显式 env 文件）。
- 2026-02-13：同步 MVP 安全边界说明（基础安全可用，暂不做强对抗防护）。
