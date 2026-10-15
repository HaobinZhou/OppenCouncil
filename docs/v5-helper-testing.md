# 统一 helper 的开发检查

当前入口为 worktree 中的 `skills/oppencouncil/scripts/oppencouncil.py`，使用 Council 的 Python 环境。此文是开发验证说明；运行中的已安装 checkout 保持 v4。worktree 中的两个旧 helper 已变成薄入口，新项目进入 v5，已有项目按原版本分派。

## 已接入的操作

```text
init TARGET --project-type research|general [--layout root|namespace]
adopt TARGET --check [--project-type TYPE --input PAYLOAD.json]
adopt TARGET --apply --project-type TYPE --input PAYLOAD.json [--layout root|namespace]
result TARGET --input PAYLOAD.json [--replace]
deliverable TARGET --input PAYLOAD.json [--replace]
data register TARGET --input PAYLOAD.json
memory add TARGET --input PAYLOAD.json
memory index TARGET
memory read TARGET --id M-NNNN
project-type TARGET [--set research|general --reason TEXT]
index TARGET
validate TARGET
review list TARGET [--offset N --limit N --actionable]
review raise TARGET --input PAYLOAD.json [--request-id ID]
review resolve TARGET --id I-NNNNNN|A-NNNN [--reason TEXT --conclusion fact_lookup|covered|not_applicable]
canonical TARGET --topic KEY --path PATH --verification PATH [--section SECTION --status STATUS --replace]
contract-audit TARGET --topic KEY --source PATH --risk-reason TEXT
contract-audit TARGET --topic KEY --input PAYLOAD.json
audit promote TARGET --stage KEY --input EXTERNAL_DIRECTORY
audit recover TARGET --stage KEY
scripts renumber TARGET --check --input INPUT.json --plan PLAN.json
scripts renumber TARGET --apply --plan PLAN.json
scripts rename-directory TARGET --check --input INPUT.json --plan PLAN.json
scripts rename-directory TARGET --apply --plan PLAN.json
explore index TARGET
explore create|update|archive|promote TARGET --check --input INPUT.json --plan PLAN.json
explore create|update|archive|promote TARGET --apply --plan PLAN.json
release create TARGET --check --input INPUT.json --plan PLAN.json
release create TARGET --apply --plan PLAN.json
release verify TARGET
upgrade-v5 TARGET --check|--apply ...
```

初始化要求新目录；现有普通项目用接管，已有治理标记的项目用显式迁移。科研类型默认根布局，普通类型默认命名空间布局；两者都可以显式选择另一种布局。重复初始化同一类型和布局不改文件。接管检查只读；实际接管只建立登记与受管基线，已有源码、根文档和产出不搬迁。输入 JSON 保留在原位置。

接管载荷保留旧的三个字段：`role_mappings`、`initial_canonical_registrations`、`initial_deliverable_registrations`。可用空对象和空数组。显式角色可包括 Scripts、Source、Data、Results、Deliverables、Explore、Releases、Audit；接管时映射目录必须已存在，区域不能重叠。原有登记的 ID、路径与列保持不变，新增溯源信息放入同一登记文件的元数据。

产出也接受旧式 `--id`、`--path`、`--kind`、`--audience`、`--producer` 参数。科研单项产出另用 `--specification` 读取绑定 JSON；输出组使用完整载荷，为每个实际成员提供 `member_specifications`。绑定字段为 `question_id`、`version`、`text_sha256`，只接受当前已由人类确认的 `output_specification`。正文只存在 Council，不复制到登记表。

普通项目沿用 Deliverables 的格式、生产者和受众规则。科研新产出由任意语言的编号脚本生成，面向 publication 或 formal-review。迁移或显式接管时已有的科研产出可以缺少规格，此后原登记的重算只提示；改变登记或声明结构变化时必须补已确认规格。文件内容的科学含义及与规格的逐元素一致性仍需要 Agent 读回核对，登记检查不宣称已经完成这一步。

数据登记字段是 `path`、`kind`、`version`，另加原始输入的 `source` 或派生数据的 `producer`。helper 记录当前 SHA-256 和大小；`raw`、`derived` 目录与声明必须一致，科研派生数据生产者须为编号脚本。分类登记不移动数据。相同登记重复执行不改变受管基线。

## 脚本与检查

重新编号输入示例：`{"order": ["R/import.R", "R/model.py"], "start": 1, "step": 10}`。`order` 必须包含所有分析脚本，可显式加入其他语言；共享 functions/config 等子目录不编号。示例会产生 `01_import.R`、`11_model.py`。目录改名输入为 `{"to": "Scripts"}`，原路径从角色登记读取。普通项目不执行科研编号操作。

