# M8 阶段测试列表（前端对局与结算，TDD）

> 依据文档：
> - `memory-bank/implementation-plan.md`（M8）
> - `memory-bank/design/frontend_ingame_design.md`
> - `memory-bank/interfaces/frontend-backend-interfaces.md`
> - `memory-bank/interfaces/backend-engine-interface.md`
> 目标：冻结 M8 前端“对局交互 + 结算展示”的非 E2E 测试清单（UT/CT/集成），供后续按测试 ID 执行 Red -> Green。
> 说明：E2E 用例统一放在 `memory-bank/tests/m8-tests-real-service.md`。

## 0) 测试环境与执行策略

- 前端测试分层：
  - 单元测试（状态切片、动作映射、选择器与状态机）。
  - 组件测试（操作区、手牌交互、棋柱视图、弹层）。
  - 集成测试（Store + API + WS 事件联动，不依赖真实后端）。
- 推荐命令（以最终 `package.json` 为准）：
  - 单元/组件/集成：`cd frontend && npm run test -- --run`
- 数据构造建议：
  - 使用固定 `public_state/private_state/legal_actions` 测试桩。
  - 覆盖 `buckle_flow`、`in_round(round_kind=0/>0)`、`settlement` 四类关键阶段。
- TDD 流程约束：
  1. 人类先指定测试 ID。
  2. 先写测试并执行 Red（失败符合预期）。
  3. 再做最小实现直到 Green。
  4. 每个测试用例通过后，回填本文件“执行记录”。

## 1) 测试用例列表（非 E2E）

### 1.1 状态层与协议映射（UT/IT）

| 测试ID | 测试描述 | 通过条件 |
|---|---|---|
| M8-UT-01 | `legal_actions` 到按钮能力映射正确 | 仅渲染后端返回动作类型，不额外推断动作 |
| M8-UT-02 | `action_idx` 取值按 `legal_actions.actions` 顺序 | 提交参数中的 `action_idx` 与当前动作下标一致 |
| M8-UT-03 | `COVER` 动作提交携带 `cover_list`，其他动作不携带 | `COVER` 请求体含 `cover_list`；非 `COVER` 为 `null` 或省略 |
| M8-IT-01 | 动作提交统一携带 `client_version=public_state.version` | 请求体 `client_version` 与当前公共态版本一致 |
| M8-IT-02 | `204` 后等待 WS 刷新而非本地伪推进 | 本地状态不提前写死，待 `GAME_PUBLIC_STATE/PRIVATE_STATE` 覆盖 |
| M8-IT-03 | `409 GAME_VERSION_CONFLICT` 自动拉态恢复 | 触发 `GET /api/games/{game_id}/state`，并覆盖 `public/private/legal_actions` |
| M8-IT-04 | `409` 恢复后清空手牌选中态与待提交动作 | `uiSelectionState` 复位，按钮回到未选择状态 |
| M8-IT-05 | 403/404/非版本 409 错误统一提示并终止提交 | 展示统一错误消息，不继续重复提交 |

### 1.2 操作区与按钮可用性（CT）

| 测试ID | 测试描述 | 通过条件 |
|---|---|---|
| M8-CT-01 | `buckle_flow` 起始决策仅显示 `BUCKLE/PASS_BUCKLE` | 操作区仅出现两类按钮 |
| M8-CT-02 | 掀棋询问阶段仅显示 `REVEAL/PASS_REVEAL` | 操作区仅出现两类按钮 |
| M8-CT-03 | `in_round` 可压制时仅显示 `PLAY` 路径 | 不出现 `COVER` 按钮 |
| M8-CT-04 | `in_round` 无法压制时仅显示 `COVER` 路径 | 不出现 `PLAY` 按钮 |
| M8-CT-05 | `PLAY/COVER` 在未形成合法选择时不可点击 | 按钮 `disabled=true` |
| M8-CT-06 | 达成合法选择后 `PLAY/COVER` 可点击 | 按钮 `disabled=false` |

### 1.3 手牌交互状态机（UT/CT）

