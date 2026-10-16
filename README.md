<p align="center">
  <img src="council/oppencouncil/assets/logo.svg" width="72" height="72" alt="OppenCouncil Logo">
</p>

# OppenCouncil

[简体中文](README.zh-CN.md)

**Vibe coding without the knowledge debt**

With an AI agent, a project can move forward for weeks without you reading a line of code. Each time the agent makes a call on its own, though, you understand your project a little less. It might decide which records to drop, how retries behave, or what counts as a duplicate customer. None of these feels important on the day it happens. They pile up until you can no longer say what your project does, why it works the way it does, or what a change would break. That is knowledge debt, and it builds up in any long-running project: research analyses, software, data pipelines, internal tools.

OppenCouncil keeps you in the decisions without sending you back into the code. Any rule that shapes how the project behaves becomes a definition, written in plain language, confirmed by you, and versioned inside the project. The AI works from it and tests check the code against it. If the AI wants to change a definition, it can only propose a revision, and nothing takes effect until you confirm it. The story around those decisions is kept too. When the project takes a major turn, the reason goes into Memory: an approach that failed, a design that was abandoned, a compromise forced by a constraint. Months later, neither you nor a fresh AI session has to rediscover why things are the way they are, or wander back into a dead end. When the AI notices something it shouldn’t settle on its own, such as code that quietly drops data or two scripts that disagree, it logs it under Attention rather than burying it in a chat. It stays visible until it is resolved, ruled out, or turned into a definition.

Every recommendation comes with what supports it: a checked source, a test result, a measurement, or a fact from your own data. When something is a convention, you can see where the convention comes from. When the options genuinely differ, you can see what each one would change in your project. AI assistants connected over MCP can contribute evidence too, and the local agent verifies it before it reaches you.

None of this has to take over your day. The AI first drops questions that don’t apply and answers what the code or data can settle. You can then review the prepared decisions in the browser or discuss them directly in Codex. In conversation, the agent presents one related group at a time, or up to three independent questions. You can ask for an explanation, revise the wording, or authorize confirmation. Both channels update the same project records, so you can switch between them without confirming twice.

## What AI does before asking you

The bundled skill asks the agent to do the groundwork first:

1. **Check whether the problem actually exists.** If the cohort has no missing sex values, there's no need to ask how to impute them. But if there are no missing values because an upstream script dropped those people without an agreed rule, that exclusion needs investigating.
2. **Recover the facts and decisions already available.** Check the data, the implementation, and previously confirmed definitions before asking you to answer the same question again.
3. **Recommend an established approach when the evidence supports it.** Explain why it fits this project and whether the agent checked the full text, an abstract, or an indirect source. Equally well-supported alternatives remain valid choices.
4. **Bring real trade-offs back to you.** When comparing a six-month and a twelve-month lookback window, for example, explain the methodological difference, check how many people it affects, and identify which analyses would need to change.

The workbench groups items so you can find the ones that need your attention:

| Category | What it contains | What to do |
| --- | --- | --- |
| **Needs a choice** | Several defensible options, or a reason to depart from usual practice | Compare the consequences and choose an approach |
| **Quick confirmation** | A recommendation with supporting evidence | Review the rationale and complete proposed wording, then confirm |
| **Further checks / blocked** | Incomplete evidence or missing information | Let the agent investigate; add context where needed |
| **Excluded** | Questions that do not need further work after investigation | Keep the reason on record and revisit if circumstances change |

A typical session looks like this:

```text
Describe the task → AI investigates and prepares proposals → Review, discuss, or confirm in the browser or Codex → Ask AI to continue → Work from the confirmed decisions
```

The workbench does not call a model in the background. After saving feedback, return to your AI session or paste the workbench's handoff message into it. The agent reads the new feedback and continues with the affected work.

Research reviews have an earlier handoff by default: the local agent checks project facts, saves shared questions for literature research, and stops. You then ask the web AI to contribute sources. When you explicitly tell the local agent to continue, it checks those sources and prepares the recommendations for review. New evidence alone does not start that next step. You can also explicitly assign the whole round to the local agent.

## Quick start

### 1. Install

You'll need [Git](https://git-scm.com/downloads), [uv](https://docs.astral.sh/uv/getting-started/installation/), and an AI client that supports local skills. This example uses Codex; the commands work in macOS and Linux terminals and Windows PowerShell:

```sh
git clone https://github.com/HaobinZhou/OppenCouncil.git
cd OppenCouncil
uv run --python 3.12 scripts/install.py --python 3.12 --skill-dir "$HOME/.agents/skills"
```

