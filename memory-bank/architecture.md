# 架构与接口设计（M0）

本文档覆盖 MVP 阶段的总体架构、数据模型、状态机；接口细节见 `memory-bank/interfaces/frontend-backend-interfaces.md` 与 `memory-bank/interfaces/backend-engine-interface.md`。

## 术语表（中英对照）
中文|English
---|---
房间|Room
对局|Game
回合|Round
回合起始玩家|Round Starter
回合收束|Round Closure
出棋|Play
垫棋|Cover
扣棋|Buckle
掀棋|Reveal
活跃掀棋者|Active Revealer
待询问顺序|Pending Reveal Order
扣掀决策阶段|buckle-flow phase
回合进行阶段|In-Round Phase
结算|Settlement
柱数|Pillar Count
够棋|Enough
瓷棋|Ceramic
黑棋|Black Chess
掀扣关系|Reveal-Buckle Relation

说明：术语语义与判定口径以 `XianQi_rules.md` 为准；本表仅用于中英文对照与索引。

## 1. 总体架构与依赖方向
- 前端（Vue3 + TS）：只做展示与交互，所有规则判定与状态演进在后端/引擎完成。
- 后端（FastAPI + 内存状态管理 + SQLite）：
  - 负责鉴权、房间/成员管理、WebSocket 推送、调用规则引擎并维护内存态。
  - 内存态（Room/Game/快照）作为唯一权威状态源，服务端重启即清空。
- 逻辑引擎（纯 Python 模块）：
  - 不依赖 Web/DB；以对象形式维护对局状态，接收动作（`action_idx` + `cover_list`）并输出状态快照。
- 数据库（SQLite）：
  - 仅存储用户账户与鉴权数据（MVP）。

依赖方向：前端 → 后端 → 逻辑引擎；后端 → 数据库。

## 2. 数据模型草图（SQLite，仅 users + refresh_tokens）
仅 MVP 必要字段，字段名可在实现阶段微调，但语义需一致。

约定：所有主键 id 使用 SQLite 的 `INTEGER PRIMARY KEY`（64 位整型），不规定位数。

### 2.1 users
用途：存储账户与鉴权信息。
- id (PK)
- username (unique)
- password_hash
- created_at

### 2.2 refresh_tokens
用途：存储 refresh token（可撤销）。
- id (PK)
- user_id (FK -> users.id)
- token_hash (unique)
- expires_at
- created_at
- revoked_at (nullable)

### 2.3 内存态数据结构（不持久化）
用途：房间、对局与快照全部存于内存，断线重连直接下发最新快照；服务端重启会清空所有房间与对局。

建议内存结构（字段名可实现时调整）：
- rooms：{id, owner_id, status, created_at, updated_at}
- room_members：{room_id, user_id, seat_index, is_ready, is_active, joined_at, left_at}
- games：{id, room_id, status, rng_seed, first_player_id, settlement_json, started_at, ended_at}
- game_players：{game_id, user_id, seat_index, hand_json, captured_pillar_count}
- game_state_snapshots：{game_id, version, public_state_json, private_state_json_map, created_at}

说明：MVP 仅保留快照；如需调试可额外维护轻量日志，但不作为协议内容。

## 3. 状态机定义

### 3.1 房间状态
- waiting：未满 3 人或有人未就绪。
- playing：已开局，对局进行中。
- settlement：单局结算展示阶段。

状态流转：
waiting → playing → settlement →（玩家选择继续）waiting 或直接创建新局

状态映射（建议）：
- engine.phase = init / buckle_flow / in_round → games.status = in_progress
- engine.phase = settlement → games.status = settlement
- engine.phase = finished → games.status = finished
- rooms.status：当前房间有 `games.status = in_progress` 则为 playing；有 `games.status = settlement` 则为 settlement；否则为 waiting

### 3.2 引擎规则状态机引用（SSOT）
- 引擎规则状态机、动作合法性、状态转移与结算触发：以 `XianQi_rules.md` 为唯一事实来源（SSOT）。
- 引擎实现层模块拆分、执行流程、异常口径与联调约定：见 `memory-bank/design/engine_design.md`。

## 4. 接口文档
接口细节已拆分为独立文档：
- 前后端接口：memory-bank/interfaces/frontend-backend-interfaces.md
- 后端对局引擎接口：memory-bank/interfaces/backend-engine-interface.md
