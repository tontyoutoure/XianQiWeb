## 当前进度（粗粒度）
- 架构文档评审已结束。
- 游戏规则与 MVP 范围评审已结束。
- 前后端接口文档评审已结束。
- 后端设计文档评审已结束。
- M1 测试清单已落地：`memory-bank/tests/m1-tests.md`。
- M1 pytest 骨架已创建：`backend/tests/`（unit/api/ws 三层目录）。
- M1-UT-05（username 规则）已完整实现并通过单测。
- M1-UT-01（密码 hash/verify）已按 TDD 红绿流程实现并通过单测。
- M1-UT-02/03/04 已按 TDD 完成红绿闭环并通过单测。

## 当前阶段
- 文档评审阶段已完成，进入后端实现与测试落地阶段。

## 最近更新
- 2026-02-14：新增 M1 测试清单文档，覆盖单元/API/WS 鉴权测试项与输入输出预期。
- 2026-02-14：搭建 `backend/tests` pytest 骨架，按 M1-UT / M1-API / M1-WS 编号对齐测试占位。
- 2026-02-14：完成 `app.core.username` 的 trim + NFC + 1~10 grapheme 校验实现，落地 M1-UT-05 全量单测（4 passed）。
- 2026-02-14：完成 `app.core.password`（bcrypt hash/verify）实现并通过 M1-UT-01（4 passed）。
- 2026-02-14：完成 `app.core.tokens`（JWT sub/exp + 过期校验）、`app.core.refresh_tokens`（issue/validate/rotate + 旧 token 失效）、`app.core.db`（SQLite foreign_keys=ON）实现，M1-UT-02/03/04 通过。
- 2026-02-14：`conda run -n XQB pytest backend/tests/unit -q` 结果：12 passed, 1 skipped。
- 2026-02-14：在 `memory-bank/tests/m1-tests.md` 追加 TDD 执行进度节，明确 UT-06 仍待完成（暂不建议直接进入 API 实现）。
- 2026-02-14：完成 M1-UT-06 红阶段：将占位测试替换为 2 个真实失败用例（refresh interval = / > access expire），当前因缺少 `app.core.config.Settings` 导致 `ModuleNotFoundError`，红阶段结果符合预期。
- 2026-02-14：完成 M1-UT-06 绿阶段：新增 `app.core.config.Settings`（pydantic-settings）并实现约束校验 `XQWEB_ACCESS_TOKEN_REFRESH_INTERVAL_SECONDS < XQWEB_ACCESS_TOKEN_EXPIRE_SECONDS`，单测结果更新为 `14 passed`。
- 2026-02-14：进入 M1 API 红阶段：`M1-API-01` 已改为真实契约测试，执行 `conda run -n XQB pytest backend/tests/api/auth/test_auth_endpoints.py -q` 结果为 `1 failed, 11 skipped`（失败原因为缺少 `app.main`，符合红阶段预期）。
- 2026-02-14：按需求调整 API-01 约定：register 除响应字段外需校验数据库落库（`users` + `refresh_tokens`，仅存 `token_hash`）；已同步更新接口/设计文档与 API-01 测试样例。
