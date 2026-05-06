---
name: plan-review-implement-loop
description: 当工程任务要求先冻结需求与方案文档、再用固定架构与代码审查门禁推进实现，并且必须把评审问题、实现问题和文档同步纳入同一闭环时使用。
---

# plan-review-implement-loop

## Overview

用一个严格的主 agent 闭环来处理新需求：先规划并写两份文档，再做双架构评审，清掉中/高风险后才实现；实现后做代码审查。若问题只影响代码实现，就留在代码审查回路内修复；若问题触及方案、边界或接口，再同步文档并回到方案评审。

这是一个显式绑定本地 agent 的个人 skill。默认目标环境就是当前 Codex 安装，不追求跨机器可移植性。

## Karpathy Behavioral Principles

本 skill 分层吸收 `andrej-karpathy-skills` 的行为守则，但不替代本文件已有的 phase/gate/ledger contract。

- `Think Before Coding`：非平凡任务先暴露关键假设、歧义和取舍；phase 1 不允许静默选择一种会影响范围、接口、验收或门禁的解释。
- `Simplicity First`：默认选择满足当前需求的最小可行方案；无请求的扩展性、配置化、抽象层或单次使用框架都必须有 `spec + plan` 依据。
- `Surgical Changes`：实现和文档同步只允许覆盖当前请求、`spec`、`plan` 或 checklist 需要的范围；禁止借机修改无关代码、注释、格式或相邻逻辑。
- `Goal-Driven Execution`：每一步都必须对应可验证的成功标准、review gate 或验证证据；不得用“看起来完成”“测试表面通过”替代明确验收。

<SUBAGENT-STOP>
如果你是被派发去执行单个实现、方案评审或代码审查任务的子代理，跳过此技能。
</SUBAGENT-STOP>

## Hard Gates

- 只由主 agent 执行此技能。不要要求 `@architect_reviewer`、`@architecture_challenger` 或 `@reviewer` 先进入 `using-superpowers`。
- 这是一个本地 skill：固定绑定 `/Users/linus/.codex/agents/architect_reviewer.toml`、`/Users/linus/.codex/agents/architecture_challenger.toml`、`/Users/linus/.codex/agents/reviewer.toml`。如果这些本地 agent 不可用，直接阻塞。
- 在 Codex 运行时，方案双审与代码审查都应优先复用既有 agent 槽：`architect_reviewer`、`architecture_challenger`、`reviewer`。同一会话内同一角色已有可用 agent 时，优先继续向该 agent 槽派发，而不是重复新开同角色 agent。
- 每个大阶段开始前，主 agent 都要先做一次基于 `using-superpowers` 纪律的 phase preflight checklist。它只是阶段检查单，不是重新调用 `using-superpowers`，也不是重新进入顶层 skill 路由，更不能再次激活 `plan-review-implement-loop` 自身。
- 第一个阶段优先进入显式 Plan Mode。若运行时没有显式 Plan Mode，执行本 skill 内部定义的封闭规划子流程：`brainstorming` 只用于探索，`writing-plans` 只用于计划写作约束，阶段控制权始终留在当前 skill，且唯一出口固定为阶段 2。
- 如果阶段 1 出现会影响范围、接口、验收标准或门禁判断的关键确认项，主 agent 必须留在阶段 1 请求用户确认；确认前不得进入阶段 2，更不得提前实现。
- 未把两份文档落盘到 canonical 路径前，不得进入任何正式方案评审或实现：
  - `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`
  - `docs/superpowers/plans/YYYY-MM-DD-<topic>.md`
