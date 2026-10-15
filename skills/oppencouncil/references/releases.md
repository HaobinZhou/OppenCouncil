# Requested local research snapshots

The research snapshot command implements an explicit human request for a submission, revision, preprint, presentation or collaborator package. `human_request` records that request; filling the field does not create authorization to package a project on the agent's initiative.

Use the project helper's `release create TARGET --check --input REQUEST.json --plan OUTSIDE_PROJECT.json`, inspect the returned inventory, then apply that exact plan with `release create TARGET --apply --plan OUTSIDE_PROJECT.json`.

Required input fields:

| Field | Value |
| --- | --- |
| `human_request` | The actual request for this snapshot |
| `purpose` | `submission`, `revision`, `preprint`, `presentation`, `collaborator`, `other` |
| `label` | Human-readable package label |
| `environment` | `{languages:{name:version}, packages:{name:version}}` from the actual environment |

Optional `environment_files` includes existing environment records; `article_numbers` maps output IDs to manuscript numbering for this snapshot.

The plan includes current Results, producers and shared functions/configuration, bound F records/dependencies/assets and all classified project-produced Data. Original inputs are excluded from the ZIP and identified by source, version, size and hash. Unknown Data classification blocks packaging. Old registered Results lacking specifications are identified in the manifest and remain eligible.

Apply recomputes input bindings, streams and verifies each archive member, and commits the ZIP and ledger together. The new read-only archive is named under Releases with date, purpose and sequence; an existing archive is not overwritten. ZIP files are excluded from Git, while `Releases/index.json` keeps their checksums and provenance visible. `release verify TARGET` checks missing or changed packages against that ledger.

The snapshot captures current files and their recorded provenance. Reproducing the outputs additionally requires the matching original inputs and the recorded execution environment; a successful archive checksum alone is not a scientific reproduction result.
