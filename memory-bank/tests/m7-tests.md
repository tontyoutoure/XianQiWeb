# M7 阶段测试列表（前端非对局，TDD）

> 依据文档：
> - `memory-bank/implementation-plan.md`（M7 非对局范围）
> - `memory-bank/design/frontend_design.md`（M7：非对局部分）
> - `memory-bank/interfaces/frontend-backend-interfaces.md`（Auth/Rooms/WS）
> 目标：按 M7 建议实施顺序，先固化测试清单，再由人类指定测试用例进入 Red -> Green 循环。

## 0) 测试环境与执行策略

- 前端测试分层：
  - 单元测试（Store / Router Guard / HTTP 拦截器 / WS 管理器）
  - 组件测试（登录页/大厅页/房间页关键交互）
  - E2E（登录 -> 大厅 -> 房间主流程与恢复能力）
- 推荐命令（以最终 `package.json` 脚本为准）：
  - 单元/组件：`pnpm vitest`
  - E2E：`pnpm playwright test`
- M7 E2E（`M7-E2E-01~03`）补充约束：
  - 需先启动后端（默认 `http://127.0.0.1:18080`）。
  - 用例内应自准备测试账号，不依赖预置账号（如 `alice/secret`）。
- TDD 流程约束：
  1. 人类先指定测试ID。
  2. 先写测试并执行 Red（失败符合预期）。
  3. 再最小实现到 Green。
  4. 每个测试用例通过后，回填本文件“执行记录”。

## 1) 按实施顺序的测试用例列表

### 1.1 阶段一：Router + Pinia + Axios 基础设施

| 测试ID | 测试描述 | 通过条件 |
|---|---|---|
| M7-UT-01 | 路由守卫：未登录访问 `/lobby` 跳转 `/login` | `requiresAuth` 生效，URL 最终为 `/login` |
| M7-UT-02 | 路由守卫：access 临近过期时触发 refresh 后放行 | refresh 成功后可进入目标受保护路由 |
| M7-UT-03 | HTTP 请求拦截器自动注入 Bearer token | 发出的请求头包含 `Authorization: Bearer <access_token>` |
| M7-UT-04 | HTTP 响应拦截器：401 时自动 refresh 并重放原请求 | 原请求被重试一次且最终成功返回 |
| M7-UT-05 | refresh 失败触发统一登出与状态清理 | token/user 清空并跳转 `/login` |

### 1.2 阶段二：`authStore` 与登录页

| 测试ID | 测试描述 | 通过条件 |
|---|---|---|
| M7-UT-06 | `authStore.login` 成功后写入会话态 | `user/accessToken/refreshToken/accessExpireAt` 正确落 store |
| M7-UT-07 | `authStore.hydrateFromStorage` 可恢复会话 | 刷新页面后 store 可恢复最小登录态 |
| M7-CT-01 | 登录页提交成功后跳转大厅 | 登录成功后导航到 `/lobby` |
| M7-CT-02 | 登录失败展示后端错误信息 | 页面展示 `message` 且不跳转 |
| M7-CT-03 | 注册并登录入口闭环 | 注册成功后进入 `/lobby` 且 store 有效 |

### 1.3 阶段三：大厅页与 `/ws/lobby`

| 测试ID | 测试描述 | 通过条件 |
|---|---|---|
| M7-CT-04 | 大厅页渲染房间列表与空态/错误态 | `room_id/status/player_count/ready_count` 正确显示 |
| M7-WS-01 | 大厅 WS 建连后接收 `ROOM_LIST` 全量快照 | store.rooms 与消息 payload 一致 |
| M7-WS-02 | 大厅 WS 增量更新房间摘要 | join/ready 事件后列表计数同步变化 |
| M7-CT-05 | 点击房间行 join 后跳到房间页 | 成功导航到 `/rooms/:roomId` |

### 1.4 阶段四：房间页与 `/ws/rooms/{room_id}`

| 测试ID | 测试描述 | 通过条件 |
|---|---|---|
| M7-WS-03 | 房间 WS 建连后接收 `ROOM_UPDATE` 初始快照 | roomDetail 与 payload 一致 |
| M7-CT-06 | 房间页 ready 切换成功 | ready 状态与 `ready_count` 同步更新 |
| M7-CT-07 | 房间页 leave 成功回大厅 | 调用成功后导航回 `/lobby` |
| M7-WS-04 | 冷结束识别与提示 | `playing -> waiting` 且无 `SETTLEMENT` 时出现“对局结束”提示 |

### 1.5 阶段五：异常恢复与收口

| 测试ID | 测试描述 | 通过条件 |
|---|---|---|
| M7-WS-05 | 房间/大厅 WS 心跳 PING/PONG 保活 | 收到 PING 后发送 PONG，连接保持可用 |
| M7-WS-06 | WS 断线自动重连 + REST 拉态兜底 | 重连成功后页面状态恢复一致 |
| M7-E2E-01 | 非对局主流程：登录 -> 大厅 -> 入房 -> ready -> leave | 全流程无阻断，页面状态一致 |
| M7-E2E-02 | token 过期自动 refresh 并恢复请求 | 用户无感恢复，不强制回登录 |
| M7-E2E-03 | 服务端重启后提示与引导 | 出现“服务已重置，请重新入房”并回大厅 |

