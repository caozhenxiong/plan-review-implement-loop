# plan-review-implement-loop-claude-code 使用说明

## 目录结构

```text
plan-review-implement-loop-claude-code/
  SKILL.md
  USAGE.md
  references/
    reviewer-fixtures.md
    reviewer-role-prompts.md
    workflow-contract.md
```

## 适用场景

这个 skill 适合以下任务：

- 新需求必须先冻结设计文档和实现计划，再开始编码
- 需要架构双审作为实现门禁
- 实现后必须再做代码审查
- 要把方案问题、代码问题、文档状态放在一个闭环里追踪
- 不希望“用户说一句 implement”就直接跳过评审开始改代码

不适合以下任务：

- 小改动、一次性脚本、纯文案修订
- 明显不需要设计文档和双审门禁的轻量任务
- 已经确定只需要代码审查，不需要方案评审的修复

## 与 Codex 版的主要差异

- 优先支持 Claude Code `Plan Mode`
- 不依赖 Codex `Plan Mode`
- 不依赖 app 里的“实施计划 / 实施此方案”按钮
- 不依赖 `.codex/agents/*.toml`
- 所有门禁都改成纯文本 contract
- 允许在 Claude Code 没有子代理时退化成主 agent 的分离式独立评审

## Reviewer Role Card

Claude Code 版额外提供：

- [reviewer-role-prompts.md](/Users/linus/Obsidian/Skills/plan-review-implement-loop-claude-code/references/reviewer-role-prompts.md)

这个文件不是单独生效的协议副本，而是供 [workflow-contract.md](/Users/linus/Obsidian/Skills/plan-review-implement-loop-claude-code/references/workflow-contract.md) 的正式 dispatch templates 强制加载的角色卡。

理解方式：

- contract 负责结构化字段、gate 语义和回环规则
- role card 负责 reviewer 的角色偏置、主责范围、禁区和最小守门提醒
- 不能只改 role card 而不经过 contract 模板派发

## 安装方式

推荐把整个目录链接到 Claude Code 的技能目录：

```bash
mkdir -p ~/.claude/skills
ln -s "/Users/linus/Obsidian/Skills/plan-review-implement-loop-claude-code" \
  "$HOME/.claude/skills/plan-review-implement-loop-claude-code"
```

如果已经存在同名目录，先处理旧目录或改成别名目录名。

## Plan Mode 支持

这个版本支持 Claude Code 的 `Plan Mode`，建议这样理解：

- phase 1：如果运行时支持 `Plan Mode`，优先在其中完成需求澄清、方案收敛和 canonical `spec + plan` 落盘
- phase 2：正常双审，不要求一直停在 `Plan Mode`
- 实现确认点：phase 2 通过后，如果运行时支持 `Plan Mode`，应重新进入 `Plan Mode`，带着当前 `spec_rev + plan_rev` 请求用户确认是否开始实现
- 如果当前环境没有显式 `Plan Mode`，则退化为当前线程里的等价确认点，门禁语义保持不变

## 触发方式

为了让 Claude Code 稳定命中这个 skill，建议在首条指令里显式点名 skill 名称：

```text
Use skill plan-review-implement-loop-claude-code.
先为这个需求生成 spec 和 plan；如果支持 Plan Mode，phase 1 和实现确认点优先进入 Plan Mode。按 skill 的 gate 执行，不要在 phase 2 通过前开始写代码。
```

中文也可以：

```text
使用 plan-review-implement-loop-claude-code 这个 skill。
先写 canonical spec 和 plan；如果支持 Plan Mode，phase 1 和实现确认点优先进入 Plan Mode。走架构双审，再进入实现确认点；不要直接开写。
```

## 推荐起手 prompt

适合新需求：

```text
Use skill plan-review-implement-loop-claude-code.

需求如下：
<在这里贴需求>

要求：
1. 先生成 canonical spec 和 plan
2. 如果支持 Plan Mode，phase 1 优先在 Plan Mode 中完成
3. phase 1 完成后直接进入 phase 2 双审
4. phase 2 通过后，如果支持 Plan Mode，回到 Plan Mode 做实现确认
5. 未清空 medium/high 之前不要开始实现
6. 每轮都输出 gate state
```

适合已经有文档、准备继续推进：

```text
Use skill plan-review-implement-loop-claude-code.

继续推进以下任务：
- spec: docs/superpowers/specs/2026-04-22-example-design.md
- plan: docs/superpowers/plans/2026-04-22-example.md

请先读取当前 canonical 文档，判断当前 gate state，并按下一道允许门禁继续推进。
如果当前运行时支持 Plan Mode，则在 phase 2 通过后的实现确认点进入 Plan Mode。
```

