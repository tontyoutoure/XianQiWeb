# 架构与接口设计（M0）

本文档覆盖 MVP 阶段的总体架构、数据模型、状态机、引擎输入/输出、后端接口、WebSocket 协议与前端数据契约。

## 术语表（中英对照）
中文|English
---|---
房间|Room
对局|Game
回合|Round
出棋|Play
垫棋|Cover
扣棋|Buckle
掀棋|Reveal
结算|Settlement
柱数|Pillar Count
够棋|Enough
瓷棋|Ceramic
掀扣关系|Reveal-Buckle Relation

## 1. 总体架构与依赖方向
- 前端（Vue3 + TS）：只做展示与交互，所有规则判定与状态演进在后端/引擎完成。
- 后端（FastAPI + SQLite）：
  - 负责鉴权、房间/成员管理、WebSocket 推送、调用规则引擎并持久化状态。
  - 作为唯一权威状态源。
- 逻辑引擎（纯 Python 模块）：
  - 不依赖 Web/DB；输入是动作与当前状态，输出是新状态与事件。
- 数据库（SQLite）：
  - 存储用户、房间、对局、事件、结算与快照。

依赖方向：前端 → 后端 → 逻辑引擎；后端 → 数据库。

## 2. 数据模型草图（SQLite）
仅 MVP 必要字段，字段名可在实现阶段微调，但语义需一致。

约定：所有主键 id 使用 SQLite 的 `INTEGER PRIMARY KEY`（64 位整型），不规定位数。

### 2.1 users
用途：存储账户与鉴权信息。
- id (PK)
- username (unique)
- password_hash
- created_at

### 2.2 rooms
用途：游戏房间的基础信息与状态。
- id (PK)
- name
- owner_id (FK users.id)
- status (waiting | playing | settlement)
- created_at
- updated_at

### 2.3 room_members
用途：房间成员关系与座次/就绪状态。
- id (PK)
- room_id (FK rooms.id)
- user_id (FK users.id)
- seat_index (0/1/2, 逆时针固定座次)
- is_ready (bool)
- is_active (bool, 离开后置 false)
- joined_at
- left_at (nullable)

### 2.4 games
用途：单局对局的整体记录与生命周期状态。
- id (PK)
- room_id (FK rooms.id)
- status (init | in_progress | settlement | finished)
  - init：对局已创建但尚未开始（发牌/先手未确定）。
  - in_progress：对局进行中（含出棋/垫棋/扣棋/掀棋流程）。
  - settlement：对局结束进入结算展示阶段，尚未完成筹码确认。
  - finished：结算已确认并落库，等待下一局或房间退出。
- rng_seed (int, 可复盘)
- first_player_id (FK users.id)
- settlement_json (结算结果快照：柱数/够瓷/掀扣关系/筹码变化)
- started_at
- ended_at

### 2.5 game_players
用途：对局内每个玩家的私有数据与统计。
- id (PK)
- game_id (FK games.id)
- user_id (FK users.id)
- seat_index (0/1/2)
- hand_json (私有手牌，JSON)
- captured_pillar_count (已赢得柱数，结算直接使用)

### 2.6 game_state_snapshots
用途：对局状态快照，用于断线重连与回放/排错。
- id (PK)
- game_id (FK games.id)
- version (int, 单调递增)
- public_state_json
- private_state_json_map (按 user_id 映射，仅后端可读)
- created_at

### 2.7 game_events
用途：对局事件流（动作与系统事件），用于回放与历史记录。
- id (PK)
- game_id (FK games.id)
- seq (int, 单调递增)
- actor_user_id (nullable, 系统事件可为空)
- event_type（TBD：事件类型后续统一定义）
- payload_json
- created_at

说明：MVP 先用 JSON 快照/事件，后续再做结构化表拆分。

## 3. 状态机定义

### 3.1 房间状态
- waiting：未满 3 人或有人未就绪。
- playing：已开局，对局进行中。
- settlement：单局结算展示阶段。

状态流转：
waiting → playing → settlement →（玩家选择继续）waiting 或直接创建新局

### 3.2 对局阶段（game phase）
- init：房间三人就绪后创建对局。
- dealing：发牌完成，随机先手。
- in_round：回合进行中（出棋/垫棋）。
- buckle_decision：当前玩家选择扣棋或出棋。
- reveal_decision：其他玩家依规则顺序决定是否掀棋。
- settlement：结算。
- finished：结算完成并记录筹码变化。

注：实现时可把 dealing 合并到 init 或 in_round，关键是动作校验与事件顺序一致。

