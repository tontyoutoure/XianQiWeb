# M3 阶段测试列表（对局引擎核心规则）

> 依据文档：`memory-bank/implementation-plan.md`（M3）、`memory-bank/interfaces/backend-engine-interface.md`、`memory-bank/design/engine_design.md`、`XianQi_rules.md`。
> 目标：先固化 M3 TDD 测试清单，再按“人类指定测试ID -> 编写测试 -> 红绿推进”执行。

## 0) 测试运行环境与执行约定

- 建议环境：conda `XQB`。
- 建议命令：`conda run -n XQB pytest engine/tests -q`。
- 约定：M3 优先做引擎纯单测（不依赖后端 API）。
- 本文档用于记录每个测试用例的 Red/Green 结果。

## 1) 引擎基础能力测试

| 测试ID | 测试描述 | 通过条件 |
|---|---|---|
| M3-UT-01 | `init_game` 发牌总量与每人手牌张数 | 三人总牌数恒为 24；每人起手 8 张 |
| M3-UT-02 | `init_game` 固定 seed 可复现 | 相同 `rng_seed` 下发牌结果、先手 seat 一致 |
| M3-UT-03 | 黑棋判定 | 任一玩家起手无士/相时，`phase` 直接进入 `settlement` |
| M3-UT-04 | 状态版本号递增规则 | 动作成功后 `version +1`；非法动作不改变 `version` |
| M3-UT-05 | `dump_state/load_state` 一致性 | dump 后 load，`public/private/legal_actions` 与 dump 前一致 |
| M3-UT-06 | `get_public_state` 脱敏投影 | 仅返回公共字段：`players[*].hand_count`（不含 `hand`），`power=-1` 的记录改为 `covered_count`，且不输出 `decision` |
| M3-UT-07 | `get_private_state` 私有态投影 | 仅返回目标 seat 的 `hand/covered`，其中 `covered` 为该 seat 历史垫牌计数聚合 |
| M3-UT-08 | `load_state` seat 索引一致性断言 | `players` 非 seat 索引顺序时快速失败（抛断言异常） |

## 2) 组合枚举器测试（重点细化）

| 测试ID | 测试描述 | 通过条件 |
|---|---|---|
| M3-CB-01 | 单张枚举（去重） | 同一 `card_type` 只产出 1 个单张组合，不受该类型 `count` 影响 |
| M3-CB-02 | 同型对子枚举 | 当某 `card_type.count >= 2` 时产出该类型对子；`count < 2` 不产出 |
| M3-CB-03 | 狗脚对枚举（R_GOU+B_GOU） | 仅当 `R_GOU>=1 且 B_GOU>=1` 时产出 `dog_pair` |
| M3-CB-04 | 狗脚对互斥去重 | 狗脚对只产出 1 条，不因枚举顺序产生重复项 |
| M3-CB-05 | 三牛枚举（红/黑） | 仅当 `R_NIU>=3` 产出红三牛；仅当 `B_NIU>=3` 产出黑三牛 |
| M3-CB-06 | 非法三张不应产出 | 非牛三张、混色三张都不会进入组合枚举结果 |
| M3-CB-07 | 对子牌力顺序 | `dog_pair = 红士对 > 黑士对 > 其他对子`，排序稳定 |
| M3-CB-08 | 三张牌力顺序 | 红三牛 > 黑三牛 |
| M3-CB-09 | 单张牌力顺序 | 满足接口文档牌力表（`R_SHI` 最高，`B_NIU` 最低） |
| M3-CB-10 | 组合排序稳定性 | 同一手牌多次调用枚举，输出顺序完全一致 |
| M3-CB-11 | 按 `round_kind` 过滤 | 指定 `round_kind=1/2/3` 时仅返回对应张数组合 |
| M3-CB-12 | 严格大于比较 | 压制判定只接受 `power > last_combo.power`，`=` 不可压制 |
| M3-CB-13 | 红狗与红车单张等价牌力 | `R_GOU` 单张 `power` 必等于 `R_CHE` |
| M3-CB-14 | 黑狗与黑车单张等价牌力 | `B_GOU` 单张 `power` 必等于 `B_CHE` |

## 3) 合法动作枚举测试（重点细化）

