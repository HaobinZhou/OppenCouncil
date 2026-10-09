---
name: oppen-project-steward
metadata:
  version: "4.2.10"
description: Maintain durable, non-scientific AI-assisted projects with canonical ownership, Git-owned history, current Deliverables, recoverable machine Audit evidence, one pending-decision view, consequential Decision Memory, deterministic registries, and path-scoped dirty-work protection. Use when initializing or adopting an existing project, governing, opening OppenCouncil batch decision discussions, recovering Audit staging, indexing, escalating material unresolved concerns, recording non-reconstructable decision context, or validating long-lived software, AI application, quantitative engineering, infrastructure, or mixed code/document projects.
---

# Oppen Project Steward v4

Keep one understandable current project truth. Keep artifact history in Git. Use AI judgment for meaning and the bundled helper for mechanics.


Use this entrypoint for daily work and [freeze-workbench.md](references/freeze-workbench.md) for Council rounds. Open [maintenance.md](references/maintenance.md) only for an explicit skill update, connection setup or a detected legacy layout. Read only task-relevant references. MCP-only clients use `get_skill_guide(skill, resource="references/NAME.md")` for linked guides. Do not load every file or both governing skills.

Distributed in the OppenCouncil product repository under `skills/oppen-project-steward`. Keep this skill as the project governor; Council provides the shared workbench and the MCP component is optional. Installation/update instructions are loaded only through the maintenance entry.

## v4 authority and compatibility

New projects use v4. Native v3 remains compatible without a mandatory upgrade. Detect legacy layouts with `validate`; use the maintenance entry only when migration is needed. Council definitions are native Canonical owners: one current version per question, at the same project JSON used by the web UI and MCP. Existing replies never become formal definitions automatically.

## Core Workflow

1. Resolve and classify the target with `validate` before managed work. For `MANAGED_READY`, read `.oppen-project-steward/registry.md`, relevant Canonical sources, implementation, tests, current Audit, and relevant Deliverables. Use `review list TARGET` for all pending decisions; navigate Decision Memory through its generated index; do not load every Memory entry. Read relevant MCP discussion documents as needed, using `Discussion/index.md` within the namespace when available.
2. Treat an ordinary unmanaged project as `ADOPTION_REQUIRED`, not damaged. Use `adopt --check`, make only the necessary semantic mappings, then use `adopt --apply`. Stop on `ADOPTION_BLOCKED`; do not invent another namespace.
3. Confirm the project is Git-backed when applicable; the helper never initializes, commits, or rewrites Git history. Use `init` only for a genuinely new project. Use the maintenance entry for a detected legacy layout.
4. Search the canonical registry before adding documentation. Update the registered owner in place instead of creating a parallel version.
5. For authorized implementation changes, update the canonical definition, implementation, and linked verification together, then execute it. Discussion-only rounds use the Council content/persistence gate.
6. Retain direct human outputs in Deliverables. Route machine evidence, traces, provenance, diagnostics, and acceptance checks to Audit.
7. Create one module/step Contract Audit only when a hidden error could materially alter core behavior, results, safety-relevant contracts, or downstream interpretation.
8. Use the pending-decision list for a material unresolved concern outside current authorization. Raising it does not grant authority to resolve it.
9. Evaluate Memory only at a consequential decision boundary. Never create it merely because a task, session, code change, or test run ended.
10. Do not widen scope when inspection reveals an adjacent issue. Complete the authorized work, then use Attention only if the separate trigger passes.
11. Run relevant tests and registered verification, then run `index` and `validate`. Do not claim completion while validation fails.
12. For an already-connected MCP project, refresh and verify its view after governance changes. Keep existing permissions. First-time connection/publication is a separate requested setup task; see [maintenance.md](references/maintenance.md).

## Five Information Systems

- Canonical states what is true now.
- Git preserves historical artifact changes.
- Audit holds machine verification for the current implementation.
- Pending decisions combine Council questions and material issues retained in Attention storage.
- Decision Memory records why a consequential decision happened.

Keep each fact in its owning system. Deliverables are registered current outputs for direct human use, not another history or verification system.

## Managed Writes

Let the helper enforce its managed-state baseline and exact write set. Unrelated dirty work stays untouched; never stash the whole repository automatically or materialize the full project. A commit is not required for unchanged managed state. Stop on `MANAGED_STATE_CONFLICT` or `MANAGED_WRITESET_CONFLICT`, reconcile only reported paths, and use [maintenance.md](references/maintenance.md) for runtime recovery/bootstrap details. Never overwrite unexplained registry, Memory, Attention or contract-audit drift.

## Project Roles

