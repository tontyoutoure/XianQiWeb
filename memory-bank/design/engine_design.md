# 对局引擎详细设计文档

本文档聚焦 M3（逻辑引擎核心规则）的实现设计，重点说明 `memory-bank/interfaces/backend-engine-interface.md` 中各对外接口在引擎内部的执行逻辑、校验链路与状态推进方式。

## 0. 范围与基线
- 文档范围：三人 MVP 掀棋规则；不包含额外规则（掀瓷包瓷、抱头等）。
- 状态机基线：`init -> buckle_flow -> in_round -> settlement -> finished`。
- 接口基线：`init_game / apply_action / settle / get_public_state / get_private_state / get_legal_actions / dump_state / load_state`。
- 一致性文档：
  - `memory-bank/architecture.md`
  - `memory-bank/product-requirements.md`
  - `memory-bank/interfaces/backend-engine-interface.md`
  - `XianQi_rules.md`
- 兼容策略（本轮变更）：立即切换不兼容。`load_state` 仅接受新 schema，不再兼容 `buckle_decision / reveal_decision / decision` 旧字段。

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
  cli.py                 # 本地命令行对局入口（单机三座次轮流操作）
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

### 3.1 状态定义来源（单一真源）
- 完整 `state` 结构、字段注释与示例以 `memory-bank/interfaces/backend-engine-interface.md` 第 `1.3` 节为准（唯一真源）。
- 本文仅描述实现推进逻辑与不变量，不再重复维护一份完整状态 schema。
- 本文会引用以下关键字段：`state.version`、`state.phase`、`state.turn`、`state.reveal`、`state.pillar_groups`、`state.players[*].hand`。

### 3.2 全局不变量
- 三名玩家手牌总和 + `pillar_groups` 中卡牌总和 = 24。
- 同一回合内所有 `plays` 的总张数一致（都等于 `round_kind`）。
- `last_combo` 只记录本轮最大非垫牌组合（`power >= 0`）。
- “当前谁在决策”统一由 `turn.current_seat` 表达；引擎内不再维护 `decision` 字段。
- `round_kind = 0` 仅允许在“本轮首手尚未打出”时出现（`buckle_flow`，或 `in_round` 且 `turn.plays` 为空）。
- `phase != buckle_flow` 时，`reveal.pending_order` 必须为空列表。
- `reveal.pending_order` 非空时，`turn.current_seat` 必须等于 `pending_order[0]`。
- `state.turn` 一致性检查（建议）：
  - `round_kind = 0` 时，`last_combo` 应为 `null`，且 `plays` 应为空数组。
  - `round_kind > 0` 时，`plays` 每条记录的总张数必须等于 `round_kind`。
  - `last_combo != null` 时，`last_combo.owner_seat` 必须出现在当前回合 `plays` 中。

### 3.3 `buckle_flow` 子流程定义（新增）
`buckle_flow` 统一承载两类决策：
1. **回合起始决策**：`pending_order=[]`，当前位仅可 `BUCKLE / PASS_BUCKLE`。
2. **扣后询问掀棋**：`pending_order!=[]`，当前位仅可 `REVEAL / PASS_REVEAL`。

## 4. 对外接口实现逻辑

### 4.1 `init_game(config, rng_seed?) -> output`
#### 4.1.1 输入与校验
- 校验 `config.player_count == 3`。
- 校验初始筹码、规则开关等参数满足 MVP 约束。
- `rng_seed` 有值则固定随机源，无值则系统随机。

#### 4.1.2 执行步骤
1. 构建 24 张牌堆并洗牌。
2. 逆时针发牌（每人 8 张），生成 `players[].hand`。
3. 判定黑棋：任一玩家若 `SHI+XIANG` 为 0，直接进入 `settlement`。
4. 若非黑棋，随机先手 seat，进入 `buckle_flow`。
5. 初始化 `turn`：`round_index=0`，`round_kind=0`，`plays=[]`，`last_combo=null`，`current_seat=先手`。
6. 初始化 `reveal`：`buckler_seat=null`，`active_revealer_seat=null`，`pending_order=[]`，`relations=[]`。
7. 输出统一 `output`（含 public/private/legal_actions）。