## 2) 阶段通过判定（M7 非对局）

- 路由守卫、会话恢复、HTTP 拦截链路稳定可用。
- 登录/注册/大厅/房间（ready/leave）主流程可用。
- 大厅与房间 WS 全量/增量同步可用，冷结束提示正确。
- 断线重连、token 过期、服务端重启三类恢复场景可用。
- 不包含对局操作 UI 与结算详情（归 M8）。

## 3) TDD 执行记录

> 说明：`UT01~UT07` 与 `CT01~CT03` 已完成 Red/Green；其余测试项待后续阶段继续执行并回填。

| 测试ID | 当前状态 | TDD阶段 | 执行日期 | 备注 |
|---|---|---|---|---|
| M7-UT-01 | ✅ Green通过 | Green完成 | 2026-03-01 | 已先 Red 后 Green；未登录访问受保护路由会跳转 `/login` |
| M7-UT-02 | ✅ Green通过 | Green完成 | 2026-03-01 | 已先 Red 后 Green；临期 token 触发 refresh 后可放行 |
| M7-UT-03 | ✅ Green通过 | Green完成 | 2026-03-01 | 已先 Red 后 Green；请求拦截器自动注入 Bearer token |
| M7-UT-04 | ✅ Green通过 | Green完成 | 2026-03-01 | 已先 Red 后 Green；401 触发 refresh 并重放原请求 |
| M7-UT-05 | ✅ Green通过 | Green完成 | 2026-03-01 | 已先 Red 后 Green；refresh 失败触发统一登出 |
| M7-UT-06 | ✅ Green通过 | Green完成 | 2026-03-01 | 已先 Red 后 Green；`login` 成功写入会话态 |
| M7-UT-07 | ✅ Green通过 | Green完成 | 2026-03-01 | 已先 Red 后 Green；`hydrateFromStorage` 可恢复会话 |
| M7-CT-01 | ✅ Green通过 | Green完成 | 2026-03-01 | 已先 Red 后 Green；登录提交成功后可导航到 `/lobby` |
| M7-CT-02 | ✅ Green通过 | Green完成 | 2026-03-01 | 已先 Red 后 Green；登录失败会展示错误信息并停留 `/login` |
| M7-CT-03 | ✅ Green通过 | Green完成 | 2026-03-01 | 已先 Red 后 Green；注册入口可完成会话写入并跳转 `/lobby` |
| M7-CT-04 | ✅ Green通过 | Green完成 | 2026-03-01 | 已先 Red 后 Green；大厅页已渲染列表容器与空态/错误态节点 |
| M7-WS-01 | ✅ Green通过 | Green完成 | 2026-03-01 | 已先 Red 后 Green；`ROOM_LIST` 可覆盖写入 `store.rooms` |
| M7-WS-02 | ✅ Green通过 | Green完成 | 2026-03-01 | 已先 Red 后 Green；`ROOM_UPDATE` 可按 `room_id` 增量更新摘要 |
| M7-CT-05 | ✅ Green通过 | Green完成 | 2026-03-01 | 已先 Red 后 Green；点击房间 join 按钮可导航到 `/rooms/:roomId` |
| M7-WS-03 | ✅ Green通过 | Green完成 | 2026-03-01 | 已先 Red 后 Green；`ROOM_UPDATE` 初始快照可同步到 `roomDetail` |
| M7-CT-06 | ✅ Green通过 | Green完成 | 2026-03-01 | 已先 Red 后 Green；房间页已提供 ready 控件与 ready 计数展示 |
| M7-CT-07 | ✅ Green通过 | Green完成 | 2026-03-01 | 已先 Red 后 Green；点击 leave 按钮可导航回 `/lobby` |
| M7-WS-04 | ✅ Green通过 | Green完成 | 2026-03-01 | 已先 Red 后 Green；`playing -> waiting` 可识别冷结束并设置“对局结束”提示 |
| M7-WS-05 | ✅ Green通过 | Green完成 | 2026-03-01 | 已先 Red 后 Green；`ws-client` 可在收到 `PING` 后回 `PONG` 并维持连接可用 |
| M7-WS-06 | ✅ Green通过 | Green完成 | 2026-03-01 | 已先 Red 后 Green；`ws store` 断线后可重连并触发 REST 拉态计数 |
| M7-E2E-01 | ✅ Green通过 | Red→Green（回归修复） | 2026-03-01 | 回归 Red：`m7-stage-1-5-red.spec.ts` 使用硬编码 `alice/secret` 导致登录失败；改为用例内注册唯一账号后复测 Green（`cd frontend && npm run test:e2e -- --project=chromium tests/e2e/m7-stage-1-5-red.spec.ts`）。 |
| M7-E2E-02 | ✅ Green通过 | Red→Green（回归修复） | 2026-03-01 | 同批次回归修复：移除预置账号依赖，改为测试内自注册后登录，复测通过。 |
| M7-E2E-03 | ✅ Green通过 | Red→Green（回归修复） | 2026-03-01 | 同批次回归修复：移除预置账号依赖，服务重置提示与回大厅引导断言通过。 |