- 正式 phase 2 的 `spec_rev` / `plan_rev` 只能从当前项目工作区 `docs/` 下的 canonical 双文档正文计算；其中 `plan_rev` 必须排除计划文档内显式分隔的 `Review Ledger` / `Execution State` 区块，并在保留正文里把纯 Markdown 任务勾选态 `[ ]` / `[x]` 归一化后再计算；禁止从仅存在于对话、Plan Mode 草稿、内联快照或临时缓冲区里的版本直接冻结。
- 方案双审通过后，不得直接进入实现。主 agent 必须先重新进入显式 Plan Mode，带着当前通过的 `spec_rev + plan_rev` 等待用户明确确认；未得到确认前，阶段 3 保持阻塞。若运行时不支持显式 Plan Mode，则在当前线程执行等价的显式确认点，但门禁语义不变。
- 除阶段 1 缺少关键业务输入、命中既有人工升级条件、或进入实现确认点外，主 agent 不得因为普通 phase 2 blocked round 停下来询问“是否继续出下一版方案”。
- 任一存在未解决的中/高风险方案问题时，不得实现。
- `BLOCKED` 在本 skill 里默认表示“阻塞实现”，不是“阻塞继续出下一版方案”。只要仍能通过修改 `spec + plan` 收敛问题，就应继续留在方案回环里推进。
- 在本 skill 里，任何 UI 动作如“实施计划”“实施此计划”“开始执行”，都默认解释为“继续按下一道门禁推进”，不是无条件进入实现阶段。
- 阶段 1 写完 canonical `spec + plan` 后，主 agent 必须在同一轮直接进入 phase 2；不得把阶段 1 结果作为可执行 implementation handoff、`<proposed_plan>`、或任何会生成“实施此方案”按钮的最终输出交给用户。
- 任何可能被下一轮通用“实施计划 / PLEASE IMPLEMENT THIS PLAN”动作消费的用户可见 handoff、确认提示或 `<proposed_plan>`，都必须显式包含 `[$plan-review-implement-loop](/Users/linus/.codex/skills/plan-review-implement-loop/SKILL.md)`，不得假设下一轮会自动继承当前 skill。
- 每一轮评审都必须绑定不可变的冻结快照：`review_round`、`spec_rev`、`plan_rev`，以及代码审查所需的 `code_rev`。其中 `review_round` 是单调递增整数；`spec_rev`、`plan_rev`、`code_rev` 才是内容寻址版本。
- 主 agent 派发评审时，必须提供与 `spec_rev` / `plan_rev` / `code_rev` 一致的权威快照；原始文件路径只用于审计，不作为门禁判定依据。若做不到这一点，自动流程直接阻塞。
- 任一评审结果缺少结构化头部、字段值不明确、返回的 `artifact_version` 与当前冻结快照不一致、或 issue 身份无法稳定追踪时，一律阻塞，不得放行。
- `@reviewer` 的门禁字段固定为：
  - `actionable_issues`
  - `requires_doc_update`
  - `issues[*].kind`
- 代码审查问题必须按 issue 级别标记 `kind`：
  - `implementation_only`：只修代码与测试，再重跑代码审查；不使最新方案双审失效
  - `design_affecting`：先同步更新 `spec + plan`，立即使上一轮方案双审失效，再回到方案双审
- 任一重跑评审都必须带上当前未关闭 issue 的账本摘录；同源未关闭问题必须复用稳定的 `reviewer_issue_id`，全局账本使用带 `source` 前缀的 `issue_id` 命名空间。
- 任一重跑评审都必须按“全量复审 + continuity 对账”执行：reviewer 必须重新审视当前完整 `spec` / `plan` / `code` 权威快照，当前未关闭 issue 摘录只用于确保旧问题被续审、关闭或归并，不得把评审范围收缩成“只看上一轮提过的问题”。
- 若存在未关闭 issue 且被审 artifact 在两轮之间发生变化，主 agent 还必须提供完整的 `anchor_remap`，把每个 prior-open 旧锚点映射为 `mapped_to`、`superseded`、`merged_into` 或 `retired` 之一；否则自动回环阻塞。
- `requires_doc_update` 必须等于 `any(open issue.kind == design_affecting)`；`actionable_issues` 必须等于 open issues 数量。只要不一致，一律阻塞。
- 任一重跑评审都必须对输入账本摘录中的每个未关闭 `issue_id` 给出显式状态结果；主 agent 再按 `workflow-contract.md` 的 `status -> disposition` 映射回填 `Review Ledger`。静默漏掉旧问题等同于无效评审。
- `Review Ledger` 必须放在计划文档的显式分隔块里；如需在执行过程中打勾或记录进度，也必须放在独立的 `Execution State` 分隔块里；这两个块都不参与 `plan_rev` 计算。若分隔块缺失或规则不清，自动回环直接阻塞。
- `Review Ledger` 必须按 issue 级别记录明细；仅写 `review_round` / reviewer / verdict / unresolved high/medium 这种汇总表，不算有效回写。
- 如果发现当前计划文档里的 `Review Ledger` 只有汇总表、没有 issue 明细，主 agent 必须先把现有 round 重写为 issue 级账本，再允许继续 phase 2 / phase 3 / phase 4；不得带着无效 ledger 继续追加新轮次。
- 涉及既有实现、协议、架构边界或关键工作流重构时，进入阶段 3 前必须先输出并获得用户确认一份 `Plan Compliance Checklist`；未确认前不得改代码。
- `Plan Compliance Checklist` 必须逐条映射：设计原文要求、当前实现位置、偏差点、必须删除或禁用的旧路径、必须新增的行为、允许修改的文件/模块、验收命令或验收用例。
- 如果实现过程中发现计划不合理、边界冲突、需要保留旧路径、需要兼容 fallback、或某条计划无法按原样落地，主 agent 必须立即停止并询问用户；不得自行降级、替换方案或“先跑通再说”。
- 对 closure / 协议切换 / 行为收口类任务，旧主路径与新主路径不得双轨并存。旧协议、旧入口、旧测试或旧 fallback 若与新设计冲突，必须删除、迁移或 fail-closed；禁止用兼容层绕过新协议。
- 实现只能修改已确认 `Plan Compliance Checklist` 中列出的文件/模块。若需要扩大写入范围，必须先更新 checklist 并再次取得用户确认。
- 每完成一个实现小阶段，主 agent 必须回填 checklist 状态并给出 diff 摘要与验证结果；不得用“测试通过”替代“计划约束已满足”的证明。
- 只有在以下情况之一成立时，才停止自动推进并升级为人工决策：
  - 同一 `issue_id` 连续两轮未关闭，且最近两轮没有带来实质性的 `spec + plan` 变化
  - 两位架构审查者连续两轮在同一 `spec_rev + plan_rev` 上出现 `pass/block` verdict 冲突，且主 agent 无法通过新的方案修订消解冲突
  - 剩余阻塞只靠人工拍板才能推进，例如缺少必须由用户确认的关键输入、或剩余问题本质上是业务取舍而非方案缺陷

