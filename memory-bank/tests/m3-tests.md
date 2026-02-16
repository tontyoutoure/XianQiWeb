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

## 2) 组合枚举器测试（重点细化）

| 测试ID | 测试描述 | 通过条件 |
|---|---|---|
| M3-CB-01 | 单张枚举（去重） | 同一 `card_type` 只产出 1 个单张组合，不受该类型 `count` 影响 |
| M3-CB-02 | 同型对子枚举 | 当某 `card_type.count >= 2` 时产出该类型对子；`count < 2` 不产出 |
| M3-CB-03 | 狗脚对枚举（R_GOU+B_GOU） | 仅当 `R_GOU>=1 且 B_GOU>=1` 时产出 `dog_pair` |
| M3-CB-04 | 狗脚对互斥去重 | 狗脚对只产出 1 条，不因枚举顺序产生重复项 |
| M3-CB-05 | 三牛枚举（红/黑） | 仅当 `R_NIU>=3` 产出红三牛；仅当 `B_NIU>=3` 产出黑三牛 |
| M3-CB-06 | 非法三张不应产出 | 非牛三张、混色三张都不会进入组合枚举结果 |
| M3-CB-07 | 对子牌力顺序 | `dog_pair > 红士对 > 黑士对 > 其他对子`，排序稳定 |
| M3-CB-08 | 三张牌力顺序 | 红三牛 > 黑三牛 |
| M3-CB-09 | 单张牌力顺序 | 满足接口文档牌力表（`R_SHI` 最高，`B_NIU` 最低） |
| M3-CB-10 | 组合排序稳定性 | 同一手牌多次调用枚举，输出顺序完全一致 |
| M3-CB-11 | 按 `round_kind` 过滤 | 指定 `round_kind=1/2/3` 时仅返回对应张数组合 |
| M3-CB-12 | 严格大于比较 | 压制判定只接受 `power > last_combo.power`，`=` 不可压制 |

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
| M3-LA-08 | 非当前决策 seat 的动作 | `seat != decision.seat` 时返回空 `actions` |
| M3-LA-09 | `reveal_decision` 动作集合 | 仅包含 `REVEAL` 与 `PASS_REVEAL` |
| M3-LA-10 | `settlement/finished` 无动作 | `get_legal_actions` 返回空 `actions` |
| M3-LA-11 | `action_idx` 稳定性 | 同一状态多次获取 `actions`，索引含义不漂移 |
| M3-LA-12 | phase 切换后动作刷新 | `apply_action` 后下一状态的 `actions` 与新 `decision.seat` 一致 |

## 4) 动作执行与校验补充测试

| 测试ID | 测试描述 | 通过条件 |
|---|---|---|
| M3-ACT-01 | `action_idx` 越界 | 引擎返回 `ENGINE_INVALID_ACTION_INDEX` |
| M3-ACT-02 | `client_version` 冲突 | 引擎返回 `ENGINE_VERSION_CONFLICT` |
| M3-ACT-03 | 非 COVER 传 `cover_list` | 引擎拒绝并返回 `ENGINE_INVALID_COVER_LIST` |
| M3-ACT-04 | COVER 传错张数 | `cover_list` 总张数不等于 `required_count` 时拒绝 |
| M3-ACT-05 | COVER 传不存在手牌 | `cover_list` 超出持牌时拒绝 |
| M3-ACT-06 | 回合结束后决策位推进 | 3 人出完后 `decision.seat` 切到 round winner |
| M3-ACT-07 | 掀棋顺序推进 | `reveal.pending_order` 消费与 `decision.seat` 推进一致 |

## 5) 阶段通过判定（M3）

- 组合枚举与牌力比较规则完整可测，且顺序稳定。
- 合法动作生成满足 phase 约束与互斥规则（PLAY/COVER、REVEAL/PASS_REVEAL）。
- `action_idx + cover_list + client_version` 三条核心校验链路均有红绿覆盖。
- 决策位（`decision.seat`）在每次状态推进后与 `turn.current_seat` 一致。

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
| M3-CB-07 | `hand={"R_GOU":1,"B_GOU":1,"R_SHI":2,"B_SHI":2,"R_MA":2}`，`round_kind=2` | 排序满足：狗脚对 > 红士对 > 黑士对 > 其他对子（如红马对） |
| M3-CB-08 | `hand={"R_NIU":3,"B_NIU":3}`，`round_kind=3` | 排序满足：红三牛在黑三牛前 |
| M3-CB-09 | `hand={"R_SHI":1,"B_SHI":1,"R_XIANG":1,"B_XIANG":1,"R_MA":1,"B_MA":1,"R_CHE":1,"B_CHE":1,"R_GOU":1,"B_GOU":1,"R_NIU":1,"B_NIU":1}`，`round_kind=1` | 单张牌力顺序严格符合接口文档（`R_SHI` 最高，`B_NIU` 最低） |
| M3-CB-10 | 任一固定手牌（建议用 CB-07）重复调用 3 次 | 组合列表顺序与内容完全一致 |
| M3-CB-11 | `hand={"R_SHI":2,"R_GOU":1,"B_GOU":1,"R_NIU":3}`，分别测试 `round_kind=1/2/3` | kind=1 仅单张；kind=2 仅对子（含狗脚对）；kind=3 仅三牛 |
| M3-CB-12 | `hand={"R_SHI":1,"B_SHI":1,"R_NIU":1,"B_NIU":1}`，`round_kind=1`，`last_combo.power=8`（可压制过滤） | 仅 `power>8` 的组合可压制（即仅红士）；黑士（=8）不可压制 |

