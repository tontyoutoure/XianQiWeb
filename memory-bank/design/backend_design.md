# 后端详细设计文档

本文档用于沉淀后端实现层面的详细设计，作为 `memory-bank/architecture.md` 与接口文档的实现补充。

## 0. 文档范围与基线
- 当前版本覆盖：M1（后端基础与鉴权）、M2（房间与大厅）、M4（后端-引擎集成）、M5（结算与重新 ready 开下一局）、M6（游戏实时推送与重连）。
- 一致性基线：
  - `memory-bank/architecture.md`
  - `memory-bank/interfaces/frontend-backend-interfaces.md`
  - `memory-bank/interfaces/backend-engine-interface.md`
- 安全基线（MVP）：安全性保持基础可用，重点保障鉴权正确与服务稳定；对用户恶意行为暂不做强对抗防护（如复杂风控、反刷、设备指纹、行为审计）。
- 非目标：前端页面实现与跨重启历史恢复（仅定义后端契约与内存态行为）。

## 1. M1 后端基础与鉴权设计

### 1.1 目标
- 建立可运行的 FastAPI 服务骨架。
- 完成 `users + refresh_tokens` 持久化模型。
- 完成 Access/Refresh 双 token 鉴权闭环（REST + WS）。

### 1.2 当前后端文件结构（实现现状）
> 说明：以下为当前仓库中的后端结构（省略 `__pycache__`、`.pytest_cache` 等生成文件）。