## Workflow

### 1. 规划与文档生成

- 先做阶段 1 的 phase preflight checklist：按 `using-superpowers` 的纪律检查当前阶段，但不要重新选择 enclosing workflow，也不要再次触发本 skill。
- 优先进入显式 Plan Mode。
- 若无显式 Plan Mode，执行本 skill 定义的规划子流程：
  - 调用 `brainstorming` 只做需求与方案探索，不接管后续阶段
  - 主 agent 直接写设计文档
  - 读取 `writing-plans` 的计划写作约束，但不使用它的执行交接段落
  - 主 agent 直接写实现计划
- 在进入实现前，必须先落盘并审视两份文档：设计文档和实现计划。
- 如果只是局部歧义且能安全推断，主 agent 可以记录假设后继续写文档；如果是不确认就会改变范围、接口、验收标准或后续门禁的关键问题，必须停在阶段 1 请求用户确认。
- `spec + plan` 必须写清成功标准、验收方式和验证点；如果缺少这些内容，不能用笼统目标进入 phase 2。
- 关键确认项未解决时，阶段 1 保持阻塞；收到确认后，先同步更新 `spec + plan`，再进入阶段 2。
- 阶段 1 的唯一出口是：`spec + plan` 已生成并写入 canonical 路径，然后进入阶段 2。不要在这里直接进入实现执行选项，也不要把阶段 1 结果包装成可点击“实施此方案”的 handoff。
- 如果设计或计划尚不完整，继续补文档，不要提前编码。

### 2. 方案双审

- 先做阶段 2 的 phase preflight checklist。
- 在冻结本轮方案快照前，先把当前被审 `spec + plan` 正文同步到 canonical 双文档；如果当前内容只存在于 Plan Mode 草稿、对话草稿、内联快照或临时缓冲区，先落盘，再继续 phase 2。
- 冻结本轮方案快照：固定 `review_round`、`spec_rev`、`plan_rev`。其中 `review_round` 是单调递增整数；`spec_rev` 和 `plan_rev` 必须来自 canonical 双文档正文的内容寻址快照，而不是自由命名版本号。
- 并行派发：
  - `@architect_reviewer`
  - `@architecture_challenger`
