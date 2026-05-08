# Phase 4 Gate Hardening 设计文档

> 本文档用于 `plan-review-implement-loop` phase 2 方案双审。它定义需求、边界和验收，不直接授权实现。

## 背景

当前 workflow 已经加入 `shared/` 可执行门禁、`review-result-json` 提取校验、`gate-state-json` 和 Claude Code 的 phase 3 后强制进入 phase 4 文案约束。近期试跑显示 Claude Code 已能强制进入 phase 4，但还存在四个流程层缺口：

- Claude Code `SKILL.md` 与 `workflow-contract.md` 的 gate output 枚举不完全一致。
- `gate_check.py` 还不能机器判定“实现已产生但代码审查尚未执行”的 `phase4_required` 状态。
- Claude Code 的 dispatch templates 比 Codex 版粗，字段和 hard requirements 展开不足。
- `shared/` 脚本缺少仓库内固定 fixtures/tests，无法持续防止回归。

## 目标

- 补齐 Claude Code Gate State Contract，使 `phase4_required` 与 `enter_code_review` 在 `SKILL.md`、`workflow-contract.md`、schema 中一致。
- 增强 `shared/scripts/gate_check.py`，当存在实现/代码快照事实但缺少最新代码审查时，输出 `phase4_required` 和 `enter_code_review`。
- 将 Claude Code 三类 dispatch templates 补到 Codex 同等细度，特别是 `review-result-json` 字段、计数字段一致性、checklist 对齐、accepted trade-off、结构质量 gate、scope violation。
- 增加共享 fixture/test 覆盖核心 gate 场景，尤其是“无 CR 不可完成”。

## 非目标

- 不引入 Web UI、MCP、GitHub Action 或外部测试框架。
- 不改变现有 phase 1-5 语义。
- 不新增自动回写 `Review Ledger` 的写入器。
- 不改变 Codex/Claude 的安装路径。
- 不在双审通过前修改本机已安装 skill。

## 设计原则

- 机器门禁优先于模型自觉：能由 `gate_check.py` 判断的状态，不只停留在文案。
- Codex 与 Claude Code 语义对齐，但保留运行时差异：Codex 绑定本地 agents，Claude Code 绑定角色槽/等价持续任务实例。
- fixture 使用 Python 标准库实现，避免新增依赖。
- 测试聚焦流程边界，不测试所有 Markdown 排版细节。

## 方案

### Gate State 补齐

`gate-state.schema.json` 增加：

- `gate_state = phase4_required`
- `next_allowed_action = enter_code_review`
- 可选事实字段 `implementation_changed`，布尔值，用于表达 phase 3 已产生实现改动。
- 可选事实字段 `latest_code_review_spec_rev`、`latest_code_review_plan_rev`、`latest_code_review_code_rev`，记录最新通过或阻塞的代码审查实际绑定的冻结三元组。
- `next_allowed_action` 增加 `write_code_rev_and_rerun_gate_check`，用于表达 phase 3 已声明实现变化但尚未写入可审代码快照的 fail-closed 修复动作。

phase 3 状态事实生产合同：

- 只要 phase 3 产生代码、测试、脚本、文档或 prompt 实现改动，主 agent 必须在进入 phase 4 前写入 `latest_code_rev`。
- `implementation_changed` 只表示“当前实现快照尚未被 phase 4 覆盖”，初始默认 false；phase 3 产生实现改动时必须置为 true。
- phase 4 代码审查完成并且 `latest_code_review_code_rev == latest_code_rev`、`latest_code_review_spec_rev == spec_rev`、`latest_code_review_plan_rev == plan_rev` 后，才允许把 `implementation_changed` 置为 false。
- 不允许用字段缺失表达“没有改动”；如果确实没有实现改动，必须保持 `latest_code_rev = null` 且 `implementation_changed = false`。

`gate_check.py` 的优先级：

1. 仍先处理 architecture open high/medium。
2. 再处理 code review open issues：`design_affecting` 优先，其次 `implementation_only`。
3. 如果 `implementation_changed = true` 但 `latest_code_rev` 为空，输出 `blocked` / `write_code_rev_and_rerun_gate_check`；不得进入 phase 4，因为代码审查没有可绑定的代码快照。
4. 如果 `latest_code_rev` 非空，但缺少最新代码审查事实，输出 `phase4_required` / `enter_code_review`。
5. 如果存在最新代码审查事实，但 `latest_code_review_spec_rev != spec_rev`、`latest_code_review_plan_rev != plan_rev` 或 `latest_code_review_code_rev != latest_code_rev`，输出 `phase4_required` / `enter_code_review`。
6. 只有最新代码审查三元组匹配、`actionable_issues = 0`、`docs_synced = true` 且 `verification_evidence` 非空时，才允许 `phase5_completed`。