| 测试ID | 测试描述 | 通过条件 |
|---|---|---|
| M3-LA-01 | `buckle_decision` 动作集合 | 仅包含 `PLAY` 与最多 1 个 `BUCKLE` |
| M3-LA-02 | `buckle_decision` 的 PLAY 完整性 | 所有可出的单张/对子/三牛均被覆盖，无遗漏 |
| M3-LA-03 | `buckle_decision` 排序稳定 | 多次调用 `get_legal_actions`，`actions` 顺序一致 |
| M3-LA-04 | `in_round` 可压制时互斥规则 | 若存在可压制组合，仅返回 `PLAY`，不返回 `COVER` |
| M3-LA-05 | `in_round` 不可压制时互斥规则 | 若无可压制组合，仅返回 1 个 `COVER(required_count=round_kind)` |
| M3-LA-06 | `COVER.required_count` 正确 | `required_count` 必等于当前 `round_kind` |
| M3-LA-07 | `in_round` 压制集合正确性 | 返回的 PLAY 全部可压制且不包含不可压制组合 |
| M3-LA-08 | 非当前行动 seat 的动作 | `seat != turn.current_seat` 时返回空 `actions` |
| M3-LA-09 | `reveal_decision` 动作集合 | 仅包含 `REVEAL` 与 `PASS_REVEAL` |
| M3-LA-10 | `settlement/finished` 无动作 | `get_legal_actions` 返回空 `actions` |
| M3-LA-11 | `action_idx` 稳定性 | 同一状态多次获取 `actions`，索引含义不漂移 |
| M3-LA-12 | phase 切换后动作刷新 | `apply_action` 后下一状态的 `actions` 与新 `turn.current_seat` 一致 |
| M3-LA-13 | `buckle_decision` 下 PLAY 组合全集覆盖 | PLAY 必须覆盖单张/对子/狗脚对/三牛全部可出组合 |
| M3-LA-14 | `buckle_decision` PLAY 与组合枚举一致性 | PLAY 的 `payload_cards` 与 `enumerate_combos` 结果一一对应 |
| M3-LA-15 | `in_round` 单张可压制全集 | 仅返回所有 `power > last_combo.power` 的单张 PLAY |
| M3-LA-16 | `in_round` 对子可压制全集（含狗脚对） | 返回所有可压制对子 PLAY，且包含狗脚对压制场景 |
| M3-LA-17 | `in_round` 对子严格大于边界 | `power == last_combo.power` 的对子不得出现在 PLAY 列表 |
| M3-LA-18 | `in_round` 三牛可压制全集 | 仅返回可压制三牛 PLAY，黑三牛不可压制红三牛 |
| M3-LA-19 | `in_round` PLAY 张数与 `round_kind` 一致 | 所有 PLAY 的牌张总数都必须等于 `round_kind` |
| M3-LA-20 | `in_round` 单张去重 | 同一 `card_type` 即使 `count>1`，PLAY 单张也只出现一次 |
| M3-LA-21 | `buckle_decision` PLAY 顺序稳定性（扩展） | 连续多次获取动作，PLAY 组合顺序完全一致 |
| M3-LA-22 | `in_round` PLAY 顺序稳定性（扩展） | 连续多次获取动作，PLAY 组合顺序完全一致 |

## 4) 动作执行与校验补充测试

| 测试ID | 测试描述 | 通过条件 |
|---|---|---|
| M3-ACT-01 | `action_idx` 越界 | 引擎返回 `ENGINE_INVALID_ACTION_INDEX` |
| M3-ACT-02 | `client_version` 冲突 | 引擎返回 `ENGINE_VERSION_CONFLICT` |
| M3-ACT-03 | 非 COVER 传 `cover_list` | 引擎拒绝并返回 `ENGINE_INVALID_COVER_LIST` |
| M3-ACT-04 | COVER 传错张数 | `cover_list` 总张数不等于 `required_count` 时拒绝 |
| M3-ACT-05 | COVER 传不存在手牌 | `cover_list` 超出持牌时拒绝 |
| M3-ACT-06 | 回合结束后行动位推进 | 3 人出完后 `turn.current_seat` 切到 round winner |
| M3-ACT-07 | 掀棋顺序推进 | `reveal.pending_order` 消费与 `turn.current_seat` 推进一致 |
| M3-ACT-08 | 一轮结束后棋柱归属 | `pillar_groups` 新增记录且 `winner_seat` 等于本轮最大组合玩家 |
| M3-ACT-09 | 对子回合分柱拆分 | `round_kind=2` 时新增 2 柱，且同一对（如 `R_SHI` 对）拆到不同柱 |
| M3-ACT-10 | 三牛回合分柱拆分 | `round_kind=3` 时新增 3 柱，且三张同型牛分散到 3 根柱 |

