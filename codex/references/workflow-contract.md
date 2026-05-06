# workflow-contract

## Artifact Contract

这是一个本地个人 skill，默认运行在当前 Codex 环境，并固定依赖以下本地 agent：

- `/Users/linus/.codex/agents/architect_reviewer.toml`
- `/Users/linus/.codex/agents/architecture_challenger.toml`
- `/Users/linus/.codex/agents/reviewer.toml`

## Agent Slot Reuse

在 Codex 运行时，评审角色不只是“角色名”，还对应当前会话里的 agent 槽位。默认策略是优先复用：

- `architect_reviewer`
- `architecture_challenger`
- `reviewer`

约束：

- 同一会话内，同一角色已有可用 agent 槽时，主 agent 应优先复用该槽继续评审
- 复用优先于重复创建新的同角色 agent
- 只有在以下情况之一成立时，才允许新开同角色 agent：
  - 原槽不可用或已关闭
  - 原槽上下文明显漂移，无法安全继续
  - 需要显式隔离上下文以避免审查污染
- 即使新开槽，也不得丢失 continuity：必须继续沿用同一组冻结快照、ledger excerpt、`reviewer_issue_id` / `issue_id` 语义和 `anchor_remap`
- “换槽重开”不能被用来规避旧 issue、重编号问题，或绕过 prior-open continuity

主 agent 在整个闭环中维护两份文档；凡是需要同步文档的场景，默认总是同时更新：

- 设计文档：`docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`
- 实现计划：`docs/superpowers/plans/YYYY-MM-DD-<topic>.md`

要求：

- 这两个 canonical 文档路径必须位于当前项目工作区的 `docs/` 树下；如果前期工作使用了 Plan Mode 草稿、内联快照或临时文件，主 agent 必须先把当前被审正文补齐并写入上述路径，才能进入任何正式 phase 2 双审
- 方案双审只审同一组冻结的文档版本
- 代码审查若要求文档更新，先同步更新这两份文档，再回到方案双审
- 最终完成前，两份文档必须与最终实现一致
- 未解决的 `high` / `medium` 默认只阻塞实现，不阻塞继续修订 `spec + plan`
- 方案双审通过后，还必须先经过“实现确认”检查点；进入该检查点前，当前通过版双文档必须已经存在于 canonical 路径
- 每次代码修改完成后，都必须先同步更新这两份文档，再继续实现、进入代码审查或宣称完成
- 如需在计划文档中记录执行进度，必须使用单独的 `Execution State` 分隔块；执行勾选、时间戳和运行备注不属于 `plan_rev`

每一轮评审前，主 agent 都要冻结本轮 artifact 快照：

- `review_round`
- `spec_rev`
- `plan_rev`
- `code_rev`（仅代码审查需要；优先使用能唯一标识当前代码内容的 git 标识，否则使用代码内容哈希）

统一约定：

- `artifact_version` 不再是自由命名字符串，而是由结构化快照字段组成
- `spec_rev` 必须由 canonical 设计文档正文内容生成，推荐格式 `sha256:<hash>`
- `plan_rev` 必须由 canonical 实现计划正文内容生成，默认排除 `Review Ledger` / `Execution State` 区块，并忽略纯 Markdown 任务勾选态 `[ ]` / `[x]` 的差异，推荐格式 `sha256:<hash>`
- `code_rev` 必须是 `git:<sha>` 或 `sha256:<hash>`；不允许使用人工命名标签
- `review_round` 是主 agent 为单次冻结派发分配的单调递增整数。只要派发时任一冻结字段变化，就必须开新一轮 `review_round`
- 任一审查结果缺少这些字段，或返回值与当前冻结快照不一致，一律视为阻塞
- 不允许把旧一轮 review 结果复用到新文档或新代码
- 方案双审只对同一组 `spec_rev + plan_rev` 有效
- 代码审查只对同一组 `spec_rev + plan_rev + code_rev` 有效
- 最终完成时，要求最新通过的方案双审与最新通过的代码审查共享同一组 `spec_rev + plan_rev`；并不要求架构 reviewer 绑定 `code_rev`

### Snapshot Normalization

为了避免“看起来版本一致，实际上不是同一内容”的假阳性，冻结快照采用内容寻址：

- `spec_rev = sha256(normalize(canonical_spec_body))`
- `plan_rev = sha256(normalize(canonical_plan_body_without_ledger_or_execution_state))`
- `code_rev = git:<sha>` 或 `sha256(normalize(code_bundle))`

`plan_rev` 不再允许靠“自然语言理解后自行实现”的归一化逻辑计算。默认采用 `plan_rev_contract_id = plan-rev/v1`，并要求优先复用唯一参考实现：

- `/Users/linus/.codex/skills/plan-review-implement-loop/references/compute_plan_rev.py`

只要该脚本可用，主 agent 就必须使用它生成 `plan_rev`；不得自行实现一个“看起来等价”的版本。

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

其中：

- `canonical_spec_body` 指 `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` 的正文
- `canonical_plan_body_without_ledger_or_execution_state` 指 `docs/superpowers/plans/YYYY-MM-DD-<topic>.md` 去掉 `Review Ledger` / `Execution State` 区块后的正文

`code_bundle` 必须是一个可复核的确定性集合：

1. 明确列出被审文件路径
2. 按路径排序
3. 对每个文件拼接 `path + normalized_content`
4. 如果被审文件范围说不清，本轮代码审查直接阻塞

如果主 agent 不能明确说明如何得到这些值，或无法说明当前 `plan_rev` 使用的 `plan_rev_contract_id`，本轮评审不得开始。

### Authoritative Review Inputs

为了避免本地 agent 读取到额外上下文后让 artifact 身份漂移，门禁只认主 agent 派发时提供的权威快照；这些快照必须直接派生自当前 canonical 双文档正文：

