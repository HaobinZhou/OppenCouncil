# Source and claim interface

Local `evidence-index TARGET` lists exact versions; `evidence-read TARGET --path PATH` returns one. MCP clients use `council_evidence_index` and `council_read_evidence` for shared records and submit contributions through [council.md](council.md). Local curation uses [work-commit](local-council.md).

In `work-commit`, `evidence` is an array of `{path, value}`. Source paths are `evidence/sources/S-NNNNNN/rNNNNNN.json`; claims use `evidence/claims/E-NNNNNN/rNNNNNN.json`. The ID and version match the path; versions are consecutive and append-only. An unused identity can start at version 1 after checking `evidence-index`.

Source value: `schema_version:1`, `id`, `version`, `source_type`, `verification`, `citation`, `read_scope`, `retrieved_at`, `disclosure`; `full_text_location` also needs `location`. Source types are `method_guideline`, `reporting_guideline`, `comparable_study`, `method_paper`, `project_experience`, `project_fact`, `engineering_constraint`. Verification methods are `full_text_location`, `abstract_only`, `model_claim_only`, `code_check`, `data_check`, `measurement`. Disclosure is `local` or `shared`.

For curated sources, `summary` explains what the source found before applying it to this project. For an empirical study, give the relevant population and setting, design or comparison, and results with the numbers and uncertainty needed to interpret them. For a method, explain its result and assumptions; for a local check, report the observations and their scope. Select enough substance for a reader to assess the cited inference. A topic description or a list of limitations alone is incomplete.

Make the source card readable in Council: use short paragraphs and descriptive Markdown headings to separate the study or method, relevant findings, and applicability. Emphasize the few results that carry the inference; retain the numbers, qualifications and context needed to interpret them instead of compressing them into one dense paragraph.

`read_scope` records what was inspected; `location` identifies the relevant passage or result. `summary` is optional in storage (1–10000 characters) so old versions remain readable; add a new version to improve an existing source, preserving the old one.

Research recommendation bases require original-text verification for literature sources. A `project_fact` or `engineering_constraint` can instead use `code_check`, `data_check` or `measurement`; abstract-only and model-only material cannot establish those facts. The type describes the actual source, not a way to bypass its verification requirement.

Claim value: `schema_version:1`, `id`, `version`, `claim`, `applicability`, nonempty `sources` with exact source-version paths, optional `counter_sources`, and `disclosure`. The server records contributor and time. External submissions retain their source identity and are locally assessed through [council.md](council.md).

Each claim states the inference its cited sources support. Separate local observations, literature findings and the recommendation's rationale when their supporting sources differ; a reference attached to the entire proposed rule does not establish every part of it.

A confirmed definition establishes the current rule, not evidence of its scientific merits. Cite its recorded rationale when relevant, rather than using confirmation status to justify the same choice. Keep agent instructions and reports of preservation, migration or submission in work comments or Audit. In the review basis, state the findings and resulting judgment; put each material limitation with the inference it qualifies instead of repeating it across every field.