| 测试ID | 测试描述 | 通过条件 |
|---|---|---|
| M8-UT-04 | 手牌三态切换：普通态/可交互态/已选中态 | 点击与取消点击后状态转移符合设计 |
| M8-UT-05 | `COVER` 未满 `required_count` 时持续可选 | 未选中牌保持可交互 |
| M8-UT-06 | `COVER` 达到 `required_count` 后锁定其余手牌 | 其余牌进入普通态且 `COVER` 按钮可点击 |
| M8-UT-07 | `COVER` 取消一张后重新开放可交互集合 | 状态回退并重算按钮可用性 |
| M8-UT-08 | `PLAY`（非首位）单击后收敛到唯一合法 `payload_cards` | 仅保留该组合已选中态，其他牌不可交互 |
| M8-UT-09 | `PLAY`（非首位）取消组合后回到初始可选集 | 点击已选中牌后恢复初始列表 |
| M8-UT-10 | `PLAY`（首位）对子/三牛部分选中时仅同组合可继续选 | 同组合剩余牌可交互，其他牌普通态 |
| M8-UT-11 | `PLAY`（首位）满足合法组合后按钮变可点击 | 达成某个 `payload_cards` 后 `PLAY` 可提交 |
| M8-UT-12 | `PLAY`（首位）撤销后重算可交互集合 | 删除已选中牌后重新计算可选牌 |

### 1.4 棋柱展示与信息隔离（CT）

| 测试ID | 测试描述 | 通过条件 |
|---|---|---|
| M8-CT-07 | 出棋状况区正确渲染 `public_state.turn.plays` | 出牌顺序与 seat 标识一致 |
| M8-CT-08 | 公共区垫牌仅显示 `covered_count` | 对手垫牌不显示具体牌面 |
| M8-CT-09 | 己方垫牌可由 `private_state.covered` 补全本地牌面 | 仅自己视角可见己方垫牌具体牌面 |
| M8-CT-10 | 主界面棋柱使用“最大牌完整 + 其余遮挡” | 每柱主牌可见，其余牌遮挡呈现 |
| M8-CT-11 | 棋柱弹层“按归属”视图全展开三枚牌 | 每柱全部牌面按归属分区展示 |
| M8-CT-12 | 棋柱弹层“按大小”视图按牌力降序排列 | 公共牌排序正确，对手垫牌仅数量化并在末尾 |
| M8-CT-13 | “包含柱外牌”开关仅影响本地展示集合 | 仅 UI 列表变化，不触发后端请求/状态变更 |

### 1.5 弹层与阶段收束（CT/IT）

| 测试ID | 测试描述 | 通过条件 |
|---|---|---|
| M8-CT-14 | 掀扣关系弹层可打开/关闭 | 点击入口显示弹层，关闭按钮仅关闭 UI |
| M8-CT-15 | 掀扣关系失效项样式正确 | 失效关系置灰且带中划线 |
| M8-IT-06 | 收到 `SETTLEMENT` 或 `phase=settlement` 时自动弹结算层 | 结算弹层出现且展示三类分项 |
| M8-CT-16 | 结算弹层展示 `delta/delta_enough/delta_reveal/delta_ceramic` | 每位玩家分项与总和渲染正确 |
| M8-IT-07 | 关闭结算弹层后回到准备态提示 | 显示“已进入准备阶段，请重新 ready 开新局” |
| M8-IT-08 | 房间冷结束（无结算）时清空对局 UI | `playing -> waiting` 且无结算时显示“对局结束” |

### 1.6 恢复与稳定性（IT）

| 测试ID | 测试描述 | 通过条件 |
|---|---|---|
| M8-IT-09 | 对局中 WS 断连后自动重连并拉态兜底 | 重连后状态与最新快照一致 |
| M8-IT-10 | 重连后 `legal_actions` 与选择态一致重建 | 操作区与可选牌和当前快照一致 |
| M8-IT-11 | 收到房间鉴权关闭（4401）时触发 refresh + 重连 | refresh 成功后恢复频道，失败回登录 |

## 2) 阶段通过判定（M8 非 E2E）

- `legal_actions -> UI -> action_idx/cover_list/client_version` 映射链路稳定。
- 手牌交互状态机在 `PLAY/COVER` 场景下行为一致且可回退。
- 公私信息隔离正确：不泄露他人手牌与垫牌牌面。
- 掀扣关系弹层与结算弹层可正确展示/关闭并驱动阶段提示。
- 409 冲突、WS 断线、鉴权关闭三类恢复路径可用。