`gate_check.py` 必须支持空 `Issue Details` 表。空表表示当前没有任何历史 issue；它不能导致 `phase4_required` 首次进入失败，也不能要求写入 dummy issue。

### Claude Contract 补齐

`claude-code/references/workflow-contract.md` 的 Gate State Contract 必须与 `claude-code/SKILL.md` 和 schema 对齐：

- `gate_state` 包含 `phase4_required`。
- `next_allowed_action` 包含 `enter_code_review`。
- 明确 phase 3 后实现改动完成时不能 `complete`。

Claude dispatch templates 必须展开到 Codex 同等要求：

- Architecture Reviewer / Challenger：明确 `artifact_version.review_round`、`spec_rev`、`plan_rev`、`source`、`verdict`、`unresolved_high`、`unresolved_medium`、`issues`。
- Code Reviewer：明确 `code_rev`、`actionable_issues`、`requires_doc_update`、计数一致性、checklist 对齐、设计偏离、scope violation、accepted trade-off、结构质量 gate。

### Fixture Tests

新增 `shared/tests/test_gate_workflow.py`，只使用 Python 标准库，动态生成临时 plan fixture 并调用 `gate_check.compute_gate`。

至少覆盖：

- 实现已改变但无 CR：输出 `phase4_required` / `enter_code_review`。
- CR 有 `implementation_only`：输出 `phase4_blocked_implementation_only` / `fix_code_and_rerun_code_review`。
- CR 有 `design_affecting`：输出 `phase4_blocked_design_affecting` / `update_canonical_docs_and_rerun_phase2`。
- CR 为 0 但没有 verification evidence：不得输出 `phase5_completed`。
- CR 为 0 且 docs/evidence 完整：输出 `phase5_completed` / `complete`。
- 旧 CR 三元组与当前 `spec_rev + plan_rev + code_rev` 不匹配：输出 `phase4_required` / `enter_code_review`。
- `implementation_changed = true` 但 `latest_code_rev` 缺失：输出 `blocked` / `write_code_rev_and_rerun_gate_check`，不得进入 code review。
- 空 `Issue Details` 表 + 实现已改变但无 CR：输出 `phase4_required`，不需要 dummy issue。
- `review-result-json` 错误 fence 被 `extract_review_result.py` 拒绝。
- `validate_review_result.py` 拒绝计数字段不一致。

新增 contract parity test：

- 从 `gate-state.schema.json` 读取 `gate_state` 与 `next_allowed_action` 枚举。
- 从 `claude-code/SKILL.md` 与 `claude-code/references/workflow-contract.md` 的 Required Output / Gate State Contract 代码块解析枚举。
- 三者集合必须一致；不能只用 `rg` 命中证明。
- 检查 Claude Code code-review dispatch 至少包含 `code_rev`、`actionable_issues`、`requires_doc_update`、`spec`、`plan`、`checklist`、`scope violation`、`accepted trade-off`、`structure-quality` 等固定要求。

## 风险与处理

- `implementation_changed` 与 `latest_code_rev` 不一致：`implementation_changed = true` 只说明实现快照需要被覆盖；进入 phase 4 仍必须有 `latest_code_rev`。如果 `latest_code_rev` 缺失，先 fail-closed 补写代码快照。
- 旧 `gate-state-json` fixture 不含 `implementation_changed`：字段可选，默认 false，保持兼容。
- Claude dispatch 文本过长：优先复制关键 gate 要求，不复制所有 Codex 本地 agent 绑定描述。

## 验收标准

- `python3 -m unittest discover -s shared/tests` 通过。
- `python3 -m json.tool shared/schemas/gate-state.schema.json` 通过。
- `python3 shared/scripts/gate_check.py <fixture>` 能对 `phase4_required` 场景输出 `enter_code_review`，且不需要 dummy issue。
- `python3 shared/scripts/gate_check.py <fixture>` 能对缺失 `latest_code_rev` 的实现变更场景输出 `write_code_rev_and_rerun_gate_check`，避免无代码快照进入 code review。
- Claude Code `SKILL.md`、`workflow-contract.md`、schema 三处 gate enum 集合精确一致。
- Claude Code dispatch templates 明确代码审查必须核对 spec / plan / checklist，不得只查 bug。