- `spec` 与 `plan` 仍可以内联快照、附件快照，或其它可复核的剥离后内容形式提供
- 但这些形式只能是 canonical 双文档正文的派生表示，不能是独立于文件之外的另一份草稿
- `Review Ledger` 与 `Execution State` 只能作为单独的账本或进度摘录提供，不能混入 `plan` artifact
- 原始文件路径由主 agent 自己记录用于审计和回溯，不发给 reviewer，也不作为 artifact 身份的判定依据
- 如果 canonical 文件不存在、或派发时提供的权威快照与 canonical 文件正文不一致，本轮 phase 2 直接阻塞
- 每个 issue 都必须提供 `artifact_anchor`
- `status = open` 的 issue 必须锚定到当前权威快照中的具体片段，不能只锚到 `prior:<issue_id>`
- `prior:<issue_id>` 只用于说明 lineage、关闭原因或账本延续，不足以单独支撑新的 open issue
- `artifact_anchor` 必须定位到唯一片段，而不是只定位到大段容器。推荐格式：
  - `spec:hNN(.hNN...)#pNN`
  - `plan:hNN(.hNN...)#bNN`
  - `code:<path>#L<start>-L<end>`
- 其中 `hNN(.hNN...)` 是从权威快照按标题层级与出现顺序生成的规范化 heading id，`pNN` / `bNN` 是标题下按出现顺序生成的规范化片段 id；不能使用自由文本标题名或自由文本片段名
- 如果 reviewer 的结论依赖了未被主 agent 明确提供的额外文本，或给不出可复核的 `artifact_anchor`，本轮审查结果视为不可复核并阻塞
- prior-open issue ledger excerpt、accepted trade-off excerpt 和 `anchor_remap` 都只是 continuity / lineage / 审计辅助输入；它们不能缩小 reviewer 的审查范围
- 只要当前冻结快照发生变化，reviewer 就必须对当前完整 artifact snapshot 重新做全量审查；不得退化成“只复查上一轮 issue”
- 如果 reviewer 明确或隐含地把本轮审查范围收缩为仅检查 prior-open issue，本轮结果视为不完整并阻塞

## Review Ledger

双文档保持不变，不新增第三份文档。

在 `plan` 文档中维护固定的 `Review Ledger` 区块，必须使用显式分隔符：

```markdown
<!-- REVIEW-LEDGER:START -->
## Review Ledger
...
<!-- REVIEW-LEDGER:END -->
```

`Review Ledger` 分为两层：

1. 可选的轮次汇总视图
2. 强制的 issue 明细视图

轮次汇总视图只用于快速阅读；它不能替代 issue 明细。像下面这种只有 `review_round` / reviewer / verdict / unresolved `high` / `medium` 的表，单独存在时视为无效：

```markdown
| Round | spec_rev | plan_rev | Reviewer | Verdict | High | Medium |
|-------|----------|----------|----------|---------|------|--------|
| R1 | ... | ... | architect_reviewer | PASS | 0 | 1 |
```

主 agent 必须把 reviewer 输出的每一个 issue 都写入 issue 明细视图；否则后续回环无法稳定追踪 `issue_id`、`artifact_anchor`、`status` 和 lineage。

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

关键约束：

- `Review Ledger` 用于状态追踪，不参与 `plan_rev` 计算
- `Review Ledger` 更新本身不会让当前方案快照失效
- 只有实现计划正文变更，才会生成新的 `plan_rev`
- 如果 `Review Ledger` 分隔符缺失，或账本内容混入正文导致无法稳定排除，则 `plan_rev` 视为未定义，本轮自动流程直接阻塞
- `accepted` 只用于用户在实现确认点明确接受的 `low-risk` 问题；它不是 reviewer 输出状态，也不能用于 `medium/high`
- `accepted` 只对当时确认的同一组 `spec_rev + plan_rev` 有效；如果文档正文变化并重新进入方案双审，已接受的 `low-risk` 必须重新评估并重新展示
- 提供给 reviewer 的“open issue ledger excerpt”只包含 `status = open` 的问题；`accepted` 项只保留在账本中用于审计，不再当作待处理 open issue
- 每个 reviewer 返回的每个 issue，都必须在 `Review Ledger` 中落成一条独立明细记录；不允许只保留汇总计数
- 如果本轮结构化评审返回了 issue，但 `Review Ledger` 没有对应的 issue 级明细回写，则本轮回环视为未完成并阻塞
- 如果本轮代码审查返回了 CR issue，但 `Review Ledger` 没有对应的 code-review issue 明细回写，则阶段 4 视为未完成并阻塞
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

推荐 issue 明细视图格式如下：

