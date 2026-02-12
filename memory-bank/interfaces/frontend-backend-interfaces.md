# 前后端接口

## 1. 后端接口设计（REST）

### 1.1 Auth
- POST `/api/auth/register`
  - body: {"username":"", "password":""}
  - resp: {"access_token":"", "expires_in":3600, "refresh_token":"", "refresh_expires_in":7776000, "user":{"id":0,"username":"","created_at":""}}
- POST `/api/auth/login`
  - body: {"username":"", "password":""}
  - resp: {"access_token":"", "expires_in":3600, "refresh_token":"", "refresh_expires_in":7776000, "user":{"id":0,"username":"","created_at":""}}
- GET `/api/auth/me`
  - header: Authorization: Bearer <access_token>
  - resp: {"id":0,"username":"","created_at":""}
- POST `/api/auth/refresh`
  - body: {"refresh_token":""}
  - resp: {"access_token":"", "expires_in":3600, "refresh_token":"", "refresh_expires_in":7776000}
- POST `/api/auth/logout`
  - body: {"refresh_token":""}
  - resp: {"ok": true}
Auth 说明：
- access_token 为 JWT（短期有效），用于所有 REST/WS 鉴权。
- refresh_token 为不透明随机串，服务端持久化（可撤销）。
- refresh 时轮换 refresh_token（旧 token 立即失效）。

### 1.2 Rooms
- GET `/api/rooms`
  - resp: [{room_id, status, player_count, ready_count}]
- POST `/api/rooms/{room_id}/join`
  - resp: room_detail
- POST `/api/rooms/{room_id}/leave`
  - resp: {"ok": true}
- POST `/api/rooms/{room_id}/ready`
  - body: {"ready": true/false}
  - resp: room_detail
- GET `/api/rooms/{room_id}`
  - resp: room_detail

#### 1.2.1 Room structures
room_summary：
```json
{"room_id":1,"status":"waiting","player_count":2,"ready_count":1}
```

room_detail：
```json
{
  "room_id": 1,
  "status": "waiting",
  "owner_id": 10,
  "members": [
    {"user_id":10,"username":"","seat":0,"ready":true,"chips":10}
  ],
  "current_game_id": null
}
```
status 枚举：`waiting` | `playing` | `settlement`。
MVP 约束：房间数量由服务端预设，`room_id` 为唯一编号；不使用 `room_name`。
实现备注：采用“预设房间”模式，不提供创建房间接口。

### 1.3 Games / Actions / Reconnect
- GET `/api/games/{game_id}/state`
  - resp: {"game_id": "", "self_seat": 0, "public_state":{}, "private_state":{...}, "legal_actions": {...}}
- POST `/api/games/{game_id}/actions`
  - body: {"action_idx": 0, "cover_list": [{"type":"B_NIU","count":1}], "client_version": 0}
- GET `/api/games/{game_id}/settlement`
  - resp: result_json
- POST `/api/games/{game_id}/continue`
  - body: {"continue": true/false}

简化做法：也可用 `/api/rooms/{room_id}/actions` 由后端定位当前 game_id。

#### 1.3.1 动作/牌载荷与 legal_actions
说明：前端只提交 `action_idx`（在 `legal_actions.actions` 中的下标）。`cover_list` 仅在动作类型为 COVER 时传入，其他动作传 `null` 或省略。

牌面载荷统一使用 `cards` 结构：
```json
{"type": "R_SHI", "count": 1}
```

legal_actions 结构（仅当前行动玩家存在，其它玩家为 `null` 或不返回）：
```jsonc
{
  "seat": 1,
  "actions": [
    {"type": "PLAY", "payload_cards": [{"type": "R_SHI", "count": 1}]},
    {"type": "COVER", "required_count": 1},
    {"type": "BUCKLE"},
    {"type": "REVEAL"},
    {"type": "PASS_REVEAL"}
  ]
}
```
- PLAY：携带 `payload_cards`（推荐出牌牌面，前端用其决定 `action_idx`）。
- COVER：只给出 `required_count`，前端自行从手牌选择同张数牌面，通过 `cover_list` 回传。
- BUCKLE / REVEAL / PASS_REVEAL：无额外载荷，列表中最多各 1 个。

#### 1.3.2 settlement / continue 调用时机
- `/settlement`：仅当 `phase = settlement | finished` 时可调用，且仅限房间成员。
- `/continue`：仅在结算阶段允许，房间成员各自提交是否继续；当三人均 `continue=true` 时服务端立即创建新局并将房间状态置为 `playing`（无需再次准备）。
- 若任一玩家提交 `continue=false`，则本局结束，房间返回 `waiting`。