### 4.1 命令行交互测试（新增需求）

| 测试ID | 测试描述 | 通过条件 |
|---|---|---|
| M3-CLI-01 | 显式 seed 启动可复现 | 相同 `--seed` 启动两次，首帧公共态（含先手/手牌分布）一致 |
| M3-CLI-02 | 未传 seed 时自动取时间 | 不传 `--seed` 启动，CLI 输出实际 seed 且可用于复现 |
| M3-CLI-03 | 轮转扮演三座次 | 每一步提示当前 `turn.current_seat`，并按 seat0/1/2 轮转推进 |
| M3-CLI-04 | 状态展示口径 | 每步展示公共态摘要 + 当前 seat 私有态；不默认泄露其他 seat 私有态 |
| M3-CLI-05 | 合法动作列表与索引 | CLI 按 `get_legal_actions` 顺序展示全部动作，`action_idx` 可直接提交 |
| M3-CLI-06 | COVER 输入链路 | 选择 COVER 后可输入 `cover_list`，张数/持牌非法时提示并重试 |
| M3-CLI-07 | 动作执行失败重试 | 非法输入或引擎错误（如 `ENGINE_INVALID_ACTION_INDEX`）不改状态并可重选 |
| M3-CLI-08 | 对局结束行为 | 到 `settlement/finished` 时能给出明确提示并结束（或触发 `settle` 流程） |

### 4.2 `apply_action` 重构等效性测试（reducer 拆分）

| 测试ID | 测试描述 | 通过条件 |
|---|---|---|
| M3-RF-01 | `core.apply_action` 委托 reducer | `engine.core` 的 `apply_action` 通过 `engine.reducer.reduce_apply_action` 推进状态，且返回结构保持 `{"new_state": ...}` |
| M3-RF-02 | reducer 成功路径等效 | 典型成功动作（如 `COVER` 收轮）后的 `phase/turn/pillar_groups/version` 与拆分前一致 |
| M3-RF-03 | reducer 失败路径等效 | 越界 `action_idx`、版本冲突、非法 `cover_list` 仍返回原错误码，失败不改 `version` |

## 5) 阶段通过判定（M3）

- 组合枚举与牌力比较规则完整可测，且顺序稳定。
- 合法动作生成满足 phase 约束与互斥规则（PLAY/COVER、REVEAL/PASS_REVEAL）。
- `action_idx + cover_list + client_version` 三条核心校验链路均有红绿覆盖。
- 当前行动位统一由 `turn.current_seat` 表达，并在每次状态推进后保持一致。
- 回合结算入柱后，棋柱归属与分柱规则（对子/三牛拆柱）可验证且稳定。
- CLI 可在命令行中按当前行动座次推进一局，并稳定展示公共态/私有态与合法动作。

## 6) Mock 数据与预期（审查版）

### 6.1 组合枚举器（M3-CB）审查样例