```markdown
### Issue Details

| review_round | source | reviewer_issue_id | issue_id | severity | kind | summary | artifact_anchor | status | disposition | first_seen_round | last_seen_round | same_as_previous | supersedes | merged_into | new_issue_reason |
|--------------|--------|-------------------|----------|----------|------|---------|-----------------|--------|-------------|------------------|-----------------|------------------|------------|-------------|------------------|
| R1 | architecture_challenger | AC-001 | architecture_challenger:AC-001 | high | architecture | `getGreaterThenBySymbol` 返回共享可变对象，调用方可能写坏缓存 | `plan:h2#b3` | open | open | R1 | R1 | false |  |  |  |
| R2 | reviewer | CR-001 | reviewer:CR-001 | medium | implementation_only | 缺少空集合测试，当前修复可能在空输入下回归 | `code:src/foo.ts#L42-L57` | open | open | R2 | R2 | false |  |  |  |
```

也允许用 YAML 列表或 Markdown 列表表示，只要字段完整且一条 issue 一条记录。

## Execution State

如需在 `plan` 文档中记录执行进度，必须使用固定的 `Execution State` 区块，使用显式分隔符：

```markdown
<!-- EXECUTION-STATE:START -->
## Execution State
...
<!-- EXECUTION-STATE:END -->
```

建议记录：

- 当前进行中的步骤
- 分步任务清单与勾选状态
- 时间戳、负责人、attempt、run note
- 相关验证或证据链接

关键约束：

- `Execution State` 只用于跟踪执行进度，不是权威实现计划正文
- `Execution State` 不参与 `plan_rev` 计算
- 只更新 `Execution State` 的勾选、时间戳、负责人、attempt 或运行备注，不会使当前方案快照失效
- 如果需要改变步骤本身、顺序、范围、接口、验收条件或交付路径，必须修改计划正文并重新计算 `plan_rev`
- 如果主 agent 想记录执行进度却把这些内容混入正文，导致无法稳定从 `plan_rev` 中排除，则应先把进度迁回 `Execution State` 区块，再继续流程
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

自动回环是否继续，不只看还有没有问题，还看最近一轮方案是否真的在收敛。

以下情况视为对 `spec + plan` 的实质变化：

- 新增、删除或改写了需求边界、接口合同、验收标准
- 改变了关键状态流、幂等/并发策略、失败恢复路径、权限边界或 rollout 路径
- 针对未关闭的 `high` / `medium` 问题给出了新的约束、字段、决策表、门禁规则或 artifact 合同

以下情况不视为实质变化：

- 只改措辞、排版、标题、示例顺序
- 只更新 `Review Ledger`
- 只更新 `Execution State`
- 只改 Markdown task list 的勾选态 `[ ]` / `[x]`，而不改步骤文本、顺序或范围
- 只重复前一轮 reviewer 的问题而没有新的方案收敛动作

## Phase Entry Contract

每个大阶段切换时，主 agent 先执行一次 phase preflight checklist，再进入该阶段：

1. 规划与文档生成
2. 方案双审
3. 实现
4. 代码审查
5. 文档回填与最终同步

适用边界：

- 这个要求只作用于主 agent
- 子代理保留各自角色约束，不要求它们调用 `using-superpowers`
- 如果运行时支持显式 Plan Mode，在阶段 1 先进入它
- 如果运行时不支持显式 Plan Mode，执行本 skill 定义的规划子流程：`brainstorming` 只负责探索，`writing-plans` 只负责计划写作约束，两个 skill 都不接管阶段出口
- phase preflight 是派生自 `using-superpowers` 的检查单，不是重新调用 skill 选择器
- 阶段 1 的规划子流程唯一出口是阶段 2；它不能绕过本 skill 直接掉进实现流程
- 阶段 1 写完 canonical `spec + plan` 后，主 agent 必须在同一轮直接继续 phase 2；不得把阶段 1 结果包装成可点击“实施此计划”的最终输出
- 阶段 1 如遇关键确认项，必须留在阶段 1 完成确认；确认前不能进入阶段 2

phase preflight 的硬约束：

- 它只负责阶段检查与技能纪律确认
- 它不是对顶层 workflow 的重新路由
- 它不能再次激活 `plan-review-implement-loop` 自身
- 它等价于“按 `using-superpowers` 的纪律做阶段检查”，而不是重新触发 `using-superpowers` 的顶层技能选择逻辑
- 阶段 3 preflight 如发现任务涉及既有实现、协议、架构边界或关键工作流重构，必须确认 `Plan Compliance Checklist` 已经由用户明确确认；否则不得进入实现
- 如果实现需要修改的文件/模块不在已确认 checklist 中，phase preflight 必须阻塞并要求先更新 checklist

## Plan Compliance And Closure Contract

当任务涉及既有实现、协议、架构边界、关键工作流或 closure/refactor 类变更时，主 agent 在阶段 3 写代码前必须先完成并获得用户确认 `Plan Compliance Checklist`。

`Plan Compliance Checklist` 不是摘要，也不是实现计划的复述；它是防止实现偏离设计的执行锁。最低字段：

- `design_requirement`：引用设计文档里的原始约束或可定位摘录
- `current_implementation`：当前实现位置，必须列出文件/模块/入口
- `deviation`：当前实现与设计的偏差；如果没有偏差，写明 why unchanged
- `delete_or_disable`：必须删除、迁移、禁用或 fail-closed 的旧路径、旧接口、旧测试、旧 fallback
- `new_behavior`：本阶段要新增或保留的目标行为
- `write_scope`：本阶段允许修改的文件或模块
- `verification`：证明该约束满足的测试、命令、浏览器验收或静态检查
- `status`：`pending` / `in_progress` / `done` / `blocked`

硬约束：

- 用户确认 checklist 前，不得修改代码
- 实现只能触碰 checklist 中的 `write_scope`
- 若需要扩大写入范围，必须先更新 checklist 并再次取得用户确认
- 若发现计划不合理、设计边界冲突、需要兼容旧路径、需要 fallback、或某条约束无法按原样落地，主 agent 必须立即停止并询问用户
- 不得自行降级需求、替换方案、绕过设计、或以“先跑通”为由保留冲突旧路径
- closure / 协议切换 / 行为收口类任务中，旧主路径和新主路径不得双轨并存；冲突旧路径必须删除、迁移或 fail-closed
- 新增新工具、新接口或新字段，不等于替换旧协议；只有旧协议被删除、迁移或 fail-closed，且验收证明旧路径不可用，才算完成
- 每完成一个实现小阶段，必须回填 checklist 状态，并给出 diff 摘要与验证结果
- 测试通过不是充分证明；必须同时证明 checklist 中的设计约束、删除项和禁用项已满足

如果本 contract 与普通兼容性策略冲突，以本 contract 为准。不得为了兼容旧测试、旧 UI、旧调用方或旧 run 数据而保留与当前设计冲突的主路径。

phase preflight 必须按阶段执行，不允许使用一份通用清单硬套所有阶段：

1. 阶段 1：确认当前 skill 仍持有控制权，且接下来要生成 `spec + plan`，并识别是否存在必须先由用户确认的关键问题
2. 阶段 2：确认 canonical `spec + plan` 已存在、当前被审正文已经同步到这两个文件、当前无待升级的人工作业、两个架构 reviewer 可用、并已准备好去掉 `Review Ledger` / `Execution State` 的权威文档快照；`spec_rev + plan_rev` 在 preflight 之后立刻从 canonical 文件正文冻结
3. 阶段 3：确认最新通过的方案双审仍匹配当前 `spec_rev + plan_rev`
   - 并确认用户已经针对同一组 `spec_rev + plan_rev` 明确批准开始实现
   - 并确认当前 canonical `spec + plan` 仍与最新通过的 `spec_rev + plan_rev` 匹配
4. 阶段 4：确认当前代码变更已准备好审查、最新通过的方案双审仍匹配当前 `spec_rev + plan_rev`、`@reviewer` 可用、并已准备好权威代码快照、未关闭代码问题摘录和必要的 `anchor_remap`；`code_rev` 在 preflight 之后立刻冻结
   - 并确认当前 `code_rev` 对应的两份文档都已同步到最新代码状态
5. 阶段 5：确认最新通过的方案双审与代码审查已闭环，并准备执行最终验证

### Stage 1 Confirmation Contract

阶段 1 对“是否必须确认”采用保守策略：

- 能安全推断且不会改变范围、接口、验收标准或门禁判断的小歧义，可以记录假设后继续
- 会影响范围、接口、验收标准、架构边界、评审门禁或回环路径的关键问题，必须请求用户确认
- 关键确认项未解决时，阶段 1 保持阻塞
- 收到确认后，主 agent 先更新 `spec + plan`，再进入阶段 2
- 如果运行在显式 Plan Mode 中，确认应在 Plan Mode 内完成；确认完成前，不得跳出到实现或方案双审

### UI Action Interpretation

本 skill 不允许把通用 UI 文案直接等同于“进入实现”。

- “实施计划”“实施此计划”“开始执行”这类动作，只能解释为“继续按当前 skill 的下一道门禁推进”
- 这类 UI 动作不能覆盖阶段门禁、phase preflight、双审结果或代码审查结果
- 阶段 1 的输出不得以会触发客户端“实施此计划”按钮的 `<proposed_plan>` 或等价 implementation handoff 收尾；写完 canonical `spec + plan` 后必须继续进入 phase 2
- 如果当前仍处于阶段 1 或阶段 2，且最新双审尚未清空 `medium/high`，那么这类 UI 动作的正确下一步是先更新 canonical 双文档并继续阶段 2，而不是进入阶段 3
- 如果最新双审已经清空 `medium/high`，但实现确认尚未完成，那么这类 UI 动作的正确下一步是进入实现确认点，而不是直接进入阶段 3
- 只有在最新通过的方案双审已经清空 `medium/high`、用户已确认实现、当前 canonical 双文档仍匹配该通过版 `spec_rev + plan_rev`、并且阶段 3 preflight 通过时，这类 UI 动作才可落到实现
- 如果 UI 文案与当前阶段门禁冲突，以 skill 的阶段门禁为准，不以按钮字面意思为准

### Implementation Handoff Contract

通用 “实施计划 / PLEASE IMPLEMENT THIS PLAN” 动作会开启新一轮消息，因此不能假设下一轮自动继承当前 skill。

- 阶段 1 和普通 phase 2 blocked round 不允许输出 `<proposed_plan>`；除非缺少关键输入或命中人工升级条件，否则主 agent 应继续同一轮推进，而不是把 blocked 状态交给用户点击
- 任何会被下一轮继续消费的 handoff、确认提示、执行计划摘要或 `<proposed_plan>` 内容，都必须显式包含 `[$plan-review-implement-loop](/Users/linus/.codex/skills/plan-review-implement-loop/SKILL.md)`
- handoff 必须把当前 gate state 写成显式字段，至少包括：
  - `current_phase`
  - `gate_state`
  - `spec_rev`
  - `plan_rev`
  - `next_allowed_action`
- `next_allowed_action` 只能取当前 skill 真正允许的下一步：
  - phase 2 blocked：`update_canonical_docs_and_rerun_phase2`
  - phase 2 passed but not confirmed：`enter_implementation_confirmation`
  - phase 3 allowed：`begin_implementation`
- 如果当前并不允许写代码，handoff 里必须显式写出 `do_not_start_coding_yet: true`
- 如果 handoff 缺少 skill 链接、缺少 gate state、或把不允许的动作写成下一步，这份 handoff 视为无效，不应交给用户点击“实施计划”
- 主 agent 不得输出诸如“按你给的实施方案直接实现”“直接收口实现”这类会把下一轮导向普通编码流程的 handoff 文案，除非当前 gate state 已经明确允许 `begin_implementation`

### Post-Review Publication And Implementation Approval

阶段 2 `pass` 只表示“方案允许进入实现确认”，不表示“可以直接写代码”。

- 主 agent 必须先重新进入显式 Plan Mode，并以当前通过的 `spec_rev + plan_rev` 为冻结版本，请求用户确认是否开始实现
- 若运行时不支持显式 Plan Mode，主 agent 必须在当前线程执行等价的显式确认点；在确认前，阶段 3 仍然阻塞
- 用户确认只能对同一组 `spec_rev + plan_rev` 生效；如果确认前文档正文发生变化，旧确认自动失效，必须重新确认
- phase 1 完成后必须直接进入 phase 2，而不是先产出一个可直接点击“实施计划”的阶段 1 handoff
- 普通 phase 2 blocked round 不是用户确认点；只要仍有 `medium/high` 且未命中升级条件，主 agent 的默认下一步必须是更新 `spec + plan` 并继续双审，而不是询问是否继续出下一版
- phase 2 的默认下一步必须先把当前被审正文写回 canonical 双文档，再从这两个文件重新计算 `spec_rev + plan_rev`
- 实现确认点不再承担“首次生成 canonical 双文档”的职责；进入确认点时，这两份文档必须已经存在并与当前通过版 `spec_rev + plan_rev` 对应
- 如果最新通过的双审仍有未关闭 `low-risk`，实现确认点必须显式列出全部这类问题，至少包含 `source`、`reviewer_issue_id` / `issue_id`、`summary`，必要时附 `artifact_anchor`
- 这份 low-risk 清单必须明确标注“这些 low-risk 不阻塞实现；当前确认将视为接受这些风险”
- 如果没有未关闭 `low-risk`，实现确认点也应明确写出“当前无未关闭 low-risk”
- 用户确认开始实现时，主 agent 必须把当前同一组 `spec_rev + plan_rev` 上仍未关闭的 `low-risk` 写回 `Review Ledger` 为 `status = accepted` / `disposition = accepted`
- 如果确认前 canonical 文档正文变化导致 `spec_rev` 或 `plan_rev` 变化，上一轮方案双审立即失效，必须回到阶段 2
- 不再存在“确认后补写 canonical 双文档”这一步；canonical 文档生成是进入正式 phase 2 的前置条件，而不是进入实现的后置动作

### Per-Change Documentation Sync

实现阶段不允许“代码先跑一大段，文档最后一次性补齐”。

- 每次形成新的代码修改后，主 agent 都必须先同步更新两份文档，再继续下一轮代码修改、进入阶段 4，或宣称阶段 3 完成
- 这里的“同步更新”默认至少包括 `spec` 与 `plan` 两份 canonical 文档；如果当前任务还有其它明确受影响的项目文档，主 agent 也必须一并更新
- 如果代码修改只影响实现细节，仍然需要回写到文档；不能因为不触发方案双审就跳过文档同步
- 执行中的分步勾选、时间戳和运行备注应优先写入 `Execution State` 区块；这些更新本身不会触发新的 `plan_rev`
- 如果文档同步改变了需求边界、接口、方案假设或交付路径，则这不是纯实现内同步，而是新的设计变化；必须重新计算 `spec_rev + plan_rev` 并回到阶段 2
- 阶段 4 preflight 发现文档未追上当前代码时，必须阻塞审查并回到阶段 3 先补文档

## Severity Policy

### High

任何会让当前方案走向明显错误方向的问题，例如：

- 关键约束被忽略
- 明显的架构死路
- 严重安全、数据一致性或可靠性风险
- 关键流程或接口定义错误

### Medium

任何虽然不是致命，但足以阻止安全实现的问题，例如：

- 重要接口或边界条件仍然模糊
- 关键集成点缺失
- 方案与计划之间不一致
- 明显会导致返工的结构性缺口

### Low

不会阻止实现开始的问题，例如：

- 表述不够清晰
- 可选优化建议
- 不影响主路径的补充改进

门禁规则：

- 只要存在未解决的 High 或 Medium，禁止进入实现
- Low 不阻塞方案双审 `pass`，但必须保留在 `issues` 列表中，不能伪装成已清零的 Medium/High
- 最新通过的方案若仍有未关闭 `low-risk`，主 agent 必须在实现确认点显式向用户展示；用户确认开始实现时，这些 `low-risk` 视为已接受并写回账本
- 未解决的 High 或 Medium 不会单独构成“停止继续出方案”的理由；只要最近一轮存在实质性的 `spec + plan` 变化，自动回环就应继续

## Structured Review Contract

三个本地 agent 都必须先输出一个结构化头部，推荐 YAML block。

### `@architect_reviewer` 与 `@architecture_challenger`

必填字段：

- `artifact_version`
- `verdict`
- `unresolved_high`
- `unresolved_medium`
- `issues`

### `@reviewer`

必填字段：

- `artifact_version`
- `verdict`
- `actionable_issues`
- `requires_doc_update`
- `issues`

fail-closed 规则：

- 缺字段：阻塞
- 字段值不明确：阻塞
- `artifact_version` 不匹配：阻塞
- 未给出明确 `verdict`：阻塞
- issue 身份字段不完整：阻塞
- `verdict` 与计数字段不一致：阻塞
- 重跑评审未覆盖输入账本摘录中的全部未关闭 `issue_id`：阻塞

所有 issue 都必须带稳定标识：

- `source`
- `reviewer_issue_id`
- `issue_id`
- `severity`
- `summary`
- `kind`
- `artifact_anchor`
- `status`: `open` / `resolved` / `superseded`
- `same_as_previous`: `true` / `false`
- `supersedes` 或 `merged_into`（如适用）
- `new_issue_reason`（仅当重跑评审里出现新的 open issue 且 `same_as_previous = false` 时需要）

说明：

- reviewer 输出里的 `status` 仍只允许 `open` / `resolved` / `superseded`
- `accepted` 仅由主 agent 在实现确认点后写入 `Review Ledger`，不要求 reviewer 直接输出

代码审查语义：

- `actionable_issues` 表示当前仍需处理的问题总数
- `requires_doc_update = true` 表示至少存在一个 `design_affecting` 问题，必须更新 `spec + plan` 后回到阶段 2
- `requires_doc_update = false` 表示所有未关闭问题都属于 `implementation_only`，只需要修代码并重跑代码审查
- `issues[*].kind` 取值只能是 `implementation_only` 或 `design_affecting`
- 代码审查返回的每一个 open issue，都必须以 `source = reviewer` 的独立记录回写到 `Review Ledger` 的 issue 明细视图
- 若本轮代码审查已返回 issue，但 ledger 明细里缺少对应 `reviewer:<reviewer_issue_id>` 记录，则本轮代码审查结果不得用于阶段 4 的后续推进
- 架构评审 issue 的 `kind` 固定为 `architecture`
- 架构评审中：`verdict = pass` 当且仅当 `unresolved_high = 0` 且 `unresolved_medium = 0`
- 架构评审中：`verdict = block` 当且仅当 `unresolved_high + unresolved_medium > 0`
- 架构评审中：`unresolved_high` 必须等于归约后的当前有效 issue 集里 `status = open and severity = high` 的 issue 数量
- 架构评审中：`unresolved_medium` 必须等于归约后的当前有效 issue 集里 `status = open and severity = medium` 的 issue 数量
- 架构评审中：允许在 `verdict = pass` 时仍存在归约后的当前有效 issue 集里 `status = open and severity = low` 的 issue
- `actionable_issues` 必须等于归约后的当前有效 issue 集里 `status = open` 的 issue 数量
- `requires_doc_update` 必须等于 `any(归约后的当前有效 issue 集里 status = open and kind = design_affecting)`
- 代码审查中：`verdict = pass` 当且仅当 `actionable_issues = 0`
- 代码审查中：`verdict = block` 当且仅当 `actionable_issues > 0`
- 如果无法稳定判断 issue 类型，按 `design_affecting` 处理
- 重跑评审里，新出现的 open issue 必须复用旧 `reviewer_issue_id`，或显式给出 `supersedes` / `merged_into` / `new_issue_reason`
- 重跑评审里，新的 open issue 只有两种合法来源：
  1. 复用旧 `reviewer_issue_id`
  2. 使用新的 `reviewer_issue_id`，但必须满足：
     - `artifact_anchor` 不等于任何同 source 的 prior-open issue anchor，或
     - 显式给出 `supersedes` / `merged_into`
- 如果新的 open issue 复用了同 source 的 prior-open anchor，却没有 lineage 字段，视为重编号绕过并阻塞
- 如果提供了 `anchor_remap`，则 remap 后命中的 prior-open anchor 也按“同锚点”处理；不能通过章节迁移或轻微改写后的换锚点绕过 continuity
- `new_issue_reason` 不是自由豁免文本；它只能解释 genuinely new 的 open issue，不能覆盖 remap 命中的旧问题
- 如果存在 `anchor_remap`，新的 open issue 只能落在：
  - 不在任何 prior-open anchor 或 remap 结果中的 genuinely new anchor
  - 或带有明确 lineage 的 remap 目标
- 如果以上一致性条件不成立，整份代码审查结果作废并阻塞

设计合规审查：

- `@reviewer` 的首要门禁之一是实现是否严格遵守当前 `spec`、去账本后的 `plan`、以及已确认的 `Plan Compliance Checklist`（如适用）。
- `@reviewer` 必须逐条核对 checklist：`new_behavior` 是否已经实现，`delete_or_disable` 中要求删除、迁移或 fail-closed 的旧路径是否已经实际处理。
- 任一实现偏离 `spec` / `plan` / checklist，或保留与设计冲突的旧主路径、兼容 fallback、旧协议、旧工具调用方式，都必须进入结构化 `issues`。
- 如果偏离影响架构、接口、协议、工作流、文档承诺或旧路径收口，`kind` 必须是 `design_affecting`，且 `requires_doc_update = true`，除非当前 `spec + plan` 已明确允许该偏离。
- 如果偏离只是在既有文档边界内的实现错误，`kind` 可以是 `implementation_only`，但仍必须修复并重跑阶段 4。
- 测试通过、页面能跑、或功能表面可用，都不能替代设计合规证明。
- 如果 reviewer 无法从代码快照判断实现是否符合设计，按阻塞处理；不得因为证据不足而默认通过。

代码质量 gate：

- `@reviewer` 不只审 correctness，也要审具有工程后果的结构质量问题。
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
- `@reviewer` 不得仅因为“另一种架构更优”就重开已接受的纯方案 trade-off。
- 如果外层 workflow 已提供 accepted trade-off excerpt，`@reviewer` 只能把它当作可选只读上下文。推荐最小字段：
  - `issue_id`
  - `summary`
  - `accepted_rationale`
  - `accepted_boundary`
- 本次 contract 只约束 `@reviewer` 如何消费外层已提供的 accepted excerpt；不重构 excerpt 的 provenance、版本模型、存储位置或 companion artifact。
- 如果外层没有提供 accepted excerpt，不能仅因 excerpt 缺失就把问题升级成 `design_affecting` 或令 `requires_doc_update = true`。
- 只有当实现本身越过当前 `spec + plan` 边界、越过 `accepted_boundary`、把已接受风险放大成新的工程风险、引入与接受理由不相容的新约束，或现有文档本身已不足以支撑安全判断时，才进入既有 `design_affecting` / `requires_doc_update` 路径。

回环规则：

- `requires_doc_update = true`：先更新 `spec + plan`，再回到方案双审
- `requires_doc_update = false` 且 `actionable_issues > 0`：修代码与测试后，仅重跑代码审查
- `actionable_issues = 0`：进入最终文档同步与完成验证

## Karpathy Behavioral Contract

本 contract 分层吸收 `andrej-karpathy-skills` 的行为守则。它不新增 phase，也不改变既有 gate，只把原则转成可派发、可复核的审查要求。

- `Think Before Coding`：关键假设、歧义、未显式 tradeoff 和 silent assumption 必须在 phase 1/2 暴露；不得靠静默假设让方案过审。
- `Simplicity First`：无计划依据的 speculative abstraction、unrequested configurability、single-use abstraction、一次性框架化都属于可审 architecture risk。
- `Surgical Changes`：实现、文档和 prompt 改动必须能追溯到用户请求、`spec`、`plan` 或 checklist；unrelated cleanup 不得混入当前 gate。
- `Goal-Driven Execution`：评审和完成判断必须绑定明确 success criteria、checklist、review gate 或验证证据；apparent functionality 不足以放行。

## Dispatch Templates

### `@architect_reviewer`

使用本地 agent：`/Users/linus/.codex/agents/architect_reviewer.toml`

优先复用当前会话内既有的 `architect_reviewer` agent 槽；仅在 `Agent Slot Reuse` 允许的例外条件下才新开。

把当前需求摘要、权威 `spec` 快照、去掉 `Review Ledger` / `Execution State` 后的权威 `plan` 快照、冻结快照和当前未关闭问题账本摘录发给它，并要求：

- 关注架构与方案层面的高/中/低风险问题，其中只有 High/Medium 会阻塞实现
- 明确指出是否仍有未解决的 Medium/High，并保留 low-risk 作为非阻塞问题
- 不要审代码实现细节

模板：

```text
Review the current design and implementation plan for architecture issues.

