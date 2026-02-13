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
- `XQWEB_ACCESS_TOKEN_REFRESH_INTERVAL_SECONDS`：客户端主动刷新 access token 的周期，默认 1800。
- `XQWEB_REFRESH_TOKEN_EXPIRE_SECONDS`：默认 7776000（90 天）。
- `XQWEB_SQLITE_PATH`：SQLite 文件路径。
- `XQWEB_CORS_ALLOW_ORIGINS`：前端域名白名单。
- `XQWEB_ROOM_COUNT`：预设房间数量（房间 id 固定为 `0..XQWEB_ROOM_COUNT-1`）。

本地开发/测试约定（无 Docker）：
- 使用项目内 env 文件，不在 shell profile（如 `~/.bashrc`）做全局 `export`。
- 开发环境使用 `.env.dev`。
- 测试环境使用 `.env.test`（与开发隔离，避免误连开发库）。
- 由应用启动参数或测试初始化逻辑按需加载对应 env 文件。
- 配置加载策略：`pydantic-settings` 负责解析与校验；启动命令显式指定 env 文件（开发 `.env.dev`，测试 `.env.test`）。

约束：
- 所有时间使用 UTC。
- secret 缺失时服务启动失败。
- `XQWEB_ACCESS_TOKEN_REFRESH_INTERVAL_SECONDS < XQWEB_ACCESS_TOKEN_EXPIRE_SECONDS`。

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

连接约束：
- 每个 SQLite 连接创建后必须执行 `PRAGMA foreign_keys=ON`，确保外键约束生效。

### 1.5 安全与鉴权策略
- 密码哈希：`bcrypt`（或 `passlib[bcrypt]`）。
- Access token：JWT，payload 至少含 `sub(user_id)`、`exp`。
- Refresh token：随机高熵字符串，仅存 `token_hash`，不明文落库。
- 会话策略（MVP）：
  - 单账号单活跃会话（以 refresh token 为准）。
  - 每次 `register/login` 成功后，撤销该用户历史全部 refresh token，再签发新 token 对。
  - 旧端 access token 不做立即失效处理，可使用到自身 `exp` 到期（默认 1 小时）。
  - 保持 access/refresh 双 token 设计，不退化为单 3 个月 token。
- Refresh 轮换：
  1. 校验旧 refresh token（存在、未撤销、未过期）。
  2. 旧 token 立即写 `revoked_at`。
  3. 新建 refresh token 记录并返回。
- Logout：撤销指定 refresh token（幂等）。

### 1.6 认证接口实现细节

#### POST `/api/auth/register`
- 输入：`username/password`
- 规则：
  - username 去前后空格，长度限制为 1-10 个“用户可见字符”（grapheme cluster）。
  - username 在校验与存储前统一做 NFC 归一化。
  - username 按 UTF-8 编码传输，大小写敏感（如 `Tom` 与 `tom` 视为不同用户名）。
  - MVP 阶段 password 不做强规则校验，允许空密码。
  - username 重复返回 409。
- 输出：登录态（access + refresh + user）。

#### POST `/api/auth/login`
- 使用 username + password 验证。
- username 与 register 使用同一处理流程（trim + NFC 归一化 + 大小写敏感匹配）。
- password 按“原样字符串”比较（MVP 允许空密码登录）。
- 密码错误返回 401（不区分账号不存在/密码错误）。
- 登录成功后撤销该用户历史 refresh token（踢掉旧登录）。
- “撤销旧 token + 签发新 token”应在同一事务中完成，避免中间态。
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
- WS 重连策略：客户端重连前可先检查 access token；若已过期或即将过期，先调用 `/api/auth/refresh` 获取新 access 后再发起 WS 重连。
- 客户端主动刷新策略：按 `XQWEB_ACCESS_TOKEN_REFRESH_INTERVAL_SECONDS`（默认每 30 分钟）调用 refresh；access 默认 1 小时过期，两个时间均可配置。
- 已建立连接的 WS 在 access token 过期后由服务端主动断开（`4401`），客户端再执行 refresh + 重连。

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
  - `foreign_keys=ON` 生效（禁止写入孤儿 refresh token）。
- API 测试：
  - register/login/me/refresh/logout 正常流。
  - 非法 token、过期 token、重复注册、错误密码。
  - username 用户可见字符长度校验（<=10 通过，>10 拒绝）。
  - username NFC 归一化一致性（组合字符与预组字符按同一用户名处理）。
  - username 大小写敏感校验（`Tom` 与 `tom` 可同时注册）。
  - 空密码注册/登录可用（MVP 口径）。
  - 登录踢旧登录：旧 refresh 失效，新 refresh 可用，旧 access 仍可在过期前使用。
- 集成测试：
  - WS token 鉴权成功/失败。

## 2. M2 房间与大厅设计

### 2.1 目标
- 实现预设房间模型与成员管理。
- 完成大厅列表与房间详情接口。
- 完成 ready 流程与房态流转。
- 实现中途离房冷结束策略。

### 2.1.1 运行约束（MVP）
- 后端按单进程/单 worker 部署，避免内存态房间在多进程间分裂。

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
- 服务启动时按 `XQWEB_ROOM_COUNT` 初始化房间，房间 id 为 `0..N-1`。
- 仅内存保存，服务重启全部重置。