#### 4.1.3 状态变化
- 新建状态后 `version=1`。
- 黑棋场景可在首次 `settle()` 后进入 `finished`。

### 4.2 `apply_action(action_idx, cover_list=None, client_version=None) -> output`

#### 4.2.1 公共校验链路（所有 phase 通用）
1. `phase` 必须允许动作（`finished/settlement` 禁止）。
2. 若传 `client_version`，必须等于 `state.version`。
3. 由当前 `state` 计算 `legal_actions(turn.current_seat)`。
4. 校验 `action_idx` 在范围内，取出目标动作 `target_action`。
5. 校验 `cover_list`：
   - `target_action.type != COVER` 时必须为空/`null`。
   - `target_action.type == COVER` 时必须存在且总张数等于 `required_count`。
   - 所选牌必须在当前行动玩家手牌中可扣减。

#### 4.2.2 分阶段执行

##### 4.2.2.1 A. `phase=buckle_flow` 且 `pending_order=[]`（回合起始决策）
- `PASS_BUCKLE`：
  1. `phase -> in_round`。
  2. 保持 `turn.current_seat` 为回合起始玩家，等待该玩家打出首手。
  3. `turn.round_kind=0`、`turn.plays=[]`、`turn.last_combo=null`。
- `BUCKLE`：
  1. 记录 `reveal.buckler_seat = turn.current_seat`。
  2. 计算 `pending_order`：
     - 若 `active_revealer_seat != null`，则从该 seat 开始询问；
     - 否则从扣棋者下一位（逆时针）开始。
  3. `turn.current_seat = pending_order[0]`，保持 `phase=buckle_flow` 进入扣后询问子流程。

##### 4.2.2.2 B. `phase=buckle_flow` 且 `pending_order!=[]`（扣后询问掀棋）
- `REVEAL`：
  1. 新增关系 `{revealer_seat, buckler_seat, revealer_enough_at_time}`。
  2. `revealer_enough_at_time` 由该玩家当前柱数（>=3）计算。
  3. `active_revealer_seat = revealer_seat`。
  4. 命中首个 `REVEAL` 后立即结束本次询问：`pending_order=[]`。
  5. `phase -> in_round`，`turn.current_seat = buckler_seat`，并初始化本轮首手前态（`round_kind=0, plays=[], last_combo=null`）。
- `PASS_REVEAL`：
  1. 若当前 seat 等于 `active_revealer_seat`，先将 `active_revealer_seat = null`。
  2. 从 `pending_order` 弹出当前 seat。
  3. 若仍有待询问玩家：`turn.current_seat = pending_order[0]`，保持 `phase=buckle_flow`。
  4. 若已无人可询问：`pending_order=[]`，`phase -> settlement`。

##### 4.2.2.3 C. `phase=in_round`
- `PLAY`（出首手或压制）：
  1. 若 `round_kind=0`，这是本轮首手：设置 `round_kind = 张数(1/2/3)`。
  2. 若 `round_kind>0`，组合张数必须等于 `round_kind`，且 `power > last_combo.power`。
  3. 扣减手牌，写入 `turn.plays`，更新 `turn.last_combo`。
- `COVER`（垫牌）：
  1. 仅允许在 `round_kind>0` 且“无可压制组合”时出现于合法动作。
  2. 从 `cover_list` 扣减手牌。
  3. 写入 `turn.plays`，`power=-1`。
  4. 不改写 `last_combo`。
- 当 `turn.plays` 达到 3 人后触发回合结算：
  1. `last_combo.owner_seat` 获得本回合 `plays`，写入 `pillar_groups`。
  2. 定义 `winner_seat = last_combo.owner_seat`，下一回合由 `winner_seat` 决策：`phase -> buckle_flow`。
  3. `round_index + 1`，并清空 `round_kind/plays/last_combo`（置初始态）。
  4. `turn.current_seat = winner_seat`。
  5. 清空本次扣后询问残留：`reveal.buckler_seat=null`，`reveal.pending_order=[]`。

