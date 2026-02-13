## 1 总体架构与依赖方向 已评审
## 2 MVP 范围与规则约束 已评审（房间改为预设编号，无创建）
## 3 对局阶段与回合流程 已评审
## 4 逻辑引擎接口设计 已评审
## 5 持久化策略调整（仅 users + refresh_tokens 入库，房间/对局内存态）已确认
## 6 前后端接口评审结论（已完成）
- ✅ 鉴权方案与 WS 鉴权方式已定义（Bearer/WS token、/me 响应结构）。
- ✅ 动作与牌载荷结构已定义，legal_actions/action_hints 已统一。
- ✅ 公共/私有状态结构已指向引擎文档 1.5.x（public/private/legal_actions），顶层字段收敛。
- ✅ 房间相关响应已定义，列表字段命名已统一，状态枚举已落地。
- ✅ WS 协议已补充版本号/初始快照/错误格式/心跳策略。
- ✅ settlement/continue 可调用时机与权限已说明。
## 7 鉴权方案已定义（access+refresh，WS query token，refresh 90 天）
## 8 TODO
- ✅ WS 各类型 payload 结构已明确（ROOM_LIST/ROOM_UPDATE/GAME_PUBLIC_STATE/SETTLEMENT 等）。
## 9 开发计划修订（已完成）
- ✅ `implementation-plan.md` 已按当前架构/接口重排里程碑（M0-M8）。
- ✅ 已纳入预设房间、冷结束规则、continue 直开新局、WS 初始快照/心跳等实现顺序。
- ✅ 已补充 `client_version` 冲突处理口径差异与建议基线（引擎校验并返回 409）。
## 10 后端设计文档（M1-M2）已补充
- ✅ 已在 `memory-bank/design/backend_design.md` 完成 M1（后端基础与鉴权）详细设计。
- ✅ 已在 `memory-bank/design/backend_design.md` 完成 M2（预设房间与大厅）详细设计。
- ✅ 已补充并发策略、错误码建议、测试清单与风险决策。
## 11 M1 鉴权策略细化（已确认）
- ✅ 登录策略：新登录撤销该用户全部历史 refresh token（踢掉旧登录）。
- ✅ logout 语义：仅注销当前 refresh token。
- ✅ refresh token 清理：服务启动执行一次 + 每日 00:00 执行一次。
- ✅ access token：MVP 暂不做立即失效，按 `exp` 自然过期。
## 12 MVP 安全边界口径已同步
- ✅ `backend_design.md` 已同步“安全性基础可用、暂不做强对抗防护”的 MVP 口径。