| 测试ID | Mock 输入（显式） | 预期结果（显式） |
|---|---|---|
| M3-CB-01 | `hand={"R_SHI":2,"B_NIU":1}`，`round_kind=null` | 至少包含 `R_SHI` 单张、`B_NIU` 单张、`R_SHI` 对子；同牌型不重复 |
| M3-CB-02 | `hand={"R_SHI":1,"R_MA":2,"B_NIU":1}`，`round_kind=2` | 包含 `R_MA` 对子；不包含 `R_SHI` 对子、不包含 `B_NIU` 对子 |
| M3-CB-03 | 子场景A：`{"R_GOU":1,"B_GOU":1}`；子场景B：`{"R_GOU":1,"B_GOU":0}`，均 `round_kind=2` | A 包含狗脚对；B 不包含狗脚对 |
| M3-CB-04 | `hand={"R_GOU":1,"B_GOU":1}`，`round_kind=2` | 狗脚对仅出现 1 次（无重复） |
| M3-CB-05 | 子场景A：`{"R_NIU":3,"B_NIU":2}`；子场景B：`{"R_NIU":2,"B_NIU":3}`，`round_kind=3` | A 仅红三牛；B 仅黑三牛 |
| M3-CB-06 | `hand={"R_SHI":2,"R_NIU":2,"B_NIU":1}`，`round_kind=3` | 不返回任何三张组合 |
| M3-CB-07 | `hand={"R_GOU":1,"B_GOU":1,"R_SHI":2,"B_SHI":2,"R_MA":2}`，`round_kind=2` | 牌力满足：狗脚对 = 红士对 > 黑士对 > 其他对子（如红马对）；排序稳定 |
| M3-CB-08 | `hand={"R_NIU":3,"B_NIU":3}`，`round_kind=3` | 排序满足：红三牛在黑三牛前 |
| M3-CB-09 | `hand={"R_SHI":1,"B_SHI":1,"R_XIANG":1,"B_XIANG":1,"R_MA":1,"B_MA":1,"R_CHE":1,"B_CHE":1,"R_GOU":1,"B_GOU":1,"R_NIU":1,"B_NIU":1}`，`round_kind=1` | 单张牌力顺序严格符合接口文档（`R_SHI` 最高，`B_NIU` 最低） |
| M3-CB-10 | 任一固定手牌（建议用 CB-07）重复调用 3 次 | 组合列表顺序与内容完全一致 |
| M3-CB-11 | `hand={"R_SHI":2,"R_GOU":1,"B_GOU":1,"R_NIU":3}`，分别测试 `round_kind=1/2/3` | kind=1 仅单张；kind=2 仅对子（含狗脚对）；kind=3 仅三牛 |
| M3-CB-12 | `hand={"R_SHI":1,"B_SHI":1,"R_NIU":1,"B_NIU":1}`，`round_kind=1`，`last_combo.power=8`（可压制过滤） | 仅 `power>8` 的组合可压制（即仅红士）；黑士（=8）不可压制 |
| M3-CB-13 | `hand={"R_GOU":1,"R_CHE":1}`，`round_kind=1` | `R_GOU` 与 `R_CHE` 单张 `power` 相等 |
| M3-CB-14 | `hand={"B_GOU":1,"B_CHE":1}`，`round_kind=1` | `B_GOU` 与 `B_CHE` 单张 `power` 相等 |

### 6.2 合法动作枚举（M3-LA）审查样例

