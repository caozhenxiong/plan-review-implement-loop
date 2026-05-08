# workflow-contract

## Artifact Contract

主 agent 维护两份 canonical 文档：

- 设计文档：`docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`
- 实现计划：`docs/superpowers/plans/YYYY-MM-DD-<topic>.md`

每轮评审前冻结：

- `review_round`
- `spec_rev`
- `plan_rev`
- `code_rev`（仅代码审查需要）

统一约定：

- `spec_rev = sha256(normalize(canonical_spec_body))`
- `plan_rev = sha256(normalize(canonical_plan_body_without_ledger_or_execution_state))`
- `code_rev = git:<sha>` 或 `sha256(normalize(code_bundle))`

`plan_rev` 不再允许靠“自然语言理解后自行实现”的归一化逻辑计算。默认采用 `plan_rev_contract_id = plan-rev/v1`，并要求优先复用 shared canonical 实现：

- `$HOME/.claude/skills/plan-review-implement-loop-claude-code/shared/scripts/freeze_snapshot.py`

兼容入口 `$HOME/.claude/skills/plan-review-implement-loop-claude-code/references/compute_plan_rev.py` 只能调用 shared canonical 实现；不得复制或重新实现算法。只要 shared 脚本可用，主 agent 就必须使用它冻结快照或生成 `plan_rev`。

`normalize(...)` 在 `plan-rev/v1` 下的精确定义为：

1. 读取 canonical plan 原文，换行统一为 LF
2. 用显式分隔符删除整个 `Review Ledger` 块：
   - 从 `<!-- REVIEW-LEDGER:START -->` 到 `<!-- REVIEW-LEDGER:END -->`，含边界注释本身
3. 用显式分隔符删除整个 `Execution State` 块：
   - 从 `<!-- EXECUTION-STATE:START -->` 到 `<!-- EXECUTION-STATE:END -->`，含边界注释本身
4. 将保留正文中的 Markdown task list 勾选态统一规范化为未勾选形式：
   - `[x]` / `[X]` / `[ ]` 都归一为 `[ ]`
5. 去掉每行行尾空白
6. 将整个文档按行拆分后，删除文档尾部多余空白行，直到最后一行不是空白行为止
7. 删除文档头部多余空白行，直到第一行不是空白行为止
8. 保留正文中的其余空白行顺序与数量；不得额外折叠中间空白段
9. 用 LF 重新连接所有保留行，并在最终字符串末尾补一个且仅一个 LF

关键约束：

- block excision 后留下的中间空白洞不再额外折叠；这是 `plan-rev/v1` 的固定语义
- 文档头尾空白必须 trim；否则不同实现会因尾部空行数量不同而得出不同 `plan_rev`
- 只要 `plan_rev_contract_id` 不变，任何实现都必须产出与 reference script 相同的字节序列
- 如果后续需要改变归一化算法，必须升级 `plan_rev_contract_id`，不得静默修改 `v1` 语义

说明：

- `Review Ledger` 与 `Execution State` 不属于 `plan_rev`
- 纯 checkbox 变化不属于计划正文变化
- 只有计划正文的实质变化才会生成新的 `plan_rev`

## Plan Mode Contract

如果 Claude Code 当前运行时提供显式 `Plan Mode`，本 skill 采用“优先使用，但不强绑定”的规则：

- phase 1 应优先在 `Plan Mode` 中完成
- phase 2 本身不要求停留在 `Plan Mode`
- phase 2 通过后的实现确认点，应优先重新进入 `Plan Mode`
- 如果当前运行时没有显式 `Plan Mode`，则退化为当前线程内的等价确认点，门禁语义保持不变

额外约束：

- phase 1 即使在 `Plan Mode` 中完成，出口仍然只能是进入 phase 2，而不是直接开始实现
- 实现确认点即使在 `Plan Mode` 中完成，也只表示“允许开始实现”，不表示已经自动开始实现
- 用户确认只对同一组 `spec_rev + plan_rev` 生效；确认前正文变化则旧确认失效

## Reviewer Slot Reuse

Claude Code 版不强绑定某一种具体的子代理实现，但对 reviewer 槽位语义有统一要求：

- `architecture_reviewer`
- `architecture_challenger`
- `reviewer` 或 `code_reviewer`

约束：

