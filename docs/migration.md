# OppenCouncil 5.0.0 升级与项目迁移

## 先区分要升级的对象

| 目的 | 操作 | 是否改变项目治理格式 |
| --- | --- | --- |
| 使用 5.0.0 的工作台、MCP 和统一 skill | 更新产品源码、安装锁定依赖、接入 skill、重启原服务 | 否；已有 v3/v4 项目继续由原实现处理。 |
| 让某个旧项目采用 v5 调查、证据、产出规格等流程 | 对该项目单独执行 `upgrade-v5 --check`，确认计划后执行 `--apply` | 是；仅针对明确选定并获准迁移的项目。 |
| 从早期独立 Council／MCP／academic-skills 仓库改用统一仓库 | 按本文后半部分核对源码、链接和服务入口 | 本身不会迁移项目。 |

新建项目使用统一 `oppencouncil` skill，显式声明 `research` 或 `general`。旧项目不能通过重新 `init`、改名或手改版本标记来升级。统一 helper 与两个旧入口都会先识别原标记；调用名称和编程语言不会覆盖已有项目类型。

## 已有统一仓库只升级软件

在原 OppenCouncil checkout 中运行下列命令，沿用原 skill 目录；示例使用旧安装常见的 `~/.codex/skills`，如果原来安装在 `~/.agents/skills`，继续使用那个目录：

```sh
git pull --ff-only
uv run --python 3.12 scripts/install.py --python 3.12 --skill-dir "$HOME/.codex/skills"
```

已经安装 MCP 时，在安装命令中加 `--with-mcp`；仅安装 skill 时用 `--skills-only`。不要为更新临时更换安装目录，或覆盖本地修改／历史分叉。Git checkout 的受支持更新器也可用统一 skill 的 `scripts/update_skill.py --apply`，随后仍需运行产品安装器刷新依赖。

安装会接入 `oppencouncil`、`oppen-project-steward`、`stepwise-r-project` 三个名称。两个兼容入口不再各自维护完整的新规则，但保留旧项目的原 helper。源码和依赖更新后，按原有进程管理方式重启 Council 与已安装的 MCP，继续使用原站点、端口、外部地址、MCP 配置、项目允许列表及 OAuth 状态。

分别确认三件事：安装版本为 5.0.0；正在运行的服务加载了新版代码；原客户端仍能读取已授权项目。项目登记和权限不应因更新而扩大。**保留旧项目 v4 的用户无需执行后面的项目迁移步骤。**

ZIP 安装不具备 Git 快进更新能力：将新源码包解压到新的固定软件目录，按后面的“已安装的 skill”及“已运行的 Council 与 MCP”调整链接和服务入口，保留外置运行状态。不要把真实项目、凭据或运行目录复制进发布源码包。

## 项目从 v3/v4 迁移到 v5

### 1. 选择项目并确认连接

直接支持原生 Stepwise／Steward v3/v4 的两种布局，保留原注册入口位置。v2 或非标准旧 Markdown／Freeze 导入先使用原有流程完成语义整理；不要把旧记录标成 v4 来绕过检查。

先升级统一 skill 和 Council。如果项目已连接 MCP，也先升级对应 MCP。检查会探测已登记的 HTTP 服务；旧进程、不可用服务或不支持 v5 都会阻塞应用。stdio 探测启动的是新进程，不能证明已有客户端会话已经重载，需要重新连接客户端。没有 MCP 连接的项目不要求安装 MCP。

确认实际的 Council 站点目录以及 MCP 代码／配置位置。默认布局可以省略连接参数；自定义布局必须明确提供，避免探测到别的站点或一份空配置。期间暂停该项目的并发编辑，以便检查与应用面对同一份内容。

### 2. 只检查并保存计划

命令从 OppenCouncil 仓库根目录运行；Windows 可把路径替换为 `C:/...`。计划必须位于目标项目之外，父目录存在、文件名未使用，不能覆盖旧计划。

默认连接布局：

```sh
uv run --project council python skills/oppencouncil/scripts/oppencouncil.py upgrade-v5 "/absolute/path/to/project" --check --plan "/absolute/path/outside-project/v5-plan.json"
```

