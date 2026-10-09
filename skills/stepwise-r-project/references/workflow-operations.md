# Daily helper operations

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
