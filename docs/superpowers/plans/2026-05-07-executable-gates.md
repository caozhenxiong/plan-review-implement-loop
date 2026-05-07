# 可执行门禁版 Workflow Skill 实现计划

> 本计划用于 `plan-review-implement-loop` 的 phase 2 双审与后续实现确认。它不是可直接跳过门禁的 implementation handoff。

## 摘要

本计划把当前 workflow skill 的关键可机械判断门禁下沉到 `shared/` 目录中的 templates、schemas 和 scripts。主 workflow 的 phase/gate/ledger 语义保持不变；新增工具只负责稳定生成快照、校验 reviewer 输出和计算 gate state。

## 实施步骤

### 任务 1：新增共享模板

修改范围：

- `shared/templates/spec.template.md`
- `shared/templates/plan.template.md`

要求：

- `spec.template.md` 必须覆盖目标、非目标、边界、约束、风险假设和验收标准。
- `plan.template.md` 必须包含显式 `Review Ledger` 和 `Execution State` 分隔块。
- `plan.template.md` 必须包含 issue details 表结构，不能只给 summary 表。
- 模板只定义 canonical 文档结构，不引入新的流程阶段。

验收：

- 模板可直接复制为 `docs/superpowers/specs/...` 和 `docs/superpowers/plans/...` 的起点。
- 模板中的执行勾选态不会影响 `plan_rev`。

### 任务 2：新增 review result schema

修改范围：

- `shared/schemas/review-result.schema.json`
- `shared/schemas/gate-state.schema.json`

要求：

- `review-result.schema.json` 支持 architecture review 和 code review 两类结果。
- 架构评审必填：`artifact_version`、`verdict`、`unresolved_high`、`unresolved_medium`、`issues`。
- 代码审查必填：`artifact_version`、`verdict`、`actionable_issues`、`requires_doc_update`、`issues`。
- issue 必填：`source`、`reviewer_issue_id`、`issue_id`、`severity`、`kind`、`artifact_anchor`、`summary`、`status`、`same_as_previous`。
- issue lineage 必填：`first_seen_round`、`last_seen_round`、`supersedes`、`merged_into`、`new_issue_reason`。
- schema 只校验结构和枚举，不负责跨字段计数一致性；跨字段逻辑由脚本校验。
- `review-result.schema.json` 是声明式结构合同；首版脚本用 Python 标准库手写校验，不引入 `jsonschema` 运行时依赖。

验收：

- 合法示例能通过 schema。
- 缺少核心字段、非法 `source`、非法 `severity`、非法 `kind` 的示例不能通过 schema。
- 缺少 lineage 字段的示例不能通过结构校验。

### 任务 3：实现 freeze_snapshot.py

修改范围：

- `shared/scripts/freeze_snapshot.py`

要求：

- 输入 `--spec <path>` 和 `--plan <path>`。
- 输出 JSON，包含 `spec_rev`、`plan_rev`、`plan_rev_contract_id`、`excluded_blocks`、`checkbox_normalized`。
- `plan_rev` 必须使用 `plan-rev/v1` 归一化。
- `shared/scripts/freeze_snapshot.py` 必须承载唯一 canonical `plan-rev/v1` 归一化实现。
- `codex/references/compute_plan_rev.py` 与 `claude-code/references/compute_plan_rev.py` 必须改为调用 shared 实现的薄包装器，不能保留第二套算法。
- 如果 plan 缺少 `Review Ledger` 或 `Execution State` 分隔块，默认 fail-closed。

验收：

- 对同一计划文档，`freeze_snapshot.py` 计算出的 `plan_rev` 与现有 `compute_plan_rev.py` 一致。
- 修改 `Execution State` 勾选态不会改变 `plan_rev`。
- 修改 plan 正文会改变 `plan_rev`。

### 任务 4：实现 extract_review_result.py 与 validate_review_result.py

修改范围：

- `shared/scripts/extract_review_result.py`
- `shared/scripts/validate_review_result.py`

要求：