检查只读，计划保存在项目外。应用重新计算并核对计划；源码、登记、关联引用或脚本清单变化都会要求重新检查。操作更新 Results 生产者、Canonical 路径、F 的验证路径和当前文本文件中的字面路径引用，并保留文件执行权限与目录权限。计划列出文件映射、读写哈希及引用改动路径；动态构造的路径仍需 Agent 对照代码检查。正式正文、历史版本、Memory 和旧审计记录不改写。路径变更记录保存在项目登记中。

文件移动、原目录移除、登记更新和基线变更在同一个持久事务中完成。失败或进程退出后可恢复原目录和字节；成功后重复应用同一计划不再修改项目。验证测试实际执行了两步 Python 分析链，并在两种布局中核对了改名后的 Results。

`index` 返回类型、角色、口径、产出、Memory 摘要及有分页标记的工作索引；`review list` 复用工作索引。基础 `validate` 已检查受管基线、Memory 关系、口径/验证路径、Council 存储、产出登记、脚本编号与 Explore 引用、数据溯源、Audit current 拓扑及未知区域文件。已有未编号脚本在迁移/接管时登记为遗留项并提示；新出现的未编号脚本报错。归档实验内容不作为当前验证输入读取。旧函数/模块审计按只读历史保留。

## 口径验证、审计及调查兼容命令

`canonical` 对普通项目继续登记唯一 owner、当前状态及验证文件，移动 owner 需要 `--replace`。科研新定义只接受已有的人类确认 F，参数为 `--path Freeze/questions/F-NNNNNN.json --section definition`；测试路径直接追加到 F 的 `verification_tests`，不复制正文或创建另一张科研 Canonical 表。旧 Markdown owner 保持可读，迁移后的含义采纳另行处理。

高风险检查用 `contract-audit`（`module-audit` 为别名）先绑定源文件和风险，再提交完成载荷。科研载荷为 `summary`、`checks`、`verification`、`limits`；`checks` 是非空、去重的可执行检查文件路径数组，其余字段为简短说明及实际检查结果。普通项目保留原四字段 `purpose_and_risk`、`contract`、`edge_cases_and_verification`、`known_limits`。新记录写入 Audit/Contracts 的 `v5_` 文件，旧模块和函数审计不改写；不恢复 function-audit 写入口。validate 检查未完成记录、源文件变更及科研检查文件变更。源码哈希不证明测试已运行，填写 verification 前仍须实际执行检查。

`audit promote` 从项目外目录分块复制证据，读回 SHA-256、大小和完整目录清单，再与登记及基线同次提交。成功替换整个 `current/`，包括移除旧文件与空目录；输入目录保留。失败或进程退出后恢复原树。`audit recover` 只识别旧 helper 的失败暂存名称；先把字节及恢复清单持久保存到系统临时目录并读回，再事务性移除残留。未分类文件或与源码、Data、产出、口径或验证文件重叠的残留会报错并保留。命令返回外部恢复路径，既有 current 不参与残留清理。

`review raise` 兼容完整旧 Attention 载荷，保存全部事实并将 blocking 转为调查阻塞；也接受新调查载荷 `title`、`why`、`dedupe_key` 和可选 `blockers`。`attention` 是同一命令的别名。旧 `A-XXXX` 在迁移后解析到对应调查 ID；`review resolve` 只关闭调查，不处理 F/B，也不重写旧 Attention 文件。未读反馈与未决事项需要先经 work_commit 处理，不能随关闭操作丢弃；`--expected-revision` 可用于锁定已读版本，旧调用未提供时读取当前版本。重复 raise 有稳定请求指纹，重复 resolve 不追加关闭记录。原始载荷文件不删除。

## 实验区与本地快照

实验创建输入为 `{"slug":"model-check","question":"要试什么"}`。helper 分配 `EXP-NNNNNN` 和 `Explore/001-model-check/experiment.json`。更新可以登记本实验内的 `scripts`、`outputs` 路径和 `in_progress`／`retained` 状态。归档输入含 `id`、`conclusion`；整个实验移至 `Explore/_archive/`，索引保留问题、状态和结论。默认索引与校验不读取归档实验内容。转正输入另含 `result_ids`，要求对应正式产出已登记、已关联人类确认的规格，并由编号脚本生成；转正操作本身不自动合并实验代码或代替人类确认。

快照只用于本地 Agent 收到的明确人类请求。`human_request` 字段记录原请求；该字段不是允许 Agent 自行决定打包的授权机制。创建输入还需 `purpose`、`label` 和实际核实的 `environment`（`languages`、`packages` 两个版本映射）。purpose 支持 submission、revision、preprint、presentation、collaborator、other。可用 `article_numbers` 映射产出 ID 到文章编号；编号只进入快照清单。可用 `environment_files` 附上现有环境记录。

