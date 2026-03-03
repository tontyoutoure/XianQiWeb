# TDD Subagent 批处理流程规范（4用例/波）

## 1. 文档定位
- 本文档定义“读取测试列表 -> 双 agent 执行 Red/Green -> 分阶段提交 -> 批次重启”的统一流程。
- 适用范围：`memory-bank/tests/m*-test*.md` 与 `memory-bank/tests/m*-tests-real-service.md` 的 TDD 执行编排。
- 非目标：不替代具体里程碑测试用例设计文档；测试 ID、通过条件仍以对应阶段文档为准。

## 2. 输入与默认参数
- `test_list_source`：测试清单文档路径（由执行批次指定）。
- `batch_size`：固定为 `4`；最后一波可小于 `4`。
- `order_policy`：按测试清单文档中的出现顺序，选取“未完成”测试 ID。
- `commit_policy`：每波固定两次提交：
  - Red 提交（测试为主）
  - Green 提交（实现为主）
- `halt_policy`：出现测试修改争议或 Red 基线异常时立即停机，等待人类决策。

## 3. 角色与职责
### 3.1 编排者（主 Agent）
- 读取测试列表并按顺序切波。
- 拉起并管理两个子 agent。
- 负责核验结果、执行 `git commit`、更新文档记录、处理停机。

### 3.2 测试 Agent（worker）
- 仅允许修改：测试代码、测试文档中的执行记录区。
- 负责本波测试的 Red 阶段：
  - 编写/补齐指定测试；
  - 执行测试并确保 Red 结果符合预期；
  - 回传失败断言摘要与变更文件列表。

### 3.3 实现 Agent（worker）
- 默认仅允许修改实现代码与必要配置。
- 负责本波 Green 阶段：
  - 基于 Red 失败实现最小修复；
  - 执行本波测试与最小回归；
  - 回传通过结果与变更文件列表。
- 若判断“必须修改测试用例”，必须先上报并停机，不得直接改测。

## 4. 每波执行状态机
### Step A：批次准备
- 从 `test_list_source` 中选择按顺序的 4 个未完成测试 ID，记为 `batch_ids`。
- 若剩余不足 4 个，取剩余全部。

### Step B：Red 阶段（测试 Agent）
- 测试 Agent 写入/调整测试并执行。
- Red 核验条件：
  - `batch_ids` 对应测试在当前实现下失败；
  - 失败原因与测试目标一致；
  - 未改动实现代码（越权改动视为异常）。

### Step C：Red 提交（由编排者执行）
- 提交内容：测试改动 + 测试文档 Red 记录。
- 提交信息模板：
  - `test(red): <milestone/module> <batch_ids>`

### Step D：Green 阶段（实现 Agent）
- 实现 Agent 基于 Red 失败进行最小实现修复并执行测试。
- Green 核验条件：
  - `batch_ids` 全部通过；
  - 最小回归集通过；
  - 未改动测试文件（若改动则停机）；
  - 未出现“需改测试用例”的上报（若出现则停机）。

### Step E：Green 提交（由编排者执行）
- 提交内容：实现改动 + 测试文档 Green 记录。
- 提交信息模板：
  - `feat(green): <milestone/module> <batch_ids>`

### Step F：波末收口
- 更新测试文档执行记录（Red/Green 状态、日期、备注）。
- 更新 `memory-bank/progress.md`（当前 Milestone 二级进度追加一条）。
- 关闭两个子 agent，并在下一波前重新拉起新实例。

## 5. 强制停机条件
满足任一条件立即停机，并通知人类确认：
- 实现 Agent 明确上报“需要修改测试用例”（含回归失败导致需改测）。
- 发现实现 Agent 擅自修改测试文件。
- Red 阶段出现“预期应失败但实际通过”（Red 未复现）。

## 6. 停机通知模板（固定字段）
- `trigger_type`：停机类型（需改测/擅改测试/Red 未复现）。
- `batch_ids`：受影响测试 ID 列表。
- `evidence`：关键日志摘要与相关文件路径。
- `option_a`：维持现有测试，继续改实现。
- `option_b`：允许调整测试（需人类明确批准后执行）。

## 7. 文件改动边界约束
- 测试 Agent 允许路径（示例）：
  - `backend/tests/**`
  - `frontend/tests/**`
  - `memory-bank/tests/*.md`（仅执行记录区）
- 实现 Agent 默认禁止修改路径（示例）：
  - `backend/tests/**`
  - `frontend/tests/**`
  - `memory-bank/tests/*.md`
- 若流程需要放宽边界，必须先由人类确认。

## 8. 追踪与审计要求
- 每波保留以下审计信息：
  - `batch_ids`
  - Red 执行结果摘要
  - Green 执行结果摘要
  - 提交哈希（Red/Green 各 1）
  - 是否触发停机及处理结论
- 该信息应可从 `git log`、测试文档执行记录、`memory-bank/progress.md` 三处交叉验证。

## 9. 默认执行口径
- 仅本地提交，不自动 `push`。
- 不 `squash`、不 `amend`。
- 每波完成后才进入下一波，不跨波并发。
- 若输入文档缺失测试 ID 或状态不明确，先停机并请求人类补充，不做猜测性推进。
