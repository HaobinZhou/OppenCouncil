# Candidate and review packet interface

For research projects, complete the human-authorized continuation in [research-handoff.md](research-handoff.md) before synthesizing the recommendation. A saved `human_continue` wait blocks local candidate/packet preparation and entry into human review; adding evidence does not release it.

Local `work-read` returns the current definition, candidate, review basis and packet. These fields are saved with [work-commit](local-council.md); external contributors append evidence or comments through [council.md](council.md).

Read [evidence.md](evidence.md) when preparing or reassessing a review basis, including when reusing saved sources and claims.

## Divide a broad review

For a review spanning several independent questions or groups, parallelize complete decision scopes, keeping linked members, alternatives and evidence together. Every subagent has the same end-to-end responsibility for its assigned scope. Do not divide agents into different roles such as literature search, analysis, writing or review, or pass one scope through a chain of specialist agents. Start each with a fresh context, its scope and file pointers. Assign a shared source to one of the scope owners so other scopes can reuse its checked findings.

Each scope owner reads this Skill and the relevant references, checks the original sources, prepares the full source and claim content and complete alternatives, and checks its own result against the originals. After integration, the same owner reads back its saved F or options and cited evidence, checks the presentation in the chosen review channel, and resolves deficiencies within that scope. Retain the substance needed for judgment throughout; a short handoff summary does not replace the complete work. Scope owners do not coordinate another full review.

The coordinating agent integrates the separate drafts, resolves cross-scope conflicts and performs managed writes through the normal helper. It remains responsible for final acceptance of every resulting F or option and its cited evidence in the chosen review channel; unresolved substantive gaps remain explicit. Queue remaining scopes for the next available slot rather than changing agent roles or absorbing all remaining scopes into the coordinator. If the environment cannot run subagents, complete bounded scopes sequentially, retaining their full content before continuing.

## Prepare the decision

Keep each separable necessary decision in its own F; keep inseparable conditions together and group related choices. Lead with the decision and practical effect, using descriptive headings, short paragraphs and parallel comparisons. Explain unfamiliar terms and shared rules once. Use inline choices for independent parameters within one approach; reserve separate columns for linked differences that must be judged together. Compare difficult alternatives on the same concrete case, labelling invented data. Candidates use concrete proposed values; selections are not confirmation.

For affected scientific choices, read [research-review.md](research-review.md).

Before marking a candidate ready, check its actual decision scope:

1. Resolve the source rule and implementation; a source name or field's existence is not an algorithm.
2. State the operative inputs and predicates/actions, including relevant units, thresholds, time anchors, aggregation and exceptions. Add missing/conflicting-input handling only when supported by the verified scope.
3. Bind consumed Council definitions by exact version through [groups.md](groups.md); identify other authorities by path/section and revision, retaining integrity hashes in Audit.
4. Walk through normal and relevant boundary cases. If materially different outcomes still fit, resolve or explicitly propose the missing decision now. Keep unresolved necessary gaps out of human-review readiness; promising to specify them later is not completeness.

Read each saved F or option together with its cited source cards as a human reviewer: can the reader follow the findings, why they support this choice, and what changes with a credible alternative? Repair missing substance through the normal helper, preserving human edits and unchanged members. For a bulk review, finish and inspect one coherent decision scope before moving to the next; report unfinished scope explicitly. Keep the candidate a complete proposed rule and objective checks in Audit; brevity, formatting and passing software tests do not establish semantic completeness.

## Save the review

Available change fields:

| Field | Shape |
| --- | --- |
| `problem_type` | `project_fact`, `research_method`, `engineering`, `output_specification`, `unknown` |
| `definition` | `{"operation":"definition_draft","value":"Complete candidate wording"}` or value `{text, dependencies}` |
| `question_ids` | Existing F IDs linked from an investigation |
| `review_basis` | `{claims: [exact claim-version paths], summary: text}` |
| `review_packet` | Research fields `common_practice`, `support`, `applicability`, `departure_check`, `default`, `project_reason`; optional `objections: [{disposition, reason}]` |
| `evidence_refs` | Existing evidence paths |
| `evidence_impact` | `{classification: non_material\|needs_check\|weakened\|reassessed, reason, refs}` |
| `external_brief` | `{disclosure: "shared", summary, questions?, uncertainties?, applicability?, excluded_directions?}`; optional values are text |

Research/output-specification review requires checked source versions and a completed review packet; engineering review requires `review_packet.verification`. Human confirmation is a separate authorized action in either the webpage or local conversation; use [local-review.md](local-review.md). A changed basis with unchanged wording requests reconfirmation on the current version, without a new formal version.

For `human_review`, each decisive objection uses `disposition: "resolved"` or `"explained_tradeoff"` with its `reason`; `tradeoff` is a conclusion value, not an objection disposition.

Structured comparison groups use [groups.md](groups.md); discussion selectors use [selectors.md](selectors.md). Table and image specifications use [output-specifications.md](output-specifications.md).