检查只读，生成项目外计划，列出打包文件、输入哈希、未压缩大小和原始输入排除量。应用时重新核对计划，分块生成 ZIP 并逐成员读回校验，再将 ZIP、索引、登记和忽略规则一起提交。ZIP 位于 `Releases/日期-用途-序号.zip`，重复用途生成新文件，旧文件不覆盖；创建后设置只读权限。ZIP 内容包括当前 Results、脚本及共享函数/配置、绑定的完整 F 记录及依赖和不可变示例图、本项目产出的全部已分类 Data。原始输入只在清单记录来源、版本、大小与 SHA-256，不进入包体。清单另含 Git 提交、dirty 标记、环境版本、规格绑定和生成时间。

所有 Data 文件必须先分类；缺少分类时拒绝打包，不猜测原始输入与派生数据。旧 Results 缺规格时继续允许快照，清单明确标记。`Releases/index.json` 是可纳入 Git 的派生校验索引，ZIP 加入忽略列表；如果现有忽略规则会隐藏索引，检查报错，不改写那些既有规则。`release verify` 与 `validate` 检查归档及其索引丢失、篡改和 ZIP 内部清单/成员不一致。工具不自动提交 Git，也不上传快照。

快照的字节校验不代替科研内容、生成溯源和规格一致性的读回。验收夹具实际解包快照，补回校验值匹配的原始输入后，按编号重新执行 Python 脚本并重建相同 Results；真实项目上的语义验收仍单列。

## 当前验证及剩余边界

`test_audits_v5.py` 覆盖两种类型和两种布局的口径登记、科研简化审计、普通四字段审计、整树替换、源文件漂移、外部恢复副本与进程退出回滚。`test_review_v5.py` 覆盖旧 payload、blocking、A 到 I 的定位、旧记录不变、关闭前反馈检查和真实 CLI。

`test_bootstrap_v5.py` 覆盖四种类型／布局组合、只读接管检查、旧根文档保持、注册冲突、实际命令行和初始化中断恢复。`test_outputs_v5.py` 覆盖正式规格绑定、组成员、旧 Results 重算、数据分类和注册事务。`test_project_transaction.py` 覆盖原有进程崩溃恢复，并检查新增目录回滚和应用期间输入变化。

产出口径送审与科研方法口径共用原文核查和完整推荐材料检查。单有摘要或缺少适用性说明不能进入待人类审阅。模拟示例的科研含义及正式产出读回仍在行为验收范围。

实验生命周期、快照、审计和 review/Attention 兼容命令及其 validate 检查已接入。完整 Skill 规则、Agent 行为与跨平台证据分别记录；上述组件检查本身不代表完整 v5 验收。进度以 [验收清单](v5-acceptance.md) 为准。

## helper 分派与安装验证

`oppencouncil-project`、新 skill 的 `scripts/oppencouncil.py` 和两个旧命令名都使用 `helper_router.py`。项目已有 v3/v4 标记时，调用原 governor 的兼容实现；即使从另一个旧名称调用，也不改变 governor。所有 v5 写入进入共享实现，类型由项目元数据决定，与名称和布局无关。新项目使用旧名称执行 init/adopt 时，Stepwise 默认为 research、Steward 默认为 general；新名称要求显式类型。重复 init 已有 v5 项目时沿用实际类型和布局。

v4 实现原样位于两个旧 skill 的 `scripts/legacy_*.py`；AST 基线原值保留，仅更新基线路径。旧 Python 维护 API 仍可导入，v5 公开入口是共享命令。迁移中断时，普通命令先从持久 journal 恢复，再识别项目标记；带 --check 的命令保持只读并报告 RECOVERY_REQUIRED。v5 不接受 function-audit 和旧迁移动作；module-audit 的 --module 与 audit-recover 分别映射新审计主题和恢复命令。旧模块载荷不静默丢字段，需要使用科研简化载荷。

安装器现在安装 `oppencouncil`、`oppen-project-steward`、`stepwise-r-project` 三条目录链接；先准备全部链接，再成组替换，后续交换失败恢复前面的旧链接。若回滚期间目标被用户改写，保留用户内容及 previous-link 并报错。三个更新器相同，仍只更新产品 checkout；不会迁移项目、改授权或重启服务。测试在临时目录安装和执行三个入口，并以本地 Git 仓库验证 check/apply/重复更新及失败保护。

MCP 的 get_skill_guide 接受三个名称，均返回同一安装中的共享 Council 指南；本地 Memory、维护文档和脚本不通过该工具公开。完整运行时 Skill 的合并及准入评测仍独立验收。