### 2.3 并发与一致性
- 每个房间一个 `asyncio.Lock`，同房间写操作串行化：`join/leave/ready`。
- 跨房间无全局锁，避免大厅操作互相阻塞。
- 写操作完成后再广播 WS，保证推送与内存状态一致。
- 涉及“从 A 房迁移到 B 房”的 join 操作，按 `room_id` 升序获取双房间锁，避免死锁。

### 2.4 房间业务规则
- 房间最大 3 人，满员时 `join` 返回 409。
- 首个进入者为 `owner_id`。
- 座位采用最小空闲 seat 分配（0→1→2）。
- 同房重复 `join` 幂等返回：若用户已在目标房间，直接返回当前 `room_detail`，不报错。
- 同一用户再次加入其他房间时，先自动离开当前所在房间，再加入目标房间。
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
6. 前端收到由 `playing -> waiting` 的冷结束切换时，提示“对局结束”并停留/进入等待态。

### 2.6 M2 REST 接口落地

#### GET `/api/rooms`
- 返回 `room_summary[]`：`room_id,status,player_count,ready_count`。
- 可按 `room_id` 升序输出。

#### GET `/api/rooms/{room_id}`
- 返回 `room_detail`（含 members、owner、current_game_id）。
- 非法 room_id 返回 404。

#### POST `/api/rooms/{room_id}/join`
- 要求已登录。
- 若用户已在目标房间：幂等返回 `200 + room_detail`。
- 校验：房间存在、目标房间未满。
- 若用户已在其它房间，先检查目标房间可加入，再执行“离开 A + 加入 B”的原子迁移（若原房间处于 playing，将触发该房间冷结束规则）。
- 成功返回最新 `room_detail`。

#### POST `/api/rooms/{room_id}/leave`
- 要求房间成员。
- 成功返回 `{"ok": true}` 并触发广播。

#### POST `/api/rooms/{room_id}/ready`
- body: `{"ready": true|false}`。
- 仅房间成员可调用。
- 仅 `room.status=waiting` 时允许变更 ready。
- 成功返回最新 `room_detail`。
- 当三人均 `ready=true` 时：
  - 若引擎未接入，先预留 `start_game` 钩子。
  - 引擎接入后切 `playing` 并创建 `current_game_id`（幂等：已有进行中 game 时不重复创建）。

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
- `ROOM_NOT_MEMBER`（403）
- `ROOM_NOT_WAITING`（409，非 waiting 状态修改 ready）。

### 2.9 M2 测试设计
- 单元测试：
  - seat 分配与回收。
  - owner 转移。
  - ready 计数正确性。
  - 同用户跨房间 join 时自动迁移行为正确。
- API 测试：
  - list/detail/join/leave/ready 全流程。
  - 房间满员、同房重复 join 幂等、非成员 ready/leave。
  - 跨房间迁移失败时不丢失原房间成员身份（迁移原子性）。
  - playing 状态 ready 修改被拒绝（409）。
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
- [ ] SQLite `foreign_keys=ON` 生效。
- [ ] 预设房间 CRUD（无创建/解散）能力可用。
- [ ] 房间初始化规则为 `id=0..N-1`（由 `XQWEB_ROOM_COUNT` 控制）。
- [ ] 单用户跨房间自动迁移规则可用（必要时触发原房间冷结束）。
- [ ] Lobby/Room WS 推送与心跳可用。
- [ ] 统一错误响应与关键日志字段可观测。

## 4. 已知风险与决策
- 风险：refresh token 无限增长。
  - 决策：服务启动清理一次 + 每天 00:00 清理一次（仅删过期/撤销记录）。
- 风险：房间并发写导致座位冲突。
  - 决策：采用房间级锁。
- 风险：登录踢旧后，旧端 access token 仍短时可用。
  - 决策：MVP 不做 access 立即失效（不做黑名单），接受最多 1 小时自然过期窗口。
- 风险：内存态在多 worker 部署时分裂。
  - 决策：MVP 固定单进程单 worker。
- 风险：`client_version` 不一致导致旧状态动作覆盖新状态。
  - 决策：后端返回 409；前端收到后立即通过 REST 拉取一次最新状态并重建本地视图。

## 5. 变更记录
- 2026-02-13：创建文档骨架。
- 2026-02-13：补充 M1-M2 后端详细设计（目录、数据、接口、并发、测试、风险）。
- 2026-02-13：统一环境变量前缀为 `XQWEB_`，补充 `.env.dev/.env.test` 本地约定。
- 2026-02-13：确认登录踢旧、logout 仅当前会话、refresh 清理时机（启动+每日 00:00）、配置加载策略（pydantic-settings + 显式 env 文件）。
- 2026-02-13：同步 MVP 安全边界说明（基础安全可用，暂不做强对抗防护）。
- 2026-02-13：补充共识约束：`XQWEB_ROOM_COUNT`、单 worker、跨房间自动迁移、ready 仅 waiting 可变更、WS 重连前可 refresh。
- 2026-02-13：补充共识约束：username 按用户可见字符计数（<=10）、access 30 分钟主动刷新/1 小时过期（可配置）、跨房间迁移原子化。
- 2026-02-13：补充共识约束：`client_version` 冲突返回 409 且前端 REST 拉态、WS token 过期主动断开、username 大小写敏感、MVP 允许空密码、冷结束前端提示“对局结束”。
- 2026-02-13：补充 username 归一化口径：注册/登录统一 NFC 归一化后再校验与匹配。