Artifacts:
- Spec snapshot under review: <authoritative spec snapshot matching spec_rev>
- Plan snapshot under review: <authoritative plan snapshot matching plan_rev and excluding Review Ledger and Execution State>
- Open issue ledger excerpt: <open-issues-for-architect_reviewer>
- Prior open issue IDs that must be accounted for: <list>
- Anchor remap for prior open issues: <all prior-open anchors -> mapped_to|superseded|merged_into|retired>
- Artifact version:
    review_round: <int>
    spec_rev: sha256:<hash>
    plan_rev: sha256:<hash>

Requirements:
- Start with a YAML block containing:
  artifact_version:
    review_round: <int>
    spec_rev: sha256:<hash>
    plan_rev: sha256:<hash>
  verdict: pass|block
  unresolved_high: <int>
  unresolved_medium: <int>
  issues:
    - source: architect_reviewer
      reviewer_issue_id: <string>
      issue_id: architect_reviewer:<reviewer_issue_id>
      severity: high|medium|low
      kind: architecture
      artifact_anchor: spec:hNN(.hNN...)#pNN|plan:hNN(.hNN...)#bNN
      summary: <string>
      status: open|resolved|superseded
      same_as_previous: true|false
      supersedes: <string|null>
      merged_into: <string|null>
      new_issue_reason: <string|null>
