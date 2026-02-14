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
- M1-API-03（username 大小写敏感）已完成绿阶段并通过测试。
- M1-API-04（MVP 空密码注册/登录）已完成绿阶段并通过测试。
- 后端入口已完成拆分重构，`main.py` 不再承载全部鉴权实现细节。
- auth 模块已进一步细分为 service/repository/session/errors 分层，职责更清晰。

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
- 2026-02-14：完成 M1-API-01 绿阶段：新增 `app.main` 最小可用注册链路（建表、username 归一化、password hash、access/refresh 签发、refresh 仅存 hash），并通过 API-01 测试（`1 passed, 11 skipped`）。
- 2026-02-14：进入 M1-API-02 红阶段：新增“重复用户名（含 NFC 等价）返回 409 + 统一错误体”测试，当前结果 `1 failed, 1 passed, 10 skipped`；失败原因为冲突错误体仍是 `{\"detail\":{...}}`。
- 2026-02-14：完成 M1-API-02 绿阶段：在 `app.main` 增加统一 HTTP 错误处理（`{code,message,detail}`），并使 NFC 等价重复注册返回 `409` 标准错误体；API 鉴权测试现状 `2 passed, 10 skipped`。
- 2026-02-14：完成 M1-API-03 绿阶段：`Tom/tom` 大小写敏感注册契约通过，执行 `conda run -n XQB pytest backend/tests/api/auth/test_m1_api_03_case_sensitive.py -q` 结果 `1 passed`；并回归 `API-01~03` 结果 `3 passed`。
- 2026-02-14：进入 M1-API-04 红阶段：新增“空密码可注册且可登录”可执行契约测试；执行 `conda run -n XQB pytest backend/tests/api/auth/test_m1_api_04_empty_password.py -q` 结果 `1 failed`（`app.main` 缺少 `LoginRequest/login`），红阶段符合预期。
- 2026-02-14：完成 M1-API-04 绿阶段：在 `app.main` 新增 `LoginRequest` 与 `POST /api/auth/login`（复用 username 归一化与密码校验，支持空密码）；执行 `conda run -n XQB pytest backend/tests/api/auth/test_m1_api_04_empty_password.py -q` 结果 `1 passed`，并回归 `API-01~04` 结果 `4 passed`。
- 2026-02-14：完成 `app.main` 拆分重构：新增 `app/auth/{models,schema,http,service}.py` 承载鉴权模型/建表/错误处理/业务逻辑，`main.py` 仅保留应用装配与路由入口；回归 `conda run -n XQB pytest backend/tests -q` 结果 `18 passed, 11 skipped`。
- 2026-02-14：完成 auth 进一步拆分：新增 `app/auth/{repository,session,errors}.py`，将数据访问、会话签发、错误构造从 `service.py` 拆离；再次回归 `conda run -n XQB pytest backend/tests -q` 结果 `18 passed, 11 skipped`。
