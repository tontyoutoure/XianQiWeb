# M8 阶段真实后端收口联调测试清单（In-game + Settlement + Real Backend）

> 目标：在真实后端服务上完成 M8 前端对局与结算收口，覆盖“操作区、手牌交互、信息隔离、冲突恢复、结算与再开局”关键链路。
> 依据文档：
> - `memory-bank/tests/m8-tests.md`
> - `memory-bank/implementation-plan.md`（M8）
> - `memory-bank/design/frontend_ingame_design.md`
> - `memory-bank/interfaces/frontend-backend-interfaces.md`
> - `memory-bank/interfaces/backend-engine-interface.md`
> - `memory-bank/design/backend_design.md`（4. M8 Seed Hunter 与 REST 注入设计）
> 口径声明：本文件是 M8 E2E（真实后端）用例 ID 与执行记录来源（SSOT）。
> 当前状态：测试设计已冻结，待按测试 ID 执行 Red -> Green。

## 0) 测试环境与执行约定（真实服务）

- 建议环境：
  - 后端：conda `XQB`
  - 前端：Node.js `22.x`
- 后端启动（推荐）：
  - `XQWEB_APP_ENV=test`
  - `XQWEB_APP_HOST=127.0.0.1`
  - `XQWEB_APP_PORT=18080`
  - `XQWEB_TEST_DB_DIR=/tmp/xqweb-test`
  - `XQWEB_JWT_SECRET=<at-least-32-byte-secret>`
  - `XQWEB_SEED_ENABLE_SEED_INJECTION=true`
  - `bash scripts/start-backend-test.sh`
- 前端环境变量（`frontend/.env.test` 或命令行覆盖）：
  - `VITE_API_BASE_URL=http://127.0.0.1:18080`
  - `VITE_WS_BASE_URL=ws://127.0.0.1:18080`
- E2E 执行建议：
  - `cd frontend && npm run test:e2e -- --project=chromium --workers=1`
- 数据隔离约定：
  - 每轮用例使用唯一账号前缀。
  - 每轮使用全新后端实例，避免房间状态串扰。
- 种子注入约定（用于稳定复现关键局面）：
  - 开局前调用 `POST /api/games/seed-injection`，请求体 `{"seed": <int>=0}`。
  - 注入 seed 仅“下一局一次性生效”；消费后自动清空。
  - 种子基础能力门禁与后端语义由 `memory-bank/tests/m7.5-test.md` 保障。

## 1) 收口前门禁（M8-GATE）

| 门禁ID | 场景 | 通过条件 |
|---|---|---|
| M8-GATE-01 | M7 基线可用 | `memory-bank/tests/m7-tests-real-service.md` 中 `M7-RS-E2E-01~12` 保持 Green |
| M8-GATE-02 | 种子注入接口可用 | `POST /api/games/seed-injection` 合法请求返回 200 |
| M8-GATE-03 | 三端可稳定进局 | 三名玩家 ready 后同房间可收到 `GAME_PUBLIC_STATE` 与各自 `GAME_PRIVATE_STATE` |
| M8-GATE-04 | E2E 三上下文可稳定运行 | Playwright 多上下文（A/B/C）可稳定执行无随机失败 |

## 2) M8 E2E 用例映射（M8-RS-E2E-01~15）

| 测试ID | 场景 | 通过条件 | 目标测试函数（规划） |
|---|---|---|---|
| M8-RS-E2E-01 | 主流程入局 | 登录 -> 加入同房 -> 三人 ready 后进入对局界面，出现手牌区与操作区 | `test_m8_rs_e2e_01_enter_ingame_after_three_ready` |
| M8-RS-E2E-02 | `buckle_flow` 按钮映射 | 回合起始决策仅展示 `BUCKLE/PASS_BUCKLE`，且可提交 | `test_m8_rs_e2e_02_buckle_flow_action_bar_mapping` |
| M8-RS-E2E-03 | 扣后掀棋决策映射 | 被询问玩家仅展示 `REVEAL/PASS_REVEAL`，命中 `REVEAL` 后立即结束本轮询问 | `test_m8_rs_e2e_03_reveal_flow_and_inquiry_short_circuit` |
| M8-RS-E2E-04 | `PLAY` 首位交互 | 首位出棋时牌面按合法组合收敛，形成合法组合后 `PLAY` 可点击 | `test_m8_rs_e2e_04_play_first_seat_selection_state_machine` |
| M8-RS-E2E-05 | `PLAY` 非首位交互 | 非首位点击后收敛到唯一合法 `payload_cards`，提交后回合推进 | `test_m8_rs_e2e_05_play_non_first_unique_payload_selection` |
| M8-RS-E2E-06 | `COVER` 交互与提交 | 达到 `required_count` 前不可提交，达到后可提交且 `cover_list` 合法 | `test_m8_rs_e2e_06_cover_required_count_and_submit` |
| M8-RS-E2E-07 | 版本冲突恢复 | 人为制造旧 `client_version` 提交触发 409，前端自动拉态并重建可继续操作 | `test_m8_rs_e2e_07_version_conflict_auto_resync` |
| M8-RS-E2E-08 | 公私信息隔离 | 对手手牌与垫牌牌面不可见；己方可见自己的手牌与垫牌明细 | `test_m8_rs_e2e_08_private_public_visibility_isolation` |
| M8-RS-E2E-09 | 棋柱弹层按归属视图 | 可从主界面进入棋柱弹层，按归属展示三方棋柱并可退出 | `test_m8_rs_e2e_09_pillar_overlay_by_owner` |
| M8-RS-E2E-10 | 棋柱弹层按大小视图 | 视图切换后按牌力排序；“包含柱外牌”开关仅影响本地展示 | `test_m8_rs_e2e_10_pillar_overlay_by_power_and_outside_toggle` |
| M8-RS-E2E-11 | 掀扣关系弹层 | 可打开/关闭，关系项显示 `revealer -> buckler`，失效关系样式正确 | `test_m8_rs_e2e_11_reveal_relation_modal` |
| M8-RS-E2E-12 | 结算弹层展示 | 收到结算后展示 `delta/delta_enough/delta_reveal/delta_ceramic` | `test_m8_rs_e2e_12_settlement_modal_fields` |
| M8-RS-E2E-13 | 结算关闭与再开局 | 关闭结算弹层后出现“重新 ready”提示；三人再次 ready 可开启新局 | `test_m8_rs_e2e_13_close_settlement_and_ready_next_game` |
| M8-RS-E2E-14 | 对局中 WS 断线重连 | 对局中断开 WS 后可自动重连并通过 REST 兜底恢复状态 | `test_m8_rs_e2e_14_ingame_ws_reconnect_and_rest_resync` |
| M8-RS-E2E-15 | 对局冷结束提示 | 对局中成员离房触发 `playing -> waiting` 且无结算时，显示“对局结束” | `test_m8_rs_e2e_15_ingame_cold_end_prompt` |