- Reuse the same reviewer_issue_id for the same unresolved issue across rounds.
- Account for every issue_id in the provided prior-open list exactly once.
- Perform a full rereview of the entire current spec and plan snapshots; do not narrow the review to only the prior-open issues.
- Identify silent assumptions, unstated trade-offs, and missing success criteria that affect implementation readiness.
- Flag speculative abstractions, unrequested configurability, or single-use abstraction layers that are not justified by the spec or plan.
- If a small direct solution is wrapped in substantially larger architecture without plan justification, report the complexity as an architecture issue.
- Focus on architecture, flow correctness, invariants, and implementation viability.
- High/Medium block implementation; Low does not block but must still be included in issues.
- Report unresolved High and Medium issues first, then include any Low issues.
- If the structured block is incomplete, the review is unusable.
- The prior-open issue inputs are continuity aids only; they do not reduce review scope.
```

### `@architecture_challenger`

使用本地 agent：`/Users/linus/.codex/agents/architecture_challenger.toml`

优先复用当前会话内既有的 `architecture_challenger` agent 槽；仅在 `Agent Slot Reuse` 允许的例外条件下才新开。

把同一组权威 `spec` / `plan` 快照、同一组冻结快照和当前未关闭问题账本摘录发给它，并要求它专门找反例、失败模式和隐藏复杂度。

模板：

```text
Challenge the current design and implementation plan.