### 6.2 合法动作枚举（M3-LA）审查样例

| 测试ID | Mock 输入（显式） | 预期结果（显式） |
|---|---|---|
| M3-LA-01 | `phase=buckle_decision`，`decision.seat=0`，`seat0.hand={"R_SHI":2,"R_GOU":1,"B_GOU":1}` | actions 仅含 PLAY 与最多 1 个 BUCKLE |
| M3-LA-02 | 同 LA-01 | PLAY 覆盖单张/对子（含狗脚对）全部可出组合，无遗漏 |
| M3-LA-03 | 同 LA-01，连续调用 3 次 | actions 顺序完全一致 |
| M3-LA-04 | `phase=in_round`，`decision.seat=1`，`round_kind=1`，`last_combo.power=2`，`seat1.hand={"R_SHI":1}` | 仅返回 PLAY（不返回 COVER） |
| M3-LA-05 | `phase=in_round`，`decision.seat=1`，`round_kind=1`，`last_combo.power=9`，`seat1.hand={"B_NIU":1}` | 仅返回 1 个 COVER |
| M3-LA-06 | `phase=in_round`，`decision.seat=1`，`round_kind=2`，`last_combo.power=3`，`seat1.hand={"R_SHI":1,"R_XIANG":1}` | 返回 COVER，且 `required_count=2`（虽然单张牌力高，但因凑不出任何合法对子只能垫牌） |
| M3-LA-07 | `phase=in_round`，`decision.seat=1`，`round_kind=2`，`last_combo.power=6`，`seat1.hand={"R_SHI":2,"R_MA":2,"B_NIU":2}` | 返回的 PLAY 全部 `power>6`，且不包含不可压制组合 |
| M3-LA-08 | 任一可行动状态，但调用 `get_legal_actions(seat!=decision.seat)` | 返回 `{"seat":x,"actions":[]}` |
| M3-LA-09 | `phase=reveal_decision`，`decision.seat=2` | actions 仅含 `REVEAL` 与 `PASS_REVEAL` |
| M3-LA-10 | `phase=settlement` 或 `phase=finished` | actions 为空 |
| M3-LA-11 | 固定同一状态（建议 LA-04）连续取 `actions` | 每个 `action_idx` 语义不漂移 |
| M3-LA-12 | 对同一局面先执行一次 `apply_action` 再取 `actions` | 新状态 actions 与新的 `decision.seat` 一致 |

## 7) TDD 执行记录（初始）

> 说明：当前仅完成测试清单细化，尚未进入具体测试代码编写。

| 测试ID | 当前状态 | TDD阶段 | 备注 |
|---|---|---|---|
| M3-UT-01 ~ M3-UT-05 | ⏳ 待执行 | 未开始 | 待人类指定优先级 |
| M3-CB-01 ~ M3-CB-04 | 🔴 失败 | Red 已执行 | 2026-02-15：已新增 `engine/tests/test_m3_red_cb_la_01_06.py` 并执行 `conda run -n XQB pytest engine/tests/test_m3_red_cb_la_01_06.py -q`；当前失败点为 `engine.combos` 模块/`enumerate_combos` 缺失 |
| M3-LA-04 ~ M3-LA-06 | 🔴 失败 | Red 已执行 | 2026-02-15：同批次 red 执行，当前失败点为 `engine.core` 模块/`XianqiGameEngine` 缺失 |
| M3-CB-05 ~ M3-CB-12 | ⏳ 待执行 | 未开始 | 组合枚举器后续用例 |
| M3-LA-01 ~ M3-LA-03, M3-LA-07 ~ M3-LA-12 | ⏳ 待执行 | 未开始 | 合法动作枚举后续用例 |
| M3-ACT-01 ~ M3-ACT-07 | ⏳ 待执行 | 未开始 | 动作校验与状态推进补充 |