## 2. WebSocket 协议
使用原因：对局与房间状态需要实时推送（避免轮询延迟与无效请求），并保证多人同步看到一致状态；此外私有状态（手牌/可行动作）也需要安全、及时地下发。

### 2.1 通道
**大厅 WS（/ws/lobby）**
- `/ws/lobby?token=ACCESS_TOKEN`：大厅房间列表更新。

**房间 WS（/ws/rooms/{room_id}）**
- `/ws/rooms/{room_id}?token=ACCESS_TOKEN`：房间与对局公共消息（含开始/结算）。

### 2.2 消息结构
```json
{
  "v": 1,
  "type": "ROOM_LIST|ROOM_UPDATE|GAME_PUBLIC_STATE|GAME_PRIVATE_STATE|SETTLEMENT|ERROR|PING|PONG",
  "payload": {}
}
```

### 2.3 关键消息（大厅）
- ROOM_LIST：推送房间列表刷新。
- payload: {"rooms":[room_summary, ...]}（room_summary 见 1.2.1）
- ERROR：{"code":"","message":"","detail":{}}。
- PING/PONG：心跳保活。

### 2.4 关键消息（房间）
- ROOM_UPDATE：成员/就绪/状态变化。
- payload: {"room": room_detail}（room_detail 见 1.2.1）
- GAME_PUBLIC_STATE：公共状态快照（不含他人手牌，适合旁观/观战）。
- payload: {"game_id":"", "public_state":{...}}（public_state 见引擎文档 1.5.1）
- GAME_PRIVATE_STATE：仅发给单连接的私有快照（手牌、已垫棋子、legal_actions）。
- payload: {"game_id":"", "self_seat":0, "private_state":{...}, "legal_actions":{...}}（private_state/ legal_actions 见引擎文档 1.5.2/1.5.3）
- SETTLEMENT：结算结果。
- payload: 见引擎文档 1.5.4（settlement）
- ERROR：{"code":"","message":"","detail":{}}。
- PING/PONG：心跳保活。

初始快照策略：连接成功后立即下发一次全量快照（大厅为 ROOM_LIST；房间为 ROOM_UPDATE + GAME_PUBLIC_STATE + GAME_PRIVATE_STATE）。
心跳策略：服务端每 30s 发送一次 PING，客户端需在 10s 内回 PONG；连续 2 次未响应可断开连接。
私有状态默认通过 WS 单连接私发；断线重连或兜底则通过 HTTP 拉取。
鉴权失败：WS 连接直接关闭（推荐 close code 4401 + reason "UNAUTHORIZED"）。

## 3. 前端数据契约（页面字段）

### 3.1 登录页
- username / password

### 3.2 大厅
- room_id, status, player_count, ready_count

### 3.3 房间
- room_detail（同 1.2.1）+ self_user_id
- actions: ready / leave

### 3.4 对局
仅列出前端需关心的“顶层字段”，具体结构按后端-引擎文档复用，避免重复与漂移。
- 顶层：`game_id`, `self_seat`, `public_state`, `private_state`, `legal_actions`
- public_state 详细字段见 `memory-bank/interfaces/backend-engine-interface.md` 的 1.5.1
- private_state 详细字段见 `memory-bank/interfaces/backend-engine-interface.md` 的 1.5.2
- legal_actions 详细字段见 `memory-bank/interfaces/backend-engine-interface.md` 的 1.5.3

### 3.5 结算
结算结构以引擎文档为准，见 `memory-bank/interfaces/backend-engine-interface.md` 的 1.5.4。

## 4. 约束与校验
- access_token 用于所有 REST/WS 鉴权；短期有效（建议 1 小时）。
- refresh_token 用于静默刷新 access_token；长期有效（建议 90 天，滑动续期）。
- 动作提交使用 `action_idx`（来自 `legal_actions.actions`）；COVER 动作需额外传 `cover_list`。
- 所有动作必须基于后端当前版本号（可选加 `client_version` 乐观锁）。
- 服务端为唯一权威；客户端只负责提交意图。
- 断线重连：重新拉取 public_state + private_state + legal_actions 快照重建 UI。
- 服务端重启后清空房间/对局，客户端需重新创建/加入房间。

### 4.1 REST 错误响应规范（MVP）
统一格式（与 WS ERROR 对齐）：
```json
{"code":"", "message":"", "detail":{}}
```
建议状态码：
- 400 参数错误
- 401/403 鉴权失败或非房间成员
- 404 资源不存在（房间/对局不存在）
- 409 业务冲突（房间已满、非自己回合、重复加入）
- 500 服务器内部错误