| 测试ID | Mock 输入（显式） | 预期结果（显式） |
|---|---|---|
| M3-LA-01 | `phase=buckle_decision`，`turn.current_seat=0`，`seat0.hand={"R_SHI":2,"R_GOU":1,"B_GOU":1}` | actions 仅含 PLAY 与最多 1 个 BUCKLE |
| M3-LA-02 | 同 LA-01 | PLAY 覆盖单张/对子（含狗脚对）全部可出组合，无遗漏 |
| M3-LA-03 | 同 LA-01，连续调用 3 次 | actions 顺序完全一致 |
| M3-LA-04 | `phase=in_round`，`turn.current_seat=1`，`round_kind=1`，`last_combo.power=2`，`seat1.hand={"R_SHI":1}` | 仅返回 PLAY（不返回 COVER） |
| M3-LA-05 | `phase=in_round`，`turn.current_seat=1`，`round_kind=1`，`last_combo.power=9`，`seat1.hand={"B_NIU":1}` | 仅返回 1 个 COVER |
| M3-LA-06 | `phase=in_round`，`turn.current_seat=1`，`round_kind=2`，`last_combo.power=3`，`seat1.hand={"R_SHI":1,"R_XIANG":1}` | 返回 COVER，且 `required_count=2`（虽然单张牌力高，但因凑不出任何合法对子只能垫牌） |
| M3-LA-07 | `phase=in_round`，`turn.current_seat=1`，`round_kind=2`，`last_combo.power=6`，`seat1.hand={"R_SHI":2,"R_MA":2,"B_NIU":2}` | 返回的 PLAY 全部 `power>6`，且不包含不可压制组合 |
| M3-LA-08 | 任一可行动状态，但调用 `get_legal_actions(seat!=turn.current_seat)` | 返回 `{"seat":x,"actions":[]}` |
| M3-LA-09 | `phase=reveal_decision`，`turn.current_seat=2` | actions 仅含 `REVEAL` 与 `PASS_REVEAL` |
| M3-LA-10 | `phase=settlement` 或 `phase=finished` | actions 为空 |
| M3-LA-11 | 固定同一状态（建议 LA-04）连续取 `actions` | 每个 `action_idx` 语义不漂移 |
| M3-LA-12 | 对同一局面先执行一次 `apply_action` 再取 `actions` | 新状态 actions 与新的 `turn.current_seat` 一致 |
| M3-LA-13 | `phase=buckle_decision`，`turn.current_seat=0`，`seat0.hand={"R_SHI":2,"R_GOU":1,"B_GOU":1,"R_NIU":3}` | PLAY 同时覆盖单张、同型对子、狗脚对、红三牛 |
| M3-LA-14 | 同 LA-13 | PLAY 的 `payload_cards` 集合与 `enumerate_combos(hand)` 输出一致 |
| M3-LA-15 | `phase=in_round`，`turn.current_seat=1`，`round_kind=1`，`last_combo.power=3`，`seat1.hand={"R_SHI":1,"B_SHI":1,"R_XIANG":1,"B_CHE":1}` | PLAY 仅含红士/黑士/红相（全部 `power>3`） |
| M3-LA-16 | `phase=in_round`，`turn.current_seat=1`，`round_kind=2`，`last_combo.power=4`，`seat1.hand={"R_SHI":2,"B_SHI":2,"R_MA":2,"R_GOU":1,"B_GOU":1,"B_NIU":2}` | PLAY 含狗脚对、红士对、黑士对、红马对；不含黑牛对 |
| M3-LA-17 | `phase=in_round`，`turn.current_seat=1`，`round_kind=2`，`last_combo.power=8`，`seat1.hand={"R_SHI":2,"B_SHI":2,"R_MA":2,"R_GOU":1,"B_GOU":1}` | PLAY 仅含狗脚对与红士对，不含黑士对（等于边界） |
| M3-LA-18 | `phase=in_round`，`turn.current_seat=1`，`round_kind=3`，`last_combo.power=10`，`seat1.hand={"R_NIU":3,"B_NIU":3}` | PLAY 仅含红三牛 |
| M3-LA-19 | `phase=in_round`，`turn.current_seat=1`，`round_kind=2`，`last_combo.power=0`，`seat1.hand={"R_SHI":2,"B_SHI":1,"R_NIU":3,"R_MA":2}` | 所有 PLAY 均为 2 张组合，不混入单张/三张 |
| M3-LA-20 | `phase=in_round`，`turn.current_seat=1`，`round_kind=1`，`last_combo.power=0`，`seat1.hand={"R_SHI":2,"B_SHI":1}` | `R_SHI` 单张 PLAY 仅出现 1 次 |
| M3-LA-21 | 固定 LA-13 状态，连续调用 3 次 `get_legal_actions` | PLAY 序列（签名）完全一致 |
| M3-LA-22 | 固定 LA-16 状态，连续调用 3 次 `get_legal_actions` | PLAY 序列（签名）完全一致 |

### 6.3 动作执行与棋柱生成（新增需求）

| 测试ID | Mock 输入（显式） | 预期结果（显式） |
|---|---|---|
| M3-ACT-08 | 构造一轮结束场景：3 人完成同一轮出牌后触发收轮，且 `last_combo.owner_seat=1` | `pillar_groups` 追加 1 组，新增组 `winner_seat=1`，且该组归档的回合数据与 `turn.plays` 一致 |
| M3-ACT-09 | 对子轮（`round_kind=2`）且 winner 为 seat1，示例含 `R_SHI` 对参与收轮 | 新增组内总计生成 2 柱；两张 `R_SHI` 分别位于不同柱（不可同柱堆叠） |
| M3-ACT-10 | 三牛轮（`round_kind=3`）且 winner 为 seat2，示例含 `R_NIU*3` 或 `B_NIU*3` | 新增组内总计生成 3 柱；三张同型牛分别位于 3 根柱（每柱至多 1 张该同型牛） |

### 6.4 命令行交互（新增需求）

| 测试ID | Mock 输入（显式） | 预期结果（显式） |
|---|---|---|
| M3-CLI-01 | `python -m engine.cli --seed 20260217` 连续启动两次 | 两次都打印相同 seed，且首轮 `turn.current_seat` 与 3 名玩家起手分布一致 |
| M3-CLI-02 | `python -m engine.cli`（无 seed） | 输出“实际 seed=xxxxxx”；复制该 seed 再次启动可复现 |
| M3-CLI-03 | 固定局面，依次提交 3 次合法动作 | 每次提示“当前操作 seat=X”，并与状态中的 `turn.current_seat` 一致 |
| M3-CLI-04 | 固定局面进入交互一轮 | 展示公共态（phase/version/turn）+ 当前 seat `hand`；其他 seat 不展示完整 `hand` |
| M3-CLI-05 | 固定局面，获取 legal actions | CLI 列表顺序与 `get_legal_actions` 一致，索引从 0 连续递增 |
| M3-CLI-06 | 选择 COVER，先输入错误张数，再输入正确 `cover_list` | 首次提示错误并重输；第二次成功推进状态 |
| M3-CLI-07 | 输入越界 `action_idx`（如 99） | 打印 `ENGINE_INVALID_ACTION_INDEX`，状态版本不变，可继续选择 |
| M3-CLI-08 | 推进到 `settlement` 或 `finished` | CLI 给出终局提示并退出；若 `settle` 可用则可执行结算后退出 |

