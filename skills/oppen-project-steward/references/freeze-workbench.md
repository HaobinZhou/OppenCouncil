# OppenCouncil review rounds

Use for preparing or continuing human review. Keep the project's original governor. Read current records before writing; the user saves feedback and manually invokes AI to continue. Saving the webpage does not start an AI turn.

## Evidence and necessity first

Read the relevant Canonical owners, project/source evidence and saved discussion/candidates. Use `Freeze/manifest.json` as the question index and the supported snapshot for a consistent read. Reuse existing IDs and decisions; investigate missing history through [freeze-recovery.md](freeze-recovery.md) before asking settled questions again.

Before adding or materially revising an F, establish what remains unresolved, why existing authority is insufficient, and what the proposed change affects. Resolve inspectable facts yourself using the applicable data snapshot/population, implementation and current checks. An imaginable exception, field name or generic best practice is insufficient. Already-settled mappings and routine defensive checks belong in their existing owner, code or tests. Skip unchanged meaning and presentation-only revisions. A genuinely new requested requirement can warrant review even before data exist; label that scope explicitly.

Present all currently necessary, evidence-backed decisions in the round. Later rounds address new information; do not defer explanations or accessible investigation to save drafting effort. When evidence is unavailable, name the exact missing fact and affected decision, and keep it unprepared instead of inventing a policy for confirmation.

## One independently reviewable decision per F

Split separable decisions that each pass the necessity check; keep inseparable conditions of one rule together. Use a topic/group for related choices and structured dependencies for consumed rules. Reference existing authority by full IDs such as F-000013 instead of copying its text. Completeness belongs across the linked rules, not in one oversized F.

Write for a reviewer with severely limited sustained attention. Start with the decision/change and practical effect. Use descriptive Markdown headings (`##`, then `###`), short paragraphs or lists and parallel comparison rows. Each block carries one point; bold emphasizes rather than replacing a section hierarchy. Keep short single-point replies/cells simple. Store Markdown source, not HTML. Preserve human replies and historical discussion.

## Discussion and comparisons

Discussion explains concrete actions, consequences, prerequisites, trade-offs and a justified recommendation. Explain unfamiliar terms. For difficult choices, work through the same concrete case under each option now; label invented data. “See an example later” or a method name is not a usable choice. Use prose/tables, without HTML simulations or a separate demonstration workflow. Ask for facts only after checking available sources, specifying the input needed.

For engineering choices, explain affected behavior, user experience, reliability, operating cost and required work where relevant. Separate expected consequences from measured results.

Decompose comparisons before writing columns:

- Explain shared rules once in the current discussion. Keep each member cell understandable with a short rule and named reference; do not paste complete candidates into every cell or say only “same as A”.
- Use inline choices for independent values/subchoices within one approach. Do not create new columns for each number or enumerate every combination. One approach with selectors is valid.
- Use separate columns for routes with linked differences that must be judged together. State their distinguishing change first; a technical difference alone does not require duplicating the entire plan.

When writing selectors, read [freeze-examples.md](freeze-examples.md) for `{{choice:stable_id;label;value1;value2}}` syntax and compatibility rules. Read back the saved comparison: remove value-only duplicate columns and check that appropriate selectors actually appear. Candidate/formal text uses concrete proposed/confirmed values, never unresolved selector notation. Selected values and saved preferences are discussion, not approval.

Use `why` for the decision context, `source_summary` for constraining facts and `presentation` for the explanation plus matching suggestion labels. Group options and shared discussion use group operations. Keep hashes, checklists, tool logs and validation receipts in objective `review_note` or Audit, outside reviewer-facing content. These records must not contain hidden reasoning. Technical facts necessary to judge the choice remain visible and explained.

## Complete candidate wording

Write a complete proposed candidate for every new/reopened question in the announced review scope, including group members, before calling it ready. Use the justified recommendation as a proposal; do not imply acceptance or require the person to assemble wording from discussion/options. Read and reconcile human edits before replacing a draft; preserve unchanged members.

