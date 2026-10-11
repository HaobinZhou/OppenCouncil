# Project implementation and helper operations

Read the relevant sections for project setup/adoption, implementation, ownership or output changes. Council-only rounds use [freeze-workbench.md](freeze-workbench.md); inspection alone does not trigger this entire procedure.

## Existing Projects

An existing project without Steward metadata is not damaged. If `.oppen-project-steward/` is absent and the target is ordinary, classify it as `ADOPTION_REQUIRED`.

Confirm the project is Git-backed where applicable; the helper does not initialize, commit or rewrite Git history. Use `init` only for a genuinely new project. Stop on `ADOPTION_BLOCKED` rather than inventing another namespace.

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

- Register one meaningful output group with a shared stable ID, audience and producer: `--kind group --path <deliverables-role>/<group>`. Every member must remain a current human output. Keep individual registration for outputs with different producers or contracts. See the helper sections below.
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

## Output groups

Register one stable directory containing related current human outputs from the same producer. Use `--kind group` with the existing result/deliverable command; the directory must sit below Results/Deliverables, not equal the whole role. A group may contain mixed table/figure/report formats, but no machine artifacts, symlinks, or historical files. At least one output must exist.

One ID, audience and producer apply to all group members. Rebuild the same directory, remove obsolete outputs, run `index` and `validate`. Group membership is the current directory tree; executable checks/Audit must still establish that the expected outputs were produced. Overlapping group/file registrations are rejected. Keep existing individual registrations; consolidate only as an explicitly authorized ownership move. A group does not change publication or scientific acceptance requirements.

```text
deliverable TARGET --id review-pack --path reports/review-pack --kind group --audience reviewers --producer src/export.py
```

Use `deliverable` with an existing producer and the mapped Deliverables role.

## One pending-decision list

```text
review list TARGET
review raise TARGET --input TEMP_JSON
review resolve TARGET --id A-0001
```

`review list` returns JSON with `project`, `count`, and `items`. Each item includes ID, title, source path, status, blocking state and next action. Council items also carry the current formal version number. An absent Freeze directory requires no Council dependency; an existing Freeze directory is read through the installed OppenCouncil package. Use its Python environment if the default interpreter cannot import it. Unreadable Council records produce an error, never a falsely complete empty list.

Pending Council questions and candidates are read in place. Historical records and effective frozen versions without an open draft are omitted. Discussion reopened on an effective version remains pending while that version stays effective. `blocking: null` for Council means no blocking judgment was made; AI must assess scientific impact from the source. Resolve a Council item through its own discussion/confirmation workflow, never `review resolve`.

Only material non-Council issues use `review raise/resolve`; the payload is the existing Attention payload. Existing Attention storage, IDs, lifecycle and MCP reading remain compatible. The list is a derived query, not another file to maintain. Never duplicate the same question in both sources.

## Material issues outside Council

Use the existing Council question for definition choices. Do not copy it into Attention. For a separate evidence-backed, material issue outside authorized work that needs a new human decision, use `review raise`; use `review resolve` only after resolution. The helper retains `Attention/` storage and the old `attention` commands for compatibility, including MCP readers. Memory remains unchanged.

Noteworthy does not mean Attention. Known pending work is not Attention when already covered by the authorized workflow. Attention is not a TODO system. Exclude routine debt, upgrades, naming and speculative improvements. Mark an issue blocking when it undermines the requested result's correctness; listing it does not make the result complete. Read **Attention Raise** in [payload-schemas.md](payload-schemas.md) only when raising a non-Council issue.

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

Before using `adopt`, `contract-audit --input`, `review raise`, or `memory`, read [references/payload-schemas.md](payload-schemas.md). Create the JSON outside the project; the helper validates and removes it after a successful write.

Expect unchanged indexing commands to be idempotent. Do not use `init` as a migration command. Do not edit generated registries, indices, IDs, paths, statuses, or relationship reverse links manually.

## Implementation completion

1. Run relevant implementation tests and every verification linked to changed canonical topics.
2. Confirm one current owner per topic and no parallel old/versioned copies.
3. If a Deliverables role is registered, confirm it contains only registered current human outputs.
4. Confirm every `.oppen-project-steward/Audit/Runs/` stage contains only one `current/` tree.
5. Complete any High-Risk Contract Audit that was actually triggered.
6. Raise any qualifying non-blocking Attention without expanding scope. Treat blocking Attention as a completion blocker.
7. Add Decision Memory only for qualifying consequential decisions; never automate it from task completion.
8. Recover deterministic operational residue, run `index`, then require `validate` to report `MANAGED_READY` and exit zero.
9. Report current deliverables, verification performed, active Attention, and unresolved blockers.
