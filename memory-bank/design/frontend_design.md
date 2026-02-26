# 前端详细设计文档（M7：非对局部分）

本文档用于指导 M7 前端实现：先完成“对局之外”的功能闭环。
对局操作与结算详情（含 `legal_actions`、`action_idx`、`cover_list`）归入 M8，在需求补充并评审后单独扩展。

## 0. 范围与基线
- 对齐文档：
  - `memory-bank/architecture.md`
  - `memory-bank/product-requirements.md`
  - `memory-bank/interfaces/frontend-backend-interfaces.md`
  - `memory-bank/implementation-plan.md`
- 本阶段包含：
  - 登录/注册、登录态管理、token 刷新
  - 大厅房间列表
  - 入房/离房/ready
  - 房间实时状态同步（`ROOM_UPDATE`）
  - 断线重连与服务端重启提示
- 本阶段不包含：
  - 对局页面操作区（出棋/垫棋/扣棋/掀棋）
  - 结算详情渲染
  - 对局合法动作选择器

## 1. 目标与完成标准
### 1.1 目标
- 打通“登录 -> 大厅 -> 房间（ready/leave）”可用链路。
- 前端建立稳定的 REST + WS 基础设施，为后续对局功能复用。

### 1.2 完成标准（DoD）
- 未登录用户访问受保护页面会跳转到 `/login`。
- 登录后可进入大厅、查看房间状态并加入房间。
- 房间页可操作 ready / leave，且三端状态同步。
- WS 断连后可自动重连并恢复房间快照。
- 服务端重启导致内存态丢失时，前端给出明确提示并引导回大厅重进。

## 2. 技术栈与工程结构

### 2.1 技术栈（前端）
- Vue 3 + TypeScript + Vite
- Vue Router
- Pinia
- Axios
- 原生 WebSocket 封装
- Tailwind CSS
- Vitest + Vue Test Utils
- Playwright

### 2.2 建议目录结构
```text
frontend/
  src/
    main.ts
    app/
      router.ts
      guards.ts
    pages/
      LoginPage.vue
      LobbyPage.vue
      RoomPage.vue
    components/
      AppHeader.vue
      RoomListTable.vue
      RoomMemberList.vue
      ReadyToggle.vue
      ErrorBanner.vue
      ConnectionBadge.vue
    stores/
      auth.ts
      lobby.ts
      room.ts
      ws.ts
    services/
      http.ts
      auth-api.ts
      rooms-api.ts
    ws/
      ws-client.ts
      lobby-channel.ts
      room-channel.ts
    types/
      api.ts
      ws.ts
      domain.ts
```

## 3. 路由与导航设计

### 3.1 路由表
- `/login`：登录/注册页
- `/lobby`：大厅页
- `/rooms/:roomId`：房间页（非对局交互阶段）

### 3.2 路由守卫
- `requiresAuth=true`：`/lobby`、`/rooms/:roomId`
- 守卫流程：
  1. 无 access token -> 跳 `/login`
  2. 有 access token 且即将过期 -> 尝试 refresh
  3. refresh 成功 -> 放行；失败 -> 清理会话并跳 `/login`

### 3.3 导航约束
- 登录成功默认跳 `/lobby`。
- join 房间成功后跳 `/rooms/:roomId`。
- leave 成功后回 `/lobby`。

## 4. 状态管理设计（Pinia）

### 4.1 `authStore`
- 状态：`user`, `accessToken`, `refreshToken`, `accessExpireAt`, `isRefreshing`
- 动作：`login`, `register`, `refresh`, `logout`, `hydrateFromStorage`
- 持久化：仅持久化 token 与最小用户信息；登出时全清。

### 4.2 `lobbyStore`
- 状态：`rooms`, `loading`, `error`, `lobbyWsConnected`, `lastSyncAt`
- 动作：`fetchRooms`, `connectLobbyWs`, `disconnectLobbyWs`, `applyRoomListEvent`

### 4.3 `roomStore`
- 状态：`roomId`, `roomDetail`, `loading`, `error`, `roomWsConnected`, `coldEnded`
- 动作：`fetchRoom`, `joinRoom`, `leaveRoom`, `setReady`, `connectRoomWs`, `applyRoomUpdate`
- 规则：`playing -> waiting` 且未收到 `SETTLEMENT` 时置 `coldEnded=true` 并提示“对局结束”。

### 4.4 `wsStore`
- 状态：通道连接状态、重连次数、最后错误
- 动作：统一管理重连退避（1s/2s/5s/10s，上限 10s）

## 5. REST 设计（Axios）