- Steward owns `registry.md`, `Memory/`, `Attention/`, and `Audit/` with fixed topology inside `.oppen-project-steward/`. The namespace also permits optional MCP-owned `Discussion/`.
- Source, Data, and Deliverables are optional logical roles mapped only to useful existing directories.
- Do not create standard role directories or reject a project because a role is absent.
- Treat root `project.md`, `Memory/`, `Attention/`, and `Audit/` as user-owned unless the legacy upgrade preflight proves old Steward ownership.

Never create a standard directory beside an existing path already serving the same role. Stop on ambiguous supplied mappings.

## MCP Discussion Documents

`.oppen-project-steward/Discussion/` is MCP-owned free-form discussion. Read relevant documents through its `index.md` when available. These can contain proposals, code, quotes and disagreements; they are not Canonical or formal confirmations and are exempt from document/Deliverable restrictions. Reading them does not require a reply or lifecycle action. Routine governance, indexing, validation and migration leave the documents and index untouched; absence or a stale index does not damage the project.

## OppenCouncil Workbench

For a Council round, read [freeze-workbench.md](references/freeze-workbench.md), then the relevant saved records. Reuse IDs, confirmed decisions and existing discussion. Present all currently identifiable choices together; later rounds address new information. Keep the project's original governor. The user saves feedback and manually invokes AI to continue.