### 6.5 `get_public_state` 脱敏投影（新增需求）

| 测试ID | Mock 输入（显式） | 预期结果（显式） |
|---|---|---|
| M3-UT-06 | `load_state` 一个“内部完整态”：`players` 含完整 `hand`；`turn.plays` 与 `pillar_groups[*].plays` 至少各含 1 条 `power=-1` 且带 `cards` 的垫牌记录；`turn.current_seat` 为有效 seat | 调用 `get_public_state()` 后：1) `players[*]` 仅含 `seat/hand_count`，不含 `hand`；2) 所有 `power=-1` 记录均使用 `covered_count`，不暴露 `cards`；3) 顶层不包含 `decision` 与计时字段；4) `turn.current_seat` 保持可见用于行动位展示 |

### 6.6 `get_private_state` 私有态投影（新增需求）

| 测试ID | Mock 输入（显式） | 预期结果（显式） |
|---|---|---|
| M3-UT-07 | `load_state` 一个“内部完整态”：`players` 含三名玩家完整 `hand`；`turn.plays` 与 `pillar_groups[*].plays` 含多个 `power=-1` 且带 `cards` 的垫牌记录（跨多个 seat）；调用 `get_private_state(1)` | 返回值仅包含 `hand/covered` 两个字段；`hand` 精确等于 seat1 手牌；`covered` 为 seat1 在 `turn.plays + pillar_groups[*].plays` 中所有垫牌 `cards` 的按类型聚合计数；不泄露其他 seat 的 `hand/covered` |

### 6.7 `load_state` players 索引断言（新增需求）

| 测试ID | Mock 输入（显式） | 预期结果（显式） |
|---|---|---|
| M3-UT-08 | `load_state` 输入 `players` 长度为 3 但顺序错位（如 `players[0].seat=1`, `players[1].seat=0`） | 调用 `load_state` 立即抛出断言异常，不进入后续状态推进 |

## 7) TDD 执行记录（进行中）

> 说明：当前已完成 `M3-UT-01~08`、`M3-CB-01~14`、`M3-LA-01~22`、`M3-ACT-01~10`、`M3-CLI-01~08` 与 `M3-RF-01~03`。

