---
name: stepwise-r-project
metadata:
  version: "4.3.1"
description: Govern scientific R analysis projects, including OppenCouncil freeze rounds. Use for project setup, coordinated analysis changes and checks of scientific ownership, results and verification; general software projects use oppen-project-steward.
---

# Stepwise R Project v4

Keep one current scientific truth and Git-owned history. Preserve the project's existing governor; Council is its decision workbench. Use AI judgment for scientific meaning and the helper for managed mechanics.

## Locate the work

Resolve the target and authorized scope. Read `project.md`, relevant registered definitions and only the R code, Results or Audit evidence needed for this task. Use `review list TARGET` for pending choices; select relevant Decision Memory through `Memory/index.md`, rather than loading every entry.

Before managed writes, distinguish a v4/compatible v3 project, an unmanaged project and a detected migration or damage condition with `validate TARGET`. Use `init` only for a new unmanaged project. Native v3 needs no mandatory upgrade; use the maintenance route for legacy layouts.

## Essential boundaries

- Canonical owns current scientific definitions and contracts; Git owns artifact history; Audit owns verification and provenance. Pending decisions combine Council and material Attention issues. Decision Memory retains the policy below.
- Search existing owners before creating documents; the default budget for new Markdown is zero. Each topic has one stable owner. Council uses `Freeze/questions/F-NNNNNN.json` → `definition`, shared by the webpage and MCP; other documents reference or render it without a second editable authority. Stop on conflicting owners or directory aliases.
- In authorized implementation work, keep scientific definitions, R implementation and linked checks consistent. Route current human outputs to Results, reusable machine data to Data, and verification to Audit. Detailed authoring/publication mechanics are loaded only for that work.
- `Discussion/` is MCP-owned free-form discussion, not formal confirmation; it is exempt from document/Result restrictions. Read relevant documents through its index when available; routine governance and migration leave documents and index untouched. A missing/stale index does not damage the project. Reading does not itself require a reply.
- Keep definition choices in Council. Raise a separate Attention issue only for an evidence-backed, material decision outside authorized work; routine debt, speculative safeguards and known authorized work do not qualify. A correctness blocker remains a blocker until resolved.

## Choose the task

Load only the row needed for the current request. Follow further links when that operation is actually needed; do not read the whole reference tree or both governing skills. MCP-only clients read the same references with `get_skill_guide(skill, resource="references/NAME.md")`.

| Task | Read next | Completion evidence |
| --- | --- | --- |
| Inspect or explain existing work | Relevant registered owners and saved records | Findings and their sources; no mutation or full test run required |
| Prepare or continue Council review | [freeze-workbench.md](references/freeze-workbench.md) | Necessary, focused decisions; saved complete candidates; verified review link |
| Implement, initialize, change ownership, publish outputs or raise a non-Council issue | Relevant sections of [workflow-operations.md](references/workflow-operations.md) | Affected checks and valid managed state |
| Update this skill, repair a connection or handle a detected legacy layout | [maintenance.md](references/maintenance.md) | Checks for that operation; no implicit project migration |

For a small authorized edit, inspect its affected owner and evidence; do not turn it into a new freeze round or a project-wide audit. A Council-only round uses its content/persistence gate, without rerunning analyses or rebuilding software. Installation, execution, deployment and publication require their own requested scope.

## Decision Memory

Create Decision Memory only when a consequential scientific or technical decision passes this test:

> Without an explicit record, could a future AI with the current project and Git history plausibly fail to explain why the decision was made, or unknowingly reintroduce a rejected approach?

Valid events preserve non-obvious causal history such as failed prior designs, diagnostic-driven strategy changes, collaborator/reviewer requirements, data-imposed compromises, or deliberately rejected credible methods. Prefer the pattern: previously X; observed Y; therefore decided Z.

Consequential technical or execution architecture also qualifies when its causal rationale is durable and cannot be reconstructed from current code, Canonical, and Git. For example: the project previously used one execution architecture; real resource behavior made it unsafe at project scale; the project therefore changed storage, concurrency, worker memory, or spill policy; future maintainers should not restore the former design without new evidence.

Do not record routine bugs, package compatibility fixes, ordinary normalization, local optimization, refactors, tests, reruns, commands, file lists, benchmarks, progress/status summaries, unchanged results, information already in Canonical or Git, Audit evidence, or unresolved concerns unless they caused a durable consequential design decision whose rationale would otherwise be lost. A task ending is never a trigger. `related_topics: []` is valid. Read [managed-systems.md](references/managed-systems.md) before adding an entry or declaring relationships.

## Tools and completion

Invoke `scripts/stepwise_r_project.py` using its absolute installed skill path and an active Python 3 interpreter (`py -3` on Windows is also valid). Use `--help` for arguments; let the helper own IDs, schemas, indices, relationships and atomic writes. Never hand-edit generated registries or relationship reverse links.

After implementation or governance mutations, run affected tests/registered verification, complete any risk-triggered audit, then `index TARGET` and `validate TARGET`; require successful validation before claiming that work complete. Report what changed, what was verified and any remaining blocker. Read-only inspection and Council-only discussion use the task-specific gates above.

For an already-connected MCP project, refresh and verify its view after governance changes while preserving permissions. First-time connection and permission changes follow the separately authorized maintenance workflow.