- 若当前会话内已存在这两个角色各自的可用 agent 槽，优先复用原槽继续评审；只有原槽不可用、上下文已失真、或明确需要隔离时，才允许新开同角色 agent。
- 两个子代理都只审同一组冻结快照，不要让它们审口头摘要，也不要让它们各自看到不同版本的文档。计划文档的 `Review Ledger` / `Execution State` 只作为账本或执行上下文，不属于被审 artifact；本轮门禁只认主 agent 提供的权威快照和旧问题账本摘录。
- 只要当前 canonical 双文档正文发生了任何改动，下一轮 phase 2 就必须是对当前完整方案的重新审查，而不是只复查上一轮 open issue。旧问题账本摘录只承担 continuity 与 lineage 作用，不能定义或缩小架构评审范围。
- phase 2 必须主动拦截未说清的前提、隐藏 tradeoff、silent assumption，以及没有计划依据的 speculative abstraction / configurability / single-use abstraction；这些可作为结构化 architecture issue。
- 汇总两边结论后，按 [workflow-contract.md](./references/workflow-contract.md) 的严重级别规则处理。
- 只要还有未解决的中/高风险问题，就先更新 canonical `spec + plan`，在计划文档的 `Review Ledger` 中按 issue 明细记录本轮结果，再重新计算 `spec_rev + plan_rev` 并再次并行双审。这些问题会阻塞实现，但默认不会阻塞继续产出下一版方案。
- 只要没有命中人工升级条件，phase 2 的默认下一步就必须是“更新 canonical `spec + plan` 并继续双审”；不要把普通 blocked round 变成“是否继续出下一版”的用户确认点。
- 每个未解决问题都必须有稳定的 `source`、`reviewer_issue_id`、`issue_id` 和 lineage 字段；没有这些字段的评审结果视为不可用于回环和升级判定。
- 解释 `Review Ledger` 时，必须先按 `issue_id` 折叠 issue 明细；同一 `issue_id` 的最后一条记录才是当前有效状态。历史 `open` 行如果后续已经被 `resolved` / `superseded` / `accepted` 覆盖，不得继续算作当前 blocker。
- 如果 `Execution State` 已记录最新 `review_round_<n>_snapshot`、`gate_state` 或等价快照，它必须与折叠后的当前 issue 状态一致；文档顶部旧的阶段描述、历史 checklist 或未同步 prose 只能视为待回填文案，不能覆盖当前 gate 判定。
- 已通过的方案双审只对同一组 `spec_rev + plan_rev` 有效。只要两份文档的正文发生实质变化，就必须开新一轮方案双审。
- 当最新一轮双审清空中/高风险后，先进入实现确认点；不要把 phase 2 `pass` 直接解释成“开始写代码”或“先写入项目 docs”。
- 实现确认点要求主 agent 重新进入显式 Plan Mode，并带着当前通过的 `spec_rev + plan_rev` 等待用户明确确认；若运行时不支持显式 Plan Mode，则在当前线程做等价确认，但在确认前仍不得进入阶段 3。
- 如果最新通过的双审仍有未关闭 `low-risk`，实现确认点必须显式列出这些 issue，至少包含 `source`、`reviewer_issue_id` / `issue_id`、`summary`，必要时附 `artifact_anchor`，并明确说明“这些 low-risk 不阻塞实现，当前确认将视为接受这些风险”。
- 实现确认点不再承担“首次生成 canonical 双文档”的职责；进入确认点时，这两份文档必须已经存在并与当前通过版 `spec_rev + plan_rev` 对应。
- 用户在实现确认点确认开始实现时，默认同时接受当前同一组 `spec_rev + plan_rev` 上仍未关闭的 `low-risk`；这些问题必须以 `accepted` 语义写回 `Review Ledger`，不能记成 `fixed`。
- 如果 UI 在阶段 1 或阶段 2 出现“实施计划”之类的按钮，且最新一轮双审尚未清空中/高风险，主 agent 必须把它解释为“先更新 canonical 双文档并继续阶段 2 方案双审”；如果双审已经通过，则下一步是实现确认点，而不是直接写代码。
- phase 1 和普通 phase 2 blocked round 都不得输出可直接消费的 `<proposed_plan>` 或等价 implementation handoff；只有到达实现确认点后，才允许输出面向“确认是否开始实现”的 handoff。
- 任何面向下一轮的 handoff、计划摘要或确认提示，都必须先写明当前 gate state、下一道允许的门禁动作，以及“此 handoff 必须继续在 `[$plan-review-implement-loop](/Users/linus/.codex/skills/plan-review-implement-loop/SKILL.md)` 下执行”。如果缺少这三项，不得把它当作可执行 handoff 发给用户。

### 3. 实现

