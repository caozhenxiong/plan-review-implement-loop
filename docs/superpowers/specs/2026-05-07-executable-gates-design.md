# 可执行门禁版 Workflow Skill 设计文档

> 本文档用于 `plan-review-implement-loop` 的 phase 2 方案双审。它只定义需求、边界和验收，不直接授权实现。

## 背景

当前仓库已经包含 Codex 版 workflow skill、Claude Code 版 workflow skill、Codex reviewer agents、`plan_rev` 参考脚本和 README 安装说明。现有流程主要依赖 Markdown contract 和 reviewer prompt 来约束模型行为，已经具备强门禁语义，但仍有一个明显风险：部分门禁只能由模型阅读后自觉遵守，缺少机器可执行校验。

本次目标是把现有 workflow 从“强规则 Markdown Skill”升级为“可执行门禁 Workflow Skill”的第一阶段，而不是做完整平台或 GitHub/Jira 插件。

## 目标

新增一组最小可用的模板、schema 和脚本，让关键门禁可以被机器校验：

- 稳定冻结 `spec_rev`、`plan_rev`，并输出使用的 contract id。
- 校验 reviewer 结构化输出字段、版本、issue 身份和计数字段。
- 从 `Review Ledger` 折叠当前有效 issue 状态，计算当前 gate state 和 next allowed action。
- 提供 canonical `spec` / `plan` 模板，减少文档结构漂移。
- 保持 Codex 和 Claude Code 两边语义对齐。

## 非目标

- 不引入 Web UI、MCP、GitHub PR 自动评论、Jira 集成或完整平台。
- 不把 `Review Ledger` 改成第三份独立 JSON 真源；本阶段仍以 plan 文档中的显式分隔块为权威账本。
- 不删除现有 Markdown contract，也不把 `SKILL.md` 缩成只有脚本调用的薄壳。
- 不改变现有 phase 1-5、双审、实现确认、代码审查和最终完成门禁语义。
- 不修改用户本机已经安装的 `$HOME/.codex/skills/...` 或 `$HOME/.claude/skills/...`；只修改当前仓库分支。

## 设计原则

- Markdown 保留主流程与硬门禁摘要，脚本负责校验可机械判断的规则。
- reviewer 继续负责架构和代码判断，但结构化输出必须能被 schema 校验。
- 任何自动更新账本的能力都必须先支持 dry-run 或明确输出 patch，避免误改计划正文。
- 新增脚本必须是本地可运行、无外部服务依赖、失败时 fail-closed。
- 新增能力必须对 Codex 和 Claude Code 两个版本都可复用，避免两套工具链分裂。

## 公共接口与目录

新增目录采用两边共享优先的结构：

```text
shared/
  schemas/
  templates/
  scripts/
```

Codex 和 Claude Code 的 contract 可以引用 `shared/` 中的脚本与 schema。若运行时要求文件位于 skill 目录内，可以在后续安装脚本中复制或同步这些共享文件，但本阶段不新增安装器。

建议新增文件：

```text
shared/templates/spec.template.md
shared/templates/plan.template.md
shared/schemas/review-result.schema.json
shared/schemas/gate-state.schema.json
shared/scripts/freeze_snapshot.py
shared/scripts/extract_review_result.py
shared/scripts/validate_review_result.py
shared/scripts/gate_check.py
```

`update_ledger.py` 暂不作为首轮必做项。原因是自动回写账本风险更高，应先完成只读校验链路，再独立设计可回写实现。

运行时路径约定：

- 仓库源码以根目录 `shared/` 作为唯一源码真源。
- 发布或安装后，README 必须说明把 `shared/` 同步到 Codex 与 Claude Code skill 根目录下的 `shared/`。
- contract 中引用的脚本路径以运行时 skill 根目录为基准，例如 `shared/scripts/freeze_snapshot.py`。
- 本次实现不直接修改用户本机已安装 skill，但必须让仓库中的安装说明足以把 shared 工具带入运行时。

## 核心行为

### 快照冻结

`freeze_snapshot.py` 输入 canonical spec 和 plan 路径，输出 JSON：

```json
{
  "spec_rev": "sha256:<hash>",
  "plan_rev": "sha256:<hash>",
  "plan_rev_contract_id": "plan-rev/v1",
  "excluded_blocks": ["Review Ledger", "Execution State"],
  "checkbox_normalized": true
}
```

`plan_rev` 必须复用现有 `plan-rev/v1` 语义，不能引入第二套归一化算法。首版实现以 `shared/scripts/freeze_snapshot.py` 内的归一化函数作为新的单一源码真源；现有 `codex/references/compute_plan_rev.py` 和 `claude-code/references/compute_plan_rev.py` 只能改成薄包装器或文档入口，不能继续保留独立算法副本。

