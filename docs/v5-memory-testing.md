# Decision Memory 验证记录

2026-10-14。范围是已确认的 Memory 合同、两种旧格式兼容和九项独立前向评测；不是完整 v5 验收。

## 实际文本和程序检查

`skills/oppencouncil/SKILL.md` 的完整 Decision Memory 段与审阅附件逐字一致，单一文本 SHA-256 为 `a0e027784e6c9188777bf668c903726749fa623b2c1266d62da085428031f274`。确认的四处修订均在实际文件中。`memory.md` 保留科研项目必填 basis、普通项目可选、两套旧字段读取、关系目标必须 active、两个数组不得重叠，以及 helper 管理 ID、状态和反向链接的约束。

依 OPP-20，旧 helper 主动 AST 基线现只锁定 Memory 函数及其记录类型、字段定义：Steward 20 个节点，Stepwise 14 个节点。节点从 4.3.1 提交 `a871bea87add686eece05ac6ac28c6e58c7ea869` 提取，并与当前 legacy 文件逐项比对相同后生成。原整体哈希作为来源记录保留；没有用改变后的 Memory 语义重置基线。

本轮检查：

- 共享 Memory 的真实文件测试：72 passed，覆盖两种旧格式、两种布局、独立项目类型、basis 校验、关系维护、原文保持和事务恢复。
- Steward Memory/Attention 及安装测试：34 passed；加入独立 Skill 导入回归后，安装测试为 17 passed。
- 三个名称的 helper 路由测试：18 passed。
- Skill scaffold 校验通过；文档摘录与实际段落一致；`git diff --check` 通过。

## 九项独立前向评测

每项使用一个无父对话的独立 Agent，分配不含含义的临时目录。Agent 只收到真实任务形式的请求、Skill 快照和合成事实，不收到评分规则、预期结果或其他案例。所有写入留在各自临时目录。主 Agent 逐项读回保存内容、核对原记录和预期行为；确定性检查不代替语义复核。

| 场景 | 实际观察 |
| --- | --- |
| 故障促成重大架构改变 | 保存一条，连接进程死亡后的确认歧义与持久化回执决定 |
| 常规修错，Git 足以解释 | 不新增 Memory |
| 项目规模下执行不安全 | 保存一条，连接内存与 spill 问题和存储、并发方向调整 |
| 任务结束 | 不新增 Memory |
| 科研诊断改变分析策略 | 保存一条，保留比例风险假设失败促成时变效应策略的因果背景 |
| 同一决定跨多轮和提交 | 只保存一条，没有按轮次或提交拆分 |
| 原假设被证伪 | 使用 invalidates；旧条目状态、反向链接正确，正文及 basis 保持 |
| 后来改变方向 | 使用 supersedes；原事实仍被保留，没有误用 invalidates |
| Council 已保存完整理由 | 读回现有 F，不新增 Memory，F 内容保持 |

科研案例的新条目均有 basis。两个关系案例的旧条目 ID、实质内容和原 basis 保持，状态和反向关系由实际 helper 更新。九个项目的受管基线均有效。

首批两个正例暴露了入口导入问题：独立复制的 `oppencouncil.py` 遮蔽同名已安装包，Agent 先用 `-P` 完成任务。已在入口移除自身脚本目录的导入优先级，增加不带 `-P` 的真实子进程回归；后续正例通过普通调用完成。因此九项语义结果符合预期，但不能把首批说成无故障的一次成功。

详细摘要和产物校验值见 [评测结果](../tests/evals/results/memory-forward-20261014.json)。原始合成项目、输入、提交 payload 和 Agent 交接文件保存在 `/private/tmp/oppencouncil-memory-forward-20261014-r03/`，不复制到产品源码。临时文件不是长期归档。

## 覆盖范围和复现

每项只运行一次，事实是给定的合成交接材料；没有验证科研原始数据或外部文献判断。读取文件清单由 Agent 报告，文件字节数和按空白分词的数量由评测器测量：只读入口的三个负例为 363 词；读取入口和 Memory 参考的六个正例为 927 词。这不是模型 token 数或完整工具调用轨迹。

本批没有执行 4.3.1 同场景比较或逐条删除规则评测，不能据此宣布普通运行时规则全部准入。Memory 原文按已确认合同保持；其他规则、六个阶段和产品验收的后续证据见 v5-acceptance.md。

准备新的一组隔离案例：

```sh
council/.venv/bin/python tests/evals/memory_fixture.py /absolute/new/temporary-directory
```

将每个目录的 `request.md` 分别交给独立评测 Agent，评分规则和顶层 manifest 仅交评测者。执行后读回结构检查：

```sh
council/.venv/bin/python tests/evals/inspect_memory_runs.py /absolute/new/temporary-directory/manifest.json --output /absolute/observations.json
```

随后按 `skill_decisions.json` 的 rubric 复核实际条目和行为；脚本不会自动判定语义通过或修改预期结果。