- 如果当前运行时支持可复用的子代理槽、持续任务槽或等价能力，应优先复用同一角色槽继续评审
- 如果运行时不支持真实槽位，也必须在逻辑上保持固定角色槽语义；不要每轮更换角色身份、命名或 continuity 语义
- 只有在以下情况之一成立时，才允许切换到新的同角色实例：
  - 原实例不可用
  - 原实例上下文明显漂移
  - 需要显式隔离上下文以避免审查污染
- 即使切换实例，也不得丢失 continuity：冻结快照、ledger excerpt、`reviewer_issue_id` / `issue_id` 语义和 `anchor_remap` 必须延续
- “换实例重开”不能被用来规避旧 issue、重编号问题，或绕过 prior-open continuity

## Authoritative Review Inputs

评审只认主 agent 提供的权威快照：

- `spec` 与 `plan` 必须直接派生自 canonical 双文档正文
- `Review Ledger` / `Execution State` 只能作为单独摘录提供，不能混入 `plan` artifact
- 若评审结论依赖了主 agent 没明确提供的额外文本，本轮评审作废

## Review Ledger

计划文档必须包含：

```markdown
<!-- REVIEW-LEDGER:START -->
## Review Ledger
...
<!-- REVIEW-LEDGER:END -->
```

`Review Ledger` 分为两层：

1. 可选的轮次汇总视图
2. 强制的 issue 明细视图

轮次汇总视图只用于快速阅读；它不能替代 issue 明细。像下面这种只有 round / reviewer / verdict / high / medium 的表，单独存在时视为无效：

```markdown
| Round | spec_rev | plan_rev | Reviewer | Verdict | High | Medium |
|-------|----------|----------|----------|---------|------|--------|
| R1 | ... | ... | architecture_reviewer | PASS | 0 | 1 |
```

主 agent 必须把 reviewer 输出的每一个 issue 都写入明细视图；否则后续回环无法稳定追踪 `issue_id`、`artifact_anchor`、`status` 和 lineage。

至少记录：

- `review_round`
- `artifact_version`
- `source`
- `reviewer_issue_id`
- `issue_id`
- `severity`
- `kind`
- `summary`
- `artifact_anchor`
- `status`
- `first_seen_round`
- `last_seen_round`
- `same_as_previous`
- `supersedes` / `merged_into`
- `new_issue_reason`
- `disposition`: `open` / `fixed` / `superseded` / `accepted` / `escalated`

这个账本是完成声明和回环升级的依据。

约束：

- `Review Ledger` 用于状态追踪，不参与 `plan_rev`
- `Review Ledger` 更新本身不会让当前方案快照失效
- 只有实现计划正文变更，才会生成新的 `plan_rev`
- 如果 `Review Ledger` 分隔符缺失，或账本内容混入正文导致无法稳定排除，则 `plan_rev` 视为未定义，本轮自动流程直接阻塞
- `accepted` 只用于用户在实现确认点明确接受的 `low-risk` 问题；它不是 reviewer 输出状态，也不能用于 `medium/high`
- `accepted` 只对当时确认的同一组 `spec_rev + plan_rev` 有效；如果文档正文变化并重新进入方案双审，已接受的 `low-risk` 必须重新评估并重新展示
- 提供给 reviewer 的“open issue ledger excerpt”只包含 `status = open` 的问题；`accepted` 项只保留在账本中用于审计，不再当作待处理 open issue
- 每个 reviewer 返回的每个 issue，都必须在 `Review Ledger` 中落成一条独立明细记录；不允许只保留汇总计数
- 如果本轮结构化评审返回了 issue，但 `Review Ledger` 没有对应的 issue 级明细回写，则本轮回环视为未完成并阻塞
- 如果本轮代码审查返回了 CR issue，但 `Review Ledger` 没有对应的 code-review issue 明细回写，则 phase 4 视为未完成并阻塞
- 轮次汇总表可以保留，但它只是二级视图，不能作为门禁依据
- 门禁、回环、升级和 continuity 只认 issue 明细视图，不认汇总计数
- 如果读到历史 ledger 只有汇总表而没有 issue 明细，主 agent 的首要动作是补齐该 round 的 issue 明细；补齐前不得继续追加新 round，也不得把该 ledger 当作有效 prior-open excerpt 使用
- 当存在未关闭 issue 且 artifact 发生变化时，主 agent 必须在派发前准备 `anchor_remap`，说明所有 prior-open anchors 如何映射到当前快照；缺少 remap 时自动回环阻塞
- `anchor_remap` 必须对每个 prior-open anchor 恰好给出一种结果：
  - `mapped_to: <current_anchor>`
  - `superseded`
  - `merged_into: <current_issue_id>`
  - `retired`
