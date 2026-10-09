<p align="center">
  <img src="council/oppencouncil/assets/logo.svg" width="72" height="72" alt="OppenCouncil Logo">
</p>

# OppenCouncil

**把与 AI 的项目讨论，变成可以审阅、确认和持续执行的项目规则。**

做科研、写软件或维护长期项目时，很多决定会散落在聊天记录里：采用哪个定义、遇到例外怎么处理、哪些方案仍有分歧、之前确认的规则是否已经修改。OppenCouncil 把这些内容放回项目，在浏览器里集中审阅，并让本地 AI 和通过 MCP 接入的 AI 使用同一份记录。

这里的「口径」是明确、可执行的项目约定。例如研究中的纳入条件和随访起点，或软件中的权限规则和失败处理方式。

## 可以用它做什么

- **集中审阅一轮问题**：让 AI 一次准备当前已识别的问题、具体方案和完整候选文本，逐项阅读后再一起反馈。
- **把相关决定放在一起**：同一个主题下比较完整组合；相互依赖的规则一起决定，每条规则仍有自己的版本。
- **持续讨论**：方案、讨论和候选正文支持 Markdown；建议、疑问和回复留在原话题里，方便下次继续。
- **明确什么已经生效**：讨论、候选与正式口径分开。表达偏好和保存草稿后，仍需审阅并确认完整文本。
- **保留修订历史**：确认后的规则有独立版本。打开修订时旧版继续有效，新版确认后替换；也可以取消修订。
- **在多个项目间切换**：一个本地站点提供项目目录，每个项目的记录保存在自己的目录中。

典型流程：

**说明目标 → AI 准备本轮问题与候选 → 网页比较和讨论 → 手动通知 AI 继续 → 确认正式口径 → 按口径推进项目**

工作台不会自动调用模型。使用本地 AI 准备内容、读取反馈并继续工作；如需让网页 AI 参与，可以加装可选 MCP。

## 选择适合项目的 skill

仓库包含两个可独立使用的 skill，以及它们共用的工作台：

| 组件 | 适合的用途 |
| --- | --- |
| **Oppen Project Steward** | 软件、工具、基础设施等长期项目。维护当前约定、交付物、验证记录和重要决策的来由。 |
| **Stepwise R Project** | 科学 R 分析项目。管理研究口径、分析脚本、结果与验收，保留可追溯的科研决定。 |
| **Council 工作台** | 在浏览器里比较方案、讨论、编辑候选和确认版本；两个 skill 共用。 |
| **OppenSteward-MCP（可选）** | 让支持 MCP 的 AI 客户端读取已授权项目、参与讨论和起草候选。 |

同一个项目沿用自己的治理 skill。已有 Stepwise R 项目可以直接使用工作台，无需改成 Steward；安装软件也不会自动迁移已有项目。

## 快速开始

### 1. 安装工作台和全局 skills

