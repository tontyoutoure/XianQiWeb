# 对局引擎详细设计文档

本文档聚焦 M3（逻辑引擎核心规则）的实现设计，重点说明 `memory-bank/interfaces/backend-engine-interface.md` 中各对外接口在引擎内部的执行逻辑、校验链路与状态推进方式。

## 0. 范围与基线
- 文档范围：三人 MVP 掀棋规则；不包含额外规则（掀瓷包瓷、抱头等）。
- 状态机基线：`init -> buckle_decision -> in_round -> reveal_decision -> settlement -> finished`。
- 接口基线：`init_game / apply_action / settle / get_public_state / get_private_state / get_legal_actions / dump_state / load_state`。
- 一致性文档：
  - `memory-bank/architecture.md`
  - `memory-bank/game-design-document.md`
  - `memory-bank/interfaces/backend-engine-interface.md`
  - `XianQi_rules.md`

## 1. 设计目标与原则
- **纯规则内核**：不依赖 FastAPI/数据库，便于单测与复用。
- **状态唯一真源**：所有可观察输出都由内部 `state` 推导，不维护重复真值。
- **确定性输出**：同一状态下 `legal_actions` 顺序稳定，保障 `action_idx` 可复现。
- **先校验后落地**：动作全部校验通过后再写入状态并 `version + 1`。
- **可恢复**：`dump_state/load_state` 可无损恢复（含 reveal 关系与垫牌明细）。

## 2. 模块划分（建议）
```text
engine/
  core.py                # XianqiGameEngine 对外接口实现
  models.py              # 状态结构（dataclass / TypedDict）
  constants.py           # card_type、phase、action_type 常量
  cards.py               # 牌堆构建、发牌、卡牌顺序与牌力
  combos.py              # 组合枚举、组合牌力计算、比较器
  actions.py             # 各 phase 合法动作生成
  reducer.py             # apply_action 的状态推进
  settlement.py          # 够/瓷/掀棋结算
  serializer.py          # state/public/private 输出与 dump/load
  errors.py              # 引擎错误码与异常定义
```

## 3. 核心状态与不变量

### 3.1 关键状态
- `state.version`：动作成功后单调递增。
- `state.phase`：当前阶段。
- `state.players[seat].hand`：手牌计数表。
- `state.turn`：当前回合（`current_seat/round_index/round_kind/last_combo/plays`）。
- `state.decision`：当前“烧时间”的决策位（`seat/context/started_at_ms/timeout_at_ms`）。
- `state.pillar_groups`：已结算回合记录（用于柱数统计与公开回放）。
- `state.reveal`：扣棋方、待决策顺序、掀扣关系。

### 3.2 全局不变量
- 三名玩家手牌总和 + `pillar_groups` 中卡牌总和 = 24。
- 同一回合内所有 `plays` 的总张数一致（都等于 `round_kind`）。
- `round_kind=0` 仅允许出现在 `buckle_decision`。
- `last_combo` 只记录本轮最大非垫牌组合（`power >= 0`）。
- `captured_pillar_count` 必须可由 `pillar_groups` 推导，且每次输出一致。
- `phase in {buckle_decision,in_round,reveal_decision}` 时，`decision.seat` 必须等于当前应决策座次。
- 为兼容既有协议，`turn.current_seat` 与 `decision.seat` 保持一致；前者可视为后者别名。
- `phase in {settlement,finished}` 时，`decision` 允许为空（或 `timeout_at_ms=null` 的非激活态）。

### 3.3 决策态字段定义（新增强调）
```jsonc
{
  "decision": {
    "seat": 1,                   // 当前正在决策（正在消耗操作时间）的玩家
    "context": "IN_ROUND",       // BUCKLE_DECISION | IN_ROUND | REVEAL_DECISION
    "started_at_ms": 1739600000, // 引擎切到该决策位的时间戳（毫秒）
    "timeout_at_ms": null        // MVP 可为空；若后续接入超时机制则写截止时间
  }
}
```
- 若后端未启用超时托管，可仅用 `seat/context` 指示“轮到谁”。  
- 前端倒计时应以 `decision.timeout_at_ms` 为准；为空则展示“轮到某玩家决策”但不显示倒计时。

