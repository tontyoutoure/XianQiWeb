# 前端配置与测试方法

本文面向前端经验较少的同学，目标是帮助你按统一方式完成：
- 本地开发环境准备
- 前端工具链理解与配置
- 单元测试 / 组件测试 / E2E 测试执行
- 常见报错排查

对齐文档：
- `memory-bank/architecture.md`
- `memory-bank/product-requirements.md`
- `memory-bank/design/frontend_design.md`
- `memory-bank/interfaces/frontend-backend-interfaces.md`
- `memory-bank/implementation-plan.md`
- `memory-bank/progress.md`

## 1. 文档边界

本文仅包含可复用的前端配置与测试方法，不记录当前阶段进度、里程碑状态或临时推进信息。  
相关进度请统一查看：
1. `memory-bank/implementation-plan.md`
2. `memory-bank/progress.md`

## 2. 环境准备

## 2.1 软件版本
- Node.js：建议 `22.x LTS`
- npm：建议 `10.x+`
- Git：任意近两年版本均可

检查命令：

```bash
node -v
npm -v
git --version
```

通过条件：
- `node -v` 返回 `v22.*`（或团队统一允许版本）
- `npm -v` 正常输出版本号

## 2.2 IDE 与插件（VS Code）
- `Volar`（Vue 官方 TS 支持）
- `ESLint`
- `Playwright Test for VSCode`（可选）

## 2.3 环境变量
前端至少需要后端地址（示例）：

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_WS_BASE_URL=ws://127.0.0.1:8000
```

建议放在 `frontend/.env.development`（开发环境）与 `frontend/.env.test`（测试环境）。

## 3. 工具链总览（每个工具做什么）

- `Vite`：开发服务器（HMR）和打包构建（build）
- `TypeScript + vue-tsc`：类型检查（type-check）
- `Vue Router`：页面路由与导航守卫
- `Pinia`：状态管理（auth/lobby/room/ws）
- `Axios`：REST 请求封装与拦截器
- `WebSocket client`：实时事件（lobby、room）
- `Vitest`：单元测试与组件测试执行器
- `Vue Test Utils`：Vue 组件测试工具
- `Playwright`：端到端（E2E）测试
- `ESLint + Prettier`：代码质量和格式统一

## 4. 推荐配置基线（待落地）

本节是“应该具备哪些配置”的最低标准，不要求你一次理解全部原理，先照着执行即可。

## 4.1 `package.json` 推荐脚本

```json
{
  "scripts": {
    "dev": "vite",
    "build": "npm run type-check && vite build",
    "preview": "vite preview",
    "type-check": "vue-tsc --noEmit",
    "lint": "eslint .",
    "lint:fix": "eslint . --fix",
    "test": "vitest run",
    "test:watch": "vitest",
    "test:ui": "vitest --ui",
    "test:e2e": "playwright test",
    "test:e2e:ui": "playwright test --ui"
  }
}
```

## 4.2 `tsconfig` 基线
- 保证 `src/**/*.ts` 与 `src/**/*.vue` 都参与类型检查。
- 为 `@` 别名（指向 `src`）提供类型支持。
- `strict` 建议开启，尽早发现空值与类型不一致问题。

## 4.3 `vite.config.ts` 基线
- 启用 Vue 插件。
- 配置 `@` -> `src` 别名。
- 通过 `import.meta.env` 读取后端 REST / WS 地址。

## 4.4 `vitest.config.ts` 基线
- `environment: "jsdom"`（组件测试常用）
- `globals: true`（可选，便于 `describe/it/expect`）
- 配置 `setupFiles`，统一放置 mock 和测试钩子。

## 4.5 `playwright.config.ts` 基线
- 设置 `baseURL`（前端本地地址，如 `http://127.0.0.1:5173`）
- 支持 `webServer` 自动拉起 `npm run dev`（或对接 CI 启动流程）
- 开启失败截图、trace（便于排查）

## 4.6 ESLint / Prettier 基线
- ESLint 负责代码质量（未使用变量、错误模式等）
- Prettier 负责格式统一（缩进、换行、引号风格）
- 提交前至少跑：`npm run lint && npm run type-check`

## 5. 日常开发命令（npm）

默认在 `frontend/` 目录下执行：

## 5.1 安装依赖

```bash
npm install
```

预期结果：生成 `node_modules/`，无致命报错。

## 5.2 启动开发服务

