# Decision Memory payload and relationships

This is the approved contract implemented by the shared v5 Memory helper. Existing v3/v4 projects continue using their original implementation until explicitly upgraded. The admission policy is in [SKILL.md](../SKILL.md#decision-memory).

For an explicitly migrated v5 project, invoke `scripts/oppencouncil.py memory add TARGET --input PAYLOAD.json`; use `memory index TARGET` and `memory read TARGET --id M-NNNN` for bounded reads. The helper leaves the submitted payload file intact. Startup checks for interrupted project transactions before reading the project anchor.

## New entries

Use `why` for the decision rationale. Required nonempty text fields are `title`, `before`, `trigger`, `decision`, `why`, `rejected_or_prior_approach`, and `consequence`.

`basis` is required nonempty text for a **research** project and optional for a **general** project. If supplied, it must be nonempty text. It identifies the traceable evidence supporting the decision, not internal reasoning. Use the project's declared type, independently of programming language, directory layout, the scientific or technical subject of the decision, or the incoming payload's field names. All newly created entries, including those submitted through legacy payload aliases, follow this requirement.

`related_topics`, `supersedes`, and `invalidates` are arrays of IDs. Each may be omitted and defaults to `[]`. Zero related topics is valid.

## Relationships and helper ownership

- Every `supersedes` or `invalidates` target must be an existing **active** Memory entry. `supersedes` changes the target to `superseded`; `invalidates` changes it to `invalidated`.
- The same ID must not appear in both `supersedes` and `invalidates`.
- Do not supply or manually edit `status`, reverse links, entry IDs, filenames, or paths. The helper allocates IDs and manages status, reverse links, storage paths, and the Memory index.

The new entry, target status changes, matching reverse links, and index update form one managed write. On failure, preserve the prior state. Other than the helper's status and relationship maintenance, existing entries are never edited.

## Compatibility with both legacy formats

Read both legacy payloads and persisted records:

| Legacy governor | Rationale | Basis | Persisted format |
| --- | --- | --- | --- |
| Stepwise | `scientific_or_technical_rationale` | Required by the legacy payload | Fixed field sequence |
| Steward | `why` | Absent from the legacy payload | Frontmatter and fixed body sections |

Map `scientific_or_technical_rationale` to `why` in memory without rewriting the source record. Preserve an existing `basis` as its own field. An old persisted record without `basis` remains readable; do not invent evidence or rewrite history to satisfy the new-entry requirement. Reading an old record and creating a new record are separate operations.

Accept both rationale field names on new submissions. If both are supplied, require identical text and reject conflicts rather than silently selecting one. A new research entry must supply `basis` even when submitted using the old Steward payload shape. New general entries may omit it; old Stepwise records retain it in full.

Keep each legacy record's ID and source format. A relationship update uses that format's writer and changes only the explicitly affected status and reverse links; preserve the original rationale, basis, and other content. Do not bulk-convert, renumber, or move legacy files.

New records use frontmatter and fixed body sections with an explicit v5 Memory format marker. Include a separate Basis section when supplied; it is always present for a new research entry. Readers retain source-format and source-path information internally, without writing provenance labels into old records.