| 测试ID | 当前状态 | TDD阶段 | 备注 |
|---|---|---|---|
| M3-UT-01 ~ M3-UT-05 | ✅ 通过 | Green 已完成 | Red：2026-02-16 首次执行失败（`init_game` 未实现）；Green：2026-02-16 完成 `engine/core.py` 的 `init_game/apply_action` 后执行 `pytest engine/tests/test_m3_red_ut_01_05.py -q`（5 passed） |
| M3-UT-06 | ✅ 通过 | Green 已完成 | Red：2026-02-17 新增 `engine/tests/test_m3_red_ut_06_public_state_masking.py` 并执行 `pytest engine/tests/test_m3_red_ut_06_public_state_masking.py -q`（1 failed）；Green：2026-02-17 在 `engine/core.py` 实现 `get_public_state` 脱敏投影后复测同命令（1 passed） |
| M3-UT-07 | ✅ 通过 | Green 已完成 | Red：2026-02-17 新增 `engine/tests/test_m3_red_ut_07_private_state_covered.py` 并执行 `pytest engine/tests/test_m3_red_ut_07_private_state_covered.py -q`（1 failed）；Green：2026-02-17 在 `engine/core.py` 实现 `get_private_state` 的 `covered` 聚合后复测同命令（1 passed） |
| M3-UT-08 | ✅ 通过 | Green 已完成 | 2026-02-17：新增 `engine/tests/test_m3_ut_08_load_state_players_indexed_by_seat.py` 并执行 `pytest engine/tests/test_m3_ut_08_load_state_players_indexed_by_seat.py -q`（1 passed），锁定 `load_state` 的 players 索引断言契约 |
| M3-CB-01 ~ M3-CB-04 | ✅ 通过 | Green 已完成 | Red：2026-02-15 执行 `conda run -n XQB pytest engine/tests/test_m3_red_cb_la_01_06.py -q`（缺失 `engine.combos`）；Green：2026-02-16 新增 `engine/combos.py` 后执行 `pytest engine/tests/test_m3_red_cb_la_01_06.py -q` 通过 |
| M3-LA-04 ~ M3-LA-06 | ✅ 通过 | Green 已完成 | Red：2026-02-15 同批次执行（缺失 `engine.core`）；Green：2026-02-16 新增 `engine/core.py` 后执行 `pytest engine/tests/test_m3_red_cb_la_01_06.py -q` 通过 |
| M3-CB-05 ~ M3-CB-12 | ✅ 通过 | Red 已执行（意外全绿） | 2026-02-16：已新增 `engine/tests/test_m3_red_cb_05_12.py` 并执行 `pytest engine/tests/test_m3_red_cb_05_12.py -q`（8 passed）；当前实现已满足用例预期 |
| M3-CB-13 ~ M3-CB-14 | ✅ 通过 | Green 已完成 | 2026-02-16：已新增 `engine/tests/test_m3_cb_13_14_gou_che_power.py` 并执行 `pytest engine/tests/test_m3_cb_13_14_gou_che_power.py -q`（2 passed） |
| M3-LA-01 ~ M3-LA-03, M3-LA-07 ~ M3-LA-12 | ✅ 通过 | Red 已执行（意外全绿） | 2026-02-17：已新增 `engine/tests/test_m3_red_la_01_03_07_12.py` 并执行 `pytest engine/tests/test_m3_red_la_01_03_07_12.py -q`（9 passed）；当前实现已满足用例预期 |
| M3-LA-13 ~ M3-LA-22 | ✅ 通过 | Green 已完成 | 2026-02-16：已新增 `engine/tests/test_m3_la_play_enumeration_13_22.py`，执行 `pytest engine/tests/test_m3_la_play_enumeration_13_22.py -q`（10 passed）与 `pytest engine/tests -q`（17 passed） |
| M3-ACT-01 ~ M3-ACT-07 | ✅ 通过 | Green 已完成 | Red：2026-02-17 已新增 `engine/tests/test_m3_red_act_01_07.py` 并执行（`6 passed, 1 failed`）；Green：2026-02-17 完成 `engine/core.py` 的 `REVEAL/PASS_REVEAL` 状态推进后执行 `pytest engine/tests/test_m3_red_act_01_07.py -q`（7 passed） |
| M3-ACT-08 ~ M3-ACT-10 | ✅ 通过 | Green 已完成 | Red：2026-02-16 首次执行失败（`apply_action` 未实现）；Green：2026-02-16 完成回合收尾与 `pillar_groups.pillars` 拆柱后执行 `pytest engine/tests/test_m3_red_act_08_10_pillars.py -q`（3 passed） |
| M3-CLI-01 ~ M3-CLI-04 | ✅ 通过 | Green 已完成 | Red：2026-02-17 执行 `pytest engine/tests/test_m3_red_cli_01_04.py -q`（4 failed）；Green：2026-02-17 在 `engine/cli.py` 补齐 `build_initial_snapshot / resolve_seed / render_turn_prompt / render_state_view` 后执行同命令（4 passed）。 |
| M3-CLI-05 ~ M3-CLI-08 | ✅ 通过 | Green 已完成 | Red：2026-02-17 执行 `pytest engine/tests/test_m3_red_cli_05_08.py -q`（4 failed）；Green：2026-02-17 在 `engine/cli.py` 修复动作索引展示、COVER 重试、错误码前缀与 settlement 提示后执行同命令（4 passed）。 |
| M3-RF-01 ~ M3-RF-03 | ✅ 通过 | Green 已完成 | Red：2026-02-17 新增 `engine/tests/test_m3_refactor_apply_action_reducer.py` 并执行 `pytest engine/tests/test_m3_refactor_apply_action_reducer.py -q`（`1 failed, 2 passed`，缺少 `reduce_apply_action` 委托入口）；Green：2026-02-17 新增 `engine/reducer.py` 并完成 `engine/core.py` 委托改造后执行同命令（`3 passed`）。 |