## 计划文档中必须保留的区块

计划文档建议至少有三个部分：

1. 计划正文
2. `Review Ledger`
3. `Execution State`

后两者使用固定分隔符：

```markdown
<!-- REVIEW-LEDGER:START -->
## Review Ledger
...
<!-- REVIEW-LEDGER:END -->

<!-- EXECUTION-STATE:START -->
## Execution State
...
<!-- EXECUTION-STATE:END -->
```

用途：

- `Review Ledger`：记评审问题和 disposition
- `Execution State`：记执行进度、勾选、attempt、验证备注

重要约束：

- 这两个区块都不参与 `plan_rev`
- 纯勾选变化不会触发重新双审
- 改步骤文本、范围、顺序、接口、验收条件才会触发新的 `plan_rev`
- `Review Ledger` 不能只写轮次汇总；必须按 issue 级别落盘明细
- 解释历史账本时，必须先按 `issue_id` 折叠 issue 明细；同一 `issue_id` 的最后一条记录才是当前有效状态
- 如果 `Execution State` 里已经写了最新 `review_round_<n>_snapshot` 或 `gate_state`，它优先于顶部旧标题、旧 checklist、旧 prose 的视觉暗示

推荐的 `Review Ledger` 写法是“两层结构”：

1. 顶部可选 round summary，方便快速浏览
2. 底部强制 issue details，作为真正的门禁账本

错误示例：

```markdown
| Round | spec_rev | plan_rev | Reviewer | Verdict | High | Medium |
|-------|----------|----------|----------|---------|------|--------|
| R1 | ... | ... | architecture_reviewer | PASS | 0 | 1 |
| R1 | ... | ... | architecture_challenger | BLOCK | 3 | 3 |
```

上面这种只有统计，没有 issue 明细，不够用。因为后续回环时会丢失：

- `issue_id`
- `reviewer_issue_id`
- `summary`
- `artifact_anchor`
- `status`
- `disposition`
- lineage 字段

推荐补成：