- **Prepare an informed choice.** Write reviewer-facing Markdown with actual actions, consequences, trade-offs and a justified recommendation. Organize long discussion, comparisons and wording with Markdown heading levels (## / ###), then short paragraphs or lists; bold alone is not a section hierarchy. Use complete question IDs such as F-000013 in prose for links. Keep machine checks and hashes in `review_note` or Audit.
- **Decompose the comparison.** Explain shared rules together. Use `{{choice:stable_id;label;value1;value2}}` for independent subchoices and local values; reserve separate columns for approaches whose linked consequences need whole-route comparison. Do not expand every combination or copy full candidates into every cell. The workflow reference defines compatibility and read-back checks.
- **Decide coupled rules together.** AI organizes groups around a complete decision, including the unresolved prerequisites needed to understand it. Prepare independently decidable upstream topics first. Preserve real dependencies and each member's separate ID, wording and history. Group management belongs to AI; people review, discuss and confirm.
- **Prepare complete candidates.** Verify available evidence, write concrete rules and relevant boundary/missing/conflict handling, and read back every in-scope candidate and group member before declaring the round ready. A genuinely blocked item is explicitly unprepared. Discussion, preference, software tests and confirmation alone do not establish semantic completeness.

For Council-managed definitions, `Freeze/questions/F-NNNNNN.json` → `definition.current_version` selects the sole effective wording. Human confirmation makes the exact candidate effective immediately; later revisions are human-opened and preserve the current version until replacement. AI edits candidates and discussion, never confirms or overwrites effective text. Canonical registers this same JSON scope; other documents reference it or render read-only views. Confirmation does not itself authorize implementation or execution.

## Existing Projects

An existing project without Steward metadata is not damaged. If `.oppen-project-steward/` is absent and the target is ordinary, classify it as `ADOPTION_REQUIRED`.

Run `adopt TARGET --check` read-only, then `adopt TARGET --apply --input TEMP_JSON`. Leave root `project.md`, directories, documentation, dirty work, and naming conventions unchanged. Register useful existing roles and authoritative documents by reference; all payload sections may be empty. Adoption stages only `.oppen-project-steward/**`, never materializes the full project, and creates no Attention or Memory merely for adoption.

For `LEGACY_STEWARD_LAYOUT`, use the maintenance entry. Daily work does not load the migration procedure.

## Canonical Ownership

For Council-managed definitions, the registered owner is the question JSON `definition` scope. Full text lives only there; Markdown/protocol outputs are references or generated read-only views. Domain version records in that file are permitted history; do not create parallel versioned files. Apply the following Markdown ownership rules to other contracts.

- Register each important semantic definition or cross-component contract under one stable topic key.
- Use one stable owner per topic. Council definitions use `Freeze/questions/F-NNNNNN.json`, section `definition`; other contracts may use one stable file or Markdown section.
- Store one `draft`, `partially-frozen`, or `frozen` status in the registry. Existing files may be registered non-invasively with `--status`; otherwise infer exactly one valid `Status:` field from the owned scope.
- Treat `frozen` as current authority. Council formal text changes only by confirming a new version at the same stable question path; direct overwrites of effective text are prohibited. Other contracts retain their existing in-place revision workflow.
- Use `canonical --replace` only for an explicit ownership move after resolving the former owner.
- Stop on conflicting owners. Never create `_old`, `_new`, `_updated`, `_final`, `_backup`, dated, or version-number copies. Git stores history.

## Deliverables And Audit

- Register one meaningful output group with a shared stable ID, audience and producer: `--kind group --path <deliverables-role>/<group>`. Every member must remain a current human output. Keep individual registration for outputs with different producers or contracts. See [workflow-operations.md](references/workflow-operations.md).
- Replace the same current output path when it changes. Use `deliverable --replace` only for an intentional path move.
- Keep logs, caches, traces, manifests, staging, backups, historical versions, temporary diagnostics, and serialized machine state out of Deliverables.
- Build run evidence in a system temporary directory, validate it, and atomically promote it to `.oppen-project-steward/Audit/Runs/<stage>/current/`.
- On failure, leave the prior `current/` untouched and keep failed staging outside the project.
- Do not retain siblings such as `previous/`, `run_001/`, dated runs, or `staging/` beside `current/`.
- Promote validated external staging with `audit promote`; let the helper perform internal SHA-256/size read-back verification and replace the whole current tree. No user-authored manifest is required.
- If failed staging already blocks a stage, run `audit recover`, inspect the reported external manifest, then rerun the blocked operation or validation.

## High-Risk Contract Audit

Ask: could a hidden error materially alter core behavior, results, a safety-relevant contract, or downstream interpretation?

If yes, use `contract-audit` to create or locate one stable audit per module or consequential contract, covering its functions together. Choose the implementing source as its hashed owner and name dependent sources/checks in the contract; audit a separately changing contract independently. Complete its four required sections through a temporary JSON payload and `contract-audit --input`; the helper refreshes the reviewed source hash and advances the managed-state baseline transactionally. Reuse the same audit for later changes. If no, normal executable tests are sufficient.

## Pending Decisions

Run `review list TARGET` to read one JSON list combining unresolved Council questions/candidates and material issues held in the existing Attention records. It is a live read-only view, with source paths, state and required next action; it creates no second authority or duplicate records. A candidate or discussion never supersedes the current formal version. MCP-only clients combine the existing Attention index and authorized `freeze_snapshot` into the same view; report missing access as incomplete, without changing permissions.

Use the existing Council question for definition choices. Do not copy it into Attention. For a separate evidence-backed, material issue outside authorized work that needs a new human decision, use `review raise`; use `review resolve` only after resolution. The helper retains `Attention/` storage and the old `attention` commands for compatibility, including MCP readers. Memory remains unchanged.

Noteworthy does not mean Attention. Known pending work is not Attention when already covered by the authorized workflow. Attention is not a TODO system. Exclude routine debt, upgrades, naming and speculative improvements. Mark an issue blocking when it undermines the requested result's correctness; listing it does not make the result complete. Read **Attention Raise** in [payload-schemas.md](references/payload-schemas.md) only when raising a non-Council issue.

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

## Helper Commands

Run `scripts/oppen_project_steward.py` with its absolute skill path:

```text
init TARGET
adopt TARGET --check
adopt TARGET --apply --input TEMP_JSON
canonical TARGET --topic KEY --path PATH [--section HEADING] [--status STATUS] --verification TEST_PATH [--replace]
deliverable TARGET --id KEY --path PATH --kind KIND --audience AUDIENCE --producer PATH [--replace]
contract-audit TARGET --topic KEY --source PATH --risk-reason TEXT
contract-audit TARGET --topic KEY --input TEMP_JSON
audit promote TARGET --stage KEY --input STAGING_DIR
audit recover TARGET --stage KEY
review list TARGET
review raise TARGET --input TEMP_JSON
review resolve TARGET --id A-XXXX
memory add TARGET --input TEMP_JSON
index TARGET
validate TARGET
```

Invoke the helper through the active Python 3 interpreter. On Windows, use `py -3 ABSOLUTE_SKILL_PATH\scripts\oppen_project_steward.py ...` or `python ...`; do not rely on the POSIX shebang. The helper preserves deterministic LF-managed text and uses the platform file-lock backend automatically.

Before using `adopt`, `contract-audit --input`, `review raise`, or `memory`, read [references/payload-schemas.md](references/payload-schemas.md). Create the JSON outside the project; the helper validates and removes it after a successful write.

Expect unchanged indexing commands to be idempotent. Do not use `init` as a migration command. Do not edit generated registries, indices, IDs, paths, statuses, or relationship reverse links manually.

## Completion Gate

1. Run relevant implementation tests and every verification linked to changed canonical topics.
2. Confirm one current owner per topic and no parallel old/versioned copies.
3. If a Deliverables role is registered, confirm it contains only registered current human outputs.
4. Confirm every `.oppen-project-steward/Audit/Runs/` stage contains only one `current/` tree.
5. Complete any High-Risk Contract Audit that was actually triggered.
6. Raise any qualifying non-blocking Attention without expanding scope. Treat blocking Attention as a completion blocker.
7. Add Decision Memory only for qualifying consequential decisions; never automate it from task completion.
8. Recover deterministic operational residue, run `index`, then require `validate` to report `MANAGED_READY` and exit zero.
9. Report current deliverables, verification performed, active Attention, and unresolved blockers.
