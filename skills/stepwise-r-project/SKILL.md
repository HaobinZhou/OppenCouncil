---
name: stepwise-r-project
metadata:
  version: "4.2.11"
description: Maintain strict, human-readable scientific R analysis projects with canonical ownership, Results, Audit, pending decisions and Decision Memory. Use for scientific freeze rounds, opening OppenCouncil discussions and recovering existing decisions and discussions, or when initializing, migrating, modifying, indexing, validating or reviewing an R analysis workspace.
---

# Stepwise R Project v4

Keep one current truth for humans. Keep artifact history in Git. Use AI discretion for scientific meaning, not project mechanics. If a decision does not require project-specific scientific or semantic context, let the helper make it deterministically.


Use this entrypoint for daily work and [freeze-workbench.md](references/freeze-workbench.md) for Council rounds. Open [maintenance.md](references/maintenance.md) only for an explicit skill update, connection setup or a detected legacy layout. Read only task-relevant references. MCP-only clients use `get_skill_guide(skill, resource="references/NAME.md")` for linked guides. Do not load every file or both governing skills.

Distributed in the OppenCouncil product repository under `skills/stepwise-r-project`. Keep this skill as the project governor; Council provides the shared workbench and the MCP component is optional. Installation/update instructions are loaded only through the maintenance entry.

## v4 authority and compatibility

New projects use v4. Native v3 remains compatible without a mandatory upgrade. Detect legacy layouts with `validate`; use the maintenance entry only when migration is needed. Council definitions are native Canonical owners: one current version per question, at the same project JSON used by the web UI and MCP. Existing replies never become formal definitions automatically.

## Core Workflow

1. Resolve the target before writing. Inspect `project.md`, relevant canonical sources, R code, Results, Audit, tests, pending decisions from `review list TARGET`, and only relevant Decision Memory identified through `Memory/index.md`. Read relevant MCP discussion documents as needed, using `Discussion/index.md` when available.
2. Treat the default budget for new Markdown documents as zero. Search the canonical registry and existing documents first.
3. Classify the project as v4, compatible v3, migration required, migration blocked but recoverable, unmanaged, or damaged. Run `init` only for a new unmanaged project; never use it as migration.
4. Resolve one current authority for every scientific definition and cross-script contract. Stop on conflicting owners or ambiguous directory aliases.
5. Perform the authorized work. For authorized implementation changes, update the canonical definition, R implementation, and contract test together. Discussion-only rounds use the Council content/persistence gate.
6. Route current human deliverables to Results and machine verification to Audit. Publish only after staging validation and atomic promotion.
7. Apply the Decision Memory counterfactual test and Human Attention trigger. Do not create either merely because a task ended.
8. Run relevant R, unit, and registered contract tests; run `index`; then require `validate` to exit zero.
9. For an already-connected MCP project, refresh and verify its view after governance changes. Keep existing permissions. First-time connection/publication is a separate requested setup task; see [maintenance.md](references/maintenance.md).

## Current-State Ownership

- Canonical answers what the current scientific truth or project contract is.
- Git answers what files and code changed.
- Audit holds verification, provenance, diagnostics, and current run state.
- Pending decisions combine Council questions and material issues retained in Attention storage.
- Decision Memory explains why a consequential design decision happened.

Never route verification to Memory, unresolved risk to Memory, decision rationale to Audit, or current definitions to history records.

## MCP Discussion Documents

`Discussion/` is MCP-owned free-form discussion. Read relevant documents through its `index.md` when available. These can contain proposals, code, quotes and disagreements; they are not Canonical or formal confirmations and are exempt from document/Deliverable restrictions. Reading them does not require a reply or lifecycle action. Routine governance, indexing, validation and migration leave the documents and index untouched; absence or a stale index does not damage the project.

## OppenCouncil Workbench

For a Council round, read [freeze-workbench.md](references/freeze-workbench.md), then the relevant saved records. Reuse IDs, confirmed decisions and existing discussion. Present all currently identifiable choices together; later rounds address new information. Keep the project's original governor. The user saves feedback and manually invokes AI to continue.

