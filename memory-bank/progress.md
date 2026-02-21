## 当前进度（精简版）
- M0 文档基线已完成并稳定：架构、规则、接口与设计文档已对齐。
- M1 鉴权链路已完成：REST + WebSocket 登录态可用。
- M2 房间大厅主链路已完成，剩余少量依赖引擎开局能力的收尾项。
- M3 逻辑引擎核心规则已实现并通过阶段测试；CLI 可完成一局从开局到结算的基础演示。
- M5 结算能力已接入 CLI：进入 `settlement` 后可直接输出按 seat 的结算明细。
- M4/M5/M6 文档已补齐（2026-02-20）：已冻结 Games REST、房间 WS 游戏事件、结算后重新 ready 开局规则与对应测试清单。
- M4-UT-01~05 已完成 Green（2026-02-20）：后端 game 编排层单测从 Red（`5 failed`）推进到 Green（`5 passed`）。
- M4 真实服务收口脚手架已完成（2026-02-21）：新增 `m4-tests-real-service.md` 与 `test_m4_rs_rest/ws/cc` 占位测试文件，初始阶段全部为 skip，后续按测试ID逐条落地测试体。
- M4 测试文档已去重（2026-02-21）：`m4-tests.md` 收敛为 UT + 收口索引，M4 API/WS/CC 清单统一由 `m4-tests-real-service.md` 维护。
- M4-API-01~05 真实服务收口已完成 Green（2026-02-21）：新增并打通 `/api/games/{id}/state`、`/api/games/{id}/actions` 基础链路，测试结果 `5 passed, 9 skipped`。
- M4-API-06~10 真实服务收口已完成 Green（2026-02-21）：补齐测试体并修复 `GET /api/games/{id}/settlement` phase gate 后，结果 `5 passed, 9 deselected`。
- M4-API-11~14 真实服务收口已完成 Green（2026-02-21）：先完成 Red（`4 failed, 10 deselected`，失败点为 80 步内未进入 settlement），随后补齐后端 settlement 迁移与 ready 重置/再开局链路后复测结果 `4 passed, 10 deselected`。
- M4-API-01~14 全量 REST 收口回归通过（2026-02-21）：执行 `pytest backend/tests/integration/real_service/test_m4_rs_rest_01_14_red.py -q`，结果 `14 passed`。
- M4-WS-01~06 红测已执行（2026-02-21）：补齐真实服务 WS 测试体并执行 `pytest backend/tests/integration/real_service/test_m4_rs_ws_01_06_red.py -q`，结果 `4 failed, 2 passed`；当前通过 `WS-01/06`，阻塞点集中在 `WS-02~05`（缺少 `GAME_PUBLIC_STATE / GAME_PRIVATE_STATE / SETTLEMENT` 推送链路）。

## 当前阶段
- 结论（2026-02-21）：M4 收口测试已从框架阶段推进到实装阶段，`M4-API-01~14` 已完成 Green，`M4-WS-01~06` 已完成 Red。
- 取舍：保持 UT 已有结果不扩写，M4 收口优先采用真实服务黑盒（REST/WS/并发）。
- 下一步重心：补齐房间 WS 游戏事件链路（初始快照有局顺序、动作后 public/private 推送、进入结算 SETTLEMENT 推送），优先将 `M4-WS-02~05` 从 Red 推进到 Green。