- 先做阶段 3 的 phase preflight checklist。
- 只有在以下条件都满足后，才允许实现：
  - 最新一轮双审没有未解决的中/高风险问题
  - 用户已经在显式 Plan Mode 的实现确认点中，明确确认基于当前 `spec_rev + plan_rev` 进入实现
  - 当前 canonical `spec + plan` 仍与最新通过的 `spec_rev + plan_rev` 匹配
- 如果任务涉及既有实现、协议、架构边界或关键工作流重构，还必须已经完成并获得用户确认 `Plan Compliance Checklist`；实现过程不得越过 checklist 的文件/模块范围。
- 实现阶段可以调用现有的实现类技能或工作流，但不能绕过当前 skill 的文档和评审门禁。
- 实现必须保持 surgical：每个代码、文档或 prompt 改动都应能追溯到用户请求、`spec`、`plan` 或 checklist；无关清理、顺手格式化、相邻逻辑整理不得混入当前实现。
- 如果在实现确认前或实现过程中修改了 canonical 双文档正文，导致 `spec_rev` 或 `plan_rev` 变化，上一轮方案双审立即失效，并回到阶段 2；纯 `Review Ledger` / `Execution State` 更新，以及仅把 Markdown 任务勾选态从 `[ ]` 变为 `[x]` 或反向变更，不算这类正文变化。
- 每次形成新的代码修改后，主 agent 都必须先同步更新两份文档，再继续后续实现、进入代码审查或宣称完成；不要把文档更新拖到整轮实现结束后统一补。
- 在执行过程中记录分步进度时，应优先写入计划文档的 `Execution State` 分隔块；只更新勾选、时间戳、负责人或运行备注，不会单独触发新的 `plan_rev`。若改动了步骤文本、顺序、范围或验收要求，仍视为计划正文变化并回到阶段 2。
- 如果实现改变了需求边界、接口、方案假设或交付路径，先更新 `spec + plan`，生成新的 `spec_rev + plan_rev`，立即使上一轮双审结果失效，并直接回到阶段 2。不要写成“更新文档后继续实现”。
- 如果实现只是在当前文档边界内修复局部代码或测试，不会自动使上一轮方案双审失效；是否需要回到阶段 2，以后续代码审查的 `requires_doc_update` 为准。

### 4. 代码审查

- 先做阶段 4 的 phase preflight checklist。
- 在一轮实现完成后，冻结代码快照：固定 `review_round`、`spec_rev`、`plan_rev`、`code_rev`。若 git 不能唯一标识当前代码内容，就改用当前被审代码集合的内容哈希。
- 阶段 4 preflight 必须先确认：当前 `code_rev` 对应的两份文档都已经同步更新；若任一文档落后于当前代码修改，先回到阶段 3 补文档，再允许审查。
- 使用本地 `@reviewer` 审查最新代码；它的 agent 定义来自 `/Users/linus/.codex/agents/reviewer.toml`。
- `@reviewer` 必须把当前实现逐条对照 canonical `spec`、去账本后的 canonical `plan`、以及已确认的 `Plan Compliance Checklist`（如适用）检查；代码是否严格遵守规范、设计和 checklist 是硬门禁，不是可选建议。
- 任一实现偏离 `spec` / `plan` / checklist、保留应删除旧路径、绕过 fail-closed、或用兼容 fallback 替代新协议，都必须作为结构化 issue 返回；测试通过不能抵消设计不合规。
- 代码审查必须检查每个改动是否能追溯到请求、`spec`、`plan` 或 checklist；无关修改、顺手清理、未要求的抽象或配置化应作为 scope violation 或明确的非阻塞 prose 记录，不能静默通过。
- 代码审查必须按明确 success criteria 判断完成度；如果当前文档缺少足够验收标准，应走 `design_affecting` / doc insufficiency 路径，而不是凭感觉放行。
- 若当前会话内已经存在可用的 `@reviewer` agent 槽，优先复用原槽继续代码审查与问题续审；只有原槽不可用、上下文已失真、或明确需要隔离时，才允许新开。
- 代码审查的门禁只认结构化字段，不依赖自由文本章节名。最低可判定集合是：`artifact_version`、`verdict`、`actionable_issues`、`requires_doc_update`、`issues`。
- 重跑代码审查时，必须把当前未关闭的代码问题账本摘录一并发给 `@reviewer`，要求它对每个同源未关闭问题给出延续、关闭或归并结果；只要旧问题没有被显式覆盖，本轮代码审查直接作废。
- 重跑代码审查时，`@reviewer` 仍必须重新检查当前完整实现对 `spec` / `plan` / checklist 的符合性；未关闭代码问题账本摘录只用于 continuity，对代码审查范围不构成缩减。
- 代码审查返回的每一个 CR issue，都必须在 `Review Ledger` 的 issue 明细视图中逐条回写；未完成这一步前，不得把本轮代码审查视为完成。
- 如果 `@reviewer` 给出 `actionable_issues = 0`，进入阶段 5。
- 如果 `@reviewer` 给出 `actionable_issues > 0` 且 `requires_doc_update = false`：
  - 只修代码与测试
  - 仍需同步更新两份文档，但不得借机改变需求边界、接口、方案假设或交付路径
  - 重新冻结 `code_rev`
  - 仅重跑阶段 4；最新通过的方案双审仍对当前 `spec_rev + plan_rev` 有效