You can also download `OppenCouncil-5.0.0.zip` from [Releases](https://github.com/HaobinZhou/OppenCouncil/releases/latest), extract it to a permanent location, and run the installation command there.

The installer prepares the Python environment and links the shared skill and its two compatibility entries into your global skills directory:

```text
~/.agents/skills/
├── oppencouncil          → <repository>/skills/oppencouncil
├── oppen-project-steward → <repository>/skills/oppen-project-steward
└── stepwise-r-project    → <repository>/skills/stepwise-r-project
```

Use `oppencouncil` for new projects. The two existing names still work; the helper reads each project's marker and selects the appropriate implementation.

Keep the cloned repository in place because the links point to it. On Windows, directory symlinks require Developer Mode or suitable permissions. For an existing installation, keep using its current skills directory. Without `--skill-dir`, the installer defaults to `~/.codex/skills`; choose one location rather than installing into both. See the [installation migration guide](docs/migration.md#已安装的-skill) if an old link or a directory already occupies that name.

The workbench needs no Node.js, R, or model API key. Your analysis environment and AI client are set up separately.

### 2. Set up or adopt a project

Open your AI client in the project directory. For a research project, you might say:

```text
Use $oppencouncil to manage this research project.

The research question is: …; the data are in Data/raw/….
Review the existing data, code, and confirmed definitions, and identify the questions that actually need my decision.
Check the facts yourself. Where there is an established approach, give me a recommendation and its sources.
When the material is ready, open OppenCouncil and give me the link.
```

For software or other general work, say that it is a general project instead. An existing codebase is inspected before adoption. Projects already using v3/v4 keep their current workflow; migration is a separate decision.

### 3. Review in the browser

The agent returns a project link when the material is ready. You can also open an adopted project manually from the OppenCouncil repository root:

```sh
uv run --project council oppencouncil open /absolute/path/to/project --port 5322
```

A new service defaults to `http://127.0.0.1:5322`. Existing deployments keep their configured port and site directory: use the address reported by `oppencouncil status` and the actual service configuration. If you use a separate site directory, pass the same `--directory` when checking its status. On first visit, set a site password; use it for later visits.

Open an item to read the options, evidence, full proposal, and discussion. You can ask follow-up questions, edit the proposed wording, or adjust the headings, rows, columns, and footnotes of a simulated table. Save your changes, then use the handoff message to ask the agent to continue.

**Saving a draft does not confirm it.** The previous definition remains in effect until you have reviewed the complete proposal and confirmed it. Later work follows that confirmed version. If recorded evidence changes, the system flags the decision for review. When the wording stays the same, reconfirmation is appended to the current version instead of creating another version solely for that purpose.

## Research and general projects

Project type is independent of whether you use R or Python. Both types share the workbench; the main differences are the evidence needed to explain a decision and the way formal outputs are organized.

| Area | General projects | Research projects |
| --- | --- | --- |
| Basis for a decision | Code constraints, tests, measurements, and actual requirements | Data facts, plus literature, evidence strength, and reasons for departing from established practice when choosing methods |
| Formal outputs | Usually registered in `Deliverables/` | Tables, figures, and other manuscript or supplementary outputs registered in `Results/`, bound to confirmed output specifications |

A research project commonly uses the following layout. Existing projects keep their own layout—for example, an existing `R/` directory does not have to be renamed to `Scripts/`.

```text
project/
├── Scripts/          # Numbered analysis scripts in R, Python, or another language
│   ├── 01_import.R
│   ├── 02_cohort.R
│   ├── 03_table1.R
│   └── functions/    # Shared functions; numbering is not required here
├── Data/
│   ├── raw/          # Original inputs, kept read-only
│   └── derived/      # Cleaned data and intermediate cohorts produced by scripts
├── Results/          # Formal tables, figures, and other manuscript outputs
├── Releases/         # Submission or revision snapshots, created on request
├── Explore/          # Exploratory work; explicitly archived work goes in _archive/
├── Audit/            # Checks, diagnostics, and verification records
├── Freeze/           # Definitions, evidence, investigations, and discussion; images in assets/
└── Memory/           # Why consequential decisions were made
```

Script numbers may repeat. They help organize the work; they do not imply that running every file in filename order will reproduce the project. Execution also depends on the registered producers, their dependencies, the original inputs, and the environment.

**Agree on the specification before producing a formal table or figure.** For Table 1, that could mean its headings, groups, and whether continuous variables use means or medians. The agent prepares a simulated example for review. Once confirmed, the real output can be registered in `Results/` against that specification. A rerun with updated data uses the same confirmation if the specification is unchanged. Intermediate data belong in `Data/derived/`; checking and diagnostic outputs belong in `Audit/`.

Use `Explore/` to try a new subgroup or method. When you decide to make the result a formal output, complete its specification and registration. Abandoned experiments can be explicitly archived; routine work does not treat archived material as current work.

Submission, revision, and handoff snapshots are also created on request. The agent first presents a packaging plan, then creates a snapshot in `Releases/`. It includes formal outputs, relevant scripts, definitions, classified project-produced data, and environment records. Original inputs are identified by their sources and hashes rather than included in the ZIP. A snapshot can be large, so it is not a routine end-of-task action. See the [snapshot guide](skills/oppencouncil/references/releases.md).

## Connect a web AI client through MCP

To let a web AI client help with literature searches, counterexamples, or a second review, install the optional MCP component:

```sh
uv run --python 3.12 scripts/install.py --with-mcp --no-skills --python 3.12
```

Then follow the [MCP setup guide](mcp/README.md#接入与运行) to configure the projects, connection, and read/write permissions. Registering a project in the Council workbench does not automatically authorize MCP access.

The external AI can read explicitly shared project briefs, definitions, discussions, and evidence, and contribute sources or comments. Its contributions are marked as external and not yet locally checked. The local agent reviews them against the project before using them.

## Everyday commands

Run these from the OppenCouncil repository root:

```sh
# Show service status and port
uv run --project council oppencouncil status

# Open another adopted project
uv run --project council oppencouncil open /absolute/path/to/project

# Remove a project from the site directory, keeping its files
uv run --project council oppencouncil disable /absolute/path/to/project

# Stop the background service
uv run --project council oppencouncil stop
```

Closing the browser tab does not stop the service. For access from another computer, use SSH forwarding, FRP, or an HTTPS reverse proxy. See the [deployment guide](council/README.md#远程访问) for ports, public addresses, and site directory settings.

Project records stay with the project. The site directory holds `projects.local.json`, authentication, and service state; MCP has its own configuration and authorization state.

## Upgrading from v4 to v5

**Software version 5.0.0 and project format v5 are separate upgrades.** You can update the workbench and skills while leaving existing projects on v4. The two old skill names remain available, and projects that have not migrated continue through the retained legacy implementation.

### 1. Update the software with your existing configuration

From your existing OppenCouncil checkout:

```sh
git pull --ff-only
uv run --python 3.12 scripts/install.py --python 3.12 --skill-dir "$HOME/.agents/skills"
```

Keep your current skills directory; if you previously used `~/.codex/skills`, keep using it. Add `--with-mcp` if MCP is already installed. Then restart Council and MCP through your existing service manager, keeping the site directory, port, project registrations, configuration files, and OAuth grants. Downloading new source does not reload a running process.

If you want your projects to stay on v4 for now, stop here. For ZIP installations, the earlier separate repositories, or skills installed as copied directories, see the [detailed migration guide](docs/migration.md).

### 2. Choose a project to migrate

When you are ready to adopt v5, ask the agent in that project's session:

```text
Use $oppencouncil to run an upgrade-v5 check on this project.
Save the migration plan outside the project and show me the proposed file changes, blockers, and legacy items. Do not apply it yet.
```

The check does not modify the project. It verifies that connected Council and MCP services support v5 and lists the exact writes and before/after hashes. Stepwise projects default to research; Steward projects default to general. If a different type is appropriate, select it during the check.

You can also generate the plan manually from the software repository root. Use an absolute project path. The plan must be outside the project, its parent directory must exist, and its filename must be new:

```sh
uv run --project council python skills/oppencouncil/scripts/oppencouncil.py upgrade-v5 "/absolute/path/to/project" --check --plan "/absolute/path/outside-project/v5-plan.json"
```

After reviewing the plan, resolving its blockers, and explicitly confirming the migration, apply that same plan:

```sh
uv run --project council python skills/oppencouncil/scripts/oppencouncil.py upgrade-v5 "/absolute/path/to/project" --apply --plan "/absolute/path/outside-project/v5-plan.json"
```

For a custom site or an external MCP configuration, supply the same `--council-directory`, `--mcp-root`, and `--mcp-config` in both commands; see the [full command examples](docs/migration.md#项目从-v3v4-迁移到-v5). Use `--project-type` only during the check; application reads the saved choice. If inputs or connection capabilities change, the old plan is rejected and a new check is required.

### What migration preserves

Existing definitions and version history, proposals, discussion, group relationships, Memory, and output registrations are retained. Unresolved Attention entries become investigations, keeping their content and blocking meaning; they do not have to be closed just to migrate. Existing proposals and unprocessed discussion are reconciled when work resumes.

Migration does not rename `R/`, renumber scripts, move data, or rerun analyses. Existing unnumbered scripts, outputs without specifications, and data awaiting classification appear in the report for later handling. The migration tool does not rewrite Git history.

Application writes only the files listed in the plan, using `.oppencouncil-migration/` inside the project for transaction recovery. It does not create a full project copy or archive. After an interruption, the helper checks and recovers the transaction; conflicts are preserved for resolution using the [recovery guide](docs/migration.md#失败中断与恢复).

Finally, run the shared helper's `index` and `validate`, then inspect the records in the existing workbench. Direct migration supports native v3/v4 projects. Earlier v2 projects or nonstandard historical records need to be reconciled through their original workflow first.

## Further documentation and development

- [Council usage and deployment](council/README.md)
- [MCP setup and permissions](mcp/README.md)
- [Detailed migration guide](docs/migration.md)
- [OppenCouncil skill](skills/oppencouncil/SKILL.md)
- [V5 acceptance records](docs/v5-acceptance.md)

When opening an issue, please include your operating system, the command you ran, and the error message.

The full test suite also requires Node.js 22+:

```sh
uv run --python 3.12 scripts/install.py --with-mcp --no-skills --dev --python 3.12
uv run --python 3.12 scripts/verify.py
uv build --project council
```

To verify only Council and the skills, omit `--with-mcp` during installation and use `scripts/verify.py --core`.

## License

[MIT License](LICENSE). Licenses for bundled third-party libraries are included alongside those libraries.
