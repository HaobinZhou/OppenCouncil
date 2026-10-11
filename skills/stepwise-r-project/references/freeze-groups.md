# Joint decision and dependency operations

Use a runtime that exposes `group-change` / `freeze_change_group` and structured dependencies (Council 0.2+; MCP 0.7+). Existing ungrouped projects remain readable. The first group or dependency write advances the Freeze manifest to schema 2; older writers reject it. Upgrade every runtime that writes that project before enabling this feature.

## Prepare the decision topic

Start from the human decision and inspect active blocking dependencies. Include unresolved rules whose alternatives must be understood together, even for one-way dependencies. Shared vocabulary or graph connectivity alone does not justify merging independent topics. Grouping preserves separate F IDs, candidates, formal versions and histories.

For every prerequisite outside the topic, either bring in the coupled choice or prepare it first as an independently decidable, reusable upstream topic. Do not leave a singleton topic with an unexplained list of open prerequisites. Check topic-level cycles: regroup coupled choices or correct an evidenced dependency error. Never delete or downgrade a real dependency just to remove warnings.

Prepare upstream topics and consumers in the same round where evidence permits, with unprepared items clearly marked. Each option covers every member with concise comparable rules, consequences and trade-offs; follow the comparison decomposition in [freeze-workbench.md](freeze-workbench.md) and the selector syntax in [freeze-examples.md](freeze-examples.md). Keep complete candidates separate. Update every affected candidate after a changed preference, preserving unchanged rules.

Required prerequisites block while unresolved; conditional ones block only under an explicitly active condition; references inform without blocking. A downstream proposal may be discussed while blocked but cannot be called ready to confirm. Group membership itself never blocks individual confirmation. Explicit human batch confirmation can approve coupled internal prerequisites together; external prerequisites must already be satisfied. AI never imitates either approval.

After upstream changes, preserve downstream text/history and assess the exact consumed rule. A semantic change needs a revised candidate and human confirmation. Verified unchanged meaning permits a `dependency_review` receipt using the payload below; that is an impact check, not a new human choice. Reads and refreshed views never silently advance stored bindings.

## Combined choices

Read `snapshot TARGET` first. Use `group-change TARGET --input payload.json`; the MCP equivalent is `freeze_change_group` with its usual `project_id` and explicit `actor`. A create payload:

```json
{
  "group_id": null, "operation": "create", "expected_revision": 0,
  "request_id": "stable-group-request",
  "value": {
    "title": "Saving and recovery", "purpose": "Choose one consistent persistence behavior",
    "member_ids": ["F-000001", "F-000002"],
    "options": [{"label": "Automatic reconciliation", "rules": {
      "F-000001": "A save returns a durable request receipt.",
      "F-000002": "Match the receipt before clearing the local draft.\n\n**Retry delay:** {{choice:retry_seconds;Retry delay;5 seconds;10 seconds}}"
    }, "consequences": "A lost response need not cause a duplicate message.",
    "tradeoffs": "Requires a stable request identity. A 5-second delay checks sooner; 10 seconds reduces request frequency. Neither changes receipt matching."}]
  }
}
```

Before building `options`, apply the comparison decomposition in [freeze-workbench.md](freeze-workbench.md). Each option must cover all member IDs in `rules` with decision-focused wording. The example deliberately keeps a selectable delay inside one approach. Save each complete normative candidate separately with `definition_draft`, and read back both options and candidates before handoff.

Each question belongs to at most one group. Grouping organizes review, not the unit of freezing: people can confirm one member without confirming its siblings, subject to that member’s real prerequisites. The separate group action remains available for explicit batch confirmation, including cyclic dependencies. `update` uses the same shape and preserves earlier membership/options in history. `comment` takes text or `{"text":"...","question_id":"F-000001"}` for a member-specific comment. Reuse the same request/content after an uncertain retry; reload after a revision conflict. AI creates, updates and discusses groups. Membership and dependency management belong to CLI/MCP, with no human-facing management controls. Put readable comparisons in discussion/options; do not generate HTML simulations. AI submits revised member candidates through `definition_draft`, including after freezing. Only the person records preferences, confirms or withdraws candidates; opening all group members together remains an optional human action.

## Dependencies on a candidate

Use `ai-change` / `freeze_change_question`, operation `definition_draft`, with this value:

```json
{"text":"Complete normative wording…", "dependencies":[
  {"question_id":"F-000001", "kind":"required", "reason":"Defines the receipt consumed during recovery"}
]}
```

The store binds the current version and hash. To record an exact binding supply `version` and `text_sha256`. When that required binding is absent or outdated, the refreshed candidate view proposes the current formal version and exposes `candidate_dependency_updates` with old/new version numbers and complete wording for human review. The confirmation token protects that exact proposed binding; only human confirmation stores it. AI must reconcile candidate meaning against the new prerequisite before handoff. Already formal versions without a candidate still require compatibility review or a complete revision. An unresolved same-group dependency can alternatively bind to the jointly approved version in an explicit batch confirmation. Previously bound versions never advance silently. For `kind: "conditional"`, supply `condition` and boolean `active`; `reference` never blocks. A candidate submission with omitted dependencies preserves the existing candidate or current version bindings. An explicit list replaces them, so removing a requirement must be justified in discussion.

After an upstream change, use `dependency_review` only after checking that the current formal wording remains correct without alteration. Value: `{"bindings":{"F-000001":[2,"exact-text-sha256"]},"reason":"Which changed clause was checked, and why the consumed rule is unchanged"}`. Supply every active required binding. A changed interpretation needs a new candidate and human confirmation, never a compatibility receipt.

## Persistence and handoff

The authoritative record remains `Freeze/questions/F-NNNNNN.json` → `definition`. `Freeze/decision-groups.json` owns group metadata/conversation and joint confirmation references. Read a project consistently with the supported store/CLI/MCP snapshot; a raw multi-file scan during writes is not a transactional snapshot. After an interrupted confirmation the next supported read completes journal recovery before returning. Never hand-edit the transaction or imitate a human approval through scripts/MCP.