- `anchor_remap` 不能遗漏任何 prior-open anchor，也不能对同一个 prior-open anchor 给出多个结果；否则阻塞
- `Review Ledger` 的默认回填映射固定为：
  - `status = open` -> `disposition = open`
  - `status = resolved` -> `disposition = fixed`
  - `status = superseded` -> `disposition = superseded`
  - `status = accepted` -> `disposition = accepted`
  - 只有自动回环停止并转人工时，主 agent 才可把未关闭问题写成 `disposition = escalated`

### Current Effective Issue State

主 agent 在根据历史账本判断当前 gate 之前，必须先把 issue 明细归约成“当前有效状态”：

- 对同一个 `issue_id`，按 `review_round` 递增、再按该 round 内的出现顺序取最后一条记录，作为该 `issue_id` 的当前有效状态
- 历史 `open` 行如果在同一 `issue_id` 下已经出现后续 `resolved` / `superseded` / `accepted` 记录，不再单独构成当前 blocker
- 提供给 reviewer 的 `open issue ledger excerpt` 必须基于归约后的当前有效 issue 集生成；不得直接摘抄所有历史 `open` 行
- 该 excerpt 只用于确保每个 prior-open issue 在新一轮里都被显式续审、关闭、归并或升级；它不是 reviewer 的审查范围定义
- `unresolved_high`、`unresolved_medium`、`actionable_issues`、`requires_doc_update` 都必须基于归约后的当前有效 issue 集计算，而不是按整张历史 issue 表逐行计数
- 如果同一个 `issue_id` 在同一轮出现多条互相冲突的记录，且账本中无法判断先后顺序或 lineage，则当前 gate 视为未定义并阻塞，先修账本再继续
- 如果 `Execution State` 中存在最新 `review_round_<n>_snapshot`、`gate_state` 或等价快照，它必须与归约后的当前有效 issue 集一致；不一致时，先同步文档状态，再继续任何下一阶段动作
- 文档顶部的阶段说明、历史 checklist、旧注释或说明性 prose 只用于阅读，不是门禁真值来源；它们若与归约后的当前 issue 状态或最新 `Execution State` snapshot 冲突，只能视为待同步文案，不能覆盖 gate 判定

推荐明细视图格式如下：