### 2.1 关键动作链路详细清单（M8-RS-E2E-04~07）

| 测试ID | 前置条件 | 操作步骤 | 通过条件 |
|---|---|---|---|
| M8-RS-E2E-04 | 三人已开局，当前玩家为回合首位，`legal_actions` 包含多个 `PLAY` 候选 | 点击手牌形成对子/三牛组合并提交 `PLAY` | 仅合法组合可选；提交成功后回合公共态更新 |
| M8-RS-E2E-05 | 三人已开局，当前玩家为非首位，存在可压制 `PLAY` | 选择单牌（或组合）并提交 | 交互自动收敛到唯一合法组合；提交后 `turn.current_seat` 推进 |
| M8-RS-E2E-06 | 当前玩家仅有 `COVER(required_count=n)` 动作 | 连续选择 n 张牌并提交 | n 未满足时按钮不可点击；满足后可提交且状态推进 |
| M8-RS-E2E-07 | 已进入可操作状态，前端持有过期版本号 | 先由他端推进版本，再以旧版本提交动作 | 返回 409 后自动拉取最新快照，清空当前选择并可继续操作 |

### 2.2 结算与收束详细清单（M8-RS-E2E-12~15）

| 测试ID | 前置条件 | 操作步骤 | 通过条件 |
|---|---|---|---|
| M8-RS-E2E-12 | 对局即将结束（可通过注入 seed 稳定复现） | 推进至 `phase=settlement` | 结算弹层展示每位玩家分项与总变化 |
| M8-RS-E2E-13 | 结算弹层已显示 | 点击关闭；三人再次 ready | 弹层关闭后回等待态提示；再次 ready 进入新局 |
| M8-RS-E2E-14 | 对局进行中，A/B 双端在同房间 | 主动中断 A 的房间 WS，B 端继续操作推进 | A 自动重连并拉态，最终与后端一致 |
| M8-RS-E2E-15 | 三人同房且已 `playing` | 任一玩家离房触发冷结束 | 其余玩家收到 `playing -> waiting` 并出现“对局结束”提示 |

## 3) 收口通过标准（M8 Exit Criteria, Real Backend）

- `M8-GATE-01~04` 全部通过。
- `M8-RS-E2E-01~15` 全部通过。
- 关键语义满足：
  - `legal_actions -> UI -> action submit` 全链路正确。
  - `client_version` 冲突可自动恢复，且恢复后可继续提交。
  - 公私信息隔离正确，不泄露对手手牌/垫牌牌面。
  - 结算展示与“再 ready 开新局”链路可用。
- 稳定性要求：同一环境连续执行 2 轮，无随机失败。

## 4) TDD 执行记录

> 约定：按“人类指定测试 ID -> 编写测试 -> 执行 Red/Green”推进；每条用例先记录 Red，再记录 Green。

| 测试ID | 当前状态 | TDD阶段 | 执行日期 | 备注 |
|---|---|---|---|---|
| M8-GATE-01 | ⏳ 待执行 | 未开始 | - | - |
| M8-GATE-02 | ⏳ 待执行 | 未开始 | - | - |
| M8-GATE-03 | ⏳ 待执行 | 未开始 | - | - |
| M8-GATE-04 | ⏳ 待执行 | 未开始 | - | - |
| M8-RS-E2E-01 | ⏳ 待执行 | 未开始 | - | - |
| M8-RS-E2E-02 | ⏳ 待执行 | 未开始 | - | - |
| M8-RS-E2E-03 | ⏳ 待执行 | 未开始 | - | - |
| M8-RS-E2E-04 | ⏳ 待执行 | 未开始 | - | - |
| M8-RS-E2E-05 | ⏳ 待执行 | 未开始 | - | - |
| M8-RS-E2E-06 | ⏳ 待执行 | 未开始 | - | - |
| M8-RS-E2E-07 | ⏳ 待执行 | 未开始 | - | - |
| M8-RS-E2E-08 | ⏳ 待执行 | 未开始 | - | - |
| M8-RS-E2E-09 | ⏳ 待执行 | 未开始 | - | - |
| M8-RS-E2E-10 | ⏳ 待执行 | 未开始 | - | - |
| M8-RS-E2E-11 | ⏳ 待执行 | 未开始 | - | - |
| M8-RS-E2E-12 | ⏳ 待执行 | 未开始 | - | - |
| M8-RS-E2E-13 | ⏳ 待执行 | 未开始 | - | - |
| M8-RS-E2E-14 | ⏳ 待执行 | 未开始 | - | - |
| M8-RS-E2E-15 | ⏳ 待执行 | 未开始 | - | - |