- `extract_review_result.py` 输入 reviewer 原始输出文本，输出 canonical review result JSON。
- reviewer 原始输出必须包含且只包含一个 `review-result-json` fenced JSON block。
- `extract_review_result.py` 必须拒绝 YAML、JSON5、多个 JSON block、缺少 block、无法解析 JSON 的输出。
- prose 可以存在，但不得作为门禁事实源；主 agent 不得手工搬运 prose/YAML 字段来绕过 extractor。
- `validate_review_result.py` 输入 extractor 产出的 canonical review result JSON 和期望 artifact version。
- 先做 schema-shaped 结构校验，再做跨字段校验；首版不依赖第三方 JSON Schema 校验器。
- reviewer 若只输出 YAML 结构化头部，本轮结果 fail-closed；可执行门禁路径只接受 `review-result-json` block。
- 校验 `artifact_version` 与当前冻结快照一致。
- 校验 `issue_id = <source>:<reviewer_issue_id>`。
- 校验架构评审 `unresolved_high` / `unresolved_medium` 等于 open issues 中对应 severity 数量。
- 校验代码审查 `actionable_issues` 等于 open issues 数量。
- 校验 `requires_doc_update` 等于是否存在 open `design_affecting` issue。
- 支持 `--prior-open-ledger <path>`，用于校验 prior-open issues continuity。
- 支持 `--anchor-remap <path>`，用于文档修订后声明旧 anchor 到新 anchor 的映射。
- 每个 prior-open issue 必须在本轮以相同 `issue_id` 继续 open、resolved、merged 或 superseded；不能静默丢失或换号重开。
- 校验失败输出明确错误并返回非 0。

验收：

- 缺字段、版本不一致、计数字段不一致、`requires_doc_update` 错误的样例都被拒绝。
- 合法架构评审和合法代码审查样例都能通过。
- prior-open issue 未被本轮覆盖时必须被拒绝。
- 缺少 `review-result-json` block 或出现多个 JSON block 的原始 reviewer 输出必须被拒绝。

### 任务 5：实现 gate_check.py

修改范围：

- `shared/scripts/gate_check.py`

要求：

- 输入 canonical plan 路径。
- 读取 `Review Ledger` 显式分隔块。
- 读取 `Execution State` 显式分隔块中的机器可读字段。
- 从 issue details 表中解析 issue 记录。
- 按 `issue_id` 折叠最后状态，计算当前 open issue 集。
- 输出当前 gate JSON，至少包含 `gate_state`、`unresolved_high`、`unresolved_medium`、`actionable_issues`、`requires_doc_update`、`next_allowed_action`。
- 如果 ledger 只有 summary、缺少 issue details、字段不完整或同一 issue 状态冲突，fail-closed。
- 严格校验 `Issue Details` 表头顺序、字段枚举和 `issue_id` 最终状态。
- `severity` 枚举必须与现有 contract 对齐为 `high`、`medium`、`low`。
- `kind` 枚举必须与现有 contract 对齐为 `architecture`、`implementation_only`、`design_affecting`。
- `status` 枚举必须与现有 contract 对齐为 `open`、`resolved`、`superseded`、`accepted`；其中 `accepted` 只允许主 agent 在实现确认点写入 ledger，不允许 reviewer 直接输出。
- `disposition` 枚举必须与现有 contract 对齐为 `open`、`fixed`、`superseded`、`accepted`、`escalated`。
- 支持 phase2、实现确认、phase4 代码审查和 phase5 完成路径，不只支持 phase2。
- phase3/phase4/phase5 判断必须依赖 `Execution State` 中的事实字段，不能只靠 issue 表为空推断。
- `Execution State` 必须至少支持：`implementation_confirmed_spec_rev`、`implementation_confirmed_plan_rev`、`latest_architecture_review_round`、`latest_architecture_verdict`、`latest_code_review_round`、`latest_code_rev`、`latest_code_review_actionable_issues`、`latest_code_review_requires_doc_update`、`docs_synced`、`verification_evidence`。
- `Execution State` 的机器事实必须放在第一个 `gate-state-json` fenced JSON block 中；不允许从 YAML、Markdown checklist 或 prose 中解析门禁事实。
- `gate-state-json` 必须是严格 JSON：`docs_synced` 为布尔值，`verification_evidence` 为数组，每个元素包含 `command`、`result`、`artifact` 三个字符串字段，代码审查计数为非负整数或 `null`。
- phase4 中 open `implementation_only` issue 输出 `phase4_blocked_implementation_only` 与 `fix_code_and_rerun_code_review`。
- phase4 中 open `design_affecting` issue 输出 `phase4_blocked_design_affecting` 与 `update_canonical_docs_and_rerun_phase2`。
- 完成条件满足时输出 `phase5_completed` 与 `complete`.

验收：

- 历史 open 行后续 resolved 时，不再算当前 blocker。
- 只有 summary 表时阻塞。
- 当前仍有 high/medium 时输出 `phase2_blocked` 与 `update_canonical_docs_and_rerun_phase2`。
- 无 high/medium 时输出 `phase2_passed_unconfirmed` 与 `enter_implementation_confirmation`。
- design-affecting 代码审查问题会回到方案双审，而不是允许只改代码。
- 缺少实现确认字段时不得输出 `phase3_allowed`。
- 缺少最新代码审查零 issue 事实、文档同步事实或验证证据时不得输出 `phase5_completed`。
- 非 JSON 的 Execution State、布尔值大小写错误、空 `verification_evidence` 或证据字段缺失时必须 fail-closed。

