<p align="center">
  <img src="council/oppencouncil/assets/logo.svg" width="72" height="72" alt="OppenCouncil Logo">
</p>

# OppenCouncil

[English](README.md)

**Vibe Coding，不积累知识债**

有了 AI Agent，即使一行代码都不看，项目也能往前推进好几周。但它每替你做一个决定，你对自己项目的了解就少一点。它可能自行决定排除哪些记录、失败后怎样重试，或什么样的客户算重复。这些事在当时看起来都不算大事，却会不断累积，直到你说不清自己的项目到底在做什么、为什么这样做，或改一处会影响哪里。这就是知识债。只要项目持续得足够久，无论是科研分析、软件、数据流水线还是内部工具，都可能积累这种债。

OppenCouncil 让你参与这些决定，而不必回头钻进代码里。凡是影响项目行为的规则，都会写成一条口径：用大白话说明，由你确认，版本保存在项目里。AI 按口径工作，测试据此检查代码。AI 想改口径，只能先提出修订，等你确认后才生效。决定背后的来龙去脉也会留下。项目发生重大转向时，原因会写进 Memory：试过却失败的方法、主动放弃的设计，或受现实条件所迫做出的折中。几个月后，无论是你还是新会话里的 AI，都不用重新摸索当初为什么这么做，也不容易再走回已经试过的死路。如果 AI 发现不该自行定夺的问题，比如代码悄悄丢掉数据，或两个脚本的处理相互矛盾，就会把它记入调查事项（Attention），而不是埋在聊天记录里。问题会一直留在那里，直到解决、排除，或形成一条正式口径。

每条推荐都有依据：核查过的来源、测试结果、实际测量，或你自己数据中的事实。如果推荐来自通行做法，你能看到这种做法的出处。如果方案之间确实存在差别，你能看到每个选择会给当前项目带来什么变化。通过 MCP 接入的 AI 助手也可以补充证据，由本地 Agent 核对后再交给你。

这些事不必占满你的一天。所有待处理的决定都放在同一个网页里，可以一次集中看完。等你打开时，AI 已经排除了不适用的问题，也查清了代码或数据能够回答的事。剩下的分成四类：需要选择、快速确认、等待补充信息，以及已经排除的事项。你留言、修改或确认，再告诉 AI 继续。它只接着处理有变化的部分，更新页面，等你下一轮审阅。

## AI 先做什么，你再看什么

附带的 Skill 要求 AI 在向你提问前，先做几件事：

1. **检查问题是不是真的存在。** 队列里没有性别缺失，就不用问“性别缺失怎么填补”。但如果“没缺失”是因为上游脚本未经确认就删掉了这批人，那要查的是这个删除动作。
2. **把已有事实和决定找回来。** 数据分布、现有代码、之前确认过的口径，应先核对清楚，不用让你重复回答。
3. **有通行做法时，给推荐答案和出处。** 说明为什么适用于当前项目，也写清究竟查到了全文、摘要，还是只有间接材料。证据同样充分的替代方案仍可选。
4. **遇到真实取舍，再把影响摆出来。** 比如比较 6 个月和 12 个月回看期，除了讲方法差异，还应核对会影响多少人、哪些分析需要重做，再交给你决定。

工作台把事项分成几类，方便先看需要你参与的部分：

| 分类 | 里面是什么 | 怎么处理 |
| --- | --- | --- |
| **需要选择** | 有多个说得通的方案，或需要偏离通行做法 | 看影响和代价，决定采用哪种 |
| **快速确认** | 有依据支持的推荐方案 | 核对推荐理由和完整候选文字后确认 |
| **补查中／阻塞** | 证据不够，或还缺信息 | 让 AI 继续查；必要时补充背景 |
| **已排除** | 查过后认为不需要推进的问题 | 保留排除理由，发现新情况再讨论 |

日常使用的节奏是：

```text
交代任务 → AI 查证并准备候选 → 在网页里审阅、批注或确认 → 叫 AI 继续 → 按正式口径推进
```

