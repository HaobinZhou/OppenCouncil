# Project helper interface

Run `python ABSOLUTE_SKILL/scripts/oppencouncil.py COMMAND TARGET ...` with the installed Council Python environment. The aliases `stepwise_r_project.py` and `oppen_project_steward.py` select the same v5 implementation by the actual project marker. Existing v3/v4 projects continue through their original implementation until explicit migration.

## Project and registered owners

`index TARGET` returns type, roles, owners, outputs, Memory summary and paginated Council work. `validate TARGET` checks the managed baseline and registered structures. `project-type TARGET` reads the declared type; `--set research|general --reason TEXT` records an explicit type change. Type and root/namespace layout are independent.

`init TARGET --project-type research|general [--layout root|namespace]` creates a new project. Existing ordinary directories use `adopt TARGET --check --project-type TYPE --input FILE`, followed by `adopt ... --apply` with the same reviewed payload. Adoption payload fields are `role_mappings`, `initial_canonical_registrations`, `initial_deliverable_registrations`; empty values are valid. The helper registers existing paths without moving source or outputs. Existing governance markers use [migration.md](migration.md).

`canonical TARGET --topic KEY --path PATH --verification TEST [--section SECTION --status STATUS --replace]` binds a definition to a check. For new research definitions the owner is an already-confirmed F JSON, section `definition`; the check is registered on that F. Existing migrated Markdown owners remain readable. General projects can register a stable file/section with `draft`, `partially-frozen` or `frozen` status. `--replace` represents an owner move.

## Outputs and data

`result TARGET --input FILE` and `deliverable TARGET --input FILE` take `id`, `path`, `kind`, `audience`, `producer`. Research outputs require a confirmed output specification and a numbered producer, regardless of language. The specification binding is `{question_id, version, text_sha256}`. A group supplies `member_specifications` for every member. `--replace` changes an intentional registered path; ordinary regeneration uses the existing registration.

Existing migrated research outputs without specifications remain eligible for unchanged regeneration with a warning. New outputs or declared structural changes require confirmed specifications. The helper verifies bindings and topology; inspecting the actual generated content establishes whether its meaning and formatting match the specification.

`data register TARGET --input FILE` takes `{path, kind, version}` plus `source` for `raw` or `producer` for `derived`. Registration records current size and SHA-256 without moving data. Research derived-data producers are numbered scripts.

## Checks and Audit

Audit creation and completion are separate calls:

```text
contract-audit TARGET --topic KEY --source FILE --risk-reason TEXT
contract-audit TARGET --topic KEY --input FILE
```

The completion call accepts `--input` without the creation options. `module-audit` is an alias. Research completion payload: `summary`, `checks` (executable file paths), `verification`, `limits`. General payload: `purpose_and_risk`, `contract`, `edge_cases_and_verification`, `known_limits`. The helper binds source/check hashes; those hashes do not assert execution. The v5 `function-audit` write command is retired and old audit files are read-only history.

`audit promote TARGET --stage KEY --input EXTERNAL_DIRECTORY` verifies and atomically replaces that stage's entire current evidence tree. The input directory is retained. `audit recover TARGET --stage KEY` recovers recognized old failed staging into a verified external copy before removing it from the project; it does not remove unclassified artifacts or current evidence.

## Investigations and Memory

`review list TARGET [--actionable --offset N --limit N]` lists work. `review raise TARGET --input FILE` accepts `{title, why, dedupe_key, blockers?}` or the compatible old Attention payload. `review resolve TARGET --id I-NNNNNN --reason TEXT --conclusion fact_lookup|covered|not_applicable` closes a resolved investigation; unresolved feedback must first be handled through [local-council.md](local-council.md). Migrated A IDs resolve to their investigation; F definitions are handled in Council. `attention` is a command alias.

Memory admission remains in [SKILL.md](../SKILL.md#decision-memory); entry and relation payloads are in [memory.md](memory.md).

## Planned file operations

Script changes, experiments and snapshots use an external immutable plan:

```text
OPERATION TARGET --check --input REQUEST.json --plan OUTSIDE_PROJECT.json
OPERATION TARGET --apply --plan OUTSIDE_PROJECT.json
```

Analysis scripts use two-digit execution prefixes; multiple scripts may share a number within the same directory or across subdirectories. Registrations identify scripts by their full project-relative paths. Shared numbers do not require renumbering.

`scripts renumber` input: `{order:[all analysis-script paths], start:1, step:10}`. This explicit operation assigns a new sequence in the supplied order. `scripts rename-directory` input: `{to:"Scripts"}` preserves existing filenames and shared numbers. Apply updates registered producers, verification paths and literal current references while preserving historical wording; runtime-computed paths still need code inspection.

`explore create` input: `{slug, question}`. `explore update` can bind `id`, experiment-local `scripts` and `outputs`, and `in_progress`/`retained` status. `explore archive` needs `id` and `conclusion`. `explore promote` also needs registered `result_ids`; it records the transfer after formal outputs exist and does not itself merge experimental code. `explore index` gives the current experiment index.

`release create` inputs and local snapshot contents are described in [releases.md](releases.md). `release verify TARGET` checks the saved archives and checksum ledger.

The helper owns generated registries, IDs, baselines and transaction recovery. A reported conflict identifies the changed paths; editing a baseline to suppress that conflict would discard its provenance check.

When the human mentions submission, revision, a preprint, presentation or sharing with collaborators without requesting a snapshot, give one brief snapshot reminder; do not create a package.
