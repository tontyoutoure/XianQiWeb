# M8 阶段真实后端收口测试设计草案（In-game + Settlement + Seed Hunter）

> 目标：在真实启动的后端服务上完成 M8 对局与结算联调收口，并先冻结“种子注入 + Seed Hunter”的测试设计口径。
> 依据文档：`memory-bank/implementation-plan.md`（M8）、`memory-bank/design/backend_design.md`、`memory-bank/design/frontend_ingame_design.md`、`memory-bank/interfaces/frontend-backend-interfaces.md`、`memory-bank/interfaces/backend-engine-interface.md`。
> 口径声明：本文件当前只保留“测试设计草案”，不包含测试用例 ID、Red/Green 执行记录与通过结果。
> 当前状态：等待测试设计评审确认。

## 0) 测试环境与执行约定（真实服务）

- 建议环境：
  - 后端：conda `XQB`
  - 前端：Node.js `22.x`
- 后端启动（推荐）：
  - `XQWEB_APP_ENV=test`
  - `XQWEB_APP_HOST=127.0.0.1`
  - `XQWEB_APP_PORT=18080`
  - `XQWEB_TEST_DB_DIR=/tmp/xqweb-test`（可选）
  - `XQWEB_JWT_SECRET=<at-least-32-byte-secret>`
  - `bash scripts/start-backend-test.sh`
- 前端环境变量（`frontend/.env.test` 或命令行覆盖）：
  - `VITE_API_BASE_URL=http://127.0.0.1:18080`
  - `VITE_WS_BASE_URL=ws://127.0.0.1:18080`
- e2e 执行建议：
  - `cd frontend && npm run test:e2e -- --project=chromium --workers=1`
- 数据隔离约定：
  - 每轮测试使用唯一用户名前缀。
  - 每轮测试使用全新后端实例（避免跨用例房间污染）。

## 1) Seed Hunter 设计索引（SSOT）

> Seed Hunter 与种子注入的设计细节 `memory-bank/design/backend_design.md` 第 4 章。