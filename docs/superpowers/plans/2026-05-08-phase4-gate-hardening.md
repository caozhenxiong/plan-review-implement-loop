# Phase 4 Gate Hardening 实现计划

> 本计划用于 `plan-review-implement-loop` phase 2 双审与后续实现确认。它不是可直接跳过门禁的 implementation handoff。

## 摘要

本计划补齐 phase 4 相关的流程硬化：让 Claude Code contract 与 `SKILL.md` 的 gate 枚举一致，让 `gate_check.py` 机器识别“实现完成但尚未代码审查”，并用 fixture tests 固化关键 gate 行为。

## 实施步骤

### 任务 1：补齐 Gate State 枚举

修改范围：

- `shared/schemas/gate-state.schema.json`
- `claude-code/references/workflow-contract.md`
- 如需要，轻微同步 `claude-code/SKILL.md`

要求：

- `gate_state` 包含 `phase4_required`。
- `next_allowed_action` 包含 `enter_code_review`。
- schema 支持可选 `implementation_changed` 布尔字段。
- schema 支持 `latest_code_review_spec_rev`、`latest_code_review_plan_rev`、`latest_code_review_code_rev`，用于绑定最新代码审查覆盖的冻结三元组。
- `next_allowed_action` 支持 `write_code_rev_and_rerun_gate_check`，用于 fail-closed 处理 `implementation_changed = true` 但 `latest_code_rev` 缺失的非法状态。
- Claude Code `SKILL.md` 与 `workflow-contract.md` 的 output contract 枚举一致。
- 新增 contract parity 测试，不允许只用 `rg` 命中证明一致。

验收：

- `python3 -m unittest discover -s shared/tests -k contract_parity` 能证明 `SKILL.md`、`workflow-contract.md`、schema 的 gate enum 集合一致。
- JSON schema 格式校验通过。

### 任务 2：增强 gate_check.py 的 phase4_required 判定

修改范围：

- `shared/scripts/gate_check.py`

要求：

- 读取 `implementation_changed`，缺失时默认 false。
- 当 `implementation_changed = true` 且 `latest_code_rev` 缺失时，输出：
  - `gate_state = blocked`
  - `next_allowed_action = write_code_rev_and_rerun_gate_check`
- 当 `latest_code_rev` 非空，且没有最新代码审查事实时，输出：
  - `gate_state = phase4_required`
  - `next_allowed_action = enter_code_review`
- 当最新代码审查事实存在但 `latest_code_review_spec_rev != spec_rev`、`latest_code_review_plan_rev != plan_rev` 或 `latest_code_review_code_rev != latest_code_rev` 时，也输出 `phase4_required`。
- 只有最新代码审查三元组与当前三元组完全匹配，且 `latest_code_review_actionable_issues = 0`、`docs_synced = true`、`verification_evidence` 非空时，才允许 `phase5_completed`。
- 支持空 `Issue Details` 表；空表表示无历史 issue，不得因此 fail-closed。
- 不破坏既有 phase2、phase4 blocked、phase5 completed 判定。

验收：

- 实现改动但无 CR 的 fixture 输出 `phase4_required`。
- `implementation_changed = true` 但 `latest_code_rev` 缺失的 fixture 输出 `blocked` / `write_code_rev_and_rerun_gate_check`，不得进入 code review。
- 旧 CR 三元组不匹配时输出 `phase4_required`。
- 空 Issue Details 表的 phase4_required fixture 不需要 dummy issue。
- CR 有 open issue 时仍优先输出对应 blocked 状态。

### 任务 2.5：定义 phase 3 状态事实生产合同

修改范围：

- `claude-code/SKILL.md`
- `claude-code/references/workflow-contract.md`
- 视需要同步 `codex/references/workflow-contract.md`

要求：

- phase 3 产生任何实现改动后，主 agent 必须在进入 phase 4 前写入 `latest_code_rev` 并将 `implementation_changed` 置为 true。
- 如果 `implementation_changed = true` 但 `latest_code_rev` 缺失，gate 必须阻塞在补写代码快照，不得进入 phase 4。
- phase 4 代码审查完成后，必须写入 `latest_code_review_spec_rev`、`latest_code_review_plan_rev`、`latest_code_review_code_rev`。
- 只有代码审查三元组匹配当前三元组时，才允许 `implementation_changed = false` 和 phase5 判断。
- 不允许用缺失字段表达“无代码改动”；无改动必须显式保持 `latest_code_rev = null` 与 `implementation_changed = false`。

验收：

- Claude Code contract 明确上述写入方、写入时机和缺失语义。
- fixture 覆盖缺失 `latest_code_rev` / mismatch `latest_code_review_code_rev` 的行为。

### 任务 3：补齐 Claude dispatch templates

修改范围：

- `claude-code/references/workflow-contract.md`

要求：

- Architecture Reviewer / Challenger 的 dispatch 明确列出 JSON 字段和严格 JSON fence 要求。
- Code Reviewer dispatch 补齐：
  - `code_rev`
  - `actionable_issues`
  - `requires_doc_update`
  - 计数字段一致性
  - spec / plan / checklist item-by-item 核对
  - scope violation
  - structure-quality gate
  - accepted trade-off 只读语义
- dispatch template 必须包含可解析的固定字段名；测试至少检查核心关键词存在，避免只靠人工阅读。
- 保留 Claude Code 运行时不强绑定 Codex 本地 agent 的差异。

验收：

- Claude Code code reviewer template 与 Codex template 在核心 gate 要求上等价。
- 文档中不出现本机绝对路径或用户名。

### 任务 4：新增 shared fixture tests

修改范围：

- `shared/tests/test_gate_workflow.py`

要求：

- 使用 Python 标准库 `unittest`。
- 动态生成最小 plan fixture，避免维护多份大 Markdown。
- 覆盖 phase4_required、implementation_only、design_affecting、缺 evidence 不 complete、完整 evidence complete。
- 覆盖旧 CR 三元组不匹配、空 Issue Details 表、contract enum parity。
- 覆盖 `implementation_changed = true` 但 `latest_code_rev` 缺失时的 fail-closed 状态。
- 覆盖 extract/validate 的至少一个正例和一个反例。

验收：

- `python3 -m unittest discover -s shared/tests` 通过。
- `python3 -m py_compile shared/scripts/*.py` 通过。

## 测试计划

- `python3 -m json.tool shared/schemas/gate-state.schema.json`
- `python3 -m py_compile shared/scripts/*.py`
- `python3 -m unittest discover -s shared/tests`
- `python3 -m unittest shared.tests.test_gate_workflow.ContractParityTests`
- 个人路径泄漏扫描。

## 风险与处理

- 过度扩大 scope：本轮只补 phase 4 gate 和 Claude template，不重做 ledger writer。
- fixture 与真实 plan 有差异：测试使用与 `gate_check.py` 表头一致的最小 Markdown，覆盖状态机而非完整文档风格。
- `implementation_changed` 可能被遗漏：`latest_code_rev` 非空也触发 `phase4_required`，降低漏判概率。
- `implementation_changed` 与 `latest_code_rev` 不一致：若前者为 true 但后者缺失，先阻塞补写快照，避免无绑定代码审查。

<!-- REVIEW-LEDGER:START -->
## Review Ledger

### Round Summary

| Round | spec_rev | plan_rev | Reviewer | Verdict | High | Medium |
|-------|----------|----------|----------|---------|------|--------|
| R1 | sha256:b964ac75ef825a0d333c291dabe1aa5e1c0a696dc9a63a7af269e06a18315e3f | sha256:e9a6c39f19d82ec7538400a462bf88885bcda05758ebe27a0d3ee21b22c22ffd | architect_reviewer | BLOCK | 0 | 3 |
| R1 | sha256:b964ac75ef825a0d333c291dabe1aa5e1c0a696dc9a63a7af269e06a18315e3f | sha256:e9a6c39f19d82ec7538400a462bf88885bcda05758ebe27a0d3ee21b22c22ffd | architecture_challenger | BLOCK | 1 | 3 |
| R2 | sha256:76e65620d8de30a7e12d3a7fa20f4f7f857df2c19ec94f4a83098d90d8b04d65 | sha256:21645b3cb94a3ab6ccdb40e66991febf73a63d854030efe0bc48d23aa6042ed7 | architect_reviewer | PASS | 0 | 0 |
| R2 | sha256:76e65620d8de30a7e12d3a7fa20f4f7f857df2c19ec94f4a83098d90d8b04d65 | sha256:21645b3cb94a3ab6ccdb40e66991febf73a63d854030efe0bc48d23aa6042ed7 | architecture_challenger | BLOCK | 0 | 1 |
| R3 | sha256:cd82a8190eea35694fbdc516c0b04b741fe01b798075c291f646233ee93d5c66 | sha256:2a05aea2414f58004fa7e2923a5d4f5f3c14564d7d4f86e1fb5051a7aecdd93f | architect_reviewer | PASS | 0 | 0 |
| R3 | sha256:cd82a8190eea35694fbdc516c0b04b741fe01b798075c291f646233ee93d5c66 | sha256:2a05aea2414f58004fa7e2923a5d4f5f3c14564d7d4f86e1fb5051a7aecdd93f | architecture_challenger | PASS | 0 | 0 |
| R4 | sha256:b33e3567edb3bc1ea63ab17aadd85a30df285a0c73f72184da913ff738b0e40f | sha256:2a05aea2414f58004fa7e2923a5d4f5f3c14564d7d4f86e1fb5051a7aecdd93f | architect_reviewer | PASS | 0 | 0 |
| R4 | sha256:b33e3567edb3bc1ea63ab17aadd85a30df285a0c73f72184da913ff738b0e40f | sha256:2a05aea2414f58004fa7e2923a5d4f5f3c14564d7d4f86e1fb5051a7aecdd93f | architecture_challenger | PASS | 0 | 0 |
| CR1 | sha256:b33e3567edb3bc1ea63ab17aadd85a30df285a0c73f72184da913ff738b0e40f | sha256:2a05aea2414f58004fa7e2923a5d4f5f3c14564d7d4f86e1fb5051a7aecdd93f | reviewer | BLOCK | 1 | 0 |
| CR2 | sha256:b33e3567edb3bc1ea63ab17aadd85a30df285a0c73f72184da913ff738b0e40f | sha256:2a05aea2414f58004fa7e2923a5d4f5f3c14564d7d4f86e1fb5051a7aecdd93f | reviewer | PASS | 0 | 0 |

### Issue Details

| review_round | spec_rev | plan_rev | source | reviewer_issue_id | issue_id | severity | kind | summary | artifact_anchor | status | disposition | first_seen_round | last_seen_round | same_as_previous | supersedes | merged_into | new_issue_reason |
|--------------|----------|----------|--------|-------------------|----------|----------|------|---------|-----------------|--------|-------------|------------------|-----------------|------------------|------------|-------------|------------------|
| R1 | sha256:b964ac75ef825a0d333c291dabe1aa5e1c0a696dc9a63a7af269e06a18315e3f | sha256:e9a6c39f19d82ec7538400a462bf88885bcda05758ebe27a0d3ee21b22c22ffd | architect_reviewer | AR-R1-001 | architect_reviewer:AR-R1-001 | medium | architecture | phase5 completion gate 缺少最新实现 revision 与最新通过代码审查 revision 的显式绑定。 | spec:Gate State 补齐 / plan:任务2 | open | open | R1 | R1 | false |  |  | R1 full review；无 prior-open issue |
| R1 | sha256:b964ac75ef825a0d333c291dabe1aa5e1c0a696dc9a63a7af269e06a18315e3f | sha256:e9a6c39f19d82ec7538400a462bf88885bcda05758ebe27a0d3ee21b22c22ffd | architect_reviewer | AR-R1-002 | architect_reviewer:AR-R1-002 | medium | architecture | `implementation_changed` / `latest_code_rev` 的生产者、写入时机和缺失语义未定义。 | spec:Gate State 补齐 / plan:任务2 | open | open | R1 | R1 | false |  |  | R1 full review；无 prior-open issue |
| R1 | sha256:b964ac75ef825a0d333c291dabe1aa5e1c0a696dc9a63a7af269e06a18315e3f | sha256:e9a6c39f19d82ec7538400a462bf88885bcda05758ebe27a0d3ee21b22c22ffd | architect_reviewer | AR-R1-003 | architect_reviewer:AR-R1-003 | medium | architecture | 验收只靠 grep，不能证明 `SKILL.md`、contract、schema 的枚举和字段合同等价。 | spec:验收标准 / plan:任务1 | open | open | R1 | R1 | false |  |  | R1 full review；无 prior-open issue |
| R1 | sha256:b964ac75ef825a0d333c291dabe1aa5e1c0a696dc9a63a7af269e06a18315e3f | sha256:e9a6c39f19d82ec7538400a462bf88885bcda05758ebe27a0d3ee21b22c22ffd | architecture_challenger | AC-001 | architecture_challenger:AC-001 | high | architecture | phase5 completion 未要求通过的代码审查绑定当前 `code_rev/spec_rev/plan_rev`，旧 CR 事实可能错误放行完成。 | spec:Gate State 补齐 / plan:任务2 | open | open | R1 | R1 | false |  |  | R1 full challenger review；无 prior-open issue |
| R1 | sha256:b964ac75ef825a0d333c291dabe1aa5e1c0a696dc9a63a7af269e06a18315e3f | sha256:e9a6c39f19d82ec7538400a462bf88885bcda05758ebe27a0d3ee21b22c22ffd | architecture_challenger | AC-002 | architecture_challenger:AC-002 | medium | architecture | `implementation_changed` 是手工可选事实，缺少设置、清除和失效生命周期，容易误报或漏报 phase4_required。 | spec:Gate State 补齐 / plan:任务2 | open | open | R1 | R1 | false |  |  | R1 full challenger review；无 prior-open issue |
| R1 | sha256:b964ac75ef825a0d333c291dabe1aa5e1c0a696dc9a63a7af269e06a18315e3f | sha256:e9a6c39f19d82ec7538400a462bf88885bcda05758ebe27a0d3ee21b22c22ffd | architecture_challenger | AC-003 | architecture_challenger:AC-003 | medium | architecture | phase4_required 首次进入时可能没有任何 issue，计划未要求 `gate_check.py` 支持空 Issue Details 表。 | spec:Fixture Tests / plan:任务4 | open | open | R1 | R1 | false |  |  | R1 full challenger review；无 prior-open issue |
| R1 | sha256:b964ac75ef825a0d333c291dabe1aa5e1c0a696dc9a63a7af269e06a18315e3f | sha256:e9a6c39f19d82ec7538400a462bf88885bcda05758ebe27a0d3ee21b22c22ffd | architecture_challenger | AC-004 | architecture_challenger:AC-004 | medium | architecture | 验收只 grep 新枚举，未要求 `SKILL.md`、contract、schema 的精确枚举等价，旧值可能继续漂移。 | spec:Claude Contract 补齐 / plan:任务1 | open | open | R1 | R1 | false |  |  | R1 full challenger review；无 prior-open issue |
| R2 | sha256:76e65620d8de30a7e12d3a7fa20f4f7f857df2c19ec94f4a83098d90d8b04d65 | sha256:21645b3cb94a3ab6ccdb40e66991febf73a63d854030efe0bc48d23aa6042ed7 | architect_reviewer | AR-R1-001 | architect_reviewer:AR-R1-001 | medium | architecture | phase5 completion gate 缺少最新实现 revision 与最新通过代码审查 revision 的显式绑定。 | spec:Gate State 补齐 / plan:任务2,任务2.5 | resolved | fixed | R1 | R2 | true |  |  |  |
| R2 | sha256:76e65620d8de30a7e12d3a7fa20f4f7f857df2c19ec94f4a83098d90d8b04d65 | sha256:21645b3cb94a3ab6ccdb40e66991febf73a63d854030efe0bc48d23aa6042ed7 | architect_reviewer | AR-R1-002 | architect_reviewer:AR-R1-002 | medium | architecture | `implementation_changed` / `latest_code_rev` 的生产者、写入时机和缺失语义未定义。 | spec:phase 3 状态事实生产合同 / plan:任务2.5 | resolved | fixed | R1 | R2 | true |  |  |  |
| R2 | sha256:76e65620d8de30a7e12d3a7fa20f4f7f857df2c19ec94f4a83098d90d8b04d65 | sha256:21645b3cb94a3ab6ccdb40e66991febf73a63d854030efe0bc48d23aa6042ed7 | architect_reviewer | AR-R1-003 | architect_reviewer:AR-R1-003 | medium | architecture | 验收只靠 grep，不能证明 `SKILL.md`、contract、schema 的枚举和字段合同等价。 | spec:Fixture Tests + contract parity / plan:任务1,任务4 | resolved | fixed | R1 | R2 | true |  |  |  |
| R2 | sha256:76e65620d8de30a7e12d3a7fa20f4f7f857df2c19ec94f4a83098d90d8b04d65 | sha256:21645b3cb94a3ab6ccdb40e66991febf73a63d854030efe0bc48d23aa6042ed7 | architecture_challenger | AC-001 | architecture_challenger:AC-001 | high | architecture | R2 adds latest_code_review_spec_rev/latest_code_review_plan_rev/latest_code_review_code_rev binding and requires phase5 completion to match the current spec_rev, plan_rev, and latest_code_rev, closing the stale CR completion path. | spec:Gate State 补齐 / plan:任务2 | resolved | fixed | R1 | R2 | true |  |  |  |
| R2 | sha256:76e65620d8de30a7e12d3a7fa20f4f7f857df2c19ec94f4a83098d90d8b04d65 | sha256:21645b3cb94a3ab6ccdb40e66991febf73a63d854030efe0bc48d23aa6042ed7 | architecture_challenger | AC-002 | architecture_challenger:AC-002 | medium | architecture | R2 defines implementation_changed and latest_code_rev producer timing, clear semantics, and clearing rules after matching phase4 review facts, closing the prior lifecycle ambiguity. | spec:phase 3 状态事实生产合同 / plan:任务2.5 | resolved | fixed | R1 | R2 | true |  |  |  |
| R2 | sha256:76e65620d8de30a7e12d3a7fa20f4f7f857df2c19ec94f4a83098d90d8b04d65 | sha256:21645b3cb94a3ab6ccdb40e66991febf73a63d854030efe0bc48d23aa6042ed7 | architecture_challenger | AC-003 | architecture_challenger:AC-003 | medium | architecture | R2 requires gate_check.py to support an empty Issue Details table and adds a no-CR phase4_required fixture without dummy issues, closing the first-run ledger failure mode. | spec:Fixture Tests / plan:任务4 | resolved | fixed | R1 | R2 | true |  |  |  |
| R2 | sha256:76e65620d8de30a7e12d3a7fa20f4f7f857df2c19ec94f4a83098d90d8b04d65 | sha256:21645b3cb94a3ab6ccdb40e66991febf73a63d854030efe0bc48d23aa6042ed7 | architecture_challenger | AC-004 | architecture_challenger:AC-004 | medium | architecture | R2 replaces grep-only acceptance with exact enum parity tests across gate-state.schema.json, Claude SKILL.md, and Claude workflow-contract.md, closing the drift-prone acceptance gap. | spec:Claude Contract 补齐 + contract parity / plan:任务1,任务4 | resolved | fixed | R1 | R2 | true |  |  |  |
| R2 | sha256:76e65620d8de30a7e12d3a7fa20f4f7f857df2c19ec94f4a83098d90d8b04d65 | sha256:21645b3cb94a3ab6ccdb40e66991febf73a63d854030efe0bc48d23aa6042ed7 | architecture_challenger | AC-005 | architecture_challenger:AC-005 | medium | architecture | The R2 gate rule still allows implementation_changed=true by itself to emit phase4_required/enter_code_review even when latest_code_rev is missing, but the producer contract says latest_code_rev must be written before phase4; in real handoff this can route the workflow into code review without a bound code snapshot. | spec:Gate State 补齐 / plan:任务2,任务2.5 | open | open | R2 | R2 | false |  |  | Full R2 rereview found an invalid-state transition introduced by combining the new phase3 producer contract with the phase4_required gate rule. |
| R3 | sha256:cd82a8190eea35694fbdc516c0b04b741fe01b798075c291f646233ee93d5c66 | sha256:2a05aea2414f58004fa7e2923a5d4f5f3c14564d7d4f86e1fb5051a7aecdd93f | architect_reviewer | AR-R3-001 | architect_reviewer:AR-R3-001 | medium | architecture | implementation_changed=true alone could route to phase4_required/enter_code_review without latest_code_rev, causing code review without a bound code snapshot. | spec:Gate State 补齐 / plan:任务1,任务2,任务2.5,任务4 | resolved | fixed | R3 | R3 | false | architecture_challenger:AC-005 |  | Reviewed AC-005 continuity from architect_reviewer slot; R3 changes now fail closed with blocked/write_code_rev_and_rerun_gate_check when implementation_changed=true but latest_code_rev is missing. |
| R3 | sha256:cd82a8190eea35694fbdc516c0b04b741fe01b798075c291f646233ee93d5c66 | sha256:2a05aea2414f58004fa7e2923a5d4f5f3c14564d7d4f86e1fb5051a7aecdd93f | architecture_challenger | AC-005 | architecture_challenger:AC-005 | medium | architecture | R3 resolves the invalid transition by making implementation_changed=true with missing latest_code_rev fail closed as blocked/write_code_rev_and_rerun_gate_check, and only allowing phase4_required/enter_code_review when latest_code_rev is nonempty. | spec:Gate State 补齐 / plan:任务1,任务2,任务2.5,任务4 | resolved | fixed | R2 | R3 | true |  |  |  |
| R3 | sha256:cd82a8190eea35694fbdc516c0b04b741fe01b798075c291f646233ee93d5c66 | sha256:2a05aea2414f58004fa7e2923a5d4f5f3c14564d7d4f86e1fb5051a7aecdd93f | architecture_challenger | AC-006 | architecture_challenger:AC-006 | low | architecture | The spec risk note still says implementation_changed and latest_code_rev may each trigger phase4_required, which is stale wording after R3; the main gate priority and fixtures are clear enough to prevent a medium blocker, but the note should be cleaned up to avoid future reader confusion. | spec:风险与处理 | open | open | R3 | R3 | false |  |  | Full R3 rereview found stale explanatory text that contradicts the new invalid-state handling, but executable acceptance tests should catch the dangerous behavior. |
| R4 | sha256:b33e3567edb3bc1ea63ab17aadd85a30df285a0c73f72184da913ff738b0e40f | sha256:2a05aea2414f58004fa7e2923a5d4f5f3c14564d7d4f86e1fb5051a7aecdd93f | architect_reviewer | AR-R4-001 | architect_reviewer:AR-R4-001 | low | architecture | stale risk note suggested implementation_changed/latest_code_rev may each trigger phase4_required, contradicting R3 invalid-state handling. | spec:风险与处理 | resolved | fixed | R4 | R4 | false | architecture_challenger:AC-006 |  | Reviewed AC-006 continuity from architect_reviewer slot; R4 spec risk note now states implementation_changed=true only means implementation snapshot needs coverage, phase 4 still requires latest_code_rev, and missing latest_code_rev fail-closes to code snapshot write. |
| R4 | sha256:b33e3567edb3bc1ea63ab17aadd85a30df285a0c73f72184da913ff738b0e40f | sha256:2a05aea2414f58004fa7e2923a5d4f5f3c14564d7d4f86e1fb5051a7aecdd93f | architecture_challenger | AC-006 | architecture_challenger:AC-006 | low | architecture | R4 resolves the stale risk-note wording: implementation_changed=true now only means the implementation snapshot needs coverage, while phase4 still requires latest_code_rev and missing latest_code_rev fail-closes to code snapshot writing. | spec:风险与处理 | resolved | fixed | R3 | R4 | true |  |  |  |
| CR1 | sha256:b33e3567edb3bc1ea63ab17aadd85a30df285a0c73f72184da913ff738b0e40f | sha256:2a05aea2414f58004fa7e2923a5d4f5f3c14564d7d4f86e1fb5051a7aecdd93f | reviewer | CR-001 | reviewer:CR-001 | high | implementation_only | phase5 completion can still be reached without any bound latest_code_rev or latest_code_review_* tuple because `(not latest_code_rev or code_review_tuple_matches)` allows CR=0/docs/evidence to complete without a code snapshot. | shared/scripts/gate_check.py:167 | open | open | CR1 | CR1 | false |  |  | Full CR1 implementation review found a remaining fail-open completion path in the new phase4 tuple gate. |
| CR2 | sha256:b33e3567edb3bc1ea63ab17aadd85a30df285a0c73f72184da913ff738b0e40f | sha256:2a05aea2414f58004fa7e2923a5d4f5f3c14564d7d4f86e1fb5051a7aecdd93f | reviewer | CR-001 | reviewer:CR-001 | high | implementation_only | phase5 completion previously could be reached without any bound latest_code_rev or latest_code_review_* tuple because `(not latest_code_rev or code_review_tuple_matches)` allowed CR=0/docs/evidence to complete without a code snapshot. CR2 now requires `latest_code_rev` and `code_review_tuple_matches` in the phase5 condition, and adds `test_zero_cr_without_code_rev_does_not_complete` as regression coverage. | shared/scripts/gate_check.py:167 | resolved | fixed | CR1 | CR2 | true |  |  |  |

<!-- REVIEW-LEDGER:END -->

<!-- EXECUTION-STATE:START -->
## Execution State

```gate-state-json
{
  "current_phase": "phase5",
  "gate_state": "phase5_completed",
  "review_round": "R4",
  "spec_rev": "sha256:b33e3567edb3bc1ea63ab17aadd85a30df285a0c73f72184da913ff738b0e40f",
  "plan_rev": "sha256:2a05aea2414f58004fa7e2923a5d4f5f3c14564d7d4f86e1fb5051a7aecdd93f",
  "previous_review_round": "R3",
  "previous_spec_rev": "sha256:cd82a8190eea35694fbdc516c0b04b741fe01b798075c291f646233ee93d5c66",
  "previous_plan_rev": "sha256:2a05aea2414f58004fa7e2923a5d4f5f3c14564d7d4f86e1fb5051a7aecdd93f",
  "implementation_confirmed_spec_rev": "sha256:b33e3567edb3bc1ea63ab17aadd85a30df285a0c73f72184da913ff738b0e40f",
  "implementation_confirmed_plan_rev": "sha256:2a05aea2414f58004fa7e2923a5d4f5f3c14564d7d4f86e1fb5051a7aecdd93f",
  "implementation_changed": false,
  "latest_architecture_review_round": "R4",
  "latest_architecture_verdict": "pass",
  "latest_code_review_round": "CR2",
  "latest_code_rev": "sha256:ac46b5f6db1043081cf55ac499e9d359387cf06157b1478b8aac96e294f8b7cf",
  "latest_code_review_spec_rev": "sha256:b33e3567edb3bc1ea63ab17aadd85a30df285a0c73f72184da913ff738b0e40f",
  "latest_code_review_plan_rev": "sha256:2a05aea2414f58004fa7e2923a5d4f5f3c14564d7d4f86e1fb5051a7aecdd93f",
  "latest_code_review_code_rev": "sha256:ac46b5f6db1043081cf55ac499e9d359387cf06157b1478b8aac96e294f8b7cf",
  "latest_code_review_actionable_issues": 0,
  "latest_code_review_requires_doc_update": false,
  "docs_synced": true,
  "verification_evidence": [
    {
      "command": "python3 -m json.tool shared/schemas/gate-state.schema.json",
      "result": "pass",
      "artifact": "/tmp/gate-state-json.out"
    },
    {
      "command": "python3 -m py_compile shared/scripts/*.py",
      "result": "pass",
      "artifact": "terminal"
    },
    {
      "command": "python3 -m unittest discover -s shared/tests",
      "result": "pass: 15 tests",
      "artifact": "terminal"
    },
    {
      "command": "python3 -m unittest shared.tests.test_gate_workflow.ContractParityTests",
      "result": "pass: 2 tests",
      "artifact": "terminal"
    }
  ],
  "next_allowed_action": "complete",
  "do_not_start_coding_yet": false
}
```

