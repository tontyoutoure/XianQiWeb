## 当前进度（精简版）
- M0 文档基线已完成并稳定：架构、规则、接口与设计文档已对齐。
- M1 鉴权链路已完成：REST + WebSocket 登录态可用。
- M2 房间大厅主链路已完成，剩余少量依赖引擎开局能力的收尾项。
- M3 逻辑引擎核心规则已实现并通过阶段测试；CLI 可完成一局从开局到结算的基础演示。
- M5 结算能力已接入 CLI：进入 `settlement` 后可直接输出按 seat 的结算明细。
- M4/M5/M6 文档已补齐（2026-02-20）：已冻结 Games REST、房间 WS 游戏事件、结算后重新 ready 开局规则与对应测试清单。
- M4-UT-01~05 已完成 Green（2026-02-20）：后端 game 编排层单测从 Red（`5 failed`）推进到 Green（`5 passed`）。
- M4 真实服务收口脚手架已完成（2026-02-21）：新增 `m4-tests-real-service.md` 与 `test_m4_rs_rest/ws/cc` 占位测试文件，当前全部为 skip，待按测试ID逐条落地测试体。
- M4 测试文档已去重（2026-02-21）：`m4-tests.md` 收敛为 UT + 收口索引，M4 API/WS/CC 清单统一由 `m4-tests-real-service.md` 维护。
- M4-API-01~05 真实服务收口已完成 Green（2026-02-21）：新增并打通 `/api/games/{id}/state`、`/api/games/{id}/actions` 基础链路，测试结果 `5 passed, 9 skipped`。

## 当前阶段
- 结论（2026-02-21）：M4 收口测试已从框架阶段推进到实装阶段，`M4-API-01~05` 已完成 Green。
- 取舍：保持 UT 已有结果不扩写，M4 收口优先采用真实服务黑盒（REST/WS/并发）。
- 下一步重心：继续推进 `M4-API-06~14`（非当前行动位、非法 cover、settlement 门禁与结算后 ready 分支）并补齐 WS/并发收口用例。