- 如果 `@reviewer` 给出 `actionable_issues > 0` 且 `requires_doc_update = true`：
  - 先同步更新 `spec + plan`
  - 使上一轮方案双审失效
  - 再回到阶段 2
  - 清空未解决的中/高风险问题后，才允许继续实现

### 5. 文档回填与最终同步

- 先做阶段 5 的 phase preflight checklist。
- 在宣称完成前，确保最终实现与两份文档一致。
- 完成声明必须绑定验证证据；不得只用口头总结、表面功能可用或局部测试通过替代最终验收。
- 只有当以下条件都满足时，才可结束：
  - 最新 `spec + plan` 已同步
  - 最新通过的方案双审与最新通过的代码审查共享同一组 `spec_rev + plan_rev`
  - 最新通过的代码审查绑定到最终 `code_rev`
  - 最新双审没有未解决的中/高风险问题
  - 最新 `@reviewer` 的 `actionable_issues = 0`
  - 最新 `@reviewer` 已明确确认实现严格遵守 `spec` / `plan` / `Plan Compliance Checklist`（如适用）
  - `Review Ledger` 已写回最终闭环状态
  - 已按 `verification-before-completion` 的要求完成验证

## Do Not

- 不要在写文档前直接实现。
- 不要在中/高风险方案问题未清之前开始实现。
- 不要在 `@reviewer` 提出 `design_affecting` 问题后只改代码不改文档。
- 不要把阶段 preflight 误用成顶层重新路由，也不要让它再次激活 `plan-review-implement-loop`。
- 不要把 `using-superpowers` 的阶段入口要求强行施加给子代理。
- 不要依赖自由文本的“问题/建议”栏目名来判定门禁。
- 不要把旧的审查结果复用到新的文档版本或新的代码快照上。
- 不要在 phase 1 或普通 phase 2 blocked round 输出会生成“实施此方案”按钮的 `<proposed_plan>` 或等价 handoff。
- 不要把 `Review Ledger` 写成只有轮次统计、reviewer verdict 和 high/medium 数量的汇总表。
- 不要把 `Review Ledger`、`Execution State` 或纯任务勾选态更新误判为计划正文变更。
- 不要在代码审查已经返回 issue 的情况下，只更新 `actionable_issues` / `requires_doc_update` / verdict，而不把 CR issue 逐条写入 `Issue Details`。
- 不要在同一会话里无故重复新开同角色 reviewer agent，绕过既有 agent 槽的连续性。
- 不要让不同 reviewer 复用同一个未命名空间化的 issue 标识。
- 不要在 issue 没有稳定身份或 lineage 的情况下继续自动回环。
- 不要在子代理不可用时用“人工脑补通过”替代正式评审。
- 不要在未确认 `Plan Compliance Checklist` 的情况下修改既有实现、协议、架构边界或关键工作流。
- 不要为了兼容旧测试、旧 UI 或旧调用方而保留与新设计冲突的旧主路径。
- 不要把新增新工具、新接口或新字段误当成已经替换旧协议；旧协议必须被显式删除、迁移或 fail-closed。
- 不要在发现计划冲突时自行降级、改口径、换实现策略或先写代码；必须停下来让用户裁决。
- 不要把代码审查降级成只找 bug 或只看测试；设计、计划和 checklist 合规性是硬门禁。
- 不要在代码偏离 `spec` / `plan` / checklist 时，因为功能能跑或测试通过就放行。

## Reference

- 详细的阶段契约、严重级别规则、派发模板和回环判定，见 [workflow-contract.md](./references/workflow-contract.md)。