### Plan Compliance Checklist

| ID | 设计原文要求 | 当前实现位置 | 偏差点 | 必须删除或禁用的旧路径 | 必须新增的行为 | 允许修改的文件/模块 | 验收命令或用例 | 状态 |
|----|--------------|--------------|--------|------------------------|----------------|----------------------|----------------|------|
| PCC-1 | `gate_state` 包含 `phase4_required`，`next_allowed_action` 包含 `enter_code_review` 与 `write_code_rev_and_rerun_gate_check`；schema 支持实现与 CR 三元组字段。 | `shared/schemas/gate-state.schema.json` | schema 当前缺少新枚举和部分字段。 | 禁止保留 schema 与文档枚举漂移。 | 增加 `phase4_required`、`enter_code_review`、`write_code_rev_and_rerun_gate_check`、`implementation_changed`、`latest_code_review_*_rev`。 | `shared/schemas/gate-state.schema.json` | `python3 -m json.tool shared/schemas/gate-state.schema.json`；contract parity tests | done |
| PCC-2 | `gate_check.py` 必须识别实现已变但无 CR、旧 CR 三元组不匹配、缺 `latest_code_rev` 的 fail-closed。 | `shared/scripts/gate_check.py` | 当前只看 CR issue / docs evidence，不识别 phase4_required 或 stale CR tuple；空 Issue Details 会 fail。 | 禁止把 `implementation_changed=true` 且无 `latest_code_rev` 送进 code review。 | 空 Issue Details 支持；phase4_required；tuple mismatch；blocked/write_code_rev_and_rerun_gate_check；phase5 tuple match gate。 | `shared/scripts/gate_check.py` | `python3 -m unittest discover -s shared/tests`；手工 fixture gate_check | done |
| PCC-3 | Claude Code `SKILL.md` 与 contract 的 Gate State Contract 必须和 schema 精确一致，并定义 phase3 状态事实生产合同。 | `claude-code/SKILL.md`、`claude-code/references/workflow-contract.md` | 当前枚举不一致，contract 缺 phase4_required / enter_code_review，状态事实写入时机不够硬。 | 禁止用 `complete` 表示实现完成但未 CR；禁止缺字段表达无改动。 | 同步枚举；补 phase3 写 `latest_code_rev` / `implementation_changed`，phase4 写 `latest_code_review_*_rev`，缺快照 fail-closed。 | `claude-code/SKILL.md`、`claude-code/references/workflow-contract.md` | `ContractParityTests`；关键词检查 | done |
| PCC-4 | Claude dispatch templates 必须补齐严格 JSON fence、字段、计数字段一致性、spec/plan/checklist 核对、scope violation、structure-quality、accepted trade-off。 | `claude-code/references/workflow-contract.md` | Claude templates 比 Codex 粗，容易漏字段或把 code review 降级成 bug review。 | 禁止引入 Codex 本地 agent 绑定；保留 Claude Code runtime 差异。 | Architecture / Challenger / Code Reviewer dispatch 模板补齐核心字段与硬要求。 | `claude-code/references/workflow-contract.md` | dispatch keyword tests；人工检查无本机路径 | done |
| PCC-5 | 共享 tests 必须用标准库动态生成 fixture，覆盖 gate 状态机、review-result 提取/校验、contract parity。 | `shared/tests/` 目前无对应测试文件。 | 缺少持续回归保护。 | 禁止新增外部测试依赖。 | 新增 `shared/tests/test_gate_workflow.py` 覆盖计划中的全部场景。 | `shared/tests/test_gate_workflow.py` | `python3 -m unittest discover -s shared/tests`；`python3 -m py_compile shared/scripts/*.py` | done |
| PCC-6 | 如 Codex contract 需要同步 phase3 状态事实，轻触不扩 scope。 | `codex/references/workflow-contract.md` | 可能缺少与 shared gate 对齐的 phase3 写入说明。 | 禁止改 Codex agent `.toml`、README、图片、本机安装 skill。 | 仅在必要处同步 `latest_code_rev` / `implementation_changed` / CR tuple 语义。 | `codex/references/workflow-contract.md` | `rg "latest_code_review_spec_rev|write_code_rev_and_rerun_gate_check" codex/references/workflow-contract.md` | done |

### Progress

- [x] 生成 canonical spec
- [x] 生成 canonical plan
- [x] 冻结 `spec_rev + plan_rev`
- [x] 触发 R1 方案双审
- [x] 根据 R1 blockers 修订 canonical spec + plan
- [x] 触发 R2 方案双审
- [x] 根据 R2 blocker 修订 canonical spec + plan
- [x] 触发 R3 方案双审
- [x] 根据 R3 low-risk 清理 canonical spec 文案
- [x] 触发 R4 方案双审
- [x] R4 双审通过
- [x] 等待用户确认进入实现
- [x] 确认 Plan Compliance Checklist
- [x] 完成 phase 3 实现并冻结 `latest_code_rev`
- [x] 进入 phase 4 代码审查
- [x] 修复 CR1 implementation_only 问题并冻结新 `latest_code_rev`
- [x] 重跑 CR2 代码审查
- [x] phase 5 最终验证完成

<!-- EXECUTION-STATE:END -->