### 3.3 回合流程（简化）
1) 当前回合起始玩家决定出棋或扣棋。
2) 出棋后，其他玩家依次压制（能压必须压）或垫棋。
3) 回合结束，最大组合玩家获得本轮棋子，更新柱数。
4) 最大组合玩家成为下一回合起始玩家。
5) 选择扣棋触发掀棋决策顺序；无人掀棋则结算。

## 4. 逻辑引擎接口设计

### 4.1 基本约定
- 引擎是一个对象，内部维护当前对局状态（state），对外暴露明确的方法。
- 所有校验在引擎完成（手牌合法性、轮次、必须压制/垫棋等）。
- 引擎内部只使用座次（seat）标识玩家；用户 id 与座次映射由后端维护。

引擎对象建议提供的方法：
- `init_game(config, rng_seed?) -> output`：初始化新局并返回一次输出快照（见 4.5）。
- `apply_action(action_idx, cover_list=None) -> output`：按 `legal_actions` 列表序号执行动作并推进状态，返回输出快照（见 4.5）。
- `settle() -> output`：在 `phase = settlement` 时计算结算并推进到 `finished`，返回输出快照（见 4.5）。
- `get_public_state() -> public_state`：获取当前公共状态（脱敏）。
- `get_private_state(seat) -> private_state`：获取指定 seat 的私有状态。
- `get_legal_actions(seat) -> legal_actions`：获取指定 seat 的合法动作列表（通常为当前行动玩家）。
- `dump_state() -> state`：导出完整内部状态用于持久化/重连。
- `load_state(state)`：从持久化状态恢复引擎。

### 4.2 卡牌与组合表示（不区分实例）
- card_type：如 `R_SHI`, `B_SHI`, `R_XIANG`, `B_XIANG`, `R_MA`, `B_MA`, `R_CHE`, `B_CHE`, `R_GOU`, `B_GOU`, `R_NIU`, `B_NIU`。
- hand 表示为计数表（多重集合）：`{\"R_SHI\": 2, \"B_NIU\": 1, ...}`。
- combo（出棋/垫棋的具体牌面，不含“本轮牌型”）：
  - power: int（按规则计算；垫棋固定为 -1）
  - cards: [{type, count}]
- round_kind（本轮牌型/张数）：
  - 1：single（单张）
  - 2：pair / dog_pair（对子/狗脚对）
  - 3：triple（三牛）

卡牌牌力（单张，数值越大越强）：
|卡牌类型|描述|牌力|
|---|---|---|
|R_SHI|红士|9|
|B_SHI|黑士|8|
|R_XIANG|红相|7|
|B_XIANG|黑象|6|
|R_MA|红马|5|
|B_MA|黑马|4|
|R_CHE|红车|3|
|B_CHE|黑车|2|
|R_GOU|红狗/炮|3（与红车同级）|
|B_GOU|黑狗/炮|2（与黑车同级）|
|R_NIU|红牛/兵|1|
|B_NIU|黑牛/卒|0|
一轮出牌是牌力为-1的时候，代表该轮是垫牌的。

### 4.3 引擎状态结构（建议）
说明：引擎状态为内部完整记录，包含垫棋牌面；对外 public_state 由后端脱敏处理。
```jsonc
{
  "version": 12, // 状态版本号，单调递增，用于乐观锁与重连校验
  "phase": "in_round", // 对局阶段（init / dealing / buckle_decision / in_round / reveal_decision / settlement / finished）
  "players": [
    {
      "seat": 0, // 座次（0/1/2，逆时针）
      "hand": {"R_SHI": 2} // 手牌计数表：card_type -> count
    },
    {"seat": 1, "hand": {"B_NIU": 1}},
    {"seat": 2, "hand": {}}
  ],
  "turn": {
    "current_seat": 0, // 当前该行动的座次
    "round_index": 2, // 第几回合（从0开始）
    "round_kind": 1, // 本轮牌型/张数（1/2/3）
    "last_combo": {
      "power": 9, // 组合强度（按规则计算，垫棋不会改写 last_combo）
      "cards": [{"type": "R_SHI", "count": 1}], // 组合内牌的类型与数量
      "owner_seat": 1 // 当前最大组合所属座次
    },
    "plays": [
      {
        "seat": 1,
        "power": 9,
        "cards": [{"type": "R_SHI", "count": 1}]
      },
      {
        "seat": 2,
        "power": -1,
        "cards": [{"type": "B_NIU", "count": 1}]
      }
    ]
  },
  "pillar_groups": [
    {
      "round_index": 1, // 本棋柱组来源的回合序号（从0开始）
      "winner_seat": 1, // 获得本棋柱组的玩家座次
      "round_kind": 2, // 1/2/3
      "plays": [
        {
          "seat": 1, // 出棋者座次
          "power": 9,
          "cards": [{"type": "R_SHI", "count": 2}] // 出棋的牌
        },
        {
          "seat": 2, // 垫棋者座次
          "power": -1,
          "cards": [{"type": "B_NIU", "count": 2}] // 垫棋牌面（内部记录）
        },
        {
          "seat": 0,
          "power": -1,
          "cards": [{"type": "R_NIU", "count": 2}]
        }
      ]
    }
  ],
  "reveal": {
    "buckler_seat": 0, // 本次扣棋发起人
    "pending_order": [2], // 待决策掀棋的座次顺序
    "relations": [
      {
        "revealer_seat": 1,
        "buckler_seat": 0,
        "revealer_enough_at_time": false // 掀棋当刻是否已够棋
      }
    ] // 掀扣关系（按时间追加）
  }
}
```