```text
backend/
  app/
    main.py                          # 应用入口：lifespan + include_router + 兼容导出
    runtime.py                       # 进程级运行态（settings/room_registry/ws连接集合）
    core/
      config.py                      # 环境变量与配置校验
      db.py                          # SQLite 连接与基础约束
      password.py                    # 密码哈希与校验
      refresh_tokens.py              # refresh token 生成/哈希辅助
      tokens.py                      # access token 编解码与校验
      username.py                    # 用户名规则（长度/NFC 等）
    auth/
      models.py                      # 鉴权请求模型
      errors.py                      # 鉴权异常映射
      http.py                        # 统一 HTTP 错误响应
      repository.py                  # users/refresh_tokens 持久化访问
      schema.py                      # 鉴权表结构初始化
      session.py                     # token 会话编排
      service.py                     # register/login/me/refresh/logout 服务
    rooms/
      models.py                      # 房间/对局 API 请求模型
      registry.py                    # 房间与对局内存态聚合根（含并发锁）
    api/
      deps.py                        # HTTP 依赖（Authorization -> current_user）
      errors.py                      # API 统一错误抛出辅助
      room_views.py                  # room_summary/room_detail 视图构造
      routers/
        auth.py                      # /api/auth/*
        rooms.py                     # /api/rooms/*
        games.py                     # /api/games/*
    ws/
      protocol.py                    # WS 消息封装（v/type/payload）
      heartbeat.py                   # PING/PONG、token 过期断连、消息循环
      broadcast.py                   # lobby/room/game 快照与广播编排
      routers.py                     # /ws/lobby 与 /ws/rooms/{room_id}

  tests/
    unit/                            # 单元测试（core/auth/registry）
    api/                             # API 契约测试（M1/M2/M5）
    integration/
      ws/                            # 进程内 WS 集成测试
      concurrency/                   # 并发一致性测试
      real_service/                  # uvicorn 真实服务测试（M1~M6）
    conftest.py                      # 测试夹具与共享配置
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
- `XQWEB_JWT_SECRET` 长度至少 32 字节（避免 HS256 弱密钥告警与安全风险）。
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
- 成功后的持久化约定：
  - `users` 表新增 1 条用户记录（保存 `password_hash`，不保存明文密码）。
  - `refresh_tokens` 表新增 1 条未撤销记录（仅保存 `token_hash`，不保存明文 refresh token）。
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
  - register 成功后校验数据库落库：`users` 新增用户，`refresh_tokens` 新增未撤销记录，且仅存 `token_hash`。
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
- M2 口径下仅 `room.status=waiting` 时允许变更 ready；M4+ 集成后扩展为 `waiting|settlement` 均可变更（settlement 用于准备下一局）。
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

## 3. M4-M6 后端引擎集成设计

### 3.1 目标
- 将现有 RoomRegistry 与引擎对象联动，形成完整对局生命周期：
  - 三人全 ready 开局
  - 动作推进
  - 结算与“结算后清空 ready，重新 ready 开下一局”
  - 房间内实时公共/私有推送

### 3.2 内存域模型补充（GameSession）

#### GameSession
- `game_id: int`
- `room_id: int`
- `status: in_progress|settlement|aborted`
- `engine: XianQiEngine`（内嵌引擎对象）
- `seat_to_user_id: dict[int, int]`
- `user_id_to_seat: dict[int, int]`
- `created_at/updated_at/ended_at`

#### GameRegistry（建议）
- `games_by_id: dict[int, GameSession]`
- `room_to_current_game: dict[int, int]`
- 约束：同一房间同一时刻最多一个“未结束” game。

### 3.3 生命周期与状态联动
- 开局触发：`/api/rooms/{room_id}/ready` 达成三人全 ready。
  1. 构造 seat 映射并创建 `GameSession`。
  2. 调用引擎 `init_game(config, rng_seed)`。
  3. 写入 `room.current_game_id`，`room.status=playing`。
  4. 广播 `ROOM_UPDATE` 与首帧 `GAME_PUBLIC_STATE/GAME_PRIVATE_STATE`。
- 动作推进：`/api/games/{game_id}/actions` 调引擎 `apply_action`，按输出更新 game 状态并推送快照。
- 进入结算：引擎 `phase=settlement` 后可 `GET /settlement`，并通过 WS 发 `SETTLEMENT`。
- 结算后下一局准备：
  - 进入结算时服务端将房间成员 `ready` 全部重置为 `false`。
  - 保持房间 `status=settlement` 展示结算；成员通过 `/api/rooms/{room_id}/ready` 重新提交准备。
  - 当三人再次 `ready=true` 时，立即创建新局并切换 `room.status=playing`。
- 冷结束：`room.status=playing` 有成员 leave 时：
  - game 标记 `aborted`，不做结算不改 chips；
  - 房间回 waiting 并广播 `ROOM_UPDATE`。

### 3.4 REST 接口落地（Games）

#### GET `/api/games/{game_id}/state`
- 权限：Bearer + 房间成员。
- 返回：`game_id/self_seat/public_state/private_state/legal_actions`。
- 用途：断线恢复、409 后刷新本地状态。

#### POST `/api/games/{game_id}/actions`
- 请求：`action_idx + cover_list? + client_version?`。
- 成功：`204 No Content`。
- 失败：
  - `409 GAME_VERSION_CONFLICT`（版本冲突）
  - `409 GAME_INVALID_ACTION`（非法动作/phase 不匹配）
  - `403 GAME_FORBIDDEN`（非成员）
  - `404 GAME_NOT_FOUND`

#### GET `/api/games/{game_id}/settlement`
- 仅 `phase = settlement` 可调用。
- 返回引擎 settlement 结构（含 `chip_delta_by_seat`）。

### 3.5 WS 推送策略（M6）
- 不新增 `/ws/games/*`；继续使用 `/ws/rooms/{room_id}` 承载游戏事件。
- 房间 WS 初始快照：
  - 无对局：仅 `ROOM_UPDATE`。
  - 有对局：`ROOM_UPDATE` -> `GAME_PUBLIC_STATE` ->（私发）`GAME_PRIVATE_STATE`。
- 动作成功后的推送顺序：
  1. 广播 `GAME_PUBLIC_STATE`
  2. 按连接私发 `GAME_PRIVATE_STATE`
  3. 如房态变化（例如进入结算/回 waiting），补发 `ROOM_UPDATE`
  4. 若本次进入结算，追加 `SETTLEMENT`
- 重连策略：客户端优先调 `GET /state`，WS 只做增量与首帧同步。
- 事件一致性约束：
  - 同一 `game_id` 下 `public_state.version` 必须严格单调递增，不允许回退或跳回旧值。
  - `GAME_PRIVATE_STATE` 的 `game_id/version` 必须与同轮次最近的 `GAME_PUBLIC_STATE` 对齐。
  - 私有态仅按连接所属 `user_id` 单播，不允许跨 seat 泄露手牌/legal_actions。
- 连接关闭语义（M6 约定）：
  - 鉴权失败/token 失效：`4401 UNAUTHORIZED`。
  - 房间不存在：`4404 ROOM_NOT_FOUND`。
  - 心跳超时：建议 `4408 HEARTBEAT_TIMEOUT`（至少保证可观测断连）。

### 3.5.1 心跳与保活细化（M6-HB）
- 参数口径：
  - 服务端固定每 30s 发送一次 `PING`。
  - 客户端须在 10s 内应答 `PONG`。
  - 连续 2 次未按时收到 `PONG`，服务端主动关闭连接。
- 连接级状态（建议）：
  - `last_ping_at`
  - `last_pong_at`
  - `missed_pong_count`
- 状态迁移：
  1. 发送 `PING` 时记录 `last_ping_at`。
  2. 超过 10s 仍未收到对应 `PONG`：`missed_pong_count += 1`。
  3. 收到有效 `PONG`：刷新 `last_pong_at` 且 `missed_pong_count = 0`。
  4. `missed_pong_count >= 2`：关闭连接并清理连接索引（lobby/room 监听集合、user 映射）。

### 3.6 错误码补充（Games）
- `GAME_NOT_FOUND`（404）
- `GAME_FORBIDDEN`（403）
- `GAME_STATE_CONFLICT`（409）
- `GAME_VERSION_CONFLICT`（409）
- `GAME_INVALID_ACTION`（409）

### 3.7 测试设计（M4-M6）
- 单元：
  - `GameSession` 生命周期（create/advance/settle/abort）
  - seat 映射与成员鉴权
  - 结算后 ready 重置与重新就绪开局逻辑
- API：
  - `/state` 快照结构与权限
  - `/actions` 204/409/403/404 分支
  - `/settlement` phase 门禁
  - 复用 `/api/rooms/{room_id}/ready` 完成结算后的下一局准备
- WS：
  - 初始快照（无局/有局）分支
  - 动作后 public/private 推送顺序
  - 结算与冷结束广播
- 并发：
  - 同一 game 并发动作仅接受一个（其余版本冲突或非法动作）
  - 结算后并发 ready 只触发一次开局

### 3.8 M6 断线重连与并发一致性细化

#### 3.8.1 断线重连恢复口径（M6-RC）
- 恢复基线：`GET /api/games/{game_id}/state` 为恢复真源（public/private/legal_actions 同步返回）。
- WS 重连首帧：
  - 房间无局：仅 `ROOM_UPDATE`。
  - 房间有局：`ROOM_UPDATE -> GAME_PUBLIC_STATE -> GAME_PRIVATE_STATE`。
  - 首帧 `version` 必须 `>=` 客户端断线前最后已确认版本。
- phase 恢复约束：
  - 先判定是否“轮到当前连接对应 seat 决策”（`self_seat == turn.current_seat`）：仅当成立时返回 `legal_actions`；否则 `legal_actions = null`（或省略）。
  - `buckle_flow`：在“轮到我行动”前提下，恢复当前决策 seat 的 `BUCKLE/PASS` 或 `REVEAL/PASS` 合法动作集合。
  - `in_round`：在“轮到我行动”前提下，恢复 `PLAY/COVER` 语义与稳定 `action_idx`（同一状态下索引不漂移）。
  - `settlement`：恢复 `phase=settlement`；`GET /settlement` 返回结构与 WS `SETTLEMENT` 一致。
- token 过期重连：
  - WS 因过期被 `4401` 关闭后，客户端 refresh 成功可重新连接并恢复同房状态。
- 服务重启边界（非恢复）：
  - 旧内存态不保证恢复；旧 `game_id` 查询返回 `404/409` 视具体接口语义。
  - 房间以重启后内存态为准（无跨重启恢复承诺）。

#### 3.8.2 并发一致性不变量（M6-CC）
- 动作并发互斥：同 `game_id + client_version` 并发动作最多 1 个成功。
- 无重复应用：同一客户端意图在竞态下最多被引擎接受 1 次，禁止版本回退。
- 重连并发收敛：重连与他人动作并发时，允许短暂“先旧后新”观察，但最终需收敛到同一 `game_id/version`。
- 多连接同账号：
  - 同账号可有多个 WS 连接。
  - 每个连接仅接收其所属 room 的私有态，不跨房间串流。
- 结算后并发 ready：
  - 从“非全员 ready”到“全员 ready”的迁移只能触发 1 次新局创建。
  - 其余并发请求返回最新房间态，不得重复创建 game。

## 4. M1-M2-M4-M6 交付检查清单
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
- [ ] 三人全 ready 可创建 game 并进入 `playing`。
- [ ] Games 三接口（`/state`、`/actions`、`/settlement`）通过契约测试。
- [ ] 动作版本冲突与非法动作分支可观测（409 + 统一错误体）。
- [ ] 房间 WS 可推送 `GAME_PUBLIC_STATE/GAME_PRIVATE_STATE/SETTLEMENT`。
- [ ] 结算后 ready 清零，且三人重新 ready 仅触发一次新局创建。
- [ ] playing 中 leave 冷结束行为在 game 与 room 侧均一致。
- [ ] 统一错误响应与关键日志字段可观测。
- [ ] 心跳超时断连机制可观测（30s PING / 10s PONG / 连续2次超时断开）。
- [ ] 断线重连恢复覆盖 `buckle_flow/in_round/settlement` 三阶段。
- [ ] 重连与动作并发竞态下，无重复应用动作、无版本回退。
- [ ] 服务重启边界行为固定（无跨重启恢复承诺，错误码口径一致）。

## 5. 已知风险与决策
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
- 风险：房间 WS 同时承载房间与对局事件，消息量上升导致前端处理复杂。
  - 决策：统一事件顺序（public -> private -> room_update），并在文档固定首帧/增量策略。
- 风险：结算后并发 ready 触发重复开局。
  - 决策：沿用同房间写锁；当 `status=settlement` 且“从非全员 ready -> 全员 ready”仅允许一次 start_game 迁移。
- 风险：心跳抖动导致误断连，影响弱网体验。
  - 决策：按“连续 2 次超时再断连”降低误杀；客户端断连后走 refresh + 重连恢复链路。
- 风险：重连与动作并发造成短时视图抖动。
  - 决策：以 `version` 单调为收敛标准，HTTP `/state` 作为兜底真源。

## 6. 变更记录
- 2026-02-13：创建文档骨架。
- 2026-02-13：补充 M1-M2 后端详细设计（目录、数据、接口、并发、测试、风险）。
- 2026-02-13：统一环境变量前缀为 `XQWEB_`，补充 `.env.dev/.env.test` 本地约定。
- 2026-02-13：确认登录踢旧、logout 仅当前会话、refresh 清理时机（启动+每日 00:00）、配置加载策略（pydantic-settings + 显式 env 文件）。
- 2026-02-13：同步 MVP 安全边界说明（基础安全可用，暂不做强对抗防护）。
- 2026-02-13：补充共识约束：`XQWEB_ROOM_COUNT`、单 worker、跨房间自动迁移、ready 仅 waiting 可变更、WS 重连前可 refresh。
- 2026-02-13：补充共识约束：username 按用户可见字符计数（<=10）、access 30 分钟主动刷新/1 小时过期（可配置）、跨房间迁移原子化。
- 2026-02-13：补充共识约束：`client_version` 冲突返回 409 且前端 REST 拉态、WS token 过期主动断开、username 大小写敏感、MVP 允许空密码、冷结束前端提示“对局结束”。
- 2026-02-13：补充 username 归一化口径：注册/登录统一 NFC 归一化后再校验与匹配。
- 2026-02-20：补充 M4-M6 后端引擎集成设计：GameSession 内存模型、Games REST、房间 WS 游戏事件、结算后重新 ready 开局与并发约束。
- 2026-02-21：补充 M6 细化设计：心跳超时断连口径、断线重连 phase 恢复规则、并发一致性不变量与服务重启边界。
