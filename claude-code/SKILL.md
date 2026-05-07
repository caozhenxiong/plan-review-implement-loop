---
name: plan-review-implement-loop-claude-code
description: Use when an engineering task in Claude Code must freeze spec and plan docs before implementation, gate work through architecture review and code review, and keep design, plan, issues, and implementation synchronized in one closed loop.
---

# plan-review-implement-loop-claude-code

## Overview

这是 `plan-review-implement-loop` 的 Claude Code 版。它保留“先冻结文档、再双架构评审、再实现、再代码审查”的闭环，去掉了 Codex 专属按钮语义和 `.codex/agents/*.toml` 绑定，同时显式支持 Claude Code 的 `Plan Mode`。

本 skill 默认在 Claude Code 当前会话内运行。它依赖的是明确的文本门禁，而不是某个特定客户端 UI。

## Karpathy Behavioral Principles

本 skill 分层吸收 `andrej-karpathy-skills` 的行为守则，但不替代本文件已有的 phase/gate/ledger contract。

- `Think Before Coding`：非平凡任务先暴露关键假设、歧义和取舍；phase 1 不允许静默选择一种会影响范围、接口、验收或门禁的解释。
- `Simplicity First`：默认选择满足当前需求的最小可行方案；无请求的扩展性、配置化、抽象层或单次使用框架都必须有 `spec + plan` 依据。
- `Surgical Changes`：实现和文档同步只允许覆盖当前请求、`spec`、`plan` 或 checklist 需要的范围；禁止借机修改无关代码、注释、格式或相邻逻辑。
- `Goal-Driven Execution`：每一步都必须对应可验证的成功标准、review gate 或验证证据；不得用“看起来完成”“测试表面通过”替代明确验收。

<SUBAGENT-STOP>
如果你只是被派发去执行单个实现、单轮评审或局部修复，请跳过这个 skill，直接完成你被分配的子任务。
</SUBAGENT-STOP>

## Hard Gates

- 只由主 agent 执行此技能。子代理只执行被派发的单个实现或评审任务。
- 若当前 Claude Code 运行时支持可复用的子代理槽或等价的持续任务槽，方案双审与代码审查都应优先复用同一角色槽；若运行时不支持真实槽位，也必须在逻辑上保持固定角色槽语义，不要每轮随意换角色实例。
- 未把两份文档写入 canonical 路径前，不得进入正式方案评审或实现：
  - `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`
  - `docs/superpowers/plans/YYYY-MM-DD-<topic>.md`
- phase 1 若 Claude Code 提供显式 `Plan Mode`，主 agent 必须优先进入它；若当前运行时无显式 `Plan Mode`，再退化为当前线程内的等价规划流程。
- phase 1 写完 canonical `spec + plan` 后，主 agent 必须直接进入 phase 2；不得把阶段 1 结果作为可直接开始编码的 handoff。
- 在本 skill 中，用户的“开始实现”“执行计划”“implement this plan”都解释为“推进到当前允许的下一道门禁”，不是无条件开始写代码。
- 每一轮评审都必须冻结不可变快照：`review_round`、`spec_rev`、`plan_rev`，以及代码审查所需的 `code_rev`。
- `plan_rev` 必须排除 `Review Ledger` / `Execution State` 区块，并忽略纯 Markdown 勾选态 `[ ]` / `[x]` 的变化。
- 未解决的 `high` / `medium` 方案问题默认只阻塞实现，不阻塞继续修改 `spec + plan` 并重跑方案双审。
- 方案双审通过后，仍不得直接写代码；必须先进入实现确认点，等待用户基于当前 `spec_rev + plan_rev` 明确确认。若 Claude Code 提供显式 `Plan Mode`，实现确认点也必须优先在其中完成。
- phase 3 只允许产生代码/文档改动和验证证据；一旦本轮实现改动完成，唯一合法出口是冻结 `code_rev` 并进入 phase 4 代码审查。不得在未完成 phase 4 的情况下输出完成声明、交付总结或“已完成”。
- 任何声称“实现完成”的响应，如果没有最新 phase 4 代码审查结果，必须自动解释为 `next_allowed_action = enter_code_review`，而不是 `complete`。
- phase 5 完成声明必须依赖最新 phase 4 代码审查 `actionable_issues = 0`；本地测试通过、构建通过、手工验证通过都不能替代 phase 4。
- 若 canonical 双文档正文发生实质变化，上一轮方案双审立即失效，必须回到 phase 2。
- 计划文档必须包含显式分隔的 `Review Ledger` 与 `Execution State` 区块；若缺失，自动回环阻塞。
- `Review Ledger` 必须按 issue 级别记录明细；仅写 round/reviewer/verdict/high/medium 这种汇总表不算有效回写。
- 如果发现当前计划文档里的 `Review Ledger` 只有汇总表、没有 issue 明细，主 agent 必须先把已有 round 重写为 issue 级账本，再允许继续 phase 2 / phase 3 / phase 4；不得带着无效 ledger 继续追加新轮次。
- 任何跨轮 handoff 都必须显式写出：
  - `current_phase`
  - `gate_state`
  - `spec_rev`
  - `plan_rev`
  - `next_allowed_action`
  - `do_not_start_coding_yet`（当尚未允许编码时）
