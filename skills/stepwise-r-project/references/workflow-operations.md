# Project implementation and helper operations

Read the relevant sections for project setup/adoption, implementation, ownership or output changes. Council-only rounds use [freeze-workbench.md](freeze-workbench.md); inspection alone does not trigger this entire procedure.

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

- Retain only publication or formal-review tables, figures, cohort flows, codebooks, and reports in Results. Register one meaningful output group with a shared stable ID, audience and producing R script. Use `--kind group --path Results/<group>` for a directory; every member remains subject to human-output validation. Use individual registration for outputs with different producers or contracts. See the helper sections below.
- Rebuild the same registered path when a deliverable changes. Use `result --replace` only for an intentional contract move.
- Put reusable machine data in Data. Put QA, provenance, manifests, diagnostics, traces, and session state in Audit.
- Build run output in a stage-specific system temporary directory. Validate schema, provenance, acceptance, and read-back there.
- Atomically replace the whole `Audit/Runs/<stage>/current/` tree only after checks pass. Publish Results afterward.
- Leave the prior `current/` untouched on failure. Keep no persistent staging, dated, historical, or backup sibling.

## Functions And Module Audit

- Create functions for reuse or genuinely error-prone logic. Use Roxygen and executable tests for reusable functions and critical logic. A simple local helper can use a clear name and a short comment; do not require a separate test/doc scaffold for it.
- Audit a risky analysis step or module once, covering its important functions together: inputs, outputs, actual scientific predicates, edge cases, executable checks and limits. Risk includes eligibility, timing, joins, exposure, outcomes, missingness, weighting and inference.
- Use `module-audit` with a stable name and the relevant R sources. Reuse that audit and refresh all source hashes after verification. Existing per-function audits remain valid; new work does not require one document per function.
- Keep source Rmd only, with no rendered audit HTML. See the helper sections below for commands.

## Output groups

Register one stable directory containing related current human outputs from the same producer. Use `--kind group` with the existing result/deliverable command; the directory must sit below Results/Deliverables, not equal the whole role. A group may contain mixed table/figure/report formats, but no machine artifacts, symlinks, or historical files. At least one output must exist.

One ID, audience and producer apply to all group members. Rebuild the same directory, remove obsolete outputs, run `index` and `validate`. Group membership is the current directory tree; executable checks/Audit must still establish that the expected outputs were produced. Overlapping group/file registrations are rejected. Keep existing individual registrations; consolidate only as an explicitly authorized ownership move. A group does not change publication or scientific acceptance requirements.

```text
result TARGET --id main-analysis --path Results/main-analysis --kind group --audience formal-review --producer R/analysis.R
```

Run `result --help` for allowed audience values. The producer must be an existing script within the R role.

## One pending-decision list

```text
review list TARGET
review raise TARGET --input TEMP_JSON
review resolve TARGET --id A-0001
```

`review list` returns JSON with `project`, `count`, and `items`. Each item includes ID, title, source path, status, blocking state and next action. Council items also carry the current formal version number. An absent Freeze directory requires no Council dependency; an existing Freeze directory is read through the installed OppenCouncil package. Use its Python environment if the default interpreter cannot import it. Unreadable Council records produce an error, never a falsely complete empty list.

Pending Council questions and candidates are read in place. Historical records and effective frozen versions without an open draft are omitted. Discussion reopened on an effective version remains pending while that version stays effective. `blocking: null` for Council means no blocking judgment was made; AI must assess scientific impact from the source. Resolve a Council item through its own discussion/confirmation workflow, never `review resolve`.

Only material non-Council issues use `review raise/resolve`; the payload is the existing Attention payload. Existing Attention storage, IDs, lifecycle and MCP reading remain compatible. The list is a derived query, not another file to maintain. Never duplicate the same question in both sources.

## One audit per analysis module

```text
module-audit TARGET --module cohort --source R/cohort.R --source R/dates.R --risk-reason "Eligibility and time-zero assignment"
module-audit TARGET --module cohort --input TEMP_JSON
```

The first command locates or creates `Audit/Modules/audit_cohort.Rmd`. Complete it using an external temporary JSON with exactly `purpose_and_risk`, `contract`, `edge_cases_and_verification`, `known_limits` (nonempty text). The second command refreshes the hashes of all registered sources and removes the payload on success. Run the described verification before completing an audit. Pass repeated `--source` arguments with completion only when intentionally changing its source set.

A draft/unfinished audit, changed source hash, missing source or rendered HTML fails validation. The project map lists module audits alongside existing function audits. Existing `function-audit` records and commands remain supported; the daily policy does not create one record per function. The helper records verification descriptions and hashes; it does not execute R tests for you.

## Material issues outside Council

Use the existing Council question for definition choices. Do not copy it into Attention. For a separate evidence-backed, material issue outside authorized work that needs a new human decision, use `review raise`; use `review resolve` only after resolution. The helper retains `Attention/` storage and the old `attention` commands for compatibility, including MCP readers. Memory remains unchanged.

Noteworthy does not mean Attention. Known pending work is not Attention when already covered by the authorized workflow. Attention is not a TODO system. Exclude routine debt, upgrades, naming and speculative improvements. Mark an issue blocking when it undermines the requested result's correctness; listing it does not make the result complete. Read **Attention Payload** in [managed-systems.md](managed-systems.md) only when raising a non-Council issue.

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

## Implementation completion

1. Run relevant R/unit tests and every contract test linked to changed canonical topics.
2. Confirm no second current definition, stale frozen content, parallel old/versioned document, unregistered Result, or invalid Audit run tree remains.
3. Complete any triggered module audit. Evaluate Decision Memory and pending decisions explicitly; "none required" is normal.
4. Do not claim an affected analysis complete while a relevant blocking Attention undermines correctness.
5. Require Memory and Attention indices to match entries and no legacy/alternative managed topology to remain.
6. Run `index`, then require `validate` to exit zero.
7. Report current deliverables, verification, migration behavior when applicable, and unresolved blockers.