## 4. 对外接口实现逻辑

### 4.1 `init_game(config, rng_seed?) -> output`
### 输入与校验
- 校验 `config.player_count == 3`。
- 校验初始筹码、规则开关等参数满足 MVP 约束。
- `rng_seed` 有值则固定随机源，无值则系统随机。

### 执行步骤
1. 构建 24 张牌堆并洗牌。
2. 逆时针发牌（每人 8 张），生成 `players[].hand`。
3. 判定黑棋：任一玩家若 `SHI+XIANG` 为 0，直接进入 `settlement`。
4. 若非黑棋，随机先手 seat，进入 `buckle_decision`。
5. 初始化 `turn`：`round_index=0`，`round_kind=0`，`plays=[]`，`last_combo=null`，`current_seat=先手`。
6. 初始化 `decision`：`seat=先手`，`context=BUCKLE_DECISION`，`started_at_ms=now`，`timeout_at_ms=null`。
7. 初始化 `reveal.relations=[]`。
8. 输出统一 `output`（含 public/private/legal_actions）。

### 状态变化
- 新建状态后 `version=1`。
- 黑棋场景可在首次 `settle()` 后进入 `finished`。

### 4.2 `apply_action(action_idx, cover_list=None, client_version=None) -> output`

### 公共校验链路（所有 phase 通用）
1. `phase` 必须允许动作（`finished/settlement` 禁止）。
2. 若传 `client_version`，必须等于 `state.version`。
3. 由当前 `state` 计算 `legal_actions`。
4. 校验 `action_idx` 在范围内，取出目标动作 `target_action`。
5. 校验 `cover_list`：
   - `target_action.type != COVER` 时必须为空/`null`。
   - `target_action.type == COVER` 时必须存在且总张数等于 `required_count`。
   - 所选牌必须在当前行动玩家手牌中可扣减。

### 分阶段执行

#### A. `phase=buckle_decision`
- `PLAY`：
  1. 扣减出牌手牌。
  2. 初始化回合：`round_kind = 张数(1/2/3)`；`plays=[当前出牌]`；`last_combo=当前出牌`。
  3. `current_seat` 切到下一位，`phase -> in_round`。
  4. 刷新 `decision`：`seat=下一位`，`context=IN_ROUND`，`started_at_ms=now`。
- `BUCKLE`：
  1. 记录 `reveal.buckler_seat = current_seat`。
  2. 计算 `pending_order`：若已有历史掀棋者，顺序以“最后掀棋者”为起点按逆时针轮转（跳过 buckler 自身）；否则按逆时针从扣棋者下一位开始。
  3. `phase -> reveal_decision`，`current_seat = pending_order[0]`。
  4. 刷新 `decision`：`seat=pending_order[0]`，`context=REVEAL_DECISION`，`started_at_ms=now`。

#### B. `phase=in_round`
- `PLAY`（压制）：
  1. 组合张数必须等于 `round_kind`。
  2. 组合牌力必须严格大于 `last_combo.power`。
  3. 扣减手牌，写入 `turn.plays`，并更新 `last_combo`。
- `COVER`（垫牌）：
  1. 从 `cover_list` 扣减手牌。
  2. 写入 `turn.plays`，`power=-1`。
  3. 不改写 `last_combo`。
- 当 `turn.plays` 达到 3 人后触发回合结算：
  1. `last_combo.owner_seat` 获得本回合 `plays`，写入 `pillar_groups`。
  2. 下一回合由 winner 决策：`phase -> buckle_decision`。
  3. `round_index + 1`，并清空 `round_kind/plays/last_combo`（置初始态）。
  4. `current_seat = winner_seat`。
  5. 刷新 `decision`：`seat=winner_seat`，`context=BUCKLE_DECISION`，`started_at_ms=now`。

