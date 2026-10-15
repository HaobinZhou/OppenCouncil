# Decision Memory 合并文本审阅

_2026-10-14 · 英文已按人类确认及四处修订写入 · payload 按项目类型区分 basis 要求_

---

## 📋 确认对象

下方 fenced block 从实际 `skills/oppencouncil/SKILL.md` 提取，与该文件中的完整段落一致。S01–S18 保留审阅编号，仅用于对应表；原 S16 与 S17 已合并。英文已获人类认可并按四处修订写入，单一文本基线由实际文件生成。

两个旧 SKILL.md 已改为指向共享入口的薄入口；两个 v4 helper 原样移至同目录的 legacy_ 文件，由薄入口按项目版本分派，继续服务尚未迁移的旧流程。`tests/integration/governance-baseline.json` 只锁定一个英文文本来源：新 `skills/oppencouncil/SKILL.md`。依 OPP-20，旧 helper 的主动 AST 检查已收窄到 Memory 函数、记录类型和字段定义；这些节点从 4.3.1 提取，并与工作树逐项比对相同后生成哈希。原整文件哈希只作为来源记录保留，其余操作由行为测试覆盖。公共 Memory helper 已实现并由新旧格式兼容测试覆盖。本文的 payload 合同见新 `references/memory.md`。

## 📚 已写入 SKILL.md 的英文原文

```markdown
## Decision Memory

Create Decision Memory only for a consequential scientific or technical decision that passes this counterfactual test: could a future agent with the current project and complete Git history plausibly fail to explain why the decision was made, or unknowingly reintroduce a rejected direction?
Write one entry per consequential decision, not one per task, conversation, change, commit, rerun, or verification.
A task ending is never a trigger.
Record the prior approach, actual trigger, decision and rationale, rejected directions, and consequences.
Do not duplicate rationale already recorded in Council.

Scientific cases include failed prior designs, changes in analysis strategy prompted by diagnostic findings, collaborator or reviewer requirements, compromises forced by data conditions, and deliberately rejected credible methods.
Technical cases include consequential decisions about architecture, execution, storage, concurrency, resources and memory, reliability, performance policy, operational safety, dependencies, deployment, and state management.
Both require a consequential decision whose causal context is durable and cannot be reconstructed from existing code, definitions, and Git history.
Technical difficulty or an incident alone does not justify a Memory entry.

Do not record routine bug fixes, compatibility work, routine cleanup, local optimization, refactors, tests, reruns, commands, file lists, benchmarks, progress or status summaries, unchanged results, Audit evidence, or unresolved concerns unless they caused a consequential decision of the kind above whose rationale would otherwise be lost.

Memory records causal history; current definitions belong in Council, verification in Audit, and unresolved issues in investigations.
Do not store chain of thought, scratchpads, discussion transcripts, verification logs, or unresolved-risk records in Memory.

`related_topics` may be empty.
Use `supersedes` when a later decision changes direction.
Use `invalidates` when later evidence shows that a key fact or assumption was wrong.
The helper updates the referenced entries’ status and reverse links; existing entries are otherwise never edited.
Read [memory.md](references/memory.md) before adding an entry or declaring relationships.
```

## 🔍 与中文修订版逐句对应

| 英文句子 | 对应中文 | 保留的边界 |
| --- | --- | --- |
| S01：Create Decision Memory… | 重大科研或技术决定通过反事实检验；未来 Agent 即使拥有项目及完整 Git，仍可能无法解释原因或重新引入已放弃方向 | 两类决定；保留 plausibly 与 unknowingly，检验的两个分支 |
| S02：Write one entry… | 每个重大决定写一条，不按任务、对话、改动、提交、重跑或验证逐条记录 | 计数单位是决定 |
| S03：A task ending… | 任务结束永远不是触发条件 | 独立句，无除外条款 |
| S04：Record the prior approach… | 此前做法、实际触发、决定及理由、被放弃方向、后果 | 因果记录内容 |
| S05：Do not duplicate rationale… | Council 已记录的口径依据不重复写入 | 不重复保存已可追溯理由 |
| S06：Scientific cases include… | 失败过的设计、诊断结果促成的分析策略改变、合作者/审稿要求、数据条件迫使的折中、有意放弃的可信方法 | 科研触发条件完整保留 |
| S07：Technical cases include… | 架构、执行方式、存储、并发、资源与内存、可靠性、性能策略、运行安全、依赖、部署、状态管理 | 技术范围逐项列出 |
| S08：Both require… | 两类都要求决定重大，且因果背景有持久价值、不能由现有代码、口径和 Git 还原 | 保留 durable；示例不绕过反事实检验 |
| S09：Technical difficulty… | 技术困难或一次事故本身不构成记录理由 | 事故本身不自动入 Memory |
| S10：Do not record routine… | 常规修错、兼容处理、整理、局部优化、重构、测试、重跑、命令、文件清单、基准、进度或状态、未变化的结果、Audit 证据和未决担忧不写 Memory，除非它们引发了上述重大且无法还原的决定 | 除非仅修饰本句，不涵盖 S03 |
| S11：Memory records… | Memory 管因果历史；口径、验证、未解决问题分别归 Council、Audit、调查事项 | 四类责任明确 |
| S12：Do not store… | 不保存推理过程、草稿、讨论记录、核查日志或待决风险 | 草稿对应 scratchpads；五类禁存内容 |
| S13：related_topics… | related_topics 可以为空 | 无强制 topic 关联 |
| S14：Use supersedes… | 后来改变方向用 supersedes | 方向被替代 |
| S15：Use invalidates… | 后来证据表明关键事实或假设错误用 invalidates | 保留“事实或假设” |
| S16＋S17：The helper updates… | helper 更新被指向条目的状态和反向关系；除此之外，既有条目永不编辑 | 合并为用户指定的完整句子，明确关系维护例外 |
| S18：Read memory.md… | 新增条目或声明关系前读 memory.md | 保留按需加载入口 |

