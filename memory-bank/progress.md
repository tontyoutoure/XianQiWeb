## 当前进度（粗粒度）
- 架构文档评审已结束。
- 游戏规则与 MVP 范围评审已结束。
- 前后端接口文档评审已结束。
- 后端设计文档评审已结束。
- M1 测试清单已落地：`memory-bank/tests/m1-tests.md`。
- M1 pytest 骨架已创建：`backend/tests/`（unit/api/ws 三层目录）。
- M1-UT-05（username 规则）已完整实现并通过单测。
- M1-UT-01（密码 hash/verify）已按 TDD 红绿流程实现并通过单测。
- M1-UT-02/03/04 红阶段测试已落地（当前按预期失败）。

## 当前阶段
- 文档评审阶段已完成，进入后端实现与测试落地阶段。

## 最近更新
- 2026-02-14：新增 M1 测试清单文档，覆盖单元/API/WS 鉴权测试项与输入输出预期。
- 2026-02-14：搭建 `backend/tests` pytest 骨架，按 M1-UT / M1-API / M1-WS 编号对齐测试占位。
- 2026-02-14：完成 `app.core.username` 的 trim + NFC + 1~10 grapheme 校验实现，落地 M1-UT-05 全量单测（4 passed）。
- 2026-02-14：完成 `app.core.password`（bcrypt hash/verify）实现并通过 M1-UT-01（4 passed）；`backend/tests/unit` 当前结果 8 passed, 4 skipped。
- 2026-02-14：将 M1-UT-02/03/04 改为真实红阶段测试并执行，当前报错为缺失 `app.core.tokens` / `app.core.refresh_tokens` / `app.core.db` 实现（符合 red 阶段预期）。
