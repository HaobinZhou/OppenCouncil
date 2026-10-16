# Candidate and review packet interface

For research projects, complete the human-authorized continuation in [research-handoff.md](research-handoff.md) before synthesizing the recommendation. A saved `human_continue` wait blocks local candidate/packet preparation and entry into human review; adding evidence does not release it.

Local `work-read` returns the current definition, candidate, review basis and packet. These fields are saved with [work-commit](local-council.md); external contributors append evidence or comments through [council.md](council.md).

Read [evidence.md](evidence.md) when preparing or reassessing a review basis, including when reusing saved sources and claims.

## Divide a broad review

For a review spanning several independent questions or groups, the coordinator first divides the work into complete decision scopes with their linked members, alternatives and evidence. When subagents are available, delegate preparation of each scope, in batches within the available capacity. Start each with a fresh context, the scope and file pointers. Each subagent reads this Skill and the relevant references, checks original sources, and saves the full source and claim content for that scope. Give shared sources one owner so different scopes can reuse the same checked findings.

The coordinating agent integrates the prepared content, resolves conflicting interpretations and performs managed writes through the normal helper; subagents prepare separate drafts. Preserve the source detail needed for judgment during integration. The coordinator remains responsible for reading every resulting F or option and its cited evidence in the webpage. If delegation is unavailable, complete bounded scopes sequentially, retaining their full content before continuing.

After integrating a scope, the coordinator assigns a reviewer with a fresh context to read its saved questions, options and cited sources against the originals, using this Skill. The reviewer reports concrete deficiencies without rewriting the whole review. The coordinator resolves those findings through the helper and rereads the affected pages; unresolved substantive gaps remain explicit. Preparation and review subagents keep to their assigned scope rather than coordinating another full review.

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

Research/output-specification review requires checked source versions and a completed review packet; engineering review requires `review_packet.verification`. Human confirmation is a separate UI action. A changed basis with unchanged wording requests reconfirmation on the current version, without a new formal version.

For `human_review`, each decisive objection uses `disposition: "resolved"` or `"explained_tradeoff"` with its `reason`; `tradeoff` is a conclusion value, not an objection disposition.

Structured comparison groups use [groups.md](groups.md); discussion selectors use [selectors.md](selectors.md). Table and image specifications use [output-specifications.md](output-specifications.md).