### 任务 6：更新 workflow contract 引用 shared 校验能力

修改范围：

- `codex/references/workflow-contract.md`
- `claude-code/references/workflow-contract.md`
- 视情况小幅更新 `README.md`

要求：

- contract 明确推荐使用 `shared/scripts/freeze_snapshot.py` 冻结快照。
- contract 明确 reviewer 必须输出 `review-result-json` fenced JSON block，并推荐先用 `shared/scripts/extract_review_result.py` 提取。
- contract 明确 reviewer 结构化输出应通过 `shared/scripts/validate_review_result.py` 校验。
- contract 明确 gate 状态应通过 `shared/scripts/gate_check.py` 或等价逻辑计算。
- 保留现有强门禁文字，不把 `SKILL.md` 降级为薄入口。
- README 明确仓库源码中的 `shared/` 是共享工具源码真源，并给出 Codex / Claude Code 安装时同步 `shared/` 的命令。
- contract 运行时路径以安装后的 skill 根目录为准；本分支不直接修改用户本机已安装 skill。

验收：

- Codex 和 Claude Code 两边都能看到同一套 shared 校验入口。
- README 对新增 shared 能力有简短说明，且不会要求修改用户本机已配置 skill 才能完成本分支实现。

## 测试计划

- 运行 `freeze_snapshot.py` 对本计划生成 `plan_rev`，与现有 `codex/references/compute_plan_rev.py` 对比。
- 准备含单个 `review-result-json` block、缺失 block、多个 block、非法 JSON 的 reviewer 原始输出，运行 `extract_review_result.py`。
- 准备合法和非法 reviewer result JSON，运行 `validate_review_result.py`。
- 准备含历史 open/resolved issue 的 plan fixture，运行 `gate_check.py`。
- 准备缺少实现确认、缺少最新代码审查事实、缺少验证证据的 Execution State fixture，确认 `gate_check.py` 不会误判 phase3 或 phase5。
- 运行 `python -m json.tool` 或等价命令校验 JSON schema 文件格式。
- 运行个人路径泄漏检查，确保发布仓库不重新引入本机用户名或绝对路径。

## 风险与处理

- Markdown 表格解析可能脆弱：首版只支持模板定义的 issue details 表，并对不符合格式的 ledger fail-closed。
- schema 无法表达所有跨字段逻辑：把跨字段规则放进 Python 标准库脚本。
- 自动回写 ledger 风险较高：首版不实现 `update_ledger.py`，避免误改文档。
- shared 目录与安装目录关系可能产生混淆：README 必须明确源码真源与运行时复制路径，当前分支不碰本机已安装目录。

<!-- REVIEW-LEDGER:START -->
## Review Ledger

### Round Summary

