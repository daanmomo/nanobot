# Do Plan

执行分阶段实施计划。用于执行 `make-plan` 创建的计划，或任何需要多步骤执行的任务。

## When to Use

- 用户说"执行"、"开始做"、"run the plan"
- 有一个已创建的计划需要执行
- 复杂任务需要分步骤完成并逐步验证

## How It Works

我是 **ORCHESTRATOR（编排者）**。用 subagent 执行所有工作。自己只负责协调、传递上下文、验证完成情况。

## Execution Protocol

### Rules

- 每个阶段使用新的 subagent（上下文隔离）
- 每个 subagent 一个明确目标，要求提供证据（执行的命令、输出、修改的文件）
- 上一步 subagent 报告完成且 orchestrator 确认后，才进入下一步

### During Each Phase

派 **Implementation subagent**：
1. 按计划执行实施
2. **复制**文档中的模式，不要发明
3. 使用不熟悉的 API 时在代码注释中引用文档来源
4. 如果某个 API 似乎不存在 → **停下来验证**，不要假设

### After Each Phase

派 subagent 做后置检查：
1. **Verification subagent** — 运行验证 checklist，证明阶段成功
2. **Anti-pattern subagent** — grep 检查计划中标注的已知坏模式
3. **Code Quality subagent** — 审查变更质量
4. **Commit subagent** — 只在验证通过后提交；否则不提交

### Between Phases

派 **Sync subagent**：
- 验证通过后推送到工作分支
- 准备下一阶段的上下文交接

## Failure Modes to Prevent

- ❌ 不要发明"应该存在"的 API — 对照文档验证
- ❌ 不要添加未文档化的参数 — 复制精确签名
- ❌ 不要跳过验证 — 每个阶段都要验证
- ❌ 不要在验证通过前提交代码

## Integration with focus.md

执行前：在 `memory/focus.md` 添加任务项 `- [ ] task_id: description`
执行中：更新为 `- [/] task_id: description`
完成后：更新为 `- [x] task_id: description`