- 跨轮 handoff 必须显式点名继续在 `plan-review-implement-loop-claude-code` 下执行，不能假设下一轮自动继承当前 skill。
- 如果运行时支持子代理，phase 2 必须形成两份彼此独立的架构评审结论；如果不支持子代理，则主 agent 必须在同一轮中模拟两位独立 reviewer 的分离审查，并保持结构化结果独立。
- 只有三种情况可以停下来请求用户决策：
  - phase 1 遇到关键业务输入缺失
  - phase 2 命中人工升级条件
  - phase 2 已通过，进入实现确认点

## Workflow

### 1. 规划与文档生成

- 主 agent 先确认当前 skill 仍持有控制权，且本轮目标是生成 `spec + plan`。
- 若 Claude Code 提供显式 `Plan Mode`，优先进入它完成 phase 1；若没有，再在当前会话中完成需求澄清、方案收敛和文档落盘。
- 若局部歧义可以安全推断，可记录假设后继续；若会影响范围、接口、验收标准或门禁判断，必须停在 phase 1 请求用户确认。
- `spec + plan` 必须写清成功标准、验收方式和验证点；如果缺少这些内容，不能用笼统目标进入 phase 2。
- phase 1 的唯一出口是：canonical `spec + plan` 已生成，然后进入 phase 2。
- 不允许以“下面我开始实现”“请点击执行计划”等文案结束 phase 1。

### 2. 方案双审

- 冻结本轮方案快照：`review_round`、`spec_rev`、`plan_rev`。
- 评审输入只认 canonical 双文档正文的权威快照；`Review Ledger` / `Execution State` 不属于被审 artifact。
- 形成两份独立的架构审查：
  - `architecture_reviewer`
  - `architecture_challenger`
- 若运行时支持子代理，优先并行派发，并优先复用既有 `architecture_reviewer` / `architecture_challenger` 槽；若不支持，则主 agent 分两次独立审查，禁止第二份结论直接复用第一份 reasoning，同时仍要保持固定角色槽语义。
- 只要还有未解决的 `medium/high`，就先更新 canonical `spec + plan`，按 issue 明细回写 `Review Ledger`，重新冻结 `spec_rev + plan_rev`，并继续 phase 2。
- 只要当前 canonical 双文档正文发生了任何改动，下一轮架构评审就必须重新审视当前完整方案；上一轮未关闭 issue 摘录只用于 continuity 对账，不得把 phase 2 误降级成“只复审上一轮问题”。
- phase 2 必须主动拦截未说清的前提、隐藏 tradeoff、silent assumption，以及没有计划依据的 speculative abstraction / configurability / single-use abstraction；这些可作为结构化 architecture issue。
- 普通 blocked round 默认不向用户询问“是否继续”；只要还能通过修改 `spec + plan` 收敛，就继续回环。
- 解释 `Review Ledger` 时，必须先按 `issue_id` 折叠 issue 明细；同一 `issue_id` 的最后一条记录才是当前有效状态。历史 `open` 行若后续已被 `resolved` / `superseded` / `accepted` 覆盖，不得继续算作当前 blocker。
- 如果 `Execution State` 已记录最新 `review_round_<n>_snapshot`、`gate_state` 或等价快照，它必须与折叠后的当前 issue 状态一致；顶部旧的阶段标题、历史 checklist 或未同步 prose 只能视为待回填文案，不能覆盖当前 gate 判定。
- 当最新一轮双审清空 `medium/high` 后，进入实现确认点，而不是直接写代码。若 Claude Code 提供显式 `Plan Mode`，主 agent 必须重新进入 `Plan Mode`，带着当前通过版 `spec_rev + plan_rev` 请求用户确认是否开始实现。
- 若仍有未关闭 `low-risk`，实现确认点必须显式列出，并说明“这些问题不阻塞实现，确认开始实现即视为接受这些风险”。