## ⚙️ memory.md 的 payload 设计

### 已核实的旧格式

[Stepwise normalize_memory_payload](../skills/stepwise-r-project/scripts/legacy_stepwise_r_project.py:1196) 要求 `scientific_or_technical_rationale` 与 `basis`，三个关联数组可省略；其文件按固定字段序列存储。

[Steward validate_memory_payload](../skills/oppen-project-steward/scripts/legacy_oppen_project_steward.py:3089) 使用 `why`，没有 `basis`，三个关联数组必填；其文件为 frontmatter 加固定正文分节。两者不仅字段名不同，落盘格式也不同。

### 已确认的新条目格式

统一新写入采用 `why`；`basis` 对科研项目必填，对普通项目可选。按项目声明的类型判断，不按语言、布局、决定是科研还是技术、或旧 payload 字段名判断。`basis` 是支持该决定的可追溯依据，不是模型内部推理。`related_topics`、`supersedes`、`invalidates` 均默认空数组。

| 项目 | 新格式 | 旧格式读取与转换 |
| --- | --- | --- |
| 决定理由 | `why` 必填 | Stepwise 的 `scientific_or_technical_rationale` 无损映射到内存中的 why |
| 支持依据 | 科研项目必填；普通项目可选；给出时须为非空文本 | Stepwise 原 basis 保留；Steward 缺失时标记未提供，不编造 |
| 关联数组 | 三个数组可省略，默认空 | 两种旧格式均识别；保持 ID/关系语义 |
| 共同内容 | title、before、trigger、decision、rejected_or_prior_approach、consequence 必填 | 原样读取 |
| 格式来源 | reader 内部保留 source_format/source_path | 不把来源标签写回旧条目 |

新 helper 接受两种旧调用 payload，也能读两种旧落盘格式。旧文件缺 basis 仍可读取，不补造依据；任何新建科研条目都必须提供 basis，包括使用旧 Steward 字段名的调用。新建普通条目可省略 basis。若同时传 why 与 scientific_or_technical_rationale，要求两者文本一致，否则拒绝并说明冲突，不自行选用其中一份。

新条目采用 Steward 的 frontmatter 与固定正文分节，显式带 v5 Memory 格式标记；科研条目包含 Basis 分节，普通条目未提供时省略。理由及独立依据保持两个字段，不拼接丢失来源。旧文件不批量改写、不重编号、不移动；关系维护使用各自格式的 writer，仅修改被明确关系操作影响的状态和反向链接，原理由及依据保持原文。

### 保留的关系约束

- 关系目标必须是已存在且 active 的条目。
- 同一 ID 不能同时出现在 supersedes 和 invalidates。
- status、反向链接、ID、文件名及路径由 helper 管理，调用方不提供或手工修改。

这些约束已写入 [memory.md](../skills/oppencouncil/references/memory.md)。

### 合并 helper 前的验证

- 两类旧记录都能读回，Stepwise 的 basis 不丢失，Steward 不出现虚构依据。
- 新建科研条目缺 basis 拒绝，新建普通条目可省略；旧记录缺 basis 保持可读，两种旧 rationale 字段均兼容，冲突字段拒绝写入。
- supersedes 与 invalidates 各自更新目标状态及正确的反向链接，失败整体回滚。
- 空关联数组有效；无关记录、原理由、原 basis 和既有 ID 保持。
- 新增条目不会因布局而使用不同的科学/技术准入标准。

## ✅ 正反例评测与基线门槛

新增到 `tests/evals/skill_decisions.json` 的用例：

| ID | 应观察到的行为 |
| --- | --- |
| memory_real_failure_changes_architecture | 真实故障导致放弃重大架构方向且原因不可还原时，写一条因果记录 |
| memory_routine_fix_is_explained_by_git | 常规修错、测试与 Git 足以解释时，不写 Memory |
| memory_execution_unsafe_at_project_scale | 原执行架构在项目规模下不安全，因此改变存储/并发/内存策略时，保留因果原因 |
| memory_task_completion_never_triggers | 仅任务结束或验收成功，不创建 Memory |
| memory_diagnostics_change_analysis_strategy | 诊断结果改变科研分析策略，且理由不可由当前代码/口径/Git 还原时，可写 Memory |
| memory_one_decision_across_multiple_turns | 同一重大决定跨多个任务/对话/提交，仍只写一条 |
| memory_false_assumption_uses_invalidates | 关键假设被证明错误时用 invalidates，helper 更新目标状态及反向链接 |
| memory_later_direction_uses_supersedes | 后来改变方向且原事实和假设仍有效时用 supersedes，不用 invalidates |
| memory_council_rationale_is_not_duplicated | Council 已完整保存理由时，不另建或复制 Memory |

英文确认已完成，原文已写入 SKILL.md，并从实际文件按既有 section 提取边界生成单一文本基线。helper 主动 AST 检查依 OPP-20 收窄到从 4.3.1 提取并核对未变的 Memory 节点；reader/writer 另有真实文件和故障恢复测试。

九项已各执行一次独立 Agent 前向评测，保存内容和关系读回符合预期。首批两个正例遇到独立 Skill 的导入遮蔽问题，随后修复并增加普通调用回归。完整证据、原始产物位置及覆盖限制见 [Memory 验证记录](v5-memory-testing.md)；这不是全 Skill 的删除评测或完整 v5 验收。
