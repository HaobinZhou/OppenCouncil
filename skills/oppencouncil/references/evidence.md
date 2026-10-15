# Source and claim interface

Local `evidence-index TARGET` lists exact versions; `evidence-read TARGET --path PATH` returns one. MCP clients use `council_evidence_index` and `council_read_evidence` for shared records and submit contributions through [council.md](council.md). Local curation uses [work-commit](local-council.md).

In `work-commit`, `evidence` is an array of `{path, value}`. Source paths are `evidence/sources/S-NNNNNN/rNNNNNN.json`; claims use `evidence/claims/E-NNNNNN/rNNNNNN.json`. The ID and version match the path; versions are consecutive and append-only. An unused identity can start at version 1 after checking `evidence-index`.

Source value: `schema_version:1`, `id`, `version`, `source_type`, `verification`, `citation`, `read_scope`, `retrieved_at`, `disclosure`; `full_text_location` also needs `location`. Source types are `method_guideline`, `reporting_guideline`, `comparable_study`, `method_paper`, `project_experience`, `project_fact`, `engineering_constraint`. Verification methods are `full_text_location`, `abstract_only`, `model_claim_only`, `code_check`, `data_check`, `measurement`. Disclosure is `local` or `shared`.

Research recommendation bases require original-text verification for literature sources. A `project_fact` or `engineering_constraint` can instead use `code_check`, `data_check` or `measurement`; abstract-only and model-only material cannot establish those facts. The type describes the actual source, not a way to bypass its verification requirement.

Claim value: `schema_version:1`, `id`, `version`, `claim`, `applicability`, nonempty `sources` with exact source-version paths, optional `counter_sources`, and `disclosure`. The server records contributor and time. External submissions retain their source identity and are locally assessed through [council.md](council.md).
