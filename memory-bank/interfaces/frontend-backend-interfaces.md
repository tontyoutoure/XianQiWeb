# 前后端接口

## 1. 后端接口设计（REST）

### 1.1 Auth
- POST `/api/auth/register`
  - body: {"username":"", "password":""}
- POST `/api/auth/login`
  - body: {"username":"", "password":""}
  - resp: {"token":"", "user":{...}}
- GET `/api/auth/me`

### 1.2 Rooms
- GET `/api/rooms`
  - resp: [{id, name, status, players, ready_count}]
- POST `/api/rooms`
  - body: {"name":""}
- POST `/api/rooms/{room_id}/join`
- POST `/api/rooms/{room_id}/leave`
- POST `/api/rooms/{room_id}/ready`
  - body: {"ready": true/false}
- GET `/api/rooms/{room_id}`
  - resp: room + members + status

### 1.3 Games / Actions / Reconnect
- GET `/api/games/{game_id}/state`
  - resp: {"public_state":{}, "private_state":{...}, "legal_actions": {...}}
- POST `/api/games/{game_id}/actions`
  - body: {"type":"PLAY|COVER|BUCKLE|REVEAL|PASS_REVEAL", "payload":{...}}
- GET `/api/games/{game_id}/settlement`
  - resp: result_json
- POST `/api/games/{game_id}/continue`
  - body: {"continue": true/false}

简化做法：也可用 `/api/rooms/{room_id}/actions` 由后端定位当前 game_id。

## 2. WebSocket 协议

### 2.1 通道
- `/ws/lobby`：大厅房间列表更新。
- `/ws/rooms/{room_id}`：房间与对局公共消息（含开始/结算）。

### 2.2 消息结构
```json
{
  "type": "ROOM_LIST|ROOM_UPDATE|GAME_PUBLIC_STATE|GAME_PRIVATE_STATE|SETTLEMENT|ERROR",
  "payload": {}
}
```

### 2.3 关键消息
- ROOM_LIST：推送房间列表刷新。
- ROOM_UPDATE：成员/就绪/状态变化。
- GAME_PUBLIC_STATE：公共状态快照（不含他人手牌，适合旁观/观战）。
- GAME_PRIVATE_STATE：仅发给单连接的私有快照（手牌、已垫棋子、legal_actions）。
- SETTLEMENT：结算结果。

私有状态默认通过 WS 单连接私发；断线重连或兜底则通过 HTTP 拉取。

## 3. 前端数据契约（页面字段）

### 3.1 登录页
- username / password

### 3.2 大厅
- room_id, room_name, status, player_count, ready_count

### 3.3 房间
- members: [{user_id, username, seat, ready}]
- room_status
- actions: ready / leave

### 3.4 对局
- 公共：
  - current_player, round_index, last_combo
  - each player: captured_count, remaining_cards_count
- 私有：
  - hand (cards)
  - action_hints (allowed_actions, must_cover_count, must_beat_combo)

### 3.5 结算
- per player: captured柱数, is_enough, is_ceramic, chip_change
- reveal/buckle relations

## 4. 约束与校验
- 所有动作必须基于后端当前版本号（可选加 version 乐观锁）。
- 服务端为唯一权威；客户端只负责提交意图。
- 断线重连：重新拉取 public_state + private_state + legal_actions 快照重建 UI。
- 服务端重启后清空房间/对局，客户端需重新创建/加入房间。
