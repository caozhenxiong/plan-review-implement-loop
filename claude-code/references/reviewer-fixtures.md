# Reviewer Fixtures

这份 fixture 清单用于校验 Codex 与 Claude Code 两侧 reviewer 的角色偏置和代码质量 gate 边界是否一致。

每个 fixture 都给出：

- 主责 reviewer
- 允许重叠的 reviewer
- 禁止误判的场景
- fail 条件

## F1 `style_only_naming`

- 场景：
  - 实现功能正确，只存在格式、命名审美、注释风格或 import 排序差异。
- 主责 reviewer：
  - `reviewer`
- 允许重叠：
  - 无
- 禁止误判：
  - 不应产出结构化 `issues`
  - 不应计入 `actionable_issues`
  - 不应触发 `requires_doc_update`
- fail 条件：
  - 任一 reviewer 把纯 style-only 评论当作 blocker

## F2 `implementation_duplicate_logic`

- 场景：
  - 两处逻辑重复实现，当前修复只改了一处，另一处高度可能在后续改动时漏修。
- 主责 reviewer：
  - `reviewer`
- 允许重叠：
  - 无
- 禁止误判：
  - 不应被降格为纯“建议优化”
  - 不应仅因为可以抽象得更优就直接升级为 `design_affecting`
- fail 条件：
  - `reviewer` 没有把它识别成具有工程后果的结构质量风险

## F3 `shared_mutable_state`

- 场景：
  - 当前实现返回或暴露共享可变对象，可能造成状态污染、一致性问题或并发隐患。
- 主责 reviewer：
  - `reviewer`
- 允许重叠：
  - `architect_reviewer` 可以在 phase 2 对相同模式报设计层一致性风险
- 禁止误判：
  - 不应被描述成纯风格问题
- fail 条件：
  - `reviewer` 没有把它识别成阻塞性工程风险

## F4 `design_boundary_drift`

- 场景：
  - 代码实现超出了当前 `spec + plan` 的接口边界或交付路径，需要文档同步才能合法化。
- 主责 reviewer：
  - `reviewer`
- 允许重叠：
  - 无
- 禁止误判：
  - 不应仅标为 `implementation_only`
  - 不应把“文档没更新”包装成可忽略建议
- fail 条件：
  - 未返回 `design_affecting`
  - 未令 `requires_doc_update = true`

## F5 `hidden_failure_path`

- 场景：
  - 实现通过危险 fallback 或过度隐蔽的控制流掩盖失败路径，导致测试、审计或排障不可靠。
- 主责 reviewer：
  - `reviewer`
- 允许重叠：
  - 无
- 禁止误判：
  - 不应只写“可优化”
- fail 条件：
  - 未指出验证/排障可靠性受损

## F6 `architecture_readiness_gap`

- 场景：
  - 方案边界、接口合同、状态一致性或失败恢复路径尚未闭合，当前还不具备安全进入实现的前提。
- 主责 reviewer：
  - `architect_reviewer`
- 允许重叠：
  - `architecture_challenger` 仅在该缺口同时带来明显现实世界失败模式时允许重叠
- 禁止误判：
  - `architecture_challenger` 不应只把这类普通方案未闭合问题重复报一遍
- fail 条件：
  - `architect_reviewer` 没有把它作为阻塞实现的问题

## F7 `real_world_assumption_failure`

- 场景：
  - 方案默认依赖输入完整、团队纪律很强或运维手工兜底始终可靠；理想执行外的现实条件很容易打穿设计。
- 主责 reviewer：
  - `architecture_challenger`
- 允许重叠：
  - `architect_reviewer` 仅在该前提已直接破坏实现前提时允许重叠
- 禁止误判：
  - `architect_reviewer` 不应把 challenger 的主责问题系统性抢报
- fail 条件：
  - `architecture_challenger` 没有明确说明触发场景与爆炸半径

## F8 `accepted_tradeoff_optional_context`

- 场景：
  - 外层没有提供 accepted trade-off excerpt，但当前实现并未越过现有 `spec + plan` 边界。
- 主责 reviewer：
  - `reviewer`
- 允许重叠：
  - 无
- 禁止误判：
  - 不应仅因 excerpt 缺失就返回 `design_affecting`
  - 不应仅因 excerpt 缺失就令 `requires_doc_update = true`
- fail 条件：
  - 把“上游 excerpt 未提供”伪装成新的设计偏离

## F9 `source_and_issue_id_contract`

- 场景：
  - reviewer 输出需要跨轮续审，必须保持固定 `source` 命名和 `issue_id` 命名空间。
- 主责 reviewer：
  - `architect_reviewer`
  - `architecture_challenger`
  - `reviewer`
- 允许重叠：
  - 无；这是共享 contract 约束
- 禁止误判：
  - 不应把 `source` 改成 `architecture reviewer`、`code_reviewer` 或其它自由文本
  - 不应把 `issue_id` 写成未命名空间化的裸编号
- fail 条件：
  - 任一侧输出的 `source`、`reviewer_issue_id`、`issue_id` 语义发生漂移

## F10 `anchor_remap_continuity`

- 场景：
  - 同一问题跨轮审查时，文档或代码锚点发生迁移，需要通过 `anchor_remap`、`supersedes` 或 `merged_into` 维持 continuity。
- 主责 reviewer：
  - `reviewer`
- 允许重叠：
  - `architect_reviewer` 与 `architecture_challenger` 也应遵守同样的 identity/lineage 约束
- 禁止误判：
  - 不应通过换锚点或重编号把旧问题伪装成新问题
  - 不应静默漏掉 prior-open issues
- fail 条件：
  - 缺少 `anchor_remap` 对应关系
  - `same_as_previous = true` 但 `issue_id` 漂移
  - 缺少 `supersedes` / `merged_into` 仍强行改名续审

## Lightweight Lint Checks

下面这些检查可以作为 fixture 之外的轻量 lint 替代，用来快速发现 continuity/source 命名的回归：

```bash
rg -n "architect_reviewer|architecture_challenger|reviewer" \
  /Users/linus/.codex/agents \
  /Users/linus/.codex/skills/plan-review-implement-loop/references/workflow-contract.md \
  /Users/linus/Obsidian/Skills/plan-review-implement-loop-claude-code/references

rg -n "Prior open issue IDs|Anchor remap|same reviewer_issue_id|continuity|design_affecting" \
  /Users/linus/.codex/skills/plan-review-implement-loop/references/workflow-contract.md \
  /Users/linus/Obsidian/Skills/plan-review-implement-loop-claude-code/references/workflow-contract.md \
  /Users/linus/Obsidian/Skills/plan-review-implement-loop-claude-code/references/reviewer-role-prompts.md
```

lint 通过标准：

- 两侧 contract 都显式要求 prior-open issue coverage 和 anchor remap
- 角色卡与 contract 中的 `source` 命名保持一致
- code reviewer 明确写出“docs insufficient to judge safely -> design_affecting”
