# 迁移到统一 OppenCouncil 产品

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

旧 academic-skills 仓库中的迁移入口用于让既有更新器发现新位置，不再维护两份功能实现。更新两个 skill 不改变所管理项目的治理类型、Memory、正式口径和讨论。

## 已运行的 Council 与 MCP

源码合并不要求立即切换服务。先安装并验收新 checkout，再安排一次受控重启；重启前后核对端口、项目登记及权限。

- Council：通过 `--directory /absolute/existing/site` 或 `OPPEN_COUNCIL_DIRECTORY` 指向原站点目录，直接复用 `projects.local.json`。停止旧进程后用新环境在相同目录启动，保持原 host、port、public-origin、认证方式和 legacy-project 设置。不要启动第二个独立登记表来替代旧站点。
- MCP：启动 `mcp/run.py --config /absolute/existing/config.local.json serve`，即使只使用 `.env` 也指定同目录的该路径。这样继续读取原 `.env`、项目列表和 OAuth 状态。已有进程管理器需把 Python/入口改为新 `mcp/` 路径；不要并行启动占用同一端口的实例。
- `OPPEN_SKILL_ROOT` 若显式指向旧源码，改为新仓库的 `skills/`；未设置时优先读取新仓库自带技能。权限和项目允许列表独立保留。
- 冻结记录始终位于研究项目中，不随软件迁移。原有 Memory 文件保持不动。

安装和验收不会读取或打包已有服务的密钥、项目列表和科研数据。旧仓库归档应在新仓库发布、入口可用并通过 CI 后进行；运行配置和已安装旧 checkout 可继续留在本机直到完成服务切换。