#### 4.2.3 成功收尾（统一）
- 动作成功后 `state.version += 1`。
- 重新计算 `public_state/private_state_by_seat/legal_actions`。
- 若新 `phase` 为 `settlement`，可在 output 附带预结算快照（不改变 `phase`）。

### 4.3 `settle() -> output`

#### 4.3.1 调用前置
- 必须 `phase == settlement`，否则拒绝。

#### 4.3.2 结算步骤
1. 基于 `pillar_groups` 统计每位玩家当前柱数（`pillar_count`）。
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

### 4.4 `get_public_state() -> public_state`
- 从内部状态投影公共字段，隐藏他人手牌与垫牌牌面。
- `players[*].hand_count` 来自手牌计数和。
- `plays`/`pillar_groups` 中 `power=-1` 的记录改为 `covered_count`。
- 当前决策位统一由 `turn.current_seat` 表示，不输出 `decision`。

### 4.5 `get_private_state(seat) -> private_state`
- 校验 `seat` 在 `0..2`。
- 返回该 seat：
  - `hand`（完整计数表）。
  - `covered`（本人历史垫牌计数表）。
- 不返回其他 seat 私有信息。

### 4.6 `get_legal_actions(seat) -> legal_actions`
- 若 `seat != turn.current_seat`，固定返回 `{"seat": seat, "actions": []}`（不抛错）。
- `phase in {settlement,finished}`：返回空动作。
- `phase=buckle_flow`：
  - `pending_order=[]`：仅 `BUCKLE` 与 `PASS_BUCKLE`。
  - `pending_order!=[]`：仅 `REVEAL` 与 `PASS_REVEAL`。
- `phase=in_round`：
  - `round_kind=0`：仅输出所有合法首手 `PLAY`。
  - `round_kind>0` 且存在可压制组合：仅输出所有可压制 `PLAY`（即 `power > last_combo.power`）。
  - `round_kind>0` 且不存在可压制组合：仅输出 `COVER(required_count=round_kind)`。
- 顺序稳定性要求：
  - 动作类型按引擎固定顺序输出；
  - PLAY 内部排序规则：先按单/双/三（`round_kind`）分组，再按牌力降序；同级下 `R_GOU` 在 `R_CHE` 前、`B_GOU` 在 `B_CHE` 前、`dog_pair` 在 `R_SHI` 对前（用于保证 `action_idx` 稳定）。

### 4.7 `dump_state() / load_state(state)`
- `dump_state`：返回可 JSON 序列化的完整内部状态（含 reveal 关系、垫牌明细、version）。
- `load_state`：
  1. 校验 schema 完整性与字段取值范围（新 schema）。
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
- 对子：狗脚对 = 红士对 > 黑士对 > 其余同类对子。
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
    - 示例 1：`phase in {settlement, finished}` 时调用 `apply_action`。
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
  - `PASS_BUCKLE -> in_round` 后，`round_kind=0` 且首手仅可 PLAY。
  - `BUCKLE` 后询问顺序正确（活跃掀棋者优先，否则逆时针）。
  - `PASS_REVEAL` 才继续推进 `pending_order`；首个 `REVEAL` 命中后立即结束询问并切回扣棋方。
  - 当活跃掀棋者选择 `PASS_REVEAL` 时，`active_revealer_seat` 被清空。
- `settle`：够/瓷/掀棋惩罚与“已够时掀棋未瓷不收够棋”边界。
- `dump/load`：序列化后再恢复，三类输出（public/private/legal）一致。

## 9. 命令行对局接口（新增设计需求）