```markdown
### Issue Details

| review_round | source | reviewer_issue_id | issue_id | severity | kind | summary | artifact_anchor | status | disposition | first_seen_round | last_seen_round | same_as_previous | supersedes | merged_into | new_issue_reason |
|--------------|--------|-------------------|----------|----------|------|---------|-----------------|--------|-------------|------------------|-----------------|------------------|------------|-------------|------------------|
| R1 | architecture_challenger | AC-001 | architecture_challenger:AC-001 | high | architecture | `getGreaterThenBySymbol` 返回共享可变对象，调用方可能写坏缓存 | `plan:h2#b3` | open | open | R1 | R1 | false |  |  |  |
| R2 | reviewer | CR-001 | reviewer:CR-001 | medium | implementation_only | 缺少空集合测试，当前修复可能在空输入下回归 | `code:src/foo.ts#L42-L57` | open | open | R2 | R2 | false |  |  |  |
```

也允许用 YAML 列表或 Markdown 列表表示，只要字段完整且一条 issue 一条记录。

## Execution State

计划文档必须包含：

```markdown
<!-- EXECUTION-STATE:START -->
## Execution State
...
<!-- EXECUTION-STATE:END -->
```

建议记录：

- 当前进行中的步骤
- 任务清单及勾选状态
- 时间戳、负责人、attempt、run note
- 验证证据

约束：

- `Execution State` 不参与 `plan_rev`
- 只更新勾选、时间戳、负责人、attempt、run note，不会使方案快照失效
- 如果修改的是步骤文本、顺序、范围、接口、验收条件或交付路径，则必须修改计划正文并重算 `plan_rev`
- 若 `Execution State` 包含最新 gate snapshot，它是当前阶段状态的权威摘要；旧的标题、阶段描述或未回填 checklist 若与其冲突，不得据此回退 gate

### Stable Issue Identity

回环、升级和“同一问题连续两轮未关闭”的判断，只认稳定 issue 身份：

- `source` 取值固定为 `architect_reviewer`、`architecture_challenger`、`reviewer`
- `reviewer_issue_id` 是同一 reviewer 在跨轮次追踪同一问题时必须复用的本地稳定标识
- `issue_id` 是全局账本标识，默认格式 `<source>:<reviewer_issue_id>`
- 自动流程中不做跨 source 的语义去重；不同 reviewer 命中相似问题时，默认保留为两个独立 `issue_id`
- 同一问题跨轮次必须复用同一个 `source + reviewer_issue_id + issue_id`
- 问题被拆分时，新 issue 必须在 `supersedes` 中引用旧 `issue_id`
- 多个问题合并时，被合并的问题必须标记 `merged_into`
- `same_as_previous = true` 但 `issue_id` 变化，视为不一致并阻塞
- 主 agent 只有在 reviewer 明确给出 `merged_into` / `supersedes` 时才允许归并账本项；否则不得主观合并跨 reviewer 问题
- 无法稳定映射 issue 身份时，主 agent 必须要求 reviewer 补齐，或直接升级为人工决策；不能主观判定“差不多是同一个问题”

### Material Change

以下变化会使既有 review 结果失效，必须重新冻结快照并全量复审：

- `spec` 正文变化
- `plan` 正文变化
- 代码审查阶段的 `code_rev` 变化
- 改变步骤文本、顺序、范围、接口、验收条件或交付路径

以下变化不单独触发新的 `plan_rev`：

- 只更新 `Review Ledger`
- 只更新 `Execution State`
- 只改变 Markdown 任务勾选态 `[ ]` / `[x]`
- 只补充运行备注、时间戳、attempt 或验证证据

## Severity Policy

### High

会让当前方案走向明显错误方向的问题，例如：

- 严重安全、数据一致性、可靠性风险
- 核心架构死路
- 关键接口合同错误

### Medium

虽然不是致命，但足以阻止安全实现的问题，例如：

- 关键边界条件不清
- 重要集成点缺失
- 方案与计划明显不一致

### Low

不阻塞实现的问题，例如：

- 表述不清
- 可选优化
- 非主路径改进建议

门禁规则：

- 只要存在未解决的 `high` / `medium`，禁止进入实现
- `low` 不阻塞 phase 2 pass，但要保留在 issues 中
- 若最新通过方案仍有 open `low-risk`，实现确认点必须显式列出

## Structured Review Contract

### 架构评审

需要两份独立结果：

- `architecture_reviewer`
- `architecture_challenger`

必填字段：

- `artifact_version`
- `verdict`
- `unresolved_high`
- `unresolved_medium`
- `issues`

### 代码审查

必填字段：

- `artifact_version`
- `verdict`
- `actionable_issues`
- `requires_doc_update`
- `issues`

### Issue 必填字段

所有 issue 都必须带：

- `source`
- `reviewer_issue_id`
- `issue_id`
- `severity`
- `summary`
- `kind`
- `artifact_anchor`
- `status`: `open` / `resolved` / `superseded`
- `same_as_previous`
- `supersedes` 或 `merged_into`（如适用）
- `new_issue_reason`（新增 open issue 时）

Fail-closed 规则：

- 缺字段：阻塞
- `artifact_version` 不匹配：阻塞
- `verdict` 与计数字段不一致：阻塞
- 旧 issue 未被显式覆盖：阻塞

## Review Semantics

### 架构评审

- `verdict = pass` 当且仅当 `unresolved_high = 0` 且 `unresolved_medium = 0`
- `verdict = block` 当且仅当 `unresolved_high + unresolved_medium > 0`
- 允许 `pass` 时仍有 `low` open issue
- `unresolved_high` 必须等于归约后的当前有效 issue 集里 `status = open and severity = high` 的 issue 数量
- `unresolved_medium` 必须等于归约后的当前有效 issue 集里 `status = open and severity = medium` 的 issue 数量
- 架构评审 `issues[*].kind` 固定为 `architecture`

### 代码审查

- `actionable_issues = count(归约后的当前有效 issue 集里 open issues)`
- `requires_doc_update = any(归约后的当前有效 issue 集里 open issue.kind == design_affecting)`
- `verdict = pass` 当且仅当 `actionable_issues = 0`
- `verdict = block` 当且仅当 `actionable_issues > 0`
- `issues[*].kind` 只能是：
  - `implementation_only`
  - `design_affecting`
- 代码审查返回的每一个 open issue，都必须以 `source = reviewer` 的独立记录回写到 `Review Ledger` 的 issue 明细视图
- 若本轮 CR 已返回 issue，但 ledger 明细里缺少对应 `reviewer:<reviewer_issue_id>` 记录，则本轮 CR 结果不得用于 phase 4 的后续推进
- 代码审查必须把当前实现逐条对照 canonical `spec`、去账本后的 canonical `plan`，以及适用时已确认的 checklist 进行核对
- 代码是否严格遵守 `spec` / `plan` / checklist 是硬门禁，不是可选建议
- 任一实现偏离 `spec` / `plan` / checklist、保留应删除旧路径、绕过 fail-closed、或用兼容 fallback 替代新协议，都必须进入结构化 `issues`
- 测试通过、行为看起来可用或只在局部 diff 中未见明显 bug，都不能抵消设计或计划偏离

### 代码质量 Gate

- `reviewer` / `code_reviewer` 不只审 correctness，也要审具有工程后果的结构质量问题。
- 只有真正的 gate issue 才能进入结构化 `issues`、`actionable_issues` 和 `Review Ledger`。
- style-only 评论、命名审美分歧、注释风格偏好和不影响风险面的可选重构建议，只能留在 prose 中；不得写入结构化 `issues`、不得计入 `actionable_issues`，也不得回写 `Review Ledger`。
- 结构质量问题只有在满足至少一条时，才可成为阻塞 issue：
  - 会明显提升 bug 或回归概率
  - 会破坏既定设计边界或当前方案假设
  - 会显著增加未来修改风险、维护失控概率或审计/定位成本
  - 会隐藏失败路径，使验证、排障或审计不再可靠
- 典型可阻塞的结构质量风险包括：
  - 重复逻辑导致后续改动极易漏修
  - 边界泄漏或职责错位导致实现偏离既定设计
  - 共享可变状态带来一致性或并发风险
  - 过度隐蔽的控制流或危险 fallback
  - 难以安全验证的失败路径
- `reviewer` / `code_reviewer` 不得仅因为“另一种架构更优”就重开已接受的纯方案 trade-off。
- 如果外层 workflow 已提供 accepted trade-off excerpt，reviewer 只能把它当作可选只读上下文。推荐最小字段：
  - `issue_id`
  - `summary`
  - `accepted_rationale`
  - `accepted_boundary`
- 本次 contract 只约束 reviewer 如何消费外层已提供的 accepted excerpt；不重构 excerpt 的 provenance、版本模型、存储位置或 companion artifact。
- 如果外层没有提供 accepted excerpt，不能仅因 excerpt 缺失就把问题升级成 `design_affecting` 或令 `requires_doc_update = true`。
- 只有当实现本身越过当前 `spec + plan` 边界、越过 `accepted_boundary`、把已接受风险放大成新的工程风险、引入与接受理由不相容的新约束，或现有文档本身已不足以支撑安全判断时，才进入既有 `design_affecting` / `requires_doc_update` 路径。

## Karpathy Behavioral Contract

本 contract 分层吸收 `andrej-karpathy-skills` 的行为守则。它不新增 phase，也不改变既有 gate，只把原则转成可派发、可复核的审查要求。

- `Think Before Coding`：关键假设、歧义、未显式 tradeoff 和 silent assumption 必须在 phase 1/2 暴露；不得靠静默假设让方案过审。
- `Simplicity First`：无计划依据的 speculative abstraction、unrequested configurability、single-use abstraction、一次性框架化都属于可审 architecture risk。
- `Surgical Changes`：实现、文档和 prompt 改动必须能追溯到用户请求、`spec`、`plan` 或 checklist；unrelated cleanup 不得混入当前 gate。
- `Goal-Driven Execution`：评审和完成判断必须绑定明确 success criteria、checklist、review gate 或验证证据；apparent functionality 不足以放行。

## Gate State Contract

跨轮 handoff 或等待用户时，必须输出：

```yaml
current_phase: phase1|phase2|phase3|phase4|phase5
gate_state: blocked|phase2_rereview_pending|phase2_blocked|phase2_passed_unconfirmed|phase3_allowed|phase4_required|phase4_blocked_implementation_only|phase4_blocked_design_affecting|phase5_completed
spec_rev: sha256:<hash>|pending
plan_rev: sha256:<hash>|pending
next_allowed_action: write_canonical_docs|enter_phase2_review|update_canonical_docs_and_rerun_phase2|rerun_full_phase2_dual_review|enter_implementation_confirmation|begin_implementation|write_code_rev_and_rerun_gate_check|enter_code_review|fix_code_and_rerun_code_review|complete
do_not_start_coding_yet: true|false
```

强约束：

- phase 1 完成后，`next_allowed_action` 必须是 `enter_phase2_review`
- phase 2 blocked 时，必须是 `update_canonical_docs_and_rerun_phase2`
- phase 2 passed 但未确认时，必须是 `enter_implementation_confirmation`
- 只有 phase 3 allowed 时，才可 `begin_implementation`
- phase 3 中任一实现改动完成后，必须先写入 `latest_code_rev` 并将 `implementation_changed = true`
- 如果 `implementation_changed = true` 但 `latest_code_rev` 缺失，下一步必须是 `write_code_rev_and_rerun_gate_check`，不得进入 phase 4
- 如果 `latest_code_rev` 非空但缺少匹配的最新代码审查结果，下一步必须是 `enter_code_review`
- 没有最新 phase 4 代码审查结果时，禁止 `complete`
- phase 4 代码审查完成后，必须写入 `latest_code_review_spec_rev`、`latest_code_review_plan_rev`、`latest_code_review_code_rev`
- 只有最新 phase 4 代码审查 `actionable_issues = 0`、且 `latest_code_review_spec_rev + latest_code_review_plan_rev + latest_code_review_code_rev` 与当前 `spec_rev + plan_rev + latest_code_rev` 匹配时，才可进入 phase 5
- 不允许用缺失字段表达“无实现改动”；无改动必须显式保持 `latest_code_rev = null` 与 `implementation_changed = false`

如果运行时支持 `Plan Mode`：

- `enter_phase2_review` 之前的 phase 1 文档生成应优先在 `Plan Mode` 内完成
- `enter_implementation_confirmation` 应优先解释为“重新进入 Plan Mode 并请求确认”

## Loop Decision Table

| 当前状态 | 下一步 |
| --- | --- |
| 尚无 canonical `spec + plan` | 留在 phase 1，继续写文档 |
| phase 1 完成 | 进入 phase 2 |
| 本轮评审已有 issue，但 `Review Ledger` 只写了汇总表，没有 issue 明细 | 阻塞，先补齐 issue 级回写 |
| 读到历史 `Review Ledger` 只有汇总表，没有 issue 明细 | 先把历史 round 重写成 issue 级账本，再继续任何新一轮评审或实现 |
| 本轮代码审查已有 CR issue，但 `Issue Details` 里没有对应 `source = reviewer` 的记录 | 阻塞，先补齐 CR issue 明细 |
| 同一 `issue_id` 同时保留历史 `open` 与后续 `resolved` / `superseded` / `accepted` 记录 | 以该 `issue_id` 的最后一条记录为准；不要因为历史 `open` 行重新阻塞 |
| `Execution State` 的最新 snapshot 已经 `pass`，但顶部阶段文案、说明 prose 或旧 checklist 还停留在 earlier round | 先同步文档状态；同步前沿用最新 snapshot 对应的 gate，不因旧文案回退 |
| 仅 `Review Ledger` / `Execution State` / 纯勾选态变化 | 不重跑 phase 2 |
| phase 2 仍有 unresolved `medium/high` 且本轮有实质性方案变化 | 更新 canonical 文档并重跑 phase 2 |
| phase 2 通过但未确认实现 | 进入实现确认点；若支持 `Plan Mode`，则在 `Plan Mode` 中确认 |
| phase 2 通过且用户已确认实现 | 进入 phase 3 |
| phase 3 已产生实现改动但 `latest_code_rev` 缺失 | 阻塞为 `write_code_rev_and_rerun_gate_check`，先补写代码快照 |
| phase 3 已产生实现改动且尚无本轮代码审查 | 冻结 `code_rev`，写入 `latest_code_rev` 与 `implementation_changed = true`，进入 phase 4；不得输出完成声明 |
| phase 3 已完成测试或验证但尚无本轮代码审查 | 仍进入 phase 4；测试/验证不能替代代码审查 |
| `latest_code_review_*_rev` 与当前 `spec_rev + plan_rev + latest_code_rev` 不匹配 | 进入 `phase4_required`，重跑代码审查 |
| 代码审查 `actionable_issues > 0` 且 `requires_doc_update = false` | 修代码并重跑 phase 4 |
| 代码审查 `actionable_issues > 0` 且 `requires_doc_update = true` | 更新文档并回到 phase 2 |
| 代码审查 `actionable_issues = 0` | 进入 phase 5 |

## Escalation

以下情况升级为人工决策：

- 同一 `issue_id` 连续两轮未关闭，且最近两轮没有实质性 `spec + plan` 变化
- 两份架构评审在同一组 `spec_rev + plan_rev` 上连续冲突，且无法通过方案修订消解
- 剩余阻塞本质上属于业务取舍或关键输入缺失

## Minimal Dispatch Templates

以下模板是 Claude Code 版的唯一正式派发载体。每次派发 reviewer 前，必须先加载：

- [Shared Reviewer Norms](./reviewer-role-prompts.md#shared-reviewer-norms)
- 对应角色卡：
  - [Architecture Reviewer](./reviewer-role-prompts.md#architecture-reviewer)
  - [Architecture Challenger](./reviewer-role-prompts.md#architecture-challenger)
  - [Code Reviewer](./reviewer-role-prompts.md#code-reviewer)

不得跳过 role card，也不得只凭临时自然语言转述来替代它。

### Architecture Reviewer

优先复用当前运行时内既有的 `architecture_reviewer` 槽或等价持续任务实例；仅在 `Reviewer Slot Reuse` 允许的例外条件下才切换。

```text
Load and apply the Shared Reviewer Norms plus the Architecture Reviewer role card from ./reviewer-role-prompts.md before reviewing.