Artifacts:
- Spec snapshot under review: <authoritative spec snapshot matching spec_rev>
- Plan snapshot under review: <authoritative plan snapshot matching plan_rev and excluding Review Ledger and Execution State>
- Open issue ledger excerpt: <open-issues-for-architecture_challenger>
- Prior open issue IDs that must be accounted for: <list>
- Anchor remap for prior open issues: <all prior-open anchors -> mapped_to|superseded|merged_into|retired>
- Artifact version:
    review_round: <int>
    spec_rev: sha256:<hash>
    plan_rev: sha256:<hash>

Requirements:
- Start with a YAML block containing:
  artifact_version:
    review_round: <int>
    spec_rev: sha256:<hash>
    plan_rev: sha256:<hash>
  verdict: pass|block
  unresolved_high: <int>
  unresolved_medium: <int>
  issues:
    - source: architecture_challenger
      reviewer_issue_id: <string>
      issue_id: architecture_challenger:<reviewer_issue_id>
      severity: high|medium|low
      kind: architecture
      artifact_anchor: spec:hNN(.hNN...)#pNN|plan:hNN(.hNN...)#bNN
      summary: <string>
      status: open|resolved|superseded
      same_as_previous: true|false
      supersedes: <string|null>
      merged_into: <string|null>
      new_issue_reason: <string|null>