工作台本身不会在后台调用模型。网页里保存反馈后，回到 AI 会话说一声，或把“复制交接说明”的内容贴过去。AI 再读取新反馈，接着处理受影响的部分。

## 快速开始

### 1. 安装

准备好 [Git](https://git-scm.com/downloads)、[uv](https://docs.astral.sh/uv/getting-started/installation/) 和支持本地 skills 的 AI 客户端。下面以 Codex 为例，命令适用于 macOS、Linux 和 Windows PowerShell：

```sh
git clone https://github.com/HaobinZhou/OppenCouncil.git
cd OppenCouncil
uv run --python 3.12 scripts/install.py --python 3.12 --skill-dir "$HOME/.agents/skills"
```

也可以从 [Releases](https://github.com/HaobinZhou/OppenCouncil/releases/latest) 下载 `OppenCouncil-5.0.0.zip`，解压到固定目录，在该目录运行上面的安装命令。

安装器会准备 Python 环境，并把统一 skill 和两个兼容入口链接到全局目录：

```text
~/.agents/skills/
├── oppencouncil          → <仓库>/skills/oppencouncil
├── oppen-project-steward → <仓库>/skills/oppen-project-steward
└── stepwise-r-project    → <仓库>/skills/stepwise-r-project
```

新项目直接用 `oppencouncil`。两个旧名字继续可用，helper 会按项目原有标记选择对应实现。

因为用的是软链接，请保留克隆下来的仓库目录。Windows 创建目录软链接需要开发者模式或相应权限。已有安装继续使用原来的 skill 目录；安装器不传 `--skill-dir` 时默认使用 `~/.codex/skills`，不要无意间装到两个位置。遇到同名目录或旧链接，按[迁移指南](docs/migration.md#已安装的-skill)处理。

工作台不需要 Node.js、R 或模型 API key；运行分析和使用 AI 客户端所需的环境另行准备。

### 2. 初始化或接入项目

在项目目录打开 AI 客户端。以科研项目为例，可以这样交代：

```text
使用 $oppencouncil 管理当前项目，这是一个科研项目。

研究问题是：……；数据在 Data/raw/……。
请先检查现有数据、代码和已确认的口径，找出真正需要我决定的问题。
能查清的事实自己查清，有通行做法的给推荐答案和出处。
准备好后打开 OppenCouncil，把链接给我。
```

软件或一般工程项目，把第一句改成“这是一个普通项目”即可。已有代码的项目先检查现状，再按接入计划处理；如果已经是 v3/v4 项目，继续使用原流程，是否迁移单独决定。

### 3. 在浏览器里审阅

AI 准备好内容后会返回项目链接。你也可以在 OppenCouncil 仓库根目录手动打开已接入的项目：

```sh
uv run --project council oppencouncil open /absolute/path/to/project --port 5322
```

新服务默认使用 `http://127.0.0.1:5322`。已有部署沿用自己的端口和站点目录，以 `oppencouncil status` 返回的地址及实际启动配置为准；使用独立站点目录时，查询状态也要带上相同的 `--directory`。首次访问设置站点密码，以后输入同一个密码登录。

点开一条口径，可以查看方案、依据、候选全文和讨论。你可以留言追问、修改候选文字，也可以编辑模拟表格的表头、行列和脚注。改完先保存，再用“复制交接说明”通知 AI 继续。

**保存草稿不等于正式确认。** 确认前旧版口径仍然生效；候选文字审阅完整后，点击确认才成为新的正式版本。后续工作以这个版本为准。已登记的依据发生变化时，系统会提示复核；如果正文不变，就在当前版本追加重新确认记录，不为此另造一个版本。

## 科研项目和普通项目有什么不同

项目类型与用 R 还是 Python 无关。两类项目用同一个工作台，主要区别在于需要说明的依据，以及正式产出的组织方式。

| 内容 | 普通项目 | 科研项目 |
| --- | --- | --- |
| 决策依据 | 代码约束、测试、运行测量和实际需求 | 除数据事实外，涉及方法选择时要说明文献依据、证据强弱及偏离通行做法的理由 |
| 正式产出 | 通常登记在 `Deliverables/` | 正文和补充材料要用的表、图等登记在 `Results/`，绑定已确认的产出规格 |

科研项目的常见目录如下。已有项目保留自己的布局，例如原来的 `R/` 不必改名成 `Scripts/`。

```text
项目根目录/
├── Scripts/          # 带编号的分析脚本；可以使用 R、Python 等语言
│   ├── 01_import.R
│   ├── 02_cohort.R
│   ├── 03_table1.R
│   └── functions/    # 共享函数，不要求编号
├── Data/
│   ├── raw/          # 原始输入，保持只读
│   └── derived/      # 脚本生成的清洗数据与中间队列
├── Results/          # 正文和补充材料使用的正式表、图等
├── Releases/         # 明确要求时才生成的投稿、返修等快照
├── Explore/          # 探索性工作；放弃后可明确归档到 _archive/
├── Audit/            # 核查、诊断和验证记录
├── Freeze/           # 口径、依据、调查事项和讨论；图片副本在 assets/
└── Memory/           # 重大决定的因果背景，帮助后来的人和 AI 理解取舍
```

脚本允许重复编号；编号用于组织和阅读，不保证把所有文件按名字跑一遍就能复现。实际运行需要结合登记的生成脚本、依赖、原始输入和环境。

**正式图表先定规格。** 比如 Table 1 的表头、分组、连续变量用均值还是中位数，先用模拟数据做成候选表格给你看。确认后，真实产出才能按这份规格登记到 `Results/`。以后数据更新重跑，规格没变就沿用原确认；中间数据放 `Data/derived/`，核查输出放 `Audit/`。

想试新亚组或新算法，可以在 `Explore/` 中做。决定转成正式产出时，再补齐相应规格与登记。放弃的实验可以明确归档，日常读取不把归档内容当作当前工作。

投稿、返修或交接快照也按需生成。只有你明确提出请求，AI 才会先列出打包计划，再生成 `Releases/` 中的快照。它会纳入正式产出、相关脚本、口径、已分类的项目生成数据和环境记录；原始输入不进压缩包，以来源和哈希记录。快照可能很大，不是日常任务结束时的默认动作。详见[快照说明](skills/oppencouncil/references/releases.md)。

## 接入网页端 AI（可选，使用 MCP）

如果想让网页端 AI 帮忙查文献、补反例或做交叉复核，可以加装 MCP：

```sh
uv run --python 3.12 scripts/install.py --with-mcp --no-skills --python 3.12
```

然后按 [MCP 接入指南](mcp/README.md#接入与运行)配置允许访问的项目、连接方式和读写权限。打开 Council 网页不会自动给 MCP 授权。

网页 AI 能读取明确共享的项目简报、口径、讨论和证据，也能提交资料或留言。贡献会标为“外部 AI · 未经本地核查”，由本地 Agent 结合项目实际情况核对。

## 日常管理

以下命令均在 OppenCouncil 仓库根目录运行：

```sh
# 查看服务状态和端口
uv run --project council oppencouncil status

# 打开另一个已接入的项目
uv run --project council oppencouncil open /absolute/path/to/project

# 从站点目录移除项目，保留项目文件
uv run --project council oppencouncil disable /absolute/path/to/project

# 停止后台服务
uv run --project council oppencouncil stop
```

关掉浏览器标签页不会停止后台服务。跨设备访问可用 SSH 转发、FRP 或 HTTPS 反向代理；端口、外部地址和站点目录设置见 [Council 部署说明](council/README.md#远程访问)。

口径等记录跟着项目走，不集中存进软件仓库。站点目录保存 `projects.local.json`、认证和服务状态；MCP 使用自己的配置与授权状态。

## 从 v4 升级到 v5

**软件 5.0.0 和项目格式 v5 是两回事。** 可以先升级工作台和 skills，让现有项目继续留在 v4。两个旧 skill 名称仍可用，原有项目会交给保留的旧实现处理。

### 1. 更新软件，沿用原配置

在已有 OppenCouncil checkout 中运行：

```sh
git pull --ff-only
uv run --python 3.12 scripts/install.py --python 3.12 --skill-dir "$HOME/.agents/skills"
```

沿用原 skill 目录；以前装在 `~/.codex/skills` 就继续用它。安装过 MCP 时加 `--with-mcp`，随后按原来的方式重启 Council 和 MCP，保留站点目录、端口、项目登记、配置文件及 OAuth 授权。只下载源码，不会让正在运行的旧进程自动换成新版。

如果想让真实项目暂时留在 v4，到这里即可。ZIP 安装、早期独立仓库和复制式 skill 安装的处理方式见[详细迁移指南](docs/migration.md)。

### 2. 单独决定要迁移哪个项目

准备采用 v5 时，在选定项目的 AI 会话里说：

```text
使用 $oppencouncil 对当前项目执行 upgrade-v5 检查。
把迁移计划保存在项目外，给我看会改哪些文件、有哪些阻塞和遗留事项，先不要应用。
```

检查不修改项目。它会核对已连接的 Council／MCP 是否支持 v5，列出确切写入及前后哈希。原 Stepwise 项目默认作为科研项目，原 Steward 默认作为普通项目；需要改选类型时，在检查阶段指定。

也可以在软件仓库根目录手动生成计划。目标项目使用绝对路径；计划在项目外，父目录需存在，文件名不能已被使用：

```sh
uv run --project council python skills/oppencouncil/scripts/oppencouncil.py upgrade-v5 "/absolute/path/to/project" --check --plan "/absolute/path/outside-project/v5-plan.json"
```

看过计划、解决阻塞项，并明确确认迁移后，应用同一份计划：

```sh
uv run --project council python skills/oppencouncil/scripts/oppencouncil.py upgrade-v5 "/absolute/path/to/project" --apply --plan "/absolute/path/outside-project/v5-plan.json"
```

自定义站点或外置 MCP 配置时，检查和应用都要指定相同的 `--council-directory`、`--mcp-root`、`--mcp-config`，详见[完整命令](docs/migration.md#项目从-v3v4-迁移到-v5)。`--project-type` 只在检查时使用，应用从计划读取。输入或连接能力变化会拒绝旧计划，需要重新检查。

### 迁移后会怎样

原有口径及历史版本、候选、讨论、分组关系、Memory 和产出登记都会保留。未解决的 Attention 转为调查事项，保留原内容及阻塞含义；不用为了迁移先把它关闭。旧候选和未处理讨论，在首次继续工作时再核对接续状态。

迁移不会改 `R/` 目录名、重排脚本编号、搬动数据或重跑分析。旧未编号脚本、缺少规格的产出、待分类的数据等列在报告里，留待后续按需处理。项目的 Git 历史也不由迁移工具改写。

应用只对计划列出的文件做事务写入，恢复信息放在项目内的 `.oppencouncil-migration/`，不创建整个项目的大型副本或归档。中断后由 helper 检查并恢复；遇到冲突时保留现场，再按[恢复指南](docs/migration.md#失败中断与恢复)处理。

最后运行统一 helper 的 `index` 和 `validate`，再到原工作台核对记录。直接迁移支持原生 v3/v4 项目；更早的 v2 或非标准历史记录，先按原流程整理。

## 更多文档与开发测试

- [Council 使用与部署](council/README.md)
- [MCP 接入与权限](mcp/README.md)
- [详细迁移指南](docs/migration.md)
- [OppenCouncil Skill](skills/oppencouncil/SKILL.md)
- [V5 验收记录](docs/v5-acceptance.md)

提 Issue 时，请附上系统版本、命令和错误信息。

完整测试还需要 Node.js 22+：

```sh
uv run --python 3.12 scripts/install.py --with-mcp --no-skills --dev --python 3.12
uv run --python 3.12 scripts/verify.py
uv build --project council
```

只验证 Council 和 skills 时，安装省略 `--with-mcp`，验证使用 `scripts/verify.py --core`。

## 许可证

本项目采用 [MIT License](LICENSE)。随附第三方库的许可证见其所在目录。