- **Complete the web handoff.** On first creation of Council records, register the project in the intended Council site and verify its directory entry and review content before returning the project link. Creating `Freeze/` files alone is not a completed web handoff. Follow the site-registration steps in [freeze-operations.md](references/freeze-operations.md); MCP authorization remains separate.
- **Prepare an informed choice.** Write reviewer-facing Markdown with actual actions, consequences, trade-offs and a justified recommendation. Organize long discussion, comparisons and wording with Markdown heading levels (## / ###), then short paragraphs or lists; bold alone is not a section hierarchy. Use complete question IDs such as F-000013 in prose for links. Keep machine checks and hashes in `review_note` or Audit.
- **Decompose the comparison.** Explain shared rules together. Use `{{choice:stable_id;label;value1;value2}}` for independent subchoices and local values; reserve separate columns for approaches whose linked consequences need whole-route comparison. Do not expand every combination or copy full candidates into every cell. The workflow reference defines compatibility and read-back checks.
- **Decide coupled rules together.** AI organizes groups around a complete decision, including the unresolved prerequisites needed to understand it. Prepare independently decidable upstream topics first. Preserve real dependencies and each member's separate ID, wording and history. Group management belongs to AI; people review, discuss and confirm.
- **Prepare complete candidates.** Verify available evidence, write concrete rules and relevant boundary/missing/conflict handling, and read back every in-scope candidate and group member before declaring the round ready. A genuinely blocked item is explicitly unprepared. Discussion, preference, software tests and confirmation alone do not establish semantic completeness.

For Council-managed definitions, `Freeze/questions/F-NNNNNN.json` → `definition.current_version` selects the sole effective wording. Human confirmation makes the exact candidate effective immediately; later revisions are human-opened and preserve the current version until replacement. AI edits candidates and discussion, never confirms or overwrites effective text. Canonical registers this same JSON scope; other documents reference it or render read-only views. Confirmation does not itself authorize implementation or execution.

## Canonical Ownership

For Council-managed definitions, the registered owner is the question JSON `definition` scope. Full text lives only there; Markdown/protocol outputs are references or generated read-only views. Domain version records in that file are permitted history; do not create parallel versioned files. Apply the following Markdown ownership rules to other contracts.

- Register one stable topic key and exactly one Markdown, QMD, or Rmd owner for each scientific definition, variable meaning, or cross-script/output contract.
- Use only `Status: draft`, `Status: partially-frozen`, or `Status: frozen`. Treat frozen as current authority, not immutable history.
- Keep frozen content free of unresolved scope, stale counts, execution status, and run history.
- Before changing frozen semantics, lower the status; revise definition, implementation, and contract test; run the test; then restore the justified status.
- Treat the registered verification path as a contract to execute, not proof of execution.
- Use `canonical --replace` only for an explicit ownership migration and resolve the former owner in the same task.
- Never create `_old`, `_new`, `_updated`, backup, dated, or versioned copies. Revise the current owner and rely on Git.
- Treat rendered HTML/PDF as a view or registered Result, never a second editable source.

## R Writing Rules

- Keep scripts runnable line by line in RStudio with visible packages, paths, seeds, inputs, outputs, and important intermediate objects.
- Use RStudio section headers for import, cleaning, analysis, validation, and export blocks.
- Keep scientifically important transformations in short pipelines or named steps.
- Use concise Chinese comments to explain why control points and transformations exist.
- Avoid hidden global state, deeply nested expressions, and whole-analysis wrapper functions.
- Preserve stable object names when they carry the same meaning across scripts.

## Results And Audit

- Retain only publication or formal-review tables, figures, cohort flows, codebooks, and reports in Results. Register one meaningful output group with a shared stable ID, audience and producing R script. Use `--kind group --path Results/<group>` for a directory; every member remains subject to human-output validation. Use individual registration for outputs with different producers or contracts. See [workflow-operations.md](references/workflow-operations.md).
- Rebuild the same registered path when a deliverable changes. Use `result --replace` only for an intentional contract move.
- Put reusable machine data in Data. Put QA, provenance, manifests, diagnostics, traces, and session state in Audit.
- Build run output in a stage-specific system temporary directory. Validate schema, provenance, acceptance, and read-back there.
- Atomically replace the whole `Audit/Runs/<stage>/current/` tree only after checks pass. Publish Results afterward.
- Leave the prior `current/` untouched on failure. Keep no persistent staging, dated, historical, or backup sibling.

## Pending Decisions

Run `review list TARGET` to read one JSON list combining unresolved Council questions/candidates and material issues held in the existing Attention records. It is a live read-only view, with source paths, state and required next action; it creates no second authority or duplicate records. A candidate or discussion never supersedes the current formal version. MCP-only clients combine the existing Attention index and authorized `freeze_snapshot` into the same view; report missing access as incomplete, without changing permissions.

Use the existing Council question for definition choices. Do not copy it into Attention. For a separate evidence-backed, material issue outside authorized work that needs a new human decision, use `review raise`; use `review resolve` only after resolution. The helper retains `Attention/` storage and the old `attention` commands for compatibility, including MCP readers. Memory remains unchanged.

Noteworthy does not mean Attention. Known pending work is not Attention when already covered by the authorized workflow. Attention is not a TODO system. Exclude routine debt, upgrades, naming and speculative improvements. Mark an issue blocking when it undermines the requested result's correctness; listing it does not make the result complete. Read **Attention Payload** in [managed-systems.md](references/managed-systems.md) only when raising a non-Council issue.

## Decision Memory

Create Decision Memory only when a consequential scientific or technical decision passes this test:

> Without an explicit record, could a future AI with the current project and Git history plausibly fail to explain why the decision was made, or unknowingly reintroduce a rejected approach?

Valid events preserve non-obvious causal history such as failed prior designs, diagnostic-driven strategy changes, collaborator/reviewer requirements, data-imposed compromises, or deliberately rejected credible methods. Prefer the pattern: previously X; observed Y; therefore decided Z.

Consequential technical or execution architecture also qualifies when its causal rationale is durable and cannot be reconstructed from current code, Canonical, and Git. For example: the project previously used one execution architecture; real resource behavior made it unsafe at project scale; the project therefore changed storage, concurrency, worker memory, or spill policy; future maintainers should not restore the former design without new evidence.

Do not record routine bugs, package compatibility fixes, ordinary normalization, local optimization, refactors, tests, reruns, commands, file lists, benchmarks, progress/status summaries, unchanged results, information already in Canonical or Git, Audit evidence, or unresolved concerns unless they caused a durable consequential design decision whose rationale would otherwise be lost. A task ending is never a trigger. `related_topics: []` is valid. Read [managed-systems.md](references/managed-systems.md) before adding an entry or declaring relationships.

## Functions And Module Audit

- Create functions for reuse or genuinely error-prone logic. Use Roxygen and executable tests for reusable functions and critical logic. A simple local helper can use a clear name and a short comment; do not require a separate test/doc scaffold for it.
- Audit a risky analysis step or module once, covering its important functions together: inputs, outputs, actual scientific predicates, edge cases, executable checks and limits. Risk includes eligibility, timing, joins, exposure, outcomes, missingness, weighting and inference.
- Use `module-audit` with a stable name and the relevant R sources. Reuse that audit and refresh all source hashes after verification. Existing per-function audits remain valid; new work does not require one document per function.
- Keep source Rmd only, with no rendered audit HTML. See [workflow-operations.md](references/workflow-operations.md) for commands.

## Helper Commands

Run `scripts/stepwise_r_project.py` using its absolute skill path:

```text
init TARGET
audit-recover TARGET --stage STAGE
canonical TARGET --topic KEY --path PATH [--section HEADING] --verification TEST_PATH [--replace]
result TARGET --id KEY --path PATH --kind KIND --audience AUDIENCE --producer PATH [--replace]
review list TARGET
review raise TARGET --input TEMP_JSON
review resolve TARGET --id A-XXXX
memory add TARGET --input TEMP_JSON
module-audit TARGET --module NAME --source PATH [--source OTHER_R_PATH] --risk-reason TEXT
index TARGET
validate TARGET
```

Let the helper own IDs, paths, fixed schemas, indices, relationships, lifecycle mechanics, and atomic writes. Never hand-edit managed indices or relationship reverse links.

## Completion Gate

1. Run relevant R/unit tests and every contract test linked to changed canonical topics.
2. Confirm no second current definition, stale frozen content, parallel old/versioned document, unregistered Result, or invalid Audit run tree remains.
3. Complete any triggered module audit. Evaluate Decision Memory and pending decisions explicitly; "none required" is normal.
4. Do not claim an affected analysis complete while a relevant blocking Attention undermines correctness.
5. Require Memory and Attention indices to match entries and no legacy/alternative managed topology to remain.
6. Run `index`, then require `validate` to exit zero.
7. Report current deliverables, verification, migration behavior when applicable, and unresolved blockers.
