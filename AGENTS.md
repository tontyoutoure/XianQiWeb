# 重要提示（必须遵守）：
- 写任何代码前必须完整阅读 memory-bank/architecture.md
- 写任何代码前必须完整阅读 memory-bank/game-design-document.md
- 每完成一个重大功能或里程碑后，必须更新 memory-bank/progress.md
- 开发计划位于 memory-bank/implementation-plan.md
- 旧版代码位于BackEnd_old和FrontEnd_old文件夹中，仅在人类明确提出需求的时候进行查找。

# TDD开发流程
在每个开发阶段，都要先生成一个测试用例列表。然后由人类发出指令实现一个或若干个测试用例，由人类验证无法通过后（红阶段），再由人类发出指令实现代码使测试用例通过（绿阶段）。每个测试用例通过后都需要更新测试用例结果记录文档。

# memory-bank 文件结构与作用（简要）
memory-bank 文件夹包含了各类文档，功能如下：
- memory-bank/architecture.md：总体架构、数据模型、状态机、接口索引。
- memory-bank/game-design-document.md：游戏规则与MVP范围说明。
- memory-bank/implementation-plan.md：开发阶段与里程碑计划。
- memory-bank/progress.md：进度与评审记录。
- memory-bank/tech-stack.md：技术栈说明。
- memory-bank/interfaces/frontend-backend-interfaces.md：前后端接口协议。
- memory-bank/interfaces/backend-engine-interface.md：后端与对局引擎接口协议。
- memory-bank/design/backend_design.md：后端详细设计文档（模块、流程、异常与联调约定）。
- memory-bank/tests/m1-test.md M1阶段的测试用例设计与结果记录。
