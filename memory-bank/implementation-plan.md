## 开发计划（MVP，已按当前架构/接口修正）
面向：三人掀棋、账号密码登录、预设房间、实时对局、结算与继续下一局。

## 标注说明
- 关注维度：架构 / 接口 / 实现 / 测试。
- 范围维度：前端 / 后端 / 逻辑引擎。
- 逻辑引擎独立性原则：核心规则与状态机不依赖 Web 框架与数据库；通过 `init_game / apply_action / settle / dump_state / load_state` 与后端集成。
- 流程约束：每一里程碑实现完成后，必须先通过对应测试/验证，再进入下一里程碑。

## 里程碑与任务拆解
### M0 架构与接口冻结（已完成）
目标：锁定 MVP 范围、状态机、协议与数据契约，作为实现基线。
- 已完成文档：`architecture.md`、`interfaces/frontend-backend-interfaces.md`、`interfaces/backend-engine-interface.md`。
- 关键冻结项：
  - 持久化仅 `users + refresh_tokens`；房间/对局/快照均为内存态。
  - 房间为服务端预设编号，不提供创建/解散接口。
  - 动作协议采用 `action_idx + cover_list (+ client_version)`。
  - WS 双通道：`/ws/lobby` 与 `/ws/rooms/{room_id}`，含初始全量快照与心跳。

### M1 后端基础与鉴权
目标：完成可用的账号体系与统一鉴权入口（REST + WS）。
- 实现：FastAPI 项目骨架、配置、日志、CORS、SQLite 初始化。
- 实现：`users`、`refresh_tokens` 表与基础索引。
- 实现：`/api/auth/register`、`/api/auth/login`、`/api/auth/me`、`/api/auth/refresh`、`/api/auth/logout`。
- 实现：JWT access token（短期）+ refresh token 轮换与撤销。
- 测试/验证：
  - 注册/登录/鉴权/刷新/登出闭环通过。
  - 失效 refresh token 不可复用。
  - WS token 鉴权失败返回未授权关闭（4401）。

### M2 房间大厅（预设房间模型）
目标：完成固定房间生命周期与成员管理。
- 实现：预设房间初始化、房主判定、座位分配、ready 状态。
- 实现：`/api/rooms`、`/api/rooms/{room_id}`、`/join`、`/leave`、`/ready`。
- 实现：房态流转 `waiting | playing | settlement` 与人数/就绪计数。
- 实现：中途离房冷结束规则（不结算、筹码不变、房间回 `waiting`）。
- 测试/验证：
  - 三人加入/离开/准备流程正确。
  - 房间满员、重复加入、非成员操作返回 4xx。
  - 冷结束后 `current_game_id` 清空。

### M3 逻辑引擎核心规则
目标：独立完成可复用的三人掀棋引擎。
- 实现：牌堆构建、发牌、先手随机、黑棋命中后按 `seed+1` 自动重发直到非黑棋。
- 实现：阶段状态机 `init → buckle_flow → in_round → settlement → finished`（`buckle_flow` 内含 BUCKLE/PASS_BUCKLE 与 REVEAL/PASS_REVEAL 询问流）。
- 实现：出棋/压制/垫棋/扣棋/掀棋与回合归属、柱数组统计。
- 实现：公开态/私有态脱敏输出与 `legal_actions` 生成。
- 实现：本地调试 CLI（`engine/cli.py`），支持可选 seed（未传则取当前时间），并按决策 seat 轮流扮演三名玩家推进一局。
- 测试/验证：
  - 牌力比较、狗脚对/三牛、必须压制/只能垫棋等核心用例通过。
  - `action_idx` 顺序稳定，非法动作被拒绝。
  - `client_version` 不一致时返回版本错误。
  - CLI 可展示公共态 + 当前 seat 私有态 + 合法动作列表，并支持 COVER 输入与错误重试。

### M4 后端-引擎集成与动作接口
目标：将引擎能力完整映射到 REST/WS 协议。
- 实现：房间座次与引擎 seat 映射、game 生命周期管理。
- 实现：`/api/games/{game_id}/state`、`/api/games/{game_id}/actions`（204）。
- 实现：动作校验链路（成员、回合、phase、`cover_list`、版本）。
- 实现：统一错误响应 `{code,message,detail}`。
- 测试/验证：
  - 动作提交后版本递增与状态推进正确。
  - 非当前行动玩家、非法 `cover_list`、phase 不匹配均被拒绝。

### M5 结算与继续下一局
目标：落地 MVP 基础筹码结算和 continue 流程。
- 实现：够棋/瓷棋/掀棋关系结算（`delta_enough / delta_reveal / delta_ceramic`）。
- 实现：`/api/games/{game_id}/settlement`、`/api/games/{game_id}/continue`。
- 实现：continue 协调：三人均 `true` 立即新开局（无需再次 ready）；任一 `false` 返回 `waiting`。
- 测试/验证：
  - 结算边界用例（够/瓷/掀棋时刻够棋）通过。
  - continue 分支行为与房态切换正确。

### M6 实时推送与断线重连
目标：保证多人一致视图与可恢复性（服务端不重启前提）。
- 实现：`/ws/lobby` 的 `ROOM_LIST` 推送。
- 实现：`/ws/rooms/{room_id}` 的 `ROOM_UPDATE`、`GAME_PUBLIC_STATE`、`GAME_PRIVATE_STATE`、`SETTLEMENT`。
- 实现：连接后初始全量快照策略与 30s PING / 10s PONG 心跳。
- 实现：重连后 HTTP/WS 快照恢复（公共+私有+legal_actions）。
- 测试/验证：
  - 三端并发操作下事件顺序一致。
  - 断线重连可恢复当前局状态。

### M7 前端 MVP 页面与交互
目标：完成从登录到结算的完整可玩前端。
- 实现：登录页、大厅页、房间页、对局页、结算弹窗。
- 实现：Token 管理（含 refresh）、WS 连接管理与重连。
- 实现：按 `legal_actions` 渲染可操作按钮与 `cover_list` 选择器。
- 实现：公共信息与私有信息隔离展示（不泄露他人手牌/垫牌牌面）。
- 测试/验证：
  - 三人实机联调流程走通。
  - 关键异常（掉线、token 过期、非法操作）可恢复且提示明确。

### M8 全链路验收与发布准备
目标：完成 MVP 发布前回归与运行文档。
- 验收：登录→加入预设房间→准备→完整对局→结算→continue 全流程。
- 回归：规则、状态机、接口契约、WS 事件与错误码。
- 文档：更新部署/运行说明与验收记录。

## 交付物清单
- 后端：FastAPI 服务、SQLite 鉴权数据层、REST + WS 协议实现。
- 逻辑引擎：独立规则模块（可单测、可序列化 dump/load）。
- 前端：Vue3 + TS MVP 页面与实时状态同步。
- 文档：`architecture.md`、接口文档、`implementation-plan.md`、`progress.md` 持续同步。

## 风险与待决
- 规则边界（尤其掀棋时刻“已够未瓷”的结算细则）需以 `XianQi_rules.md` 与测试样例固化。
- `client_version` 冲突处理已定：后端返回 409，前端立即 REST 拉取最新状态，避免旧状态覆盖。
- 服务端重启后内存态清空：前端需明确提示并引导用户重新入房。