#### C. `phase=reveal_decision`
- `REVEAL`：
  1. 新增一条关系 `{revealer_seat, buckler_seat, revealer_enough_at_time}`。
  2. `revealer_enough_at_time` 由该玩家当前柱数（>=3）计算。
  3. 当前掀棋者成为“最后掀棋者”，供下次扣棋决定顺序使用。
- `PASS_REVEAL`：仅记录该 seat 本次放弃。
- 推进 `pending_order`：
  - 若仍有待决策玩家：`current_seat = 下一位`，保持 `reveal_decision`，并同步刷新 `decision` 到该 seat（`context=REVEAL_DECISION`）。
  - 若已清空：
    - 本轮有人 `REVEAL`：回到 `buckle_decision`，并由“最后掀棋者”先决策出棋/扣棋。
    - 无人 `REVEAL`：`phase -> settlement`。
    - 两个分支都要刷新 `decision`：前者设置到“最后掀棋者”，后者置空（或标记为非激活）。

### 成功收尾（统一）
- 动作成功后 `state.version += 1`。
- 重新计算 `public_state/private_state_by_seat/legal_actions`。
- 若新 `phase` 为 `settlement`，可在 output 附带预结算快照（不改变 `phase`）。

### 4.3 `settle() -> output`

### 调用前置
- 必须 `phase == settlement`，否则拒绝。

### 结算步骤
1. 统计每位玩家 `captured_pillar_count`。
2. 标记身份：
   - `enough`: `3 <= pillar < 6`
   - `ceramic`: `pillar >= 6`
3. 计算 `delta_enough`：
   - 默认规则：每个未够玩家向每个够玩家付 1，向每个瓷玩家付 3。
   - 字段拆分：`够棋付款`计入 `delta_enough`，`瓷棋付款`计入 `delta_ceramic`。
   - 特殊规则：若玩家“已够时掀棋且最终未瓷”，该玩家不收 `delta_enough`（对应接口文档“`delta_enough=0`”口径）。
4. 计算 `delta_reveal`：对每条掀扣关系，若 `revealer_enough_at_time=false` 且该 revealer 最终未够，则 revealer 向 buckler 付 1。
5. `delta = delta_enough + delta_reveal + delta_ceramic`（`delta_ceramic` 可单列或并入 enough 规则实现，但输出需独立字段）。
6. 生成 `settlement.final_state` 与 `chip_delta_by_seat`。
7. `phase -> finished`，`version += 1`。
8. `decision` 置空（`finished` 不再有行动玩家）。

### 4.4 `get_public_state() -> public_state`
- 从内部状态投影公共字段，隐藏他人手牌与垫牌牌面。
- `players[*].hand_count` 来自手牌计数和。
- `players[*].captured_pillar_count` 必须由 `pillar_groups` 即时计算，不缓存脏数据。
- `plays`/`pillar_groups` 中 `power=-1` 的记录改为 `covered_count`。
- 输出包含 `decision`（至少 `seat/context/timeout_at_ms`），用于前端明确“当前谁在决策/谁的时钟在走”。

### 4.5 `get_private_state(seat) -> private_state`
- 校验 `seat` 在 `0..2`。
- 返回该 seat：
  - `hand`（完整计数表）。
  - `covered`（本人历史垫牌计数表）。
- 不返回其他 seat 私有信息。

### 4.6 `get_legal_actions(seat) -> legal_actions`
- 若 `seat != decision.seat`，固定返回 `{\"seat\": seat, \"actions\": []}`（不抛错）。
- `buckle_decision`：枚举当前玩家所有可出组合（PLAY）+ `BUCKLE`。
- `in_round`：
  - 若存在可压制组合，仅输出 `PLAY`（不允许 `COVER`）。
  - 若不存在可压制组合，仅输出 `COVER(required_count=round_kind)`。