### 9.1 目标与边界
- 目标：提供 `engine` 本地 CLI，让单个人在命令行中按座次（seat0→seat1→seat2）依次扮演三名玩家，完整推进一局对局。
- 边界：该 CLI 仅用于本地调试与规则验证，不替代后端 REST/WS 协议。
- 一致性：CLI 只调用引擎公开接口（`init_game / get_public_state / get_private_state / get_legal_actions / apply_action / settle`），不直接改内部状态。

### 9.2 启动方式与随机种子
- 建议入口：`python -m engine.cli [--seed 123456]`。
- `--seed` 可选：
  - 传入：使用给定 seed 初始化，保证可复现。
  - 不传：使用当前时间戳（建议毫秒或纳秒）作为 seed。
- 启动后必须打印“本局实际 seed”，便于复盘和复测。

### 9.3 交互主循环（单人扮演三座次）
1. 初始化引擎并创建新局（`init_game`）。
2. 每个回合先展示公共态摘要：
   - `version / phase / turn.current_seat / round_index / round_kind / last_combo / 当前回合plays`。
   - 三名玩家的 `hand_count`；如需柱数，基于 `pillar_groups` 现场推导并展示。
3. 根据 `turn.current_seat` 提示“当前请扮演 seatX 操作”。
4. 仅展示当前 seat 的私有态：
   - `hand`（完整）。
   - `covered`（若已实现）。
5. 展示该 seat 全部合法动作（包含 `action_idx`）：
   - PLAY：显示牌型、`payload_cards`、`power`。
   - COVER：显示 `required_count`，并提示输入 `cover_list`。
   - BUCKLE / PASS_BUCKLE / REVEAL / PASS_REVEAL：显示动作名。
6. 用户输入动作并执行：
   - 非 COVER：输入 `action_idx` 即可。
   - COVER：先选 `action_idx`，再输入 `cover_list`（如 `R_SHI:1,B_NIU:1`）。
7. 调用 `apply_action`，成功后进入下一轮循环；失败则展示错误码并重试。
8. 当 `phase=settlement`：
   - 若 `settle` 已实现，提示执行结算（或默认自动 `settle`）。
   - 若 `settle` 未实现，提示“结算阶段已到达，当前版本未实现 settle”，并结束本次演练。
9. 当 `phase=finished`，打印结束信息并退出。

### 9.4 显示与隐私口径
- 默认仅展示当前决策 seat 的私有手牌；其余 seat 只显示公共信息。
- 对 `power=-1` 的垫牌记录，公共展示用 `covered_count` 或“垫X张”文案，不展示牌面细节。
- 为便于单人三座次调试，可提供显式调试命令（如 `:peek seat1`）查看指定私有态；默认关闭，防止误把调试模式当正式口径。

### 9.5 输入格式与错误处理
- 动作输入非法（非数字、越界）：提示并重输，不改状态。
- `cover_list` 解析失败或张数不匹配：提示并重输，不改状态。
- 引擎抛错（如 `ENGINE_VERSION_CONFLICT`、`ENGINE_INVALID_COVER_LIST`）：按原错误码输出，便于直接对照接口文档定位问题。

### 9.6 非功能要求
- 输出顺序稳定：同一状态下动作列表顺序必须与 `get_legal_actions` 返回顺序一致。
- 可复现：日志首行打印 seed，结束时打印“可复现命令”示例（`python -m engine.cli --seed <seed>`）。
- 可测试：CLI 主循环应拆分为可单测函数（解析输入、动作渲染、state 渲染），便于用 pytest + monkeypatch 覆盖关键交互路径。

## 10. 变更记录
- 2026-02-15：创建文档，补充引擎接口实现逻辑、动作校验链路、结算算法口径与后端集成约定。
- 2026-02-17：新增“命令行对局接口”设计（seed 约定、状态展示口径、交互循环与错误处理）。
- 2026-02-17：根据规则澄清完成状态机重构：`buckle_decision/reveal_decision` 合并为 `buckle_flow`，并移除 `decision` 字段，统一以 `turn.current_seat` 表达当前决策位。
