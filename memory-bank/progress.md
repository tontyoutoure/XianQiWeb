## 1 总体架构与依赖方向 已评审
## 2 MVP 范围与规则约束 已评审
## 3 对局阶段与回合流程 已评审
## 4 逻辑引擎接口设计 已评审
## 5 持久化策略调整（仅 users 入库，房间/对局内存态）已确认
## 6 前后端接口评审结论（已完成）
- ✅ 鉴权方案与 WS 鉴权方式已定义（Bearer/WS token、/me 响应结构）。
- ✅ 动作与牌载荷结构已定义，legal_actions/action_hints 已统一。
- ✅ 公共/私有状态结构已指向引擎文档 1.5.x（public/private/legal_actions），顶层字段收敛。
- ✅ 房间相关响应已定义，列表字段命名已统一，状态枚举已落地。
- ✅ WS 协议已补充版本号/初始快照/错误格式/心跳策略。
- ✅ settlement/continue 可调用时机与权限已说明。
## 7 鉴权方案已定义（access+refresh，WS query token，refresh 90 天）