Within each decision's actual scope:

1. Resolve the named source rule and implementation. A direction, source name or field's existence does not define an algorithm.
2. Specify the operative predicate/action and relevant inputs, units, equality/thresholds, logic, time anchors, aggregation and exceptions. Include missing/conflicting-input handling when supported by the verified scope, not as generic template padding. Propose genuinely unbound choices explicitly.
3. Bind consumed authority precisely. Use structured Council dependencies; for other owners record path/section and revision/hash in verification evidence. A mutable “latest” or bare source name is insufficient. Read [freeze-groups.md](freeze-groups.md) when creating/reviewing those bindings.
4. Check concrete normal and relevant boundary cases against the wording. If two materially different outcomes still fit, supply the missing rule or surface the decision now. Record objective results in `review_note`/Audit. Keep the candidate itself a clean normative document.

Necessary decision detail takes priority over brevity. Saved text, headings, hashes, software tests or a confirmation do not prove semantic completeness. If a confirmed rule has a gap, preserve its history and prepare the necessary correction; never silently overwrite it or clear a human dispute.

## Related decisions and formal authority

When choices must be understood together, load [freeze-groups.md](freeze-groups.md) to prepare a coherent topic and its dependencies. Grouping is AI's work. Keep each F independently confirmable when its real prerequisites are satisfied; group membership alone never requires batch freezing. A topic that sends the reviewer to unresolved prerequisites elsewhere is not ready until those choices are grouped coherently or prepared as independently decidable upstream topics.

`Freeze/questions/F-NNNNNN.json` → `definition.current_version` selects the sole effective wording in `definition.versions`; `definition.draft` is the candidate. Discussion, legacy replies and recovered summaries are not formal versions. AI can submit a complete `definition_draft` before or after freezing without a human opening step. An unchanged submission creates no new version. Only explicit human confirmation makes a candidate the current version; the prior version remains effective until then and becomes immutable history afterward. AI/MCP cannot confirm, withdraw or overwrite formal versions. Confirmation grants no separate execution/deployment authority.

Canonical registers that same JSON `definition` scope, without a second synchronization approval. Other documents reference it or generate read-only views. For registration or adoption from a previous Markdown owner, read [freeze-operations.md](freeze-operations.md).

## Writes and handoff

Use `oppencouncil snapshot TARGET`, `ai-change TARGET --input update.json` and `definition TARGET --question F-000001`, or their authorized MCP equivalents. Do not hand-edit question JSON. Question updates carry `question_id`, `operation`, `value`, current `expected_revision` and a stable `request_id`. Reuse the exact request/content after an uncertain retry; on conflicts reread and reconcile edits. Load [freeze-operations.md](freeze-operations.md) for operation payloads, imports or site setup. MCP writers declare the actual actor (`codex` or `chatgpt`); preserve unknown historical authors.

Before returning the review link:

- Read back the entire announced scope, not only the most recently edited records. Verify necessary focused decisions, usable comparisons, complete saved candidates, real dependency readiness and preserved history. Explicitly identify blocked/unprepared IDs and their effects; do not present empty or incomplete candidates as ready.
- On first creation, register the project in the intended Council site and verify its directory entry and readable review content using the setup reference, even if records were created through MCP. Files alone do not complete web delivery. Reuse existing permissions and service configuration; website registration grants no MCP access.
- Verify the page in a browser when available, otherwise use authorized site API reads and report visual verification as pending. Return the verified project URL, site URL and port; claim remote forwarding only after testing it. Unsaved browser drafts are not project records: save them through the human workflow or identify excluded drafts.
- Report discussion saved, candidate ready, formally confirmed and implementation verified as distinct states. A discussion-only round needs content and persistence acceptance; authorized implementation subsequently uses the governor's implementation checks.