Review the current design and implementation plan for architecture issues.

Artifacts:
- Spec snapshot under review: <spec matching spec_rev>
- Plan snapshot under review: <plan matching plan_rev and excluding Review Ledger and Execution State>
- Open issue ledger excerpt: <open-issues-for-architecture_reviewer>
- Prior open issue IDs that must be accounted for: <list>
- Anchor remap for prior open issues: <all prior-open anchors -> mapped_to|superseded|merged_into|retired>
- Artifact version:
  review_round: <int>
  spec_rev: sha256:<hash>
  plan_rev: sha256:<hash>

Requirements:
- Start with exactly one `review-result-json` fenced JSON block containing `artifact_version`, `source`, `verdict`, `unresolved_high`, `unresolved_medium`, and `issues`.
- The block must be strict JSON, not YAML or JSON5. Prose may follow the block, but prose is not a gate fact source.
- Reuse the same reviewer_issue_id for the same unresolved issue across rounds.
- Account for every issue_id in the provided prior-open list exactly once.
- Perform a full rereview of the entire current spec and plan snapshots; do not narrow the review to only the prior-open issues.
- Identify silent assumptions, unstated trade-offs, and missing success criteria that affect implementation readiness.
- Flag speculative abstractions, unrequested configurability, or single-use abstraction layers that are not justified by the spec or plan.
- If a small direct solution is wrapped in substantially larger architecture without plan justification, report the complexity as an architecture issue.
- Focus on implementation readiness, interface/contracts, state consistency, failure recovery, observability, and long-term evolution.
- Respect the role-card ownership boundary; do not spend most of the review on pure failure-mode hunting.
- Use prose only after the structured block.
- Treat prior-open issue inputs as continuity aids only; they do not reduce review scope.
```

### Architecture Challenger

优先复用当前运行时内既有的 `architecture_challenger` 槽或等价持续任务实例；仅在 `Reviewer Slot Reuse` 允许的例外条件下才切换。

```text
Load and apply the Shared Reviewer Norms plus the Architecture Challenger role card from ./reviewer-role-prompts.md before reviewing.

