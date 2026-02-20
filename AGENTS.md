# 重要提示（必须遵守）：
- 每次对文件进行变更后，都在最后输出一条建议的commit message，内容应当尽可能简略，用于可能的版本控制。plan mode/计划模式不用给出commit message。
- 写任何代码前必须完整阅读 memory-bank/architecture.md
- 写任何代码前必须完整阅读 memory-bank/product-requirements.md
- 每完成一个重大功能或里程碑后，必须更新 memory-bank/progress.md
- 开发计划位于 memory-bank/implementation-plan.md
- 旧版代码位于BackEnd_old和FrontEnd_old文件夹中，仅在人类明确提出需求的时候进行查找。
- 在plan模式中，把**打算做的事情**尽可能写的简单扼要一些。如果有疑问的话要尽可能提出来。

# TDD开发流程
在每个开发阶段，都要先生成一个测试用例列表（包含测试用例的描述、通过条件等），输出到对应的测试用例设计文档中，再在该文档后面记录每个测试用例的红绿阶段执行结果。
之后人类会指定一个或多个测试用例，由你进行测试用例的编写，然后由人类确认测试用例可执行后，你再进行代码开发，直到测试用例通过。
每个测试用例通过后都需要更新测试用例结果记录文档。

# memory-bank 文件结构与作用（简要）
memory-bank 文件夹包含了各类文档，功能如下：
- memory-bank/architecture.md：总体架构、数据模型、状态机、接口索引。
- memory-bank/product-requirements.md：游戏规则与MVP范围说明。
- memory-bank/implementation-plan.md：开发阶段与里程碑计划。
- memory-bank/progress.md：进度与评审记录。
- memory-bank/tech-stack.md：技术栈说明。
- memory-bank/interfaces/frontend-backend-interfaces.md：前后端接口协议。
- memory-bank/interfaces/backend-engine-interface.md：后端与对局引擎接口协议。
- memory-bank/design/backend_design.md：后端详细设计文档（模块、流程、异常与联调约定）。
- memory-bank/tests/m*-test.md M*阶段的测试用例设计与结果记录。
- memory-bank/tests/m*-tests-real-service.md M*阶段的收口测试用例。