自定义站点且已配置 MCP 的示例（替换成实际路径；`--mcp-root` 指向包含 `run.py` 和 `.venv` 的 MCP 目录）：

```sh
uv run --project council python skills/oppencouncil/scripts/oppencouncil.py upgrade-v5 "/absolute/path/to/project" --check --plan "/absolute/path/outside-project/v5-plan.json" --council-directory "/absolute/path/to/existing-site" --mcp-root "/absolute/path/to/OppenCouncil/mcp" --mcp-config "/absolute/path/to/existing-mcp/config.local.json"
```

`--check` 不写项目，只输出并保存计划；有阻塞项时退出码为 2。重点核对：

- `root` 和 `project_type`：项目是否正确。默认 Stepwise 为 `research`，Steward 为 `general`；需要另选时，只在本次 `--check` 增加 `--project-type research` 或 `--project-type general`。
- `capabilities`：实际连接的组件是否支持 v5。
- `writes`：将写入的确切路径、前后哈希和大小。
- `blockers`：应用前必须解决的问题，例如旧治理状态冲突、未恢复事务或组件不支持 v5。
- `warnings`：需保留供后续处理的遗留事项，例如旧产出缺规格、数据来源待分类、旧未编号脚本、未整理实验。它们不会授权重新分析或改写科研决定。

未决 Attention 可以迁移，保留其原有阻塞含义；它影响对应后续工作的推进，不会仅因“尚未解决”就阻止迁移计划。

### 3. 明确确认后应用同一计划

默认连接布局：

```sh
uv run --project council python skills/oppencouncil/scripts/oppencouncil.py upgrade-v5 "/absolute/path/to/project" --apply --plan "/absolute/path/outside-project/v5-plan.json"
```

自定义连接必须使用与检查时相同的参数：

```sh
uv run --project council python skills/oppencouncil/scripts/oppencouncil.py upgrade-v5 "/absolute/path/to/project" --apply --plan "/absolute/path/outside-project/v5-plan.json" --council-directory "/absolute/path/to/existing-site" --mcp-root "/absolute/path/to/OppenCouncil/mcp" --mcp-config "/absolute/path/to/existing-mcp/config.local.json"
```

**不要给 `--apply` 再传 `--project-type`**：应用从计划中读取已选类型。如果检查后文件、计划或服务能力变化，应用会拒绝；重新生成新文件名的计划，审阅后再应用。不能通过手改计划哈希或删掉阻塞项强行执行。同一已成功计划重放不会再修改项目。

### 4. 核对结果并接续旧事项

```sh
uv run --project council python skills/oppencouncil/scripts/oppencouncil.py index "/absolute/path/to/project"
uv run --project council python skills/oppencouncil/scripts/oppencouncil.py validate "/absolute/path/to/project"
```

在原站点重新查看项目：正式口径的当前版本及历史、候选和讨论、Memory、Results／交付登记应仍可追溯。迁移为旧 Attention 创建调查事项，并补入工作流和反馈状态；旧候选／未处理讨论在首次接续时需要由 Agent 读取、核对并完成一次接续整理，不能把机械迁移当作讨论已处理。

数据、模型结果和分析脚本保持原位置，不重跑、不改方法、不替人确认。旧脚本不自动重编号；重复编号允许，旧未编号分析脚本列为遗留提示。旧产出登记保留，但缺失的 v5 规格不会凭空补齐，后续变更按已确认口径逐项接入。旧 Memory 内容保持不动，新条目字段规则见 [memory.md](../skills/oppencouncil/references/memory.md)。

## 失败、中断与恢复

检查和应用以确切输入与计划为边界。应用在目标项目同一文件系统的 `.oppencouncil-migration/` 暂存本次治理写入的恢复信息，不制作整个项目副本，不创建数据或模型归档。这是事务恢复信息，不是成功迁移后长期保留的完整项目备份。

