# M3+M5 阶段联合收尾测试列表（引擎层）

> 依据文档：`memory-bank/implementation-plan.md`（M3/M5）、`memory-bank/interfaces/backend-engine-interface.md`、`memory-bank/tests/m3-tests.md`、`memory-bank/tests/m5-tests.md`、`XianQi_rules.md`。
> 当前范围：仅引擎层联合收口（`load_state + apply_action + settle`），不包含 real-service 联调。
> 目标：验证 M3（状态推进）与 M5（结算）在同一条链路中的协同正确性，并完成回归收口。

## 0) 测试运行环境与执行约定

- 建议环境：conda `XQB`。
- 建议命令：
  - 联合用例：`conda run -n XQB pytest engine/tests/test_m3_m5_joint_*.py -q`
  - 全量回归：`conda run -n XQB pytest engine/tests -q`
- 构造约定：
  - 本轮默认使用 `load_state` 固定局面（固定手牌、固定行动位、固定 reveal 关系）。
  - 本轮不新增生产接口（例如 `init_game` 的 preset 参数）。
- 记录约定：
  - 按 TDD 执行：先写用例清单，再按指定测试 ID 落地测试并记录 Red/Green。

## 1) 强不变量（联合收尾新增要求）

### 1.1 标准牌堆模板（24 张）

```json
{
  "R_SHI": 2,
  "B_SHI": 2,
  "R_XIANG": 2,
  "B_XIANG": 2,
  "R_MA": 2,
  "B_MA": 2,
  "R_CHE": 2,
  "B_CHE": 2,
  "R_GOU": 1,
  "B_GOU": 1,
  "R_NIU": 3,
  "B_NIU": 3
}
```

### 1.2 回合收轮后牌面守恒校验（每一轮都执行）

- `CARD-INV-COUNT`：每次收轮入柱后，断言
  - `三家手牌总张数 + 所有柱中牌总张数 == 24`
- `CARD-INV-MULTISET`：每次收轮入柱后，断言
  - `三家手牌 + 所有柱中牌` 聚合得到的 `{card_type -> count}`
  - 与“标准牌堆模板”严格一致（不仅总数一致，且每个牌型计数一致）

说明：`CARD-INV-COUNT` 与 `CARD-INV-MULTISET` 必须同时通过；任一失败均视为严重错误。

## 2) 联合测试用例清单（最小核心链路）

| 测试ID | 测试描述 | 通过条件 |
|---|---|---|
| JOINT-01 | 主链路：`buckle_flow -> in_round -> round_end -> settlement -> settle` | 阶段推进正确；`settle` 后 `phase=finished`；版本号递增正确；每次收轮后通过 `CARD-INV-COUNT/MULTISET` |
| JOINT-02 | `PASS_BUCKLE` 分支后进入 `in_round` 并完成结算 | `PASS_BUCKLE` 后保持首手前态（`round_kind=0/plays=[]/last_combo=null`）；最终可 `settle`；收轮后通过牌面守恒双校验 |
| JOINT-03 | `BUCKLE + REVEAL` 命中后切回扣棋方并完成结算 | `relations` 追加正确、`pending_order` 清空、`turn.current_seat` 切回 buckler；最终结算成功；收轮后通过牌面守恒双校验 |
| JOINT-04 | 收轮触发提前结算（任一玩家瓷）并执行 `settle` | 收轮后直接 `phase=settlement`；当前行动位 `legal_actions` 为空；结算守恒通过；收轮后通过牌面守恒双校验 |
| JOINT-05 | 收轮触发提前结算（两家够）并执行 `settle` | 两名玩家 `pillar>=3` 时直接结算；结算守恒通过；收轮后通过牌面守恒双校验 |
| JOINT-06 | 含掀扣关系的联合结算拆分 | 同时覆盖 `delta_enough` 与 `delta_reveal`；字段分解正确；收轮后通过牌面守恒双校验 |
| JOINT-07 | 特殊规则：掀时已够、最终未瓷 | 对应玩家 `delta_enough=0`（不赢够棋筹码）；掀棋相关增量独立正确；收轮后通过牌面守恒双校验 |
| JOINT-08 | 黑棋路径直达结算 | `phase=settlement` 后可直接 `settle`；三家 `delta/delta_enough/delta_reveal/delta_ceramic` 全为 0 |

## 3) 通用断言（适用于每个成功结算样例）

- 阶段推进：`settlement -> finished`。
- 版本变化：成功推进后 `version + 1`。
- 结算分解一致性：`delta = delta_enough + delta_reveal + delta_ceramic`。
- 全局守恒：`sum(delta)=0`，且 `sum(delta_enough)=sum(delta_reveal)=sum(delta_ceramic)=0`。
- 返回结构完整：`chip_delta_by_seat` 长度为 3，且 seat 覆盖 `0/1/2`。
- 提前结算分支一致性：`reveal.pending_order=[]`，且当前行动位 `legal_actions=[]`。

## 4) 阶段通过判定（M3+M5 联合收尾）

- JOINT-01 ~ JOINT-08 全部通过。
- 联合套件执行全绿。
- `pytest engine/tests -q` 全量回归全绿（无 M3/M5 回归）。

## 5) TDD 执行记录（进行中）

| 测试ID | 当前状态 | TDD阶段 | 备注 |
|---|---|---|---|
| JOINT-01 | ⏳ 待执行 | - | - |
| JOINT-02 | ⏳ 待执行 | - | - |
| JOINT-03 | ⏳ 待执行 | - | - |
| JOINT-04 | ⏳ 待执行 | - | - |
| JOINT-05 | ⏳ 待执行 | - | - |
| JOINT-06 | ⏳ 待执行 | - | - |
| JOINT-07 | ⏳ 待执行 | - | - |
| JOINT-08 | ⏳ 待执行 | - | - |