## 3) TDD 执行记录

> 说明：当前阶段先冻结测试设计；执行状态待人类指定测试 ID 后逐条回填。

| 测试ID | 当前状态 | TDD阶段 | 执行日期 | 备注 |
|---|---|---|---|---|
| M8-UT-01 | ❌ Red失败 | Red完成 | 2026-03-03 | `tests/unit/m8-actions-stage-1-red.test.ts` 失败：缺少 `@/stores/ingame-actions.mapLegalActionsToButtonTypes`，无法验证 legal_actions->按钮映射仅来自后端动作集合。 |
| M8-UT-02 | ❌ Red失败 | Red完成 | 2026-03-03 | 同次执行失败：缺少 `@/stores/ingame-actions.buildActionSubmitPayload`，无法验证 `action_idx` 按 `legal_actions.actions` 顺序。 |
| M8-UT-03 | ❌ Red失败 | Red完成 | 2026-03-03 | 同次执行失败：缺少 `@/stores/ingame-actions.buildActionSubmitPayload`，无法验证 COVER/非COVER 的 `cover_list` 携带规则。 |
| M8-IT-01 | ❌ Red失败 | Red完成 | 2026-03-03 | 同次执行失败：缺少 `@/stores/ingame-actions.buildActionSubmitPayload`，无法验证所有动作提交携带 `client_version=public_state.version`。 |
| M8-IT-02 | ⏳ 待执行 | 未开始 | - | - |
| M8-IT-03 | ⏳ 待执行 | 未开始 | - | - |
| M8-IT-04 | ⏳ 待执行 | 未开始 | - | - |
| M8-IT-05 | ⏳ 待执行 | 未开始 | - | - |
| M8-CT-01 | ⏳ 待执行 | 未开始 | - | - |
| M8-CT-02 | ⏳ 待执行 | 未开始 | - | - |
| M8-CT-03 | ⏳ 待执行 | 未开始 | - | - |
| M8-CT-04 | ⏳ 待执行 | 未开始 | - | - |
| M8-CT-05 | ⏳ 待执行 | 未开始 | - | - |
| M8-CT-06 | ⏳ 待执行 | 未开始 | - | - |
| M8-UT-04 | ⏳ 待执行 | 未开始 | - | - |
| M8-UT-05 | ⏳ 待执行 | 未开始 | - | - |
| M8-UT-06 | ⏳ 待执行 | 未开始 | - | - |
| M8-UT-07 | ⏳ 待执行 | 未开始 | - | - |
| M8-UT-08 | ⏳ 待执行 | 未开始 | - | - |
| M8-UT-09 | ⏳ 待执行 | 未开始 | - | - |
| M8-UT-10 | ⏳ 待执行 | 未开始 | - | - |
| M8-UT-11 | ⏳ 待执行 | 未开始 | - | - |
| M8-UT-12 | ⏳ 待执行 | 未开始 | - | - |
| M8-CT-07 | ⏳ 待执行 | 未开始 | - | - |
| M8-CT-08 | ⏳ 待执行 | 未开始 | - | - |
| M8-CT-09 | ⏳ 待执行 | 未开始 | - | - |
| M8-CT-10 | ⏳ 待执行 | 未开始 | - | - |
| M8-CT-11 | ⏳ 待执行 | 未开始 | - | - |
| M8-CT-12 | ⏳ 待执行 | 未开始 | - | - |
| M8-CT-13 | ⏳ 待执行 | 未开始 | - | - |
| M8-CT-14 | ⏳ 待执行 | 未开始 | - | - |
| M8-CT-15 | ⏳ 待执行 | 未开始 | - | - |
| M8-IT-06 | ⏳ 待执行 | 未开始 | - | - |
| M8-CT-16 | ⏳ 待执行 | 未开始 | - | - |
| M8-IT-07 | ⏳ 待执行 | 未开始 | - | - |
| M8-IT-08 | ⏳ 待执行 | 未开始 | - | - |
| M8-IT-09 | ⏳ 待执行 | 未开始 | - | - |
| M8-IT-10 | ⏳ 待执行 | 未开始 | - | - |
| M8-IT-11 | ⏳ 待执行 | 未开始 | - | - |