- Reuse the same reviewer_issue_id for the same unresolved issue across rounds.
- Account for every issue_id in the provided prior-open list exactly once.
- Perform a full rereview of the entire current spec and plan snapshots; do not narrow the review to only the prior-open issues.
- Identify hidden assumptions, speculative complexity, unrequested configurability, and abstractions that are larger than the problem requires.
- Treat unjustified complexity growth as a real-world failure-mode risk when it increases implementation, maintenance, rollout, or debugging cost.
- If a small direct solution is wrapped in substantially larger architecture without plan justification, report the complexity as an architecture issue.
- Look for hidden complexity, unsafe assumptions, rollback gaps, and failure modes.
- High/Medium block implementation; Low does not block but must still be included in issues.
- Report unresolved High and Medium issues first, then include any Low issues.
- If the structured block is incomplete, the review is unusable.
- The prior-open issue inputs are continuity aids only; they do not reduce review scope.
```

### `@reviewer`

使用本地 agent：`/Users/linus/.codex/agents/reviewer.toml`

优先复用当前会话内既有的 `reviewer` agent 槽；仅在 `Agent Slot Reuse` 允许的例外条件下才新开。

在一轮实现后，把权威 `spec` / `plan` 快照、权威代码快照、冻结快照和当前未关闭代码问题账本摘录发给它。

模板：

```text
Review the latest implementation for actionable issues.

Artifacts:
- Spec snapshot under review: <authoritative spec snapshot matching spec_rev>
- Plan snapshot under review: <authoritative plan snapshot matching plan_rev and excluding Review Ledger and Execution State>
- Code snapshot under review: <authoritative code snapshot matching code_rev>
- Plan Compliance Checklist under enforcement (required when applicable): <checklist|none>
- Accepted trade-off excerpt (optional, read-only if provided): <excerpt|none>
- Code revision: <code_rev>
- Open issue ledger excerpt: <open-issues-for-reviewer>
- Prior open issue IDs that must be accounted for: <list>
- Anchor remap for prior open issues: <all prior-open anchors -> mapped_to|superseded|merged_into|retired>
- Artifact version:
    review_round: <int>
    spec_rev: sha256:<hash>
    plan_rev: sha256:<hash>
    code_rev: git:<sha>|sha256:<hash>
- Code range or changed files: <diff-context>

Requirements:
- Start with a YAML block containing:
  artifact_version:
    review_round: <int>
    spec_rev: sha256:<hash>
    plan_rev: sha256:<hash>
    code_rev: git:<sha>|sha256:<hash>
  verdict: pass|block
  actionable_issues: <int>
  requires_doc_update: true|false
  issues:
    - source: reviewer
      reviewer_issue_id: <string>
      issue_id: reviewer:<reviewer_issue_id>
      severity: high|medium|low
      artifact_anchor: code:<path>#L<start>-L<end>
      summary: <string>
      status: open|resolved|superseded
      kind: implementation_only|design_affecting
      same_as_previous: true|false
      supersedes: <string|null>
      merged_into: <string|null>
      new_issue_reason: <string|null>