### 3. 实现

- 只有在以下条件都满足时，才允许实现：
  - 最新一轮方案双审无未解决 `medium/high`
  - 用户已经基于当前 `spec_rev + plan_rev` 明确确认开始实现；若运行时支持 `Plan Mode`，该确认应优先在 `Plan Mode` 中完成
  - 当前 canonical `spec + plan` 仍与最近通过版 `spec_rev + plan_rev` 匹配
- 实现过程中，每形成一轮新的代码修改，先同步更新文档，再继续下一轮实现或进入代码审查。
- 本轮实现改动完成后，主 agent 必须立即冻结 `code_rev` 并进入 phase 4；不允许把验证结果当作最终完成信号。
- 如果运行时无法派发独立 `code_reviewer`，主 agent 也必须按 phase 4 的结构化代码审查 contract 自查，并把结果写入 `Review Ledger`；不得跳过 phase 4。
- 实现必须保持 surgical：每个代码、文档或 prompt 改动都应能追溯到用户请求、`spec`、`plan` 或 checklist；无关清理、顺手格式化、相邻逻辑整理不得混入当前实现。
- 进度勾选、时间戳、attempt、run note 优先写入 `Execution State` 区块；仅这些内容变化不会触发新的 `plan_rev`。
- 若改动了步骤文本、顺序、范围、接口、验收要求或交付路径，视为计划正文变化，必须回到 phase 2。

### 4. 代码审查

- phase 4 是 phase 3 后的强制阶段，不是可选复核。只要本轮存在代码、测试、脚本、文档或 prompt 实现改动，就必须执行 phase 4。
- 一轮实现后，冻结代码快照：`review_round`、`spec_rev`、`plan_rev`、`code_rev`。
- 若运行时支持子代理，可派发独立 `code_reviewer`，并优先复用既有 reviewer 槽；否则主 agent 按代码审查 contract 自查，但必须用结构化输出约束自己，并保持固定 reviewer 槽语义。
- 只要当前代码或对应文档发生了改动，下一轮代码审查就必须重新检查当前完整实现对 `spec` / `plan` 的符合性；CR issue excerpt 只用于 continuity，对代码审查范围不构成缩减。
- 代码审查必须把当前实现逐条对照 canonical `spec`、去账本后的 canonical `plan`，以及适用时已确认的 checklist 进行核对；代码是否严格遵守设计、计划和 checklist 是硬门禁，不是可选建议。
- 任一实现偏离 `spec` / `plan` / checklist、保留应删除旧路径、绕过 fail-closed、或用兼容 fallback 替代新协议，都必须作为结构化 issue 返回；测试通过不能抵消设计不合规。
- 代码审查必须检查每个改动是否能追溯到请求、`spec`、`plan` 或 checklist；无关修改、顺手清理、未要求的抽象或配置化应作为 scope violation 或明确的非阻塞 prose 记录，不能静默通过。
- 代码审查必须按明确 success criteria 判断完成度；如果当前文档缺少足够验收标准，应走 `design_affecting` / doc insufficiency 路径，而不是凭感觉放行。
- 代码审查返回的每一个 CR issue，都必须在 `Review Ledger` 的 issue 明细视图中逐条回写；未完成这一步前，不得把本轮 CR 视为完成。
- 若 `actionable_issues = 0`，进入 phase 5。
- 若 `actionable_issues > 0` 且 `requires_doc_update = false`：
  - 只修代码与测试
  - 同步更新文档
  - 重冻 `code_rev`
  - 仅重跑 phase 4