| 遇到的情况 | 处理 |
| --- | --- |
| 计划文件已存在 | 保留旧计划，使用新的项目外文件名重新检查。 |
| 提示输入、能力或计划改变 | 重新检查并审阅，不直接复用过期计划。 |
| `RECOVERY_REQUIRED` 或迁移中断 | 保留事务目录，运行统一 helper 的 `validate` 触发恢复；再检查实际代际，重新生成计划。只读 `--check` 会报告待恢复，不自行改写。 |
| 恢复时发现后续人工改动或损坏的前像 | 保留冲突文件和日志，核对后单独修复；不要删除 journal 或覆盖后续改动。 |
| 已成功迁移但想回到 v4 | 当前没有一键降级命令。需要另行评估并恢复一致的原治理状态；不能只改标记、切换旧 helper 或回退软件就认为项目已降级。 |

事务恢复只处理本次声明的写入；项目迁移不重启服务、不改变站点登记、MCP 允许列表、OAuth 授权或权限。是否备份或归档大型科研项目由用户另行决定，不是自动迁移步骤。

以下保留从早期独立仓库转到统一产品时的操作说明。

## 源码归属

唯一维护仓库为 [HaobinZhou/OppenCouncil](https://github.com/HaobinZhou/OppenCouncil)。

| 原来源 | 新位置 |
| --- | --- |
| OppenCouncil 工作台 | `council/` |
| OppenSteward-MCP | `mcp/` |
| academic-skills/oppen-project-steward | `skills/oppen-project-steward/` |
| academic-skills/stepwise-r-project | `skills/stepwise-r-project/` |
| academic-skills/tests | `tests/integration/` |

公开仓库从统一产品的源码快照开始。早期开发历史保留在原仓库及本地，不随此次发布上传。本仓库包含软件、skills、文档和合成测试；不包含本项目的治理记录、Memory、Audit、实际项目口径、密码或运行配置。后续产品更新在本仓库维护。

## 已安装的 skill

1. 检查旧 checkout 的本地修改与未推送提交，先保留 Git 基线。不要用 reset 或批量删除处理它们。
2. 克隆新仓库，运行 `python3 scripts/install.py --check --replace-existing-links`，核对目标路径。
3. 原安装是符号链接时，运行 `python3 scripts/install.py --replace-existing-links`。仅替换链接，原源码和 Git 历史保留。加装 MCP 才使用 `--with-mcp`。
4. 原安装是复制目录时，安装器拒绝覆盖。先比较本地定制，将已确认的修改合并到新 checkout，再由用户选择旧目录的保留位置后安装链接。

旧 academic-skills 仓库中的迁移入口用于让既有更新器发现新位置，不再维护两份功能实现。统一 skill 与两个兼容入口的安装不改变所管理项目的治理类型、Memory、正式口径和讨论。

## 已运行的 Council 与 MCP

源码合并不要求立即切换服务。先安装并验收新 checkout，再安排一次受控重启；重启前后核对端口、项目登记及权限。

- Council：通过 `--directory /absolute/existing/site` 或 `OPPEN_COUNCIL_DIRECTORY` 指向原站点目录，直接复用 `projects.local.json`。停止旧进程后用新环境在相同目录启动，保持原 host、port、public-origin、认证方式和 legacy-project 设置。不要启动第二个独立登记表来替代旧站点。
- MCP：启动 `mcp/run.py --config /absolute/existing/config.local.json serve`，即使只使用 `.env` 也指定同目录的该路径。这样继续读取原 `.env`、项目列表和 OAuth 状态。已有进程管理器需把 Python/入口改为新 `mcp/` 路径；不要并行启动占用同一端口的实例。
- `OPPEN_SKILL_ROOT` 若显式指向旧源码，改为新仓库的 `skills/`；未设置时优先读取新仓库自带技能。权限和项目允许列表独立保留。
- 冻结记录始终位于研究项目中，不随软件迁移。原有 Memory 文件保持不动。

安装和验收不会读取或打包已有服务的密钥、项目列表和科研数据。旧源码、运行配置和 Git 历史可以继续保留；是否归档由用户另行决定，安装、更新和项目迁移均不自动归档。