Challenge the current design and implementation plan.

Artifacts:
- Spec snapshot under review: <spec matching spec_rev>
- Plan snapshot under review: <plan matching plan_rev and excluding Review Ledger and Execution State>
- Open issue ledger excerpt: <open-issues-for-architecture_challenger>
- Prior open issue IDs that must be accounted for: <list>
- Anchor remap for prior open issues: <all prior-open anchors -> mapped_to|superseded|merged_into|retired>
- Artifact version:
  review_round: <int>
  spec_rev: sha256:<hash>
  plan_rev: sha256:<hash>

Focus on:
- hidden complexity
- rollback gaps
- unsafe assumptions
- failure modes

Requirements:
- Return the same structured `review-result-json` contract as architecture reviewer.
- Reuse the same reviewer_issue_id for the same unresolved issue across rounds.
- Account for every issue_id in the provided prior-open list exactly once.
- Perform a full rereview of the entire current spec and plan snapshots; do not narrow the review to only the prior-open issues.
- Identify hidden assumptions, speculative complexity, unrequested configurability, and abstractions that are larger than the problem requires.
- Treat unjustified complexity growth as a real-world failure-mode risk when it increases implementation, maintenance, rollout, or debugging cost.
- If a small direct solution is wrapped in substantially larger architecture without plan justification, report the complexity as an architecture issue.
- Respect the role-card ownership boundary; do not repeat ordinary architecture-readiness issues unless they also have a real-world failure-mode dimension.
- Use prose only after the structured block.
- Treat prior-open issue inputs as continuity aids only; they do not reduce review scope.
```

### Code Reviewer

优先复用当前运行时内既有的 `reviewer` / `code_reviewer` 槽或等价持续任务实例；仅在 `Reviewer Slot Reuse` 允许的例外条件下才切换。

```text
Load and apply the Shared Reviewer Norms plus the Code Reviewer role card from ./reviewer-role-prompts.md before reviewing.

