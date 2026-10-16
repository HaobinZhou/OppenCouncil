# OppenCouncil 5.0.1

## English

5.0.1 lets you review, edit, and confirm project definitions directly in Codex, and improves how you read them alongside their supporting literature in the web workbench. Discuss one group at a time in chat, or open the webpage to compare the wording with its sources. Both use the same project records.

### Highlights

- **Review and confirm definitions in Codex.** The AI still checks the facts, appraises the literature, and prepares complete proposals before bringing them to you. With your explicit authorization, Codex can save discussion, edit proposals, record your preferred option, confirm or reconfirm a definition, or withdraw a proposal. The corresponding records also appear in the workbench. By default, each exchange covers one related group, or up to three standalone questions when no groups remain, then waits for your feedback. The proposed wording and the decision you need to make come first, with short sentences and clearly separated points.

- **Read definitions and literature side by side, with evidence that follows your selected option.** Select A to see only the evidence cited by A; switch to B to see B’s evidence. The full literature reader is available for both standalone definitions and group members. Citation numbers are generated automatically in order of first appearance within the current review. Click a number to locate the supporting evidence, then open the original source.

- **More screen space for the material you are reviewing.** A compact header leaves more room for reading, while groups support both individual review and option comparison. Definition text appears before the recommendation’s rationale. AI discussion is collapsed by default when viewing evidence and can be reopened whenever needed. Darker text, clearer paragraphs, and more distinct spacing make definitions, findings, and applicability easier to read, with better use of large displays.

- **Source cards explain the findings before applying them to your decision.** A dedicated source summary now holds the substance of the evidence. The Skill asks the agent to describe the relevant population, study design, comparisons, and results, retaining the numbers and uncertainty needed for interpretation before explaining applicability. Summaries are separate from notes on which passages were checked, and substantive evidence is separate from project confirmation, migration, and save records. When preparation runs in parallel, each subagent owns a complete set of related questions, including source checks, proposal preparation, and self-review.

- **Research reviews include a deliberate handoff for literature research.** By default, the local agent checks project facts, prepares shared research questions, and returns control to you so you can arrange literature contributions from a web AI. It checks the contributed material, synthesizes it, and prepares the review only after you explicitly ask it to continue. You can also explicitly assign the entire round to the local agent.

This release also fixes the home page’s combined listing of projects on different governance versions, adds the browser tab icon, and corrects source links that included trailing citation punctuation.

### Installation and upgrades

**OppenCouncil-5.0.1.zip** is the complete bundle, including the workbench, skills, and optional MCP component. The wheel and tar.gz packages contain the Council Python component. See the [README](https://github.com/HaobinZhou/OppenCouncil#quick-start) or [Chinese README](https://github.com/HaobinZhou/OppenCouncil/blob/main/README.zh-CN.md#快速开始) for installation and update instructions.

Existing projects can stay on v3/v4. Software updates and project migrations are separate steps; when you want to change a project’s format, follow the [migration guide](https://github.com/HaobinZhou/OppenCouncil/blob/main/docs/migration.md).

---

## 简体中文

5.0.1 增加了直接在 Codex 对话中审阅、修改和确认口径的方式，也重新整理了网页的文献查阅和阅读布局。你可以在对话里逐组讨论，也可以打开网页，把口径与原文依据放在一起看；两边使用同一份项目记录。

### 重点更新

- **在 Codex 里完成口径审阅。** AI 仍先完成事实核查、文献评估和完整候选准备，再与你讨论。你明确授权后，Codex 可以保存讨论、修改候选、选择方案、确认口径、重新确认或撤回候选，网页也能看到对应记录。对话默认每轮一个关联组；只剩独立问题时，每轮最多三条，等你反馈后再继续。口径和需要你决定的内容放在前面，解释使用短句和清楚的分项。

- **口径和文献并排看，切换方案就切换依据。** 选择 A 时只显示 A 引用的依据，选择 B 时切换到 B 的依据。独立 F 和组内 F 都能使用完整的文献查阅区。引用编号由代码按当前审阅内容的首次引用顺序生成；点击编号即可定位依据，再打开原文。

- **把更多屏幕空间留给正在审阅的内容。** 页面压缩了顶部说明，组内支持逐条阅读和方案比较。口径正文排在推荐理由之前；查看依据时默认收起 AI 讨论，需要时可以手动展开。正文、文献发现和适用条件使用更深的文字、更清楚的段落与间距，大屏幕上的阅读区也更充分。

- **文献卡先讲研究发现，再讲它与当前决定的关系。** 新增独立的来源摘要。Skill 要求说明相关研究的人群、设计、比较和结果，保留判断所需的数值与不确定性，再解释适用条件。原文核查位置与摘要分开，项目的确认、迁移和保存记录也与实质依据分开。多个问题需要并行准备时，每个子代理负责一组完整问题，完成查证、候选整理和自查。

- **科研审阅留出真正的文献交接。** 默认由本地 Agent 核查项目事实、整理共享问题，然后交回控制权，让你安排网页 AI 补充文献。收到你明确的继续指令后，本地 Agent 才核对资料、汇总并准备送审。你也可以明确指定由本地 Agent 完成整轮工作。

此外，修复了新旧治理版本的项目无法同时出现在首页的问题，补齐浏览器标签页图标，并修正了部分文献链接把句末标点带入地址的问题。

### 安装与升级

完整安装包是 **OppenCouncil-5.0.1.zip**，包含工作台、skills 和可选 MCP；wheel 和 tar.gz 是 Council Python 组件。安装与更新步骤见 [README](https://github.com/HaobinZhou/OppenCouncil#quick-start)／[中文版](https://github.com/HaobinZhou/OppenCouncil/blob/main/README.zh-CN.md#快速开始)。

已有项目可以继续使用 v3/v4。软件更新与项目迁移分别进行；需要转换项目格式时，按[迁移指南](https://github.com/HaobinZhou/OppenCouncil/blob/main/docs/migration.md)处理。