- `reveal_decision`：仅输出 `REVEAL` 与 `PASS_REVEAL`。
- 顺序稳定性要求：
  - 先按动作类型固定顺序（示例：PLAY -> COVER -> BUCKLE -> REVEAL -> PASS_REVEAL）。
  - PLAY 内部按“牌力降序 + 牌型字典序”排序。

### 4.7 `dump_state() / load_state(state)`
- `dump_state`：返回可 JSON 序列化的完整内部状态（含 reveal 关系、垫牌明细、version）。
- `load_state`：
  1. 校验 schema 完整性与字段取值范围。
  2. 校验全局不变量（卡牌总数、phase 与 turn 一致性）。
  3. 覆盖当前状态并重建必要索引/缓存。
- 成功后 `get_public_state/get_private_state/get_legal_actions` 结果应与 dump 前一致。

## 5. 合法动作生成与比较规则（实现口径）

### 5.1 组合枚举
- 单张：任意 `count>=1` 的 card_type。
- 对子：同 type 且 `count>=2`；额外允许 `R_GOU + B_GOU` 组成狗脚对。
- 三牛：仅 `R_NIU*3`、`B_NIU*3`。

### 5.2 牌力计算
- 按接口文档牌力表：`R_SHI(9) ... B_NIU(0)`；`R_GOU=3`、`B_GOU=2`。
- 对子：狗脚对 > 红士对 > 黑士对 > 其余同类对子。
- 三张：红三牛 > 黑三牛。

### 5.3 必须压制判定
- `in_round` 下对每个可出组合比较 `combo.power > last_combo.power`。
- 若存在任一满足，legal actions 仅保留这些 `PLAY`；否则只给 `COVER`。

## 6. 错误模型与后端映射建议
- 引擎统一抛业务异常 `{code, message, detail}`，后端透传或映射：
  - `ENGINE_VERSION_CONFLICT` -> HTTP 409
  - `ENGINE_INVALID_ACTION_INDEX` -> HTTP 400
  - `ENGINE_INVALID_COVER_LIST` -> HTTP 400
  - `ENGINE_INVALID_PHASE` -> HTTP 409
  - `ENGINE_INVALID_STATE` -> HTTP 500/409（按触发场景）
- 所有拒绝动作都不得改变状态，也不得增加 `version`。

## 7. 与后端集成约定（M4 前置）
- 后端负责：`user_id <-> seat` 映射、鉴权、房间成员校验。
- 引擎负责：规则合法性与状态演进。
- 推荐调用链：
  1. 后端根据房间找到 seat。
  2. 后端先取 `legal_actions(seat)` 判断是否轮到本人。
  3. 后端调用 `apply_action(action_idx, cover_list, client_version)`。
  4. 后端将 `public_state` 广播全房，将 `private_state_by_seat[seat]` 定向发送。
- 断线恢复：后端存内存快照（`dump_state`），重连时 `load_state` 后按 seat 下发私有态。

## 8. 测试建议（接口行为优先）
- 详细测试清单见 `memory-bank/tests/m3-tests.md`（含组合枚举器与合法动作枚举专项）。
- `init_game`：固定 seed 下发牌与先手可复现；黑棋分支可触发。
- `apply_action`：
  - `action_idx` 稳定性与越界错误。
  - `client_version` 冲突返回。
  - 必须压制/只能垫棋分支。
  - `BUCKLE -> reveal_decision` 顺序正确。
- `settle`：够/瓷/掀棋惩罚与“已够时掀棋未瓷不收够棋”边界。
- `dump/load`：序列化后再恢复，三类输出（public/private/legal）一致。

## 9. 变更记录
- 2026-02-15：创建文档，补充引擎接口实现逻辑、动作校验链路、结算算法口径与后端集成约定。
- 2026-02-15：补充 `decision` 决策态定义，明确“当前谁在决策/谁的计时在走”的状态字段与阶段切换更新规则。
