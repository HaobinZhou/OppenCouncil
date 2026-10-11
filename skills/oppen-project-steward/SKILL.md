---
name: oppen-project-steward
metadata:
  version: "4.3.1"
description: Govern ongoing software, infrastructure and mixed code/document projects, including OppenCouncil review rounds. Use for project adoption, coordinated changes and governance checks; scientific R analysis projects use stepwise-r-project.
---

# Oppen Project Steward v4

Keep one current project truth and Git-owned history. Preserve the project's existing governor; Council is its decision workbench, not a replacement governor. Use the helper for managed writes and AI judgment for project meaning.

## Locate the work

Resolve the target and authorized scope. Inspect `.oppen-project-steward/registry.md`, relevant owners and only the implementation/evidence needed for this task. For pending choices use `review list TARGET`; select relevant Decision Memory through its index, rather than loading every entry.

Before managed writes, classify the project with `validate TARGET`. New projects use v4; native v3 remains compatible. An ordinary existing project without the namespace needs adoption, not repair. Use `init` only for a genuinely new project; adoption and legacy handling are routed below.

## Essential boundaries

- Canonical owns current definitions; Git owns artifact history; Audit owns verification. Pending decisions combine Council and material Attention issues. Decision Memory owns consequential causal history under its unchanged policy below.
- Search existing owners before creating documentation. Each topic has one stable owner. Council uses `Freeze/questions/F-NNNNNN.json` → `definition`, shared by the webpage and MCP; other outputs may reference or render it, not maintain competing wording.
- Steward owns `.oppen-project-steward/` except MCP-owned `Discussion/`. Source, Data and Deliverables are optional roles mapped to useful existing paths. Root-level files/directories remain user-owned unless legacy ownership is proven. Do not invent parallel directories or guess ambiguous mappings.
- Preserve unrelated dirty work. Let the helper enforce its managed baseline and exact write set. On `MANAGED_STATE_CONFLICT` or `MANAGED_WRITESET_CONFLICT`, reconcile only reported paths; never reset unexplained drift, stash the repository or copy the whole project.
- Free-form `.oppen-project-steward/Discussion/` contains proposals and disagreements, not formal authority; it is exempt from document/Deliverable restrictions. Read relevant documents through its index when available; ordinary governance leaves both untouched. A missing/stale index does not damage the project. Reading does not itself require a reply.
- Council questions remain in Council. Raise a separate Attention issue only for an evidence-backed, material decision outside authorized work; routine debt, speculative safeguards and known authorized work do not qualify. A correctness blocker remains a blocker until resolved.

## Choose the task

Load only the row needed for the current request. Follow further links when that operation is actually needed; do not read the whole reference tree or both governing skills. MCP-only clients read the same references with `get_skill_guide(skill, resource="references/NAME.md")`.

| Task | Read next | Completion evidence |
| --- | --- | --- |
| Inspect or explain existing work | Relevant registered owners and saved records | Findings and their sources; no mutation or full test run required |
| Prepare or continue Council review | [freeze-workbench.md](references/freeze-workbench.md) | Necessary, focused decisions; saved complete candidates; verified review link |
| Implement, adopt/init, change ownership, publish outputs or raise a non-Council issue | Relevant sections of [workflow-operations.md](references/workflow-operations.md) | Affected checks and valid managed state |
| Update this skill, repair a connection or handle a detected legacy layout | [maintenance.md](references/maintenance.md) | Checks for that operation; no implicit project migration |
| Write qualifying Decision Memory or its relationships | Memory payload in [payload-schemas.md](references/payload-schemas.md) | Existing Memory policy below and helper-validated relationships |

For a small authorized edit, inspect its affected owner and evidence; do not turn it into a new freeze round or a project-wide audit. A Council-only round uses its content/persistence gate, without rerunning analyses or rebuilding software. Installation, execution, deployment and publication require their own requested scope.

## Decision Memory

- Apply the counterfactual test: without an explicit record, could a future agent with the current project and complete Git history fail to explain a consequential decision or repeat a rejected direction?
- Create one Memory entry only when the answer is yes and the decision is consequential. Do not create one per task, conversation, change, commit, rerun, verification, or unresolved concern.
- Use `supersedes` when a later decision changes direction. Use `invalidates` when later evidence shows a key fact or assumption was wrong. Let the helper update prior status and reverse links.
- Allow zero related canonical topics. Memory records causal history; Canonical records current belief, Audit records verification, and Attention records unresolved significance.
- Never store chain of thought, scratchpads, deliberation transcripts, unresolved-risk fields, or verification logs in Attention or Memory.
- Yes: a real failure or user experience causes an important architectural direction to be abandoned and replaced. No: a routine bug fix passes tests and Git fully explains the change.
- Technical difficulty alone does not justify Decision Memory. Exclude subtle compatibility, parser, optimization, refactor, and isolated defect work when code, tests, and Git explain it.
- Allow consequential architecture, execution, storage, concurrency, reliability, performance policy, operational safety, dependency, deployment, or state-management decisions when the counterfactual test passes.
- An incident alone is Audit, logs, or Git as appropriate. Create Memory only when the incident causes a durable consequential decision whose causal context would otherwise be lost.

## Tools and completion

Invoke `scripts/oppen_project_steward.py` using its absolute installed skill path and an active Python 3 interpreter (`py -3` on Windows is also valid). Use `--help` for arguments; let the helper own IDs, schemas, indices, relationships and atomic writes. Never hand-edit generated registries or relationship reverse links.

After implementation or governance mutations, run affected tests/registered verification, complete any risk-triggered audit, then `index TARGET` and `validate TARGET`; require successful validation before claiming that work complete. Report what changed, what was verified and any remaining blocker. Read-only inspection and Council-only discussion use the task-specific gates above.

For an already-connected MCP project, refresh and verify its view after governance changes while preserving permissions. First-time connection and permission changes follow the separately authorized maintenance workflow.