| Round | spec_rev | plan_rev | Reviewer | Verdict | High | Medium |
|-------|----------|----------|----------|---------|------|--------|
| R1 | sha256:3fe99e67b9cbc410f8ec8e07e348acbfa00e76c9b76b157dceeafa41e2441f32 | sha256:65e805bdc329ac111ee99e9c2d1e0555c43081dd118f8c85cd120070ebb70610 | architect_reviewer | BLOCK | 0 | 3 |
| R1 | sha256:3fe99e67b9cbc410f8ec8e07e348acbfa00e76c9b76b157dceeafa41e2441f32 | sha256:65e805bdc329ac111ee99e9c2d1e0555c43081dd118f8c85cd120070ebb70610 | architecture_challenger | BLOCK | 1 | 4 |
| R2 | sha256:bc43c6c5b41651e3401c6a5d9b952d69061993ac23120382d1804e882eeada84 | sha256:84b214503c35fd8c48a6863d8c8aef42c3742b00d5357592fe5e6c307ccaf8b3 | architect_reviewer | BLOCK | 0 | 2 |
| R2 | sha256:bc43c6c5b41651e3401c6a5d9b952d69061993ac23120382d1804e882eeada84 | sha256:84b214503c35fd8c48a6863d8c8aef42c3742b00d5357592fe5e6c307ccaf8b3 | architecture_challenger | BLOCK | 0 | 2 |
| R3 | sha256:ba8b6bf43c2f950b153a8fe86e0706a8b7a8bb7d4cdb16878f28d7c33e19b353 | sha256:a25f090ab1750ffb2b93f4e676e1c4421e604a5fa2b11f821374e26979a62dff | architect_reviewer | PASS | 0 | 0 |
| R3 | sha256:ba8b6bf43c2f950b153a8fe86e0706a8b7a8bb7d4cdb16878f28d7c33e19b353 | sha256:a25f090ab1750ffb2b93f4e676e1c4421e604a5fa2b11f821374e26979a62dff | architecture_challenger | BLOCK | 0 | 2 |
| R4 | sha256:a8a6ef2dc84a1dfd83b91bb5f4728c64416981fc71e8cc4363a040a2261a62b6 | sha256:49b0a0eb8a02565f9af38676050dd446b0ef94156c0fd52d0be596de4e8740cc | architect_reviewer | PASS | 0 | 0 |
| R4 | sha256:a8a6ef2dc84a1dfd83b91bb5f4728c64416981fc71e8cc4363a040a2261a62b6 | sha256:49b0a0eb8a02565f9af38676050dd446b0ef94156c0fd52d0be596de4e8740cc | architecture_challenger | PASS | 0 | 0 |
| R5 | sha256:a8a6ef2dc84a1dfd83b91bb5f4728c64416981fc71e8cc4363a040a2261a62b6 | sha256:8c8782138ab074bec96901194676ab15a06f99c83decdd96bc5cb12e3ebeca2f | architect_reviewer | PASS | 0 | 0 |
| R5 | sha256:a8a6ef2dc84a1dfd83b91bb5f4728c64416981fc71e8cc4363a040a2261a62b6 | sha256:8c8782138ab074bec96901194676ab15a06f99c83decdd96bc5cb12e3ebeca2f | architecture_challenger | PASS | 0 | 0 |

### Issue Details