```bash
npm run dev
```

预期结果：终端输出本地访问地址（通常 `http://127.0.0.1:5173`）。

## 5.3 类型检查

```bash
npm run type-check
```

预期结果：退出码 0；若失败，按报错定位到 `.ts/.vue` 文件修复。

## 5.4 代码检查

```bash
npm run lint
```

自动修复（如果配置支持）：

```bash
npm run lint:fix
```

## 5.5 单元/组件测试

```bash
npm run test
```

开发时持续监听：

```bash
npm run test:watch
```

## 5.6 E2E 测试

```bash
npm run test:e2e
```

需要图形调试时：

```bash
npm run test:e2e:ui
```

## 5.7 生产构建与预览

```bash
npm run build
npm run preview
```

## 6. 测试方法（非对局流程示例）

本节聚焦非对局闭环：登录、鉴权、房间、大厅、连接恢复。

## 6.1 单元测试（Vitest）

推荐优先级：
1. `authStore`
2. `roomStore`
3. `services/http.ts`
4. `ws` 重连退避逻辑

关键用例：
- 登录成功后 token 与用户信息入库
- access token 过期时 refresh 成功/失败分支
- `playing -> waiting` 且无 `SETTLEMENT` 时 `coldEnded=true`
- HTTP 401 后触发 refresh 并重放一次请求

通过条件：
- 覆盖关键分支，不只验证 happy path
- 断言状态变化与副作用（跳转、清理会话）正确

## 6.2 组件测试（Vue Test Utils）

推荐对象：
- `LobbyPage.vue`
- `RoomPage.vue`
- `ConnectionBadge.vue`

关键场景：
- 房间列表正常态 / 空态 / 错误态
- ready 开关点击后 UI 状态反馈
- WS 连接状态变化时标识文本变化

通过条件：
- 使用语义化断言（看用户可见结果，不测实现细节）
- 必要时 mock store 与 API，不依赖真实网络

## 6.3 E2E 测试（Playwright）

主流程场景：
1. 登录 -> 进入大厅 -> 可见房间列表
2. 加入房间 -> ready -> 取消 ready -> leave
3. 模拟断网/断连后恢复，页面能自动重连并恢复房间态

建议：
- 每个场景独立账号或独立测试前置，避免相互污染
- 失败时保留截图与 trace，优先用回放定位问题

## 6.4 REST/WS 的 mock 策略

- 单元/组件测试：优先 mock `auth-api.ts`、`rooms-api.ts` 和 `ws-client.ts`
- E2E：尽量连真实后端测试环境，保证协议联动真实

## 7. 提交前检查（建议固化为习惯）

在 `frontend/` 目录执行：

```bash
npm run type-check
npm run lint
npm run test
```

如果改动影响登录/房间主流程，再执行：

```bash
npm run test:e2e
```

## 8. 常见问题排查

## 8.1 `npm install` 失败
- 先检查 Node/npm 版本
- 删除 `node_modules` 与 lock 文件后重装（团队允许时）
- 检查网络代理/镜像源

## 8.2 `npm run dev` 启动但页面空白
- 检查 `main.ts` 是否正确挂载
- 检查路由初始跳转是否误导到受保护页面
- 查看浏览器控制台与 Network 面板

## 8.3 401 循环刷新
- 检查 refresh 接口是否返回新 token
- 确认拦截器只重放一次，避免无限递归
- refresh 失败时必须清会话并回 `/login`

## 8.4 WS 频繁断连
- 检查 `PING/PONG` 处理
- 检查重连退避是否生效（1s/2s/5s/10s）
- 重连成功后是否执行 REST 拉态兜底

## 8.5 E2E 不稳定
- 避免依赖 `sleep`，改为等待可见状态或接口响应
- 固定测试数据与账号
- 对关键节点加截图/日志

## 9. 新手一步跑通清单

1. 安装 Node.js 22 与 npm。
2. 进入 `frontend/` 执行 `npm install`。
3. 配置 `.env.development` 中的后端 REST/WS 地址。
4. 执行 `npm run dev`，确认页面可打开。
5. 执行 `npm run type-check` 和 `npm run lint`。
6. 执行 `npm run test`，确认单元/组件测试可跑。
7. 执行 `npm run test:e2e`，确认主流程可跑。

---

如果你只想先做最小闭环，请记住一句话：
先跑通 `dev -> type-check -> lint -> test`，再进功能开发。