### 评审结果校验

`extract_review_result.py` 输入 reviewer 原始输出文本，输出 canonical review result JSON。它必须校验：

- 原始输出中必须恰好存在一个标记为 `review-result-json` 的 fenced JSON block。
- fenced block 内容必须是严格 JSON，不能是 YAML、JSON5 或含注释 JSON。
- fenced block 必须包含 `artifact_version`、`source` 和 review 类型对应的计数字段。
- 如果缺少 JSON block、存在多个 JSON block、或 JSON 无法解析，返回非 0。
- prose 可以存在，但不得作为门禁事实源；所有门禁事实只从 JSON block 读取。

`validate_review_result.py` 输入 `extract_review_result.py` 产出的 canonical JSON、期望的 `review_round`、`spec_rev`、`plan_rev`，代码审查时还包括 `code_rev`。它必须校验：

- `artifact_version` 与当前冻结快照完全一致。
- `source` 只能是 `architect_reviewer`、`architecture_challenger`、`reviewer`。
- 每个 issue 都有 `source`、`reviewer_issue_id`、`issue_id`、`severity`、`kind`、`artifact_anchor`、`summary`、`status`、`same_as_previous`。
- 每个 issue 都有最小 lineage 字段：`first_seen_round`、`last_seen_round`、`supersedes`、`merged_into`、`new_issue_reason`。
- `issue_id` 默认等于 `<source>:<reviewer_issue_id>`。
- `unresolved_high` / `unresolved_medium` 或 `actionable_issues` 与归约后的 open issue 数量一致。
- `requires_doc_update` 等于是否存在 open `design_affecting` issue。
- 当存在 prior-open issues 时，每个 prior-open issue 必须在本轮以相同 `issue_id` 继续 open、标记 resolved，或通过 `merged_into` / `supersedes` 明确归并；不能静默丢失或换号重开。

校验失败时必须返回非 0 exit code，并输出可读错误。

输入边界：

- 可执行校验的唯一输入格式是 canonical JSON，JSON schema 文件是结构合同，跨字段逻辑由 Python 标准库脚本实现。
- reviewer prose 可以继续存在，但结构化结果必须由 `extract_review_result.py` 从原始输出中提取，不能由主 agent 手工搬运字段。
- 可执行门禁派发模板必须要求 reviewer 先输出 `review-result-json` fenced JSON block，再写 prose。
- 既有 contract 中的 YAML 结构化头部只能作为旧文档示例保留；进入可执行门禁路径时，如果 reviewer 没有输出 `review-result-json` fenced JSON block，本轮审查结果 fail-closed。
- 首版不引入 `jsonschema` 或 `PyYAML` 依赖；`review-result.schema.json` 作为声明式结构合同，`validate_review_result.py` 使用标准库手写校验核心字段、枚举和跨字段规则。
- continuity 校验需要显式输入 prior-open ledger excerpt；如果 artifact anchor 因文档修订变化，还必须提供 anchor remap。

### Gate 检查

`gate_check.py` 输入 canonical plan，读取 `Review Ledger` 的 issue details 和 `Execution State` 的机器可读字段，按 `issue_id` 折叠最后状态，输出当前 gate 摘要：

```json
{
  "current_phase": "phase2",
  "gate_state": "phase2_blocked",
  "unresolved_high": 1,
  "unresolved_medium": 0,
  "next_allowed_action": "update_canonical_docs_and_rerun_phase2"
}
```

`gate_check.py` 首版必须覆盖以下 gate 状态：

- `phase2_blocked`：架构双审存在当前 open high / medium issue。
- `phase2_passed_unconfirmed`：架构双审无当前 open high / medium issue，但用户尚未确认实现。
- `phase3_allowed`：用户确认同一组 `spec_rev + plan_rev` 后允许实现。
- `phase4_blocked_implementation_only`：代码审查存在 open `implementation_only` issue，允许只改代码并重跑代码审查。
- `phase4_blocked_design_affecting`：代码审查存在 open `design_affecting` issue，必须更新 spec/plan 并回到方案双审。
- `phase5_completed`：双审通过、代码审查 `actionable_issues = 0`、文档同步完成且存在验证证据。

这些状态不能只从 issue 明细推断。`gate_check.py` 必须同时读取 `Execution State` 中的事实字段：

- `implementation_confirmed_spec_rev`
- `implementation_confirmed_plan_rev`
- `latest_architecture_review_round`
- `latest_architecture_verdict`
- `latest_code_review_round`
- `latest_code_rev`
- `latest_code_review_actionable_issues`
- `latest_code_review_requires_doc_update`
- `docs_synced`
- `verification_evidence`