- Reuse the same reviewer_issue_id for the same unresolved issue across rounds.
- Account for every issue_id in the provided prior-open list exactly once.
- Perform a full rereview of the entire current code snapshot against the full current spec snapshot, plan snapshot, and checklist; do not narrow the review to only the prior-open issues.
- Every changed line should trace to the request, spec, plan, or checklist; unrelated cleanup or opportunistic refactoring belongs in prose or a separate follow-up, not the current gate.
- Treat unrelated edits, unrequested abstractions, unrequested configurability, and adjacent cleanup as reviewable scope violations when they affect risk or maintainability.
- Judge completion against explicit success criteria and checklist evidence, not apparent functionality alone.
- Ensure actionable_issues == count(open issues).
- Ensure requires_doc_update == any(open issue.kind == design_affecting).
- Compare the implementation item-by-item against the Spec snapshot, Plan snapshot, and Plan Compliance Checklist when provided.
- For every checklist item, verify `new_behavior` is implemented and `delete_or_disable` is actually deleted, migrated, or fail-closed.
- If code keeps or uses an old main path, compatibility fallback, legacy protocol, old tool semantics, or old workflow branch that the checklist/design requires removing, report it as a structured blocking issue.
- Passing tests are not sufficient for pass; design, plan, and checklist compliance must be proven from the code snapshot.
- Any deviation from spec/plan/checklist must be in structured `issues`, not prose only.
- If a deviation changes architecture, interface, boundary, workflow, protocol, old-path behavior, or documented delivery semantics, classify it as `design_affecting` and set `requires_doc_update = true` unless current docs explicitly allow it.
- Review correctness, edge cases, regression risk, missing tests, architecture-boundary violations, and structure-quality risks with engineering consequences.
- Restrict structured issues to actionable gate issues only; keep style-only comments and optional suggestions in prose.
- If an accepted trade-off excerpt is provided, treat it as optional read-only context; do not reopen an accepted pure trade-off unless the implementation exceeds the accepted boundary or introduces a new engineering risk.
- If the current implementation cannot be judged safely because the current docs are insufficient, escalate it as `design_affecting` instead of silently downgrading it to `implementation_only`.
- Use the YAML fields as the gate contract; prose findings come after that.
- If the structured block is incomplete, the review is unusable.
- The prior-open issue inputs are continuity aids only; they do not reduce review scope.
```

## Convergence And Escalation

自动回环不是无限的。

以下情况必须停止自动推进并升级为人工决策：

- 同一 `issue_id` 连续 2 轮仍未关闭，且最近两轮没有出现实质性的 `spec + plan` 变化
- 两位架构审查者连续 2 轮在同一组 `spec_rev + plan_rev` 上出现 `pass/block` verdict 冲突，且主 agent 已经无法通过新的方案修订消解冲突
- 剩余阻塞本质上需要人工拍板，例如缺少用户确认、业务取舍无法由方案自动决定、或结构化评审结果失去可判定性

以下情况本身不会触发人工升级：

- `review_round > 3`
- 仍有 unresolved `medium/high`

只要最近一轮方案确实在收敛，这两种情况都只意味着“还不能实现”，不意味着“不能继续出方案”。

禁止行为：

- 靠主 agent 主观降级 severity 来强行出循环
- 用“这次先继续，后面再看”绕过升级条件
- 把“还有中高风险问题”误解成“必须停止继续出方案”

## Loop Decision Table

| 当前状态 | 下一步 |
| --- | --- |
| 还没有 `spec + plan` | 留在阶段 1，继续写文档 |
| 结构化头部缺字段 / verdict 不明确 / artifact_version 不匹配 | 阻塞，修正派发或重新审查 |
| 当前被审正文尚未写入 canonical `spec + plan` | 先写入 canonical 双文档，再冻结 `spec_rev + plan_rev` 并进入/继续 phase 2 |
| 本轮评审已有 issue，但 `Review Ledger` 只写了汇总表，没有 issue 明细 | 阻塞，先补齐 issue 级回写 |
| 读到历史 `Review Ledger` 只有汇总表，没有 issue 明细 | 先把历史 round 重写成 issue 级账本，再继续任何新一轮评审或实现 |
| 本轮代码审查已有 CR issue，但 `Issue Details` 里没有对应 `source = reviewer` 的记录 | 阻塞，先补齐 CR issue 明细 |
| 同一 `issue_id` 同时保留历史 `open` 与后续 `resolved` / `superseded` / `accepted` 记录 | 以该 `issue_id` 的最后一条记录为准；不要因为历史 `open` 行重新阻塞 |
| `Execution State` 的最新 snapshot 已经 `pass`，但顶部阶段文案、说明 prose 或旧 checklist 还停留在 earlier round | 先同步文档状态；同步前沿用最新 snapshot 对应的 gate，不因旧文案回退 |
| 只有 `Review Ledger` / `Execution State` / 纯任务勾选态发生变化 | 不重跑 phase 2，沿用当前通过版 `spec_rev + plan_rev` |
| 双审仍有未解决 Medium/High，且本轮有实质性方案变化 | 更新 canonical `spec + plan`，重复阶段 2，不额外询问是否继续出下一版 |
| 双审仍有未解决 Medium/High，且同一 `issue_id` 连续 2 轮未关闭并且最近两轮无实质性方案变化 | 升级为人工决策 |
| 双审已通过，但用户尚未确认实现 | 进入显式 Plan Mode 的实现确认点并等待确认；若仍有 open `low-risk`，必须显式列出 |
| 双审已通过，但 canonical 双文档正文已变化，不再匹配通过版 `spec_rev + plan_rev` | 回到 phase 2，重新冻结快照并重跑双审 |
| 双审已通过、用户已确认实现、且当前 canonical 双文档仍匹配通过版 `spec_rev + plan_rev` | 进入阶段 3 实现 |
| 实现导致边界、接口、方案假设或交付路径发生实质变化 | 更新 `spec + plan`，使上一轮双审失效，回到阶段 2 |
| 代码审查发现实现偏离 `spec` / `plan` / `Plan Compliance Checklist` | 若偏离属于 `design_affecting`，更新 `spec + plan` 与 `Review Ledger` 后回到阶段 2；否则修代码与测试、同步文档并重跑阶段 4 |
| 代码审查 `actionable_issues > 0` 且 `requires_doc_update = false` | 修代码与测试，并同步更新两份文档后重跑阶段 4 |
| 代码审查 `actionable_issues > 0` 且 `requires_doc_update = true` | 更新 `spec + plan` 与 `Review Ledger`，回到阶段 2 |
| 代码审查 `actionable_issues = 0` | 进入阶段 5 |
| 双 reviewer 连续 2 轮冲突且无法通过新方案修订消解 / 缺少人工拍板 | 升级为人工决策 |
| 任一所需子代理不可用 | 报告阻塞并停止 |

## Completion Contract

宣称完成前，主 agent 必须确认：

1. 最新 `spec + plan` 已同步到最终实现
2. 最新通过的方案双审与最新通过的代码审查共享同一组 `spec_rev + plan_rev`
3. 最新一轮方案双审没有未解决的 Medium/High
4. 最新一轮 `@reviewer` 的 `actionable_issues = 0`
5. 最新一轮 `@reviewer` 已明确检查并确认实现严格遵守 `spec` / `plan` / `Plan Compliance Checklist`（如适用）
6. `Review Ledger` 已记录最终闭环状态
7. 已执行完成验证，而不是靠推断声称完成