- 若 `actionable_issues > 0` 且 `requires_doc_update = true`：
  - 先更新 `spec + plan`
  - 使上一轮方案双审失效
  - 回到 phase 2

### 5. 文档回填与最终同步

- 结束前必须确认最终实现与两份文档一致。
- 完成声明必须绑定验证证据；不得只用口头总结、表面功能可用或局部测试通过替代最终验收。
- 未完成 phase 4 或 phase 4 未明确 `actionable_issues = 0` 时，不得进入 phase 5。
- 只有当以下条件同时满足时，才可宣称完成：
  - 最新 `spec + plan` 已同步
  - 最新通过的方案双审与最新通过的代码审查共享同一组 `spec_rev + plan_rev`
  - 最新通过的代码审查绑定到最终 `code_rev`
  - 最新双审没有未解决的 `medium/high`
  - 最新代码审查 `actionable_issues = 0`
  - `Review Ledger` 已记录最终闭环状态
  - 已完成实际验证，而不是推断式宣称完成

## Required Output Contract

每次需要跨轮 handoff 或等待用户时，都必须显式输出当前 gate state，最少包含：

```yaml
current_phase: phase1|phase2|phase3|phase4|phase5
gate_state: blocked|phase2_blocked|phase2_passed_unconfirmed|phase3_allowed|phase4_required|phase4_blocked_implementation_only|phase4_blocked_design_affecting|phase5_completed
spec_rev: sha256:<hash>|pending
plan_rev: sha256:<hash>|pending
next_allowed_action: write_canonical_docs|enter_phase2_review|update_canonical_docs_and_rerun_phase2|enter_implementation_confirmation|begin_implementation|enter_code_review|rerun_phase4|complete
do_not_start_coding_yet: true|false
```

约束：

- phase 1 完成后的 `next_allowed_action` 只能是 `enter_phase2_review`
- phase 2 blocked 时只能是 `update_canonical_docs_and_rerun_phase2`
- phase 2 passed but not confirmed 时只能是 `enter_implementation_confirmation`
- 只有 phase 3 allowed 时才允许 `begin_implementation`
- phase 3 实现改动完成后只能是 `enter_code_review`
- 只有 phase 4 代码审查 `actionable_issues = 0` 后才允许 `complete`

## Do Not

- 不要在写文档前直接实现。
- 不要在未清空 `medium/high` 方案问题前开始实现。
- 不要在 phase 1 或普通 phase 2 blocked round 输出“可直接开工”的实施 handoff。
- 不要把 `Review Ledger` 写成只有轮次统计、reviewer verdict 和 high/medium 数量的汇总表。
- 不要把 `Review Ledger`、`Execution State` 或纯勾选态变化误判为计划正文变化。
- 不要把旧 review 结果复用到新 `spec_rev` / `plan_rev` / `code_rev` 上。
- 不要把代码审查的 `design_affecting` 问题当作只改代码即可处理。
- 不要在实现后跳过 phase 4；没有代码审查结果时，不能宣称完成。
- 不要在代码审查已经返回 issue 的情况下，只更新 `actionable_issues` / `requires_doc_update` / verdict，而不把 CR issue 逐条写入 `Issue Details`。
- 不要在支持子代理/持续任务槽的运行时里无故重复新开同角色 reviewer/challenger 槽，绕过既有连续性。
- 不要依赖某个客户端 UI 按钮来代替文本门禁。
- 不要在运行时明明支持 Claude Code `Plan Mode` 时，跳过 phase 1 或实现确认点里的 `Plan Mode` 入口。

## Reference

- 详细 contract、严重级别规则、派发模板与回环判定，见 [workflow-contract.md](./references/workflow-contract.md)。