### 4.4 动作输入（ActionIndex）
```json
{
  "action_idx": 0,
  "cover_list": [{"type": "B_NIU", "count": 1}]
}
```
说明：
- `action_idx` 为当前 `legal_actions.actions` 的下标（从 0 开始）。
- `cover_list` 仅在 `action_idx` 指向 COVER 时需要，表示实际垫牌牌面；其他动作传 `null`。

### 4.5 引擎输出
- new_state（完整状态，内部用）
- public_state（完整公共快照，前端可直接渲染）
- private_state_by_seat（每个座次的私有快照，仅向本人发送）
- legal_actions（当前应行动玩家的全部合法动作）
- events（事件列表，便于历史记录/回放）
- settlement（结算结果，仅在 `phase = settlement / finished` 时提供；包含完整状态与每个玩家筹码变更）

#### 4.5.1 public_state（脱敏）
```jsonc
{
  "version": 12,
  "phase": "in_round",
  "players": [
    {"seat": 0, "hand_count": 6, "captured_pillar_count": 2},
    {"seat": 1, "hand_count": 6, "captured_pillar_count": 3},
    {"seat": 2, "hand_count": 6, "captured_pillar_count": 3}
  ],
  "turn": {
    "current_seat": 0,
    "round_index": 2,
    "round_kind": 1,
    "last_combo": {
      "power": 9,
      "cards": [{"type": "R_SHI", "count": 1}],
      "owner_seat": 1
    },
    "plays": [
      {"seat": 1, "power": 9, "cards": [{"type": "R_SHI", "count": 1}]},
      {"seat": 2, "power": -1, "covered_count": 1}
    ]
  },
  "pillar_groups": [
    {
      "round_index": 1,
      "winner_seat": 1,
      "round_kind": 2,
      "plays": [
        {"seat": 1, "power": 9, "cards": [{"type": "R_SHI", "count": 2}]},
        {"seat": 2, "power": -1, "covered_count": 2},
        {"seat": 0, "power": -1, "covered_count": 2}
      ]
    }
  ],
  "reveal": {
    "buckler_seat": 0,
    "pending_order": [2],
    "relations": [{"revealer_seat": 1, "buckler_seat": 0, "revealer_enough_at_time": false}]
  }
}
```
- `hand_count`、`captured_pillar_count` 为公开信息；`captured_pillar_count` 可由 `pillar_groups` 推导，但为前端便利提供。
- 垫棋在公共视图中不暴露牌面，使用 `covered_count` 代替 `cards`。

#### 4.5.2 private_state_by_seat
```jsonc
{
  "0": {"hand": {"R_SHI": 2, "B_NIU": 1}},
  "1": {"hand": {"B_NIU": 1}},
  "2": {"hand": {}}
}
```
- 后端仅将对应 seat 的私有状态下发给本人。

#### 4.5.3 legal_actions（仅当前行动玩家）
同一状态下 `actions` 只包含当前阶段合法动作：PLAY 与 COVER 互斥；REVEAL / PASS_REVEAL 仅在 `phase = reveal_decision` 出现。`actions` 需稳定排序：先按 `type` 固定顺序（PLAY -> COVER -> BUCKLE -> REVEAL -> PASS_REVEAL），再按出牌张数，最后按 `card_type` 字符序。

回合进行中示例（可压制或可扣时）：
```jsonc
{
  "seat": 0,
  "actions": [
    {
      "type": "PLAY",
      "payload_cards": [{"type": "R_SHI", "count": 1}]
    },
    {
      "type": "PLAY",
      "payload_cards": [{"type": "B_NIU", "count": 1}]
    },
    {"type": "BUCKLE"},
  ]
}
```
只能垫牌示例：
```jsonc
{
  "seat": 1,
  "actions": [
    {
      "type": "COVER",
      "required_count": 1
    }
  ]
}
```

