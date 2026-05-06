# plan-review-implement-loop

`plan-review-implement-loop` 是一个强门禁工程工作流 skill：先冻结 `spec + plan` 两份 canonical 文档，再经过方案双审、实现确认、实现、代码审查和最终文档同步。

仓库同时包含两个运行时版本：

- `codex/`：Codex 版主 workflow skill。
- `codex-agents/`：Codex 版依赖的三个 reviewer agent。
- `claude-code/`：Claude Code 版 workflow skill。

## 核心能力

- 双文档闭环：`spec` 定义需求、边界和验收；`plan` 定义执行、评审账本和执行状态。
- 方案双审：`architect_reviewer` 审架构就绪性，`architecture_challenger` 挑战失败模式和隐藏复杂度。
- 严格门禁：中/高风险未清前不得实现；代码审查发现 `design_affecting` 问题时必须回到方案双审。
- 稳定追踪：`Review Ledger` 使用 issue 级明细，按 `issue_id` 追踪跨轮问题。
- 稳定哈希：`plan_rev` 使用 `plan-rev/v1`，排除 `Review Ledger` 和 `Execution State`。
- 行为原则：分层吸收 Karpathy Guidelines，要求先想清楚、简单优先、精确改动、目标驱动。

## 安装到 Codex

在本机执行：

```bash
git clone git@github.com:caozhenxiong/plan-review-implement-loop.git
cd plan-review-implement-loop

mkdir -p "$HOME/.codex/skills/plan-review-implement-loop"
mkdir -p "$HOME/.codex/agents"

rsync -a --delete codex/ "$HOME/.codex/skills/plan-review-implement-loop/"
rsync -a codex-agents/*.toml "$HOME/.codex/agents/"
```

安装脚本使用 `$HOME` 路径，无需修改用户名。如果你从旧版迁移过来，可用下面命令把旧的绝对路径替换为当前用户目录：

```bash
find "$HOME/.codex/skills/plan-review-implement-loop" "$HOME/.codex/agents" \
  -type f \( -name '*.md' -o -name '*.toml' -o -name '*.yaml' -o -name '*.py' \) \
  -exec perl -pi -e 's#/Users/[^/]+#$ENV{HOME}#g' {} +
```

使用方式：

```text
Use skill plan-review-implement-loop.
```

## 安装到 Claude Code

在本机执行：

```bash
git clone git@github.com:caozhenxiong/plan-review-implement-loop.git
cd plan-review-implement-loop

mkdir -p "$HOME/.claude/skills"
rsync -a --delete claude-code/ "$HOME/.claude/skills/plan-review-implement-loop-claude-code/"
```

安装脚本使用 `$HOME` 路径，无需修改用户名。如果你从旧版迁移过来，可用下面命令把旧的绝对路径替换为当前用户目录：

```bash
find "$HOME/.claude/skills/plan-review-implement-loop-claude-code" \
  -type f \( -name '*.md' -o -name '*.py' \) \
  -exec perl -pi -e 's#/Users/[^/]+#$ENV{HOME}#g' {} +
```

使用方式：

```text
Use skill plan-review-implement-loop-claude-code.
```

Claude Code 版支持 Plan Mode：phase 1 优先在 Plan Mode 中完成规划，phase 2 通过后也优先回到 Plan Mode 做实现确认。

## 推荐目录结构

业务项目中，workflow 会生成并维护：

```text
docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md
docs/superpowers/plans/YYYY-MM-DD-<topic>.md
```

其中：

- `spec`：需求、边界、接口、约束、验收和风险。
- `plan`：实施步骤、Review Ledger、Execution State、回环规则和完成证据。

## 注意事项

- `Review Ledger` 和 `Execution State` 不参与 `plan_rev`。
- 只更新执行勾选态不会触发重新双审。
- 文档正文发生实质变化后，必须重新冻结 `spec_rev + plan_rev` 并全量双审。
- prior-open issue 只用于 continuity，不缩小复审范围。
- 代码审查必须核对实现是否严格符合 `spec`、`plan` 和 checklist。