| review_round | spec_rev | plan_rev | source | reviewer_issue_id | issue_id | severity | kind | summary | artifact_anchor | status | disposition | first_seen_round | last_seen_round | same_as_previous | supersedes | merged_into | new_issue_reason |
|--------------|----------|----------|--------|-------------------|----------|----------|------|---------|-----------------|--------|-------------|------------------|-----------------|------------------|------------|-------------|------------------|
| R1 | sha256:3fe99e67b9cbc410f8ec8e07e348acbfa00e76c9b76b157dceeafa41e2441f32 | sha256:65e805bdc329ac111ee99e9c2d1e0555c43081dd118f8c85cd120070ebb70610 | architect_reviewer | AR-001 | architect_reviewer:AR-001 | medium | architecture | `validate_review_result.py` 输入固定为 JSON，缺少 reviewer YAML block 到可校验对象的解析边界。 | spec:评审结果校验#p1; plan:任务4#b1 | open | open | R1 | R1 | false |  |  | R1 full rereview 发现输入格式与既有 reviewer 输出 contract 不闭合 |
| R1 | sha256:3fe99e67b9cbc410f8ec8e07e348acbfa00e76c9b76b157dceeafa41e2441f32 | sha256:65e805bdc329ac111ee99e9c2d1e0555c43081dd118f8c85cd120070ebb70610 | architect_reviewer | AR-002 | architect_reviewer:AR-002 | medium | architecture | `gate_check.py` 状态机只覆盖 phase2 blocked/pass，未闭合 phase4 和 phase5 路径。 | spec:Gate检查#p1; plan:任务5#b1 | open | open | R1 | R1 | false |  |  | R1 full rereview 发现 gate state 和 next action 覆盖不完整 |
| R1 | sha256:3fe99e67b9cbc410f8ec8e07e348acbfa00e76c9b76b157dceeafa41e2441f32 | sha256:65e805bdc329ac111ee99e9c2d1e0555c43081dd118f8c85cd120070ebb70610 | architect_reviewer | AR-003 | architect_reviewer:AR-003 | medium | architecture | `validate_review_result.py` 缺少 prior-open ledger、prior issue ids、anchor_remap 输入合同，无法机器校验 continuity。 | spec:评审结果校验#p1; plan:任务4#b1 | open | open | R1 | R1 | false |  |  | R1 full rereview 发现 continuity 校验输入缺失 |
| R1 | sha256:3fe99e67b9cbc410f8ec8e07e348acbfa00e76c9b76b157dceeafa41e2441f32 | sha256:65e805bdc329ac111ee99e9c2d1e0555c43081dd118f8c85cd120070ebb70610 | architecture_challenger | AC-R1-001 | architecture_challenger:AC-R1-001 | high | architecture | review result schema 未要求完整 lineage 字段，会让机器校验通过但主 workflow 仍判定评审无效。 | plan:任务2 review-result schema / spec:评审结果校验 | open | open | R1 | R1 | false |  |  | 当前快照首次审查发现；prior open issue 为空 |
| R1 | sha256:3fe99e67b9cbc410f8ec8e07e348acbfa00e76c9b76b157dceeafa41e2441f32 | sha256:65e805bdc329ac111ee99e9c2d1e0555c43081dd118f8c85cd120070ebb70610 | architecture_challenger | AC-R1-002 | architecture_challenger:AC-R1-002 | medium | architecture | 计划要求 schema 校验但默认标准库优先，未说明 JSON Schema 校验器来源或手写校验边界。 | plan:任务4 validate_review_result.py / spec:约束与兼容 | open | open | R1 | R1 | false |  |  | 当前快照首次审查发现；prior open issue 为空 |
| R1 | sha256:3fe99e67b9cbc410f8ec8e07e348acbfa00e76c9b76b157dceeafa41e2441f32 | sha256:65e805bdc329ac111ee99e9c2d1e0555c43081dd118f8c85cd120070ebb70610 | architecture_challenger | AC-R1-003 | architecture_challenger:AC-R1-003 | medium | architecture | Review Ledger 的块边界、issue details 表头、状态枚举和冲突判定没有定义成可解析 grammar。 | spec:Gate 检查 / plan:任务5 gate_check.py | open | open | R1 | R1 | false |  |  | 当前快照首次审查发现；prior open issue 为空 |
| R1 | sha256:3fe99e67b9cbc410f8ec8e07e348acbfa00e76c9b76b157dceeafa41e2441f32 | sha256:65e805bdc329ac111ee99e9c2d1e0555c43081dd118f8c85cd120070ebb70610 | architecture_challenger | AC-R1-004 | architecture_challenger:AC-R1-004 | medium | architecture | shared 工具只放仓库且不新增安装器、不改已安装 skill，实际运行时可能仍使用旧 Markdown-only 门禁。 | spec:公共接口与目录 / plan:任务6 更新 workflow contract | open | open | R1 | R1 | false |  |  | 当前快照首次审查发现；prior open issue 为空 |
| R1 | sha256:3fe99e67b9cbc410f8ec8e07e348acbfa00e76c9b76b157dceeafa41e2441f32 | sha256:65e805bdc329ac111ee99e9c2d1e0555c43081dd118f8c85cd120070ebb70610 | architecture_challenger | AC-R1-005 | architecture_challenger:AC-R1-005 | medium | architecture | `plan_rev` 允许 shared 脚本调用或复制两份 compute_plan_rev.py，仍会保留双源漂移风险。 | spec:快照冻结 / plan:任务3 freeze_snapshot.py | open | open | R1 | R1 | false |  |  | 当前快照首次审查发现；prior open issue 为空 |
| R2 | sha256:bc43c6c5b41651e3401c6a5d9b952d69061993ac23120382d1804e882eeada84 | sha256:84b214503c35fd8c48a6863d8c8aef42c3742b00d5357592fe5e6c307ccaf8b3 | architect_reviewer | AR-001 | architect_reviewer:AR-001 | medium | architecture | YAML 到 canonical JSON 的转换边界已定义，转换失败 fail-closed；JSON-only 输入边界问题已收口。 | spec:评审结果校验/输入边界; plan:任务4 validate_review_result.py | resolved | fixed | R1 | R2 | true |  |  |  |
| R2 | sha256:bc43c6c5b41651e3401c6a5d9b952d69061993ac23120382d1804e882eeada84 | sha256:84b214503c35fd8c48a6863d8c8aef42c3742b00d5357592fe5e6c307ccaf8b3 | architect_reviewer | AR-002 | architect_reviewer:AR-002 | medium | architecture | gate_check 状态枚举已扩展，但缺少用户实现确认、代码审查通过、文档同步完成和验证证据的事实来源合同。 | spec:Gate检查/gate状态列表; plan:任务5 gate_check.py | open | open | R1 | R2 | true |  |  |  |
| R2 | sha256:bc43c6c5b41651e3401c6a5d9b952d69061993ac23120382d1804e882eeada84 | sha256:84b214503c35fd8c48a6863d8c8aef42c3742b00d5357592fe5e6c307ccaf8b3 | architect_reviewer | AR-003 | architect_reviewer:AR-003 | medium | architecture | prior-open ledger excerpt 与 anchor_remap 输入已补充，continuity 输入问题已收口。 | spec:评审结果校验/continuity输入; plan:任务4 validate_review_result.py | resolved | fixed | R1 | R2 | true |  |  |  |
| R2 | sha256:bc43c6c5b41651e3401c6a5d9b952d69061993ac23120382d1804e882eeada84 | sha256:84b214503c35fd8c48a6863d8c8aef42c3742b00d5357592fe5e6c307ccaf8b3 | architect_reviewer | AR-004 | architect_reviewer:AR-004 | medium | architecture | R2 ledger grammar 新增状态和 kind 枚举，与现有 workflow contract 的 reviewer 输出枚举不一致。 | spec:Gate检查/Review Ledger可解析grammar; plan:任务5 gate_check.py | open | open | R2 | R2 | false |  |  | R2 full rereview 发现 ledger grammar 枚举与既有 workflow contract 漂移 |
| R2 | sha256:bc43c6c5b41651e3401c6a5d9b952d69061993ac23120382d1804e882eeada84 | sha256:84b214503c35fd8c48a6863d8c8aef42c3742b00d5357592fe5e6c307ccaf8b3 | architecture_challenger | AC-R1-001 | architecture_challenger:AC-R1-001 | high | architecture | issue lineage 必填字段和 prior-open continuity 校验已补充。 | spec:评审结果校验/lineage字段; plan:任务2 review-result schema | resolved | fixed | R1 | R2 | true |  |  |  |
| R2 | sha256:bc43c6c5b41651e3401c6a5d9b952d69061993ac23120382d1804e882eeada84 | sha256:84b214503c35fd8c48a6863d8c8aef42c3742b00d5357592fe5e6c307ccaf8b3 | architecture_challenger | AC-R1-002 | architecture_challenger:AC-R1-002 | medium | architecture | 已明确首版不依赖 jsonschema/PyYAML，schema 作为结构合同，脚本用标准库手写校验。 | spec:评审结果校验/输入边界; plan:任务4 validate_review_result.py | resolved | fixed | R1 | R2 | true |  |  |  |
| R2 | sha256:bc43c6c5b41651e3401c6a5d9b952d69061993ac23120382d1804e882eeada84 | sha256:84b214503c35fd8c48a6863d8c8aef42c3742b00d5357592fe5e6c307ccaf8b3 | architecture_challenger | AC-R1-003 | architecture_challenger:AC-R1-003 | medium | architecture | Review Ledger block marker、固定表头、字段枚举和冲突 fail-closed 规则已定义。 | spec:Gate检查/Review Ledger grammar; plan:任务5 gate_check.py | resolved | fixed | R1 | R2 | true |  |  |  |
| R2 | sha256:bc43c6c5b41651e3401c6a5d9b952d69061993ac23120382d1804e882eeada84 | sha256:84b214503c35fd8c48a6863d8c8aef42c3742b00d5357592fe5e6c307ccaf8b3 | architecture_challenger | AC-R1-004 | architecture_challenger:AC-R1-004 | medium | architecture | 仓库 shared 为源码真源、安装后同步到 skill 根目录，并要求 README 给出同步命令。 | spec:公共接口与目录/运行时路径约定; plan:任务6 workflow contract and README | resolved | fixed | R1 | R2 | true |  |  |  |
| R2 | sha256:bc43c6c5b41651e3401c6a5d9b952d69061993ac23120382d1804e882eeada84 | sha256:84b214503c35fd8c48a6863d8c8aef42c3742b00d5357592fe5e6c307ccaf8b3 | architecture_challenger | AC-R1-005 | architecture_challenger:AC-R1-005 | medium | architecture | 已要求 freeze_snapshot.py 承载唯一 canonical plan-rev/v1 实现，旧 compute_plan_rev.py 只能是薄包装器。 | spec:快照冻结/单一plan-rev源码真源; plan:任务3 freeze_snapshot.py | resolved | fixed | R1 | R2 | true |  |  |  |
| R2 | sha256:bc43c6c5b41651e3401c6a5d9b952d69061993ac23120382d1804e882eeada84 | sha256:84b214503c35fd8c48a6863d8c8aef42c3742b00d5357592fe5e6c307ccaf8b3 | architecture_challenger | AC-R2-001 | architecture_challenger:AC-R2-001 | medium | architecture | canonical JSON 由主 agent 从 reviewer YAML/prose 提取，但缺少受控 extractor/normalizer，机器门禁仍依赖模型手工搬运关键字段。 | spec:评审结果校验/输入边界; plan:任务4 validate_review_result.py | open | open | R2 | R2 | false |  |  | R2 full rereview 发现原始输出到 canonical JSON 缺少受控转换路径 |
| R2 | sha256:bc43c6c5b41651e3401c6a5d9b952d69061993ac23120382d1804e882eeada84 | sha256:84b214503c35fd8c48a6863d8c8aef42c3742b00d5357592fe5e6c307ccaf8b3 | architecture_challenger | AC-R2-002 | architecture_challenger:AC-R2-002 | medium | architecture | gate_check 覆盖 phase3_allowed、phase5_completed，但未定义用户实现确认、code_rev、代码审查零 issue、最终验证证据的机器可读事实来源。 | spec:Gate检查; plan:任务5 gate_check.py | open | open | R2 | R2 | false |  |  | R2 full rereview 发现状态所需事实源没有同步定义 |
| R3 | sha256:ba8b6bf43c2f950b153a8fe86e0706a8b7a8bb7d4cdb16878f28d7c33e19b353 | sha256:a25f090ab1750ffb2b93f4e676e1c4421e604a5fa2b11f821374e26979a62dff | architect_reviewer | AR-002 | architect_reviewer:AR-002 | medium | architecture | gate_check 已明确读取 Review Ledger 与 Execution State 事实字段，并要求事实缺失、版本不一致或与 issue 折叠状态冲突时 fail-closed。 | spec:Gate检查/Execution State fact fields; plan:任务5 gate_check.py | resolved | fixed | R1 | R3 | true |  |  |  |
| R3 | sha256:ba8b6bf43c2f950b153a8fe86e0706a8b7a8bb7d4cdb16878f28d7c33e19b353 | sha256:a25f090ab1750ffb2b93f4e676e1c4421e604a5fa2b11f821374e26979a62dff | architect_reviewer | AR-004 | architect_reviewer:AR-004 | medium | architecture | Review Ledger grammar 已对齐既有 workflow contract 枚举，枚举漂移问题已收口。 | spec:Gate检查/Review Ledger可解析grammar; plan:任务5 gate_check.py | resolved | fixed | R2 | R3 | true |  |  |  |
| R3 | sha256:ba8b6bf43c2f950b153a8fe86e0706a8b7a8bb7d4cdb16878f28d7c33e19b353 | sha256:a25f090ab1750ffb2b93f4e676e1c4421e604a5fa2b11f821374e26979a62dff | architecture_challenger | AC-R2-001 | architecture_challenger:AC-R2-001 | medium | architecture | 已新增 extract_review_result.py，要求恰好一个 review-result-json fenced JSON block，prose 非权威，并禁止主 agent 手工搬运字段。 | spec:评审结果校验/extract_review_result.py; plan:任务4 extract_review_result.py 与 validate_review_result.py | resolved | fixed | R2 | R3 | true |  |  |  |
| R3 | sha256:ba8b6bf43c2f950b153a8fe86e0706a8b7a8bb7d4cdb16878f28d7c33e19b353 | sha256:a25f090ab1750ffb2b93f4e676e1c4421e604a5fa2b11f821374e26979a62dff | architecture_challenger | AC-R2-002 | architecture_challenger:AC-R2-002 | medium | architecture | Execution State 已列出字段名，但没有定义可解析 grammar、字段类型、空值语义和验证证据格式。 | spec:Gate检查/Execution State fact fields; plan:任务5 gate_check.py | open | open | R2 | R3 | true |  |  |  |
| R3 | sha256:ba8b6bf43c2f950b153a8fe86e0706a8b7a8bb7d4cdb16878f28d7c33e19b353 | sha256:a25f090ab1750ffb2b93f4e676e1c4421e604a5fa2b11f821374e26979a62dff | architecture_challenger | AC-R3-001 | architecture_challenger:AC-R3-001 | medium | architecture | spec 前文要求 freeze_snapshot.py 是唯一 plan-rev/v1 源码真源，但约束与兼容仍保留可以调用或复制旧算法的冲突表述。 | spec:约束与兼容 / spec:快照冻结 / plan:任务3 freeze_snapshot.py | open | open | R3 | R3 | false |  |  | R3 full rereview 发现 spec 内部存在互相冲突的 plan_rev 源码真源约束 |
| R4 | sha256:a8a6ef2dc84a1dfd83b91bb5f4728c64416981fc71e8cc4363a040a2261a62b6 | sha256:49b0a0eb8a02565f9af38676050dd446b0ef94156c0fd52d0be596de4e8740cc | architecture_challenger | AC-R2-002 | architecture_challenger:AC-R2-002 | medium | architecture | Execution State 机器事实已收口到 gate-state-json fenced JSON block，并定义字段类型、null 语义和验证证据数组格式。 | spec:Gate检查/Execution State可解析grammar; plan:任务5 gate_check.py | resolved | fixed | R2 | R4 | true |  |  |  |
| R4 | sha256:a8a6ef2dc84a1dfd83b91bb5f4728c64416981fc71e8cc4363a040a2261a62b6 | sha256:49b0a0eb8a02565f9af38676050dd446b0ef94156c0fd52d0be596de4e8740cc | architecture_challenger | AC-R3-001 | architecture_challenger:AC-R3-001 | medium | architecture | 兼容入口已改为只能调用 shared canonical plan-rev/v1 实现，明确禁止复制或重新实现算法。 | spec:约束与兼容 / spec:快照冻结; plan:任务3 freeze_snapshot.py | resolved | fixed | R3 | R4 | true |  |  |  |