如果进入 phase3/phase4/phase5 所需事实字段缺失、与当前 `spec_rev` / `plan_rev` 不一致，或与折叠后的 issue 状态冲突，必须 fail-closed。

如果 ledger 缺失、只有 summary、issue details 字段不完整或同一 issue 状态冲突，必须 fail-closed。

Execution State 可解析 grammar：

- 必须用 `<!-- EXECUTION-STATE:START -->` 和 `<!-- EXECUTION-STATE:END -->` 包围。
- 机器可读事实必须放在第一个 fenced JSON block 中，info string 必须是 `gate-state-json`。
- `gate-state-json` block 必须是严格 JSON，不允许 YAML、JSON5、注释或 Markdown 混排。
- `current_phase` 是字符串枚举：`phase1`、`phase2`、`phase3`、`phase4`、`phase5`。
- `gate_state` 是字符串枚举，必须属于 `gate-state.schema.json` 定义的状态集合。
- `review_round`、`spec_rev`、`plan_rev` 是必填字符串。
- `implementation_confirmed_spec_rev` 与 `implementation_confirmed_plan_rev` 可以是 `null` 或字符串；只有二者都等于当前冻结快照时，才允许输出 `phase3_allowed`。
- `latest_architecture_review_round` 与 `latest_architecture_verdict` 可以是 `null` 或字符串；架构 verdict 只允许 `pass` / `block`。
- `latest_code_review_round` 与 `latest_code_rev` 可以是 `null` 或字符串。
- `latest_code_review_actionable_issues` 可以是 `null` 或非负整数。
- `latest_code_review_requires_doc_update` 可以是 `null` 或布尔值。
- `docs_synced` 必须是布尔值；缺失或非布尔值时不得输出 `phase5_completed`。
- `verification_evidence` 必须是数组；每项必须包含 `command`、`result`、`artifact` 三个字符串字段；数组为空时不得输出 `phase5_completed`。
- fenced JSON block 外的 checklist、时间戳、备注和 prose 只用于阅读，不参与机器 gate 判断。

Review Ledger 可解析 grammar：

- 必须用 `<!-- REVIEW-LEDGER:START -->` 和 `<!-- REVIEW-LEDGER:END -->` 包围。
- 必须包含 `### Round Summary` 与 `### Issue Details` 两个二级块。
- `Issue Details` 表头顺序必须固定为：`review_round`、`spec_rev`、`plan_rev`、`source`、`reviewer_issue_id`、`issue_id`、`severity`、`kind`、`summary`、`artifact_anchor`、`status`、`disposition`、`first_seen_round`、`last_seen_round`、`same_as_previous`、`supersedes`、`merged_into`、`new_issue_reason`。
- `severity` 只允许 `high`、`medium`、`low`。
- `kind` 只允许 `architecture`、`implementation_only`、`design_affecting`。
- `status` 只允许 `open`、`resolved`、`superseded`、`accepted`。
- reviewer 结构化输出中的 `status` 只允许 `open`、`resolved`、`superseded`；`accepted` 只能由主 agent 在用户实现确认低风险问题时写入账本。
- `disposition` 只允许 `open`、`fixed`、`superseded`、`accepted`、`escalated`。
- 同一 `issue_id` 的权威状态是按表格顺序出现的最后一条记录；若最后状态冲突、字段缺失、或同一轮同一 issue 出现多个不同最终状态，必须 fail-closed。

## 约束与兼容

- 所有脚本使用 Python 标准库优先；如需第三方库必须在 README 中说明。
- JSON schema 不得要求 reviewer 把 prose 删除；结构化结果可被校验，prose 作为补充说明保留。
- 现有 README 安装方式不应被破坏。
- 现有 `codex/references/compute_plan_rev.py` 和 `claude-code/references/compute_plan_rev.py` 仍可保留为兼容入口，但只能调用 `shared/scripts/freeze_snapshot.py` 中的 canonical `plan-rev/v1` 实现；不得复制或重新实现算法。
- 本阶段不要求发布到远端，除非后续实现确认后用户明确要求。

## 验收标准

- 能在本仓库内生成 `spec_rev + plan_rev`，且 `plan_rev` 与现有 `compute_plan_rev.py` 对同一 plan 的结果一致。
- 能用 schema 或脚本拒绝缺字段、版本不一致、计数字段不一致的 reviewer 结果。
- 能从计划文档中的 `Review Ledger` 计算当前 gate state。
- Codex 与 Claude Code 的 workflow contract 都能指向同一套 shared 校验能力。
- 本次改动不触碰已安装的本机 Codex / Claude Code skill 目录。