### 5.1 HTTP 客户端
- `baseURL` 从环境变量读取。
- 请求拦截器：自动注入 `Authorization: Bearer <access_token>`。
- 响应拦截器：
  - 401 时尝试一次 refresh 后重放原请求。
  - refresh 失败则触发统一登出。

### 5.2 API 封装
- `auth-api.ts`
  - `POST /api/auth/register`
  - `POST /api/auth/login`
  - `GET /api/auth/me`
  - `POST /api/auth/refresh`
  - `POST /api/auth/logout`
- `rooms-api.ts`
  - `GET /api/rooms`
  - `GET /api/rooms/{room_id}`
  - `POST /api/rooms/{room_id}/join`
  - `POST /api/rooms/{room_id}/leave`
  - `POST /api/rooms/{room_id}/ready`

### 5.3 错误处理
- 后端统一错误结构 `{code,message,detail}` 映射为前端 `AppError`。
- 页面只消费统一错误对象，不直接依赖 Axios 错误原始结构。

## 6. WebSocket 设计（非对局阶段）

### 6.1 通道职责
- `/ws/lobby`：处理 `ROOM_LIST`。
- `/ws/rooms/{room_id}`：处理 `ROOM_UPDATE`。

### 6.2 事件处理策略
- 已支持：`ROOM_LIST`, `ROOM_UPDATE`, `ERROR`, `PING`, `PONG`
- 占位透传（先不渲染详情）：`GAME_PUBLIC_STATE`, `GAME_PRIVATE_STATE`, `SETTLEMENT`
  - 行为：仅记录“收到对局事件”，不触发操作 UI。

### 6.3 心跳与重连
- 收到 `PING` 立即回 `PONG`。
- 断连触发自动重连；重连成功后立刻发起一次 REST 拉态兜底。
- 若收到鉴权关闭（4401），先 refresh，再重连；refresh 失败则退回登录。

## 7. 页面交互设计（非对局）

### 7.1 登录页（`/login`）
- 两个入口：注册并登录、登录。
- 成功后拉取 `/api/auth/me` 并进入大厅。
- 失败展示后端 `message`。

### 7.2 大厅页（`/lobby`）
- 展示字段：`room_id`, `status`, `player_count`, `ready_count`。
- 支持手动刷新 + WS 自动刷新。
- 点击房间行执行 join。

### 7.3 房间页（`/rooms/:roomId`）
- 展示字段：`room_id`, `status`, `owner_id`, `members(seat,ready,chips)`。
- 提供按钮：ready 开关、leave。
- 当房间状态为 `playing` 或 `settlement`：
  - 本阶段仅显示“对局模块待补充”占位区，不提供对局操作按钮。

## 8. 异常与恢复
- token 过期：自动 refresh；失败则回登录。
- 房间满员/非成员操作：显示业务错误并停留当前页。
- 服务端重启（内存态清空）：
  - REST 404/409 或 WS 断连后重连失败时提示“服务已重置，请重新入房”。
  - 跳回大厅并清理当前房间态。

## 9. 测试与验收（本阶段）

### 9.1 单元测试（Vitest）
- `authStore`：登录、refresh、登出清理。
- `roomStore`：`playing -> waiting` 冷结束识别。
- `http.ts`：401 自动 refresh 与重放。

### 9.2 组件测试（Vue Test Utils）
- `LobbyPage`：房间列表渲染、空态、错误态。
- `RoomPage`：ready 按钮状态与成员列表刷新。
- `ConnectionBadge`：连接状态变化显示。

### 9.3 E2E（Playwright）
- 场景 A：登录 -> 大厅看到房间。
- 场景 B：join 房间 -> ready/取消 ready -> leave。
- 场景 C：断网恢复后页面自动重连并恢复房间快照。

## 10. M8 对局与结算扩展点（待补需求后冻结）
- 对局视图结构（公共态/私有态）
- `legal_actions` 渲染策略
- `action_idx + cover_list + client_version` 提交流程
- 409 冲突处理细节
- 结算弹窗字段映射与再开局引导

## 11. M7 实施顺序（建议）
1. 建立 Router + Pinia + Axios 基础设施。
2. 实现 `authStore` 与登录页。
3. 实现大厅页与 `/ws/lobby`。
4. 实现房间页与 `/ws/rooms/{room_id}`（仅 ROOM_UPDATE）。
5. 完成异常恢复与测试收口。

## 12. 里程碑映射说明
- 本文档对应 `implementation-plan.md` 的 **M7（非对局范围）**。
- 前端对局与结算实现归属 **M8**，不在本文件当前实现范围内。