```markdown
### Issue Details

| review_round | source | reviewer_issue_id | issue_id | severity | kind | summary | artifact_anchor | status | disposition |
|--------------|--------|-------------------|----------|----------|------|---------|-----------------|--------|-------------|
| R1 | architecture_challenger | AC-001 | architecture_challenger:AC-001 | high | architecture | `getGreaterThenBySymbol` 返回共享可变对象 | `plan:h2#b3` | open | open |
| R1 | architecture_challenger | AC-002 | architecture_challenger:AC-002 | medium | architecture | 并发语义只写“接受风险”但缺少约束边界 | `spec:h3#p2` | open | open |
```

代码审查的 CR issue 也一样，不能只留在 prose 或 verdict 里，必须逐条进 `Issue Details`：

```markdown
| review_round | source | reviewer_issue_id | issue_id | severity | kind | summary | artifact_anchor | status | disposition |
|--------------|--------|-------------------|----------|----------|------|---------|-----------------|--------|-------------|
| R2 | reviewer | CR-001 | reviewer:CR-001 | medium | implementation_only | 缺少空输入测试，当前修复可能回归 | `code:src/foo.ts#L42-L57` | open | open |
| R2 | reviewer | CR-002 | reviewer:CR-002 | high | design_affecting | 新增缓存策略改变了接口时序，需要回写 spec/plan | `code:src/bar.ts#L88-L126` | open | open |
```

## 推荐 gate state 语义

建议在每次需要等待用户或跨轮 handoff 时输出：

```yaml
current_phase: phase1|phase2|phase3|phase4|phase5
gate_state: blocked|phase2_blocked|phase2_passed_unconfirmed|phase3_allowed|completed
spec_rev: sha256:<hash>|pending
plan_rev: sha256:<hash>|pending
next_allowed_action: write_canonical_docs|enter_phase2_review|update_canonical_docs_and_rerun_phase2|enter_implementation_confirmation|begin_implementation|rerun_phase4|complete
do_not_start_coding_yet: true|false
```

关键映射：

- phase 1 文档落盘后：`enter_phase2_review`
- phase 2 仍有 `medium/high`：`update_canonical_docs_and_rerun_phase2`
- phase 2 通过但未确认：`enter_implementation_confirmation`
- 只有 phase 3 allowed：`begin_implementation`

如果运行时支持 Claude Code `Plan Mode`：

- phase 1 应优先在 `Plan Mode` 内完成
- `enter_implementation_confirmation` 应优先解释为“进入 Plan Mode 并请求实现确认”

## Claude Code 没有子代理时怎么跑

如果当前运行环境没有子代理能力，也可以跑，但要遵守两个要求：

- 两份架构评审必须分离输出，不能把 challenger 写成 reviewer 的附和总结
- 代码审查必须继续使用结构化头部，不能只给自由文本建议

推荐做法：

1. 主 agent 先冻结 `spec_rev + plan_rev`
2. 用 reviewer 视角输出第一份结构化架构评审
3. 清空上下文依赖后，再用 challenger 视角输出第二份结构化架构评审
4. 汇总后决定是否继续 phase 2 或进入实现确认点

## 最小验证办法

可以用一个很小的需求验证这个 skill 是否按预期工作：

1. 给 Claude Code 一个新需求，并显式点名 `plan-review-implement-loop-claude-code`
2. 如果当前环境支持 `Plan Mode`，观察 phase 1 是否优先进入 `Plan Mode`
3. 观察 phase 1 完成后，是否直接进入 phase 2，而不是输出可直接开工的 handoff
4. phase 2 通过后，如果当前环境支持 `Plan Mode`，观察它是否回到 `Plan Mode` 做实现确认
5. 手动在 `Execution State` 里把某个任务从 `[ ]` 改成 `[x]`
6. 再次让它判断 gate state，确认它没有因为纯勾选变化而重跑 phase 2

## 常见失败模式

### 1. 写完文档就开始编码

原因：
- 没有显式点名这个 skill
- 没有把 gate state 作为必输字段
- handoff 仍在用普通“implement this plan”语气

修正：
- 在 prompt 里明确要求“phase 1 结束后直接进入 phase 2 双审”
- 如果环境支持 Plan Mode，再明确要求“phase 1 和实现确认点优先进入 Plan Mode”
- 要求每轮输出 `current_phase` / `gate_state` / `next_allowed_action`

### 2. 执行过程中勾选任务导致重新双审

原因：
- 勾选写在计划正文，而不是 `Execution State`
- 或实现方没有按 contract 排除 `Execution State`

修正：
- 把执行进度迁到 `Execution State`
- 明确要求 `plan_rev` 排除 `Review Ledger` / `Execution State` 并忽略 checkbox-only changes

### 3. phase 2 blocked 后停下来问“要不要继续”

原因：
- 没有把 blocked 解释为“阻塞实现”而不是“阻塞继续出方案”

修正：
- 明确要求 phase 2 默认下一步是更新 canonical 文档并继续双审

### 4. `Review Ledger` 只有汇总，没有问题明细

原因：
- skill 虽然要求记录 ledger，但没有把“issue 明细强制回写”理解成 fail-closed
- 实现方偷懒，只写了 reviewer 轮次统计表

修正：
- 明确要求每个 reviewer 返回的每一个 issue 都要落成独立 ledger 记录
- 把 round summary 当成可选视图，不当成正式门禁账本

### 5. CR 出来的问题没有写进 `Issue Details`

原因：
- 只更新了代码审查 verdict、`actionable_issues` 和 `requires_doc_update`
- CR 问题还停留在自由文本结论里，没有落成 ledger 明细

修正：
- 要求代码审查的每个 open issue 都以 `source = reviewer` 单独回写
- 每条 CR issue 至少补齐 `reviewer_issue_id`、`issue_id`、`kind`、`summary`、`artifact_anchor`、`status`、`disposition`
- 缺少这些明细时，不允许把 phase 4 视为完成

### 6. 历史 `open` 行还在，但后面其实已经 `resolved`

原因：
- 主 agent 直接按整张 `Issue Details` 历史表扫 `open`，没有先按 `issue_id` 折叠成当前有效状态
- 顶部阶段标题、旧 checklist 或旧 prose 没同步，视觉上看起来像还在 `phase 2 blocked`

修正：
- 对同一个 `issue_id`，永远以最后一条记录作为当前状态
- gate 统计只看折叠后的当前有效 issue 集，不看历史 `open` 残留行
- 如果 `Execution State` 已经记录最新 `review_round_<n>_snapshot = PASS` 或等价 gate snapshot，且与折叠后的账本一致，就按它推进；旧文案只当作待回填状态

## 建议

第一次正式使用前，先拿一个小需求做 smoke test。这个 skill 的关键不是会不会写文档，而是能不能稳定守住两个门：

- phase 1 结束先入双审
- 有 Plan Mode 时，phase 1 和实现确认点优先走 Plan Mode
- 进度勾选不影响 `plan_rev`