Review the latest implementation for actionable issues.

Artifacts:
- Spec snapshot under review: <spec matching spec_rev>
- Plan snapshot under review: <plan matching plan_rev and excluding Review Ledger and Execution State>
- Code snapshot under review: <code matching code_rev>
- Accepted trade-off excerpt (optional, read-only if provided): <excerpt|none>
- Open issue ledger excerpt: <open-issues-for-reviewer>
- Prior open issue IDs that must be accounted for: <list>
- Anchor remap for prior open issues: <all prior-open anchors -> mapped_to|superseded|merged_into|retired>
- Artifact version:
  review_round: <int>
  spec_rev: sha256:<hash>
  plan_rev: sha256:<hash>
  code_rev: git:<sha>|sha256:<hash>

Requirements:
- Start with exactly one `review-result-json` fenced JSON block containing `artifact_version`, `source`, `verdict`, `actionable_issues`, `requires_doc_update`, and `issues`.
- The block must be strict JSON, not YAML or JSON5. Prose may follow the block, but prose is not a gate fact source.
- Reuse the same reviewer_issue_id for the same unresolved issue across rounds.
- Account for every issue_id in the provided prior-open list exactly once.
- Perform a full rereview of the entire current code snapshot against the full current spec snapshot and plan snapshot; do not narrow the review to only the prior-open issues.
- Compare the implementation item-by-item against the full current spec snapshot, the full current plan snapshot, and the enforced checklist when provided.
- Treat strict compliance with the spec, plan, and checklist as a hard gate, not an optional suggestion.
- Every changed line should trace to the request, spec, plan, or checklist; unrelated cleanup or opportunistic refactoring belongs in prose or a separate follow-up, not the current gate.
- Treat unrelated edits, unrequested abstractions, unrequested configurability, and adjacent cleanup as reviewable scope violations when they affect risk or maintainability.
- Judge completion against explicit success criteria and checklist evidence, not apparent functionality alone.
- If code keeps an old main path, compatibility fallback, legacy protocol, old tool semantics, or old workflow branch that the design/plan/checklist requires removing, report it as a structured blocking issue.
- Any deviation from spec/plan/checklist must appear in structured issues, not prose only.
- Restrict structured issues to actionable gate issues; keep style-only comments and optional suggestions in prose.
- Review correctness, edge cases, regression risk, missing tests, design deviation, and structure-quality risks with engineering consequences.
- If an accepted trade-off excerpt is provided, treat it as optional read-only context; do not reopen an accepted pure trade-off unless the implementation exceeds the accepted boundary or introduces a new engineering risk.
- If the current implementation cannot be judged safely because the current docs are insufficient, escalate it as `design_affecting` instead of silently downgrading it to `implementation_only`.
- Use prose only after the structured block.
- Treat prior-open issue inputs as continuity aids only; they do not reduce review scope.
```

## Completion Contract

宣称完成前，必须确认：

1. 最新 `spec + plan` 已同步到最终实现
2. 最新通过的方案双审与最新通过的代码审查共享同一组 `spec_rev + plan_rev`
3. 最新方案双审无 unresolved `high` / `medium`
4. 最新代码审查 `actionable_issues = 0`
5. `Review Ledger` 已记录最终状态
6. 已执行真实验证
