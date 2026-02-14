## 当前进度（粗粒度）
- 架构/规则/MVP范围/前后端接口/后端设计文档评审已完成。
- M1 后端鉴权能力（Auth REST + WS 鉴权）已完成并通过既有 pytest 回归；真实服务联调清单已建立，当前已完成前 5 条 REST 红阶段执行。
- 测试细节与逐条状态不再在本文件展开，统一维护在 `memory-bank/tests/m1-tests-real-service.md`（当前主记录）。

## 当前阶段
- M1 真实服务验收阶段：继续按 `memory-bank/tests/m1-tests-real-service.md` 推进剩余 REST/WS/E2E 用例并更新记录。

## 最近更新
- 2026-02-14：将 progress 中历史测试流水简化为里程碑级描述；逐条测试进度改为在 `memory-bank/tests/m1-tests-real-service.md` 维护。
- 2026-02-14：补充真实服务联调中的代理注意事项（`HTTP_PROXY/HTTPS_PROXY` 可能导致本地 `502`）与本地验证方法（`curl --noproxy *`）。