<!-- REVIEW-LEDGER:END -->

<!-- EXECUTION-STATE:START -->
## Execution State

```gate-state-json
{
  "current_phase": "phase3",
  "gate_state": "phase3_allowed",
  "review_round": "R5",
  "spec_rev": "sha256:a8a6ef2dc84a1dfd83b91bb5f4728c64416981fc71e8cc4363a040a2261a62b6",
  "plan_rev": "sha256:8c8782138ab074bec96901194676ab15a06f99c83decdd96bc5cb12e3ebeca2f",
  "previous_review_round": "R4",
  "previous_spec_rev": "sha256:a8a6ef2dc84a1dfd83b91bb5f4728c64416981fc71e8cc4363a040a2261a62b6",
  "previous_plan_rev": "sha256:49b0a0eb8a02565f9af38676050dd446b0ef94156c0fd52d0be596de4e8740cc",
  "implementation_confirmed_spec_rev": "sha256:a8a6ef2dc84a1dfd83b91bb5f4728c64416981fc71e8cc4363a040a2261a62b6",
  "implementation_confirmed_plan_rev": "sha256:8c8782138ab074bec96901194676ab15a06f99c83decdd96bc5cb12e3ebeca2f",
  "latest_architecture_review_round": "R5",
  "latest_architecture_verdict": "pass",
  "latest_code_review_round": null,
  "latest_code_rev": null,
  "latest_code_review_actionable_issues": null,
  "latest_code_review_requires_doc_update": null,
  "docs_synced": true,
  "verification_evidence": [
    {
      "command": "python3 -m json.tool shared/schemas/review-result.schema.json && python3 -m json.tool shared/schemas/gate-state.schema.json",
      "result": "pass",
      "artifact": "shared schema JSON files"
    },
    {
      "command": "python3 -m py_compile shared/scripts/*.py codex/references/compute_plan_rev.py claude-code/references/compute_plan_rev.py",
      "result": "pass",
      "artifact": "shared scripts and runtime wrappers"
    },
    {
      "command": "python3 shared/scripts/freeze_snapshot.py --spec docs/superpowers/specs/2026-05-07-executable-gates-design.md --plan docs/superpowers/plans/2026-05-07-executable-gates.md",
      "result": "pass",
      "artifact": "spec_rev and plan_rev snapshot"
    },
    {
      "command": "python3 shared/scripts/gate_check.py docs/superpowers/plans/2026-05-07-executable-gates.md",
      "result": "pass",
      "artifact": "phase3_allowed gate calculation"
    },
    {
      "command": "personal path leakage scan",
      "result": "pass",
      "artifact": "README, codex, claude-code, codex-agents, shared, docs"
    }
  ],
  "next_allowed_action": "begin_implementation",
  "do_not_start_coding_yet": false
}
```

### Progress

- [x] 创建隔离分支 `feature/executable-gates-plan`
- [x] 生成 canonical spec
- [x] 生成 canonical plan
- [x] 冻结 `spec_rev + plan_rev`
- [x] 触发 phase 2 双审
- [x] 根据 R1 blockers 修订 canonical spec + plan
- [x] 触发 R2 全量方案双审
- [x] 根据 R2 blockers 修订 canonical spec + plan
- [x] 触发 R3 全量方案双审
- [x] 根据 R3 blockers 修订 canonical spec + plan
- [x] 触发 R4 全量方案双审
- [x] R4 双审通过
- [x] 修订测试计划中的本机路径检查表述
- [x] 触发 R5 全量方案双审
- [x] R5 双审通过
- [x] 用户确认同一组 `spec_rev + plan_rev` 后进入实现
- [x] 新增 shared templates / schemas / scripts
- [x] 将 Codex / Claude Code `compute_plan_rev.py` 改为 shared wrapper
- [x] 更新 README 安装说明同步 `shared/`
- [x] 更新 Codex / Claude Code contract 引用可执行门禁
- [x] 运行验证
- [ ] 进入 phase 4 独立代码审查

<!-- EXECUTION-STATE:END -->