掀棋决策示例：
```jsonc
{
  "seat": 2,
  "actions": [
    {"type": "REVEAL"},
    {"type": "PASS_REVEAL"}
  ]
}
```
- COVER 仅给出 `required_count`，由前端在手牌中选择任意同张数牌面并通过 `cover_list` 传回，最终由引擎校验合法性。

#### 4.5.4 events（记录/回放）
事件包含最小必要信息：
```jsonc
{"type": "PLAYED", "seat": 1, "round_index": 2, "cards": [{"type": "R_SHI", "count": 1}], "power": 9}
```
事件类型：
  - GAME_STARTED / DEAL_DONE
  - TURN_STARTED
  - PLAYED / COVERED
  - ROUND_ENDED
  - BUCKLED
  - REVEAL_DECISION / REVEALED / REVEAL_PASSED
  - GAME_ENDED / SETTLED

#### 4.5.5 settlement（结算结果）
```jsonc
{
  "final_state": { /* 完整对局状态（未脱敏） */ },
  "chip_delta_by_seat": [
    {
      "seat": 0,
      "delta": -1,
      "delta_enough": 0,
      "delta_reveal": -1,
      "delta_ceramic": 0
    },
    {
      "seat": 1,
      "delta": 2,
      "delta_enough": 1,
      "delta_reveal": 0,
      "delta_ceramic": 1
    },
    {
      "seat": 2,
      "delta": -1,
      "delta_enough": -1,
      "delta_reveal": 0,
      "delta_ceramic": 0
    }
  ]
}
```
- 结算时下发完整状态，便于结果解释（“输家做个明白鬼”）。
- `delta_enough / delta_reveal / delta_ceramic` 分别表示够棋、掀棋、瓷棋导致的筹码变更（加和为 `delta`）。若玩家已够但未瓷且因掀棋而不赢够棋筹码，则 `delta_enough = 0`。

## 5. 后端接口设计（REST）

### 5.1 Auth
- POST `/api/auth/register`
  - body: {"username":"", "password":""}
- POST `/api/auth/login`
  - body: {"username":"", "password":""}
  - resp: {"token":"", "user":{...}}
- GET `/api/auth/me`

### 5.2 Rooms
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

### 5.3 Games / Actions / History
- GET `/api/games/{game_id}/state`
  - resp: {"public_state":{}, "private_state":{...}}
- POST `/api/games/{game_id}/actions`
  - body: {"type":"PLAY|COVER|BUCKLE|REVEAL|PASS_REVEAL", "payload":{...}}
- GET `/api/games/{game_id}/events?since=SEQ`
  - resp: {"events":[...], "latest_seq":123}
- GET `/api/games/{game_id}/settlement`
  - resp: result_json
- POST `/api/games/{game_id}/continue`
  - body: {"continue": true/false}

简化做法：也可用 `/api/rooms/{room_id}/actions` 由后端定位当前 game_id。

## 6. WebSocket 事件协议

### 6.1 通道
- `/ws/lobby`：大厅房间列表更新。
- `/ws/rooms/{room_id}`：房间与对局公共事件（含开始/结算）。

### 6.2 事件结构
```json
{
  "type": "ROOM_LIST|ROOM_UPDATE|GAME_STATE|GAME_EVENT|SETTLEMENT|ERROR",
  "payload": {}
}
```

### 6.3 关键事件
- ROOM_LIST：推送房间列表刷新。
- ROOM_UPDATE：成员/就绪/状态变化。
- GAME_STATE：公共状态快照（不含他人手牌）。
- GAME_EVENT：动作事件流（含时间线）。
- SETTLEMENT：结算结果。

私有状态（手牌/可行动作提示）通过 HTTP 拉取或在 WS 中针对单连接私发。

## 7. 前端数据契约（页面字段）

### 7.1 登录页
- username / password

### 7.2 大厅
- room_id, room_name, status, player_count, ready_count

### 7.3 房间
- members: [{user_id, username, seat, ready}]
- room_status
- actions: ready / leave

### 7.4 对局
- 公共：
  - current_player, round_index, last_combo, history_timeline
  - each player: captured_count, remaining_cards_count
- 私有：
  - hand (cards)
  - action_hints (allowed_actions, must_cover_count, must_beat_combo)

### 7.5 结算
- per player: captured柱数, is_enough, is_ceramic, chip_change
- reveal/buckle relations

## 8. 约束与校验
- 所有动作必须基于后端当前版本号（可选加 version 乐观锁）。
- 服务端为唯一权威；客户端只负责提交意图。
- 断线重连：重新拉取 game_state + events 重建 UI。