准备 [Git](https://git-scm.com/downloads)、[uv](https://docs.astral.sh/uv/getting-started/installation/) 和能使用本地 skills 的 AI 客户端。以下以 Codex 为例，在 macOS、Linux 终端或 Windows PowerShell 中运行：

```sh
git clone https://github.com/HaobinZhou/OppenCouncil.git
cd OppenCouncil
uv run --python 3.12 scripts/install.py --python 3.12 --skill-dir "$HOME/.agents/skills"
```

`uv` 会按需准备 Python 3.12。安装器创建 Council 的本地运行环境，并把两个 skill **以软链接方式**接入用户级全局目录：

```text
~/.agents/skills/
├── oppen-project-steward → <仓库>/skills/oppen-project-steward
└── stepwise-r-project  → <仓库>/skills/stepwise-r-project
```

[Codex 支持该目录及软链接](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills)。请保留克隆后的仓库目录；移动或删除它会使链接失效。安装成功后，在 Codex 的 skill 选择器中查找这两个名称；若尚未出现，重新启动客户端。

- **已有全局目录**：把 `--skill-dir` 改为客户端实际使用的位置。安装器未传此参数时仍使用 `~/.codex/skills`；旧安装请继续指定原位置，避免两处重复安装。
- **Windows**：创建目录软链接需要启用开发者模式或具备相应权限；安装器不会改用复制目录来代替。
- **发现同名目录或旧链接**：安装器会停止并保留它们，按 [已有安装迁移说明](docs/migration.md#已安装的-skill) 处理。

工作台不需要 Node.js、R 或模型 API key。R 是运行科研分析时的独立环境；AI 客户端和可选 MCP 的连接配置另行准备。

### 2. 让 AI 准备项目

在需要管理的项目目录中打开 Codex，选择适合的 skill，并说明目标。例如软件项目：

```text
使用 $oppen-project-steward 管理当前项目。

我准备实现一个团队文件共享工具。请先读取已有约定和讨论，
一次列出当前需要确定的规则，把需要联动决定的内容组织成主题。
每个方案写清具体做法、实际影响和代价，并准备完整候选口径。
准备好后打开 OppenCouncil，返回浏览器可以访问的链接。
```

科学 R 项目将第一行改为 `使用 $stepwise-r-project 管理当前项目`，并描述研究目标、现有数据和准备开展的分析。

已有项目先由 AI 检查并接入相应 skill；不要为打开网页而覆盖项目入口或已有记录。工作台识别原生 Stepwise R 或 Steward v3/v4 项目，普通文件夹需要先完成项目准备。

### 3. 打开并审阅

AI 可以直接返回工作台链接。也可以回到 **OppenCouncil 仓库根目录**，手动打开已准备的项目：

```sh
uv run --project council oppencouncil open /absolute/path/to/project --port 5322
```

将路径换为实际项目的绝对路径。命令会登记项目，启动或复用本地服务，并返回访问链接。在系统浏览器中打开链接即可。默认地址使用 `127.0.0.1:5322`，首次访问设置站点密码，以后输入密码登录，无需用户名。密码随站点保留，服务重启不会清除。

按以下顺序审阅：

1. 阅读主题中的方案比较和候选全文。最多同时展示两个方案，其余可从选择菜单切换。
2. 点击「倾向此方案」会将偏好填入讨论输入框；可补充意见，点击「保存讨论」才提交。
3. 有分歧时继续留言。候选可以编辑并保存，也可以让 AI 根据反馈重新起草。
4. 完成一轮后，手动告诉 AI「我已在 Council 保存反馈，请读取并继续」。也可用「复制交接说明」生成并复制说明，粘贴到 AI 对话中。
5. 候选已经完整、准确且没有待解决的前序问题时，确认该条或整组口径。之后的项目工作按正式版本执行。

如果 AI 发现新问题，可以追加下一轮。保存成功表示内容已写入项目；正式确认也需要审阅者判断文字是否足以指导实际工作。

## 日常使用

以下命令均在仓库根目录运行：

```sh
# 查看服务地址与状态
uv run --project council oppencouncil status

# 打开另一个已准备的项目
uv run --project council oppencouncil open /absolute/path/to/another-project

# 将一个项目移出站点目录，保留项目文件
uv run --project council oppencouncil disable /absolute/path/to/project

# 停止工作台服务
uv run --project council oppencouncil stop
```

关闭浏览器标签页不会停止服务。再次 `open` 会复用站点；电脑休眠、关机或网络转发断开时，远程页面不可用。

### 从另一台电脑访问

服务运行在项目文件所在的电脑上。可以通过 SSH 转发、FRP 或 HTTPS 反向代理访问。先完成首次密码设置，再分享转发后的项目链接；审阅者输入同一个站点密码。`--public-origin` 用来生成外部地址，本身不会创建网络转发。

端口、外部地址、免密访问和独立站点目录的配置见 [Council 部署说明](council/README.md#远程访问)。

### 让网页 AI 参与（可选）

加装 MCP 环境：

```sh
uv run --python 3.12 scripts/install.py --with-mcp --no-skills --python 3.12
```

然后按 [MCP 接入指南](mcp/README.md#接入与运行) 配置项目允许列表、连接方式和读写权限。AI 可以读讨论、追加问题和修改候选；正式确认仍由人在工作台完成。网页登记和 MCP 授权是独立的，只打开工作台不会自动向 MCP 开放项目。

### 只安装 skills

如果暂时只需要项目管理流程：

```sh
uv run --python 3.12 scripts/install.py --skills-only --skill-dir "$HOME/.agents/skills"
```

以后需要网页审阅时，再运行快速开始中的完整安装命令。

## 数据保存在哪里

口径、候选和讨论保存在**被管理项目自己的 `Freeze/` 目录**中，采用可读 JSON。网页、CLI 和 MCP 共用这些记录；正式口径以已确认的当前版本为准，其他文档引用它或生成只读展示。

软件安装目录保存运行环境和站点登记。默认源码安装使用 `council/projects.local.json` 登记项目，`council/.runtime/` 保存服务状态。可通过 [站点目录设置](council/README.md#站点目录) 把这些运行文件放到别处。

备份项目时应包含完整的项目目录及 `Freeze/`。是否将项目记录纳入 Git，由各项目的规则决定；安装器不会将其复制到这个软件仓库。通过 MCP 使用云端 AI 时，获准读取的内容会发送给该客户端。

## 更新

在仓库目录中运行：

```sh
git pull --ff-only
uv run --python 3.12 scripts/install.py --python 3.12 --skill-dir "$HOME/.agents/skills"
```

使用其他 skill 目录时沿用原来的 `--skill-dir`；安装过 MCP 时加上 `--with-mcp`。软链接会指向更新后的源码，无需重新复制 skills。如果 Git 提示本地修改或历史分叉，先处理这些修改再更新。

更新完软件，按原有端口和访问配置重启正在运行的服务。已有项目记录继续保留，历史项目的迁移见 [迁移说明](docs/migration.md)。

## 更多说明

- [Council 使用与部署](council/README.md)：端口、远程访问、数据与正式版本。
- [MCP 接入](mcp/README.md)：让网页 AI 访问指定项目。
- [Oppen Project Steward](skills/oppen-project-steward/SKILL.md)：一般项目的完整工作流程。
- [Stepwise R Project](skills/stepwise-r-project/SKILL.md)：科学 R 项目的完整工作流程。

遇到问题时，可在仓库的 Issues 中附上系统版本、执行命令和错误信息；请先移除访问链接中的凭据及项目私有内容。

<details>
<summary>参与开发与运行测试</summary>

在仓库根目录安装开发依赖。测试还需要 Node.js 22+：

```sh
uv run --python 3.12 scripts/install.py --with-mcp --no-skills --dev --python 3.12
uv run --python 3.12 scripts/verify.py
uv build --project council
```

只验证 Council 和 skills 时，安装时省略 `--with-mcp`，验证时使用 `scripts/verify.py --core`。CI 配置覆盖 macOS、Linux 和 Windows。

</details>

## 许可证

[MIT License](LICENSE)。可以使用、修改和分发，请保留许可证声明。随附第三方库的许可证见其所在目录。
