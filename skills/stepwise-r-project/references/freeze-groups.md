# Joint decision and dependency operations

Use a runtime that exposes `group-change` / `freeze_change_group` and structured dependencies (Council 0.2+; MCP 0.7+). Existing ungrouped projects remain readable. The first group or dependency write advances the Freeze manifest to schema 2; older writers reject it. Upgrade every runtime that writes that project before enabling this feature.

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

Before building `options`, apply “Readable rules and inline parameters” in [freeze-workbench.md](freeze-workbench.md). Each option must cover all member IDs in `rules` with decision-focused wording. The example deliberately keeps a selectable delay inside one approach. Save each complete normative candidate separately with `definition_draft`, and read back both options and candidates before handoff.

Each question belongs to at most one group. `update` uses the same shape and preserves earlier membership/options in history. `comment` takes text or `{"text":"...","question_id":"F-000001"}` for a member-specific comment. Reuse the same request/content after an uncertain retry; reload after a revision conflict. AI creates, updates and discusses groups. Membership and dependency management belong to CLI/MCP, with no human-facing management controls. Put readable comparisons in discussion/options; do not generate HTML simulations. Only the person can record an option preference, open group revisions or confirm them.

## Dependencies on a candidate

Use `ai-change` / `freeze_change_question`, operation `definition_draft`, with this value:

```json
{"text":"Complete normative wording…", "dependencies":[
  {"question_id":"F-000001", "kind":"required", "reason":"Defines the receipt consumed during recovery"}
]}
```

The store binds the current version and hash. To cite an exact historical version supply `version` and `text_sha256`; stale required bindings block confirmation. An unresolved same-group dependency is bound to the jointly approved version. For `kind: "conditional"`, supply `condition` and boolean `active`; `reference` never blocks. A string-only candidate edit preserves existing dependencies. An explicit list replaces them, so removing a requirement must be justified in discussion.

After an upstream change, use `dependency_review` only after checking that the current formal wording remains correct without alteration. Value: `{"bindings":{"F-000001":[2,"exact-text-sha256"]},"reason":"Which changed clause was checked, and why the consumed rule is unchanged"}`. Supply every active required binding. A changed interpretation needs a new candidate and human confirmation, never a compatibility receipt.

## Persistence and handoff

The authoritative record remains `Freeze/questions/F-NNNNNN.json` → `definition`. `Freeze/decision-groups.json` owns group metadata/conversation and joint confirmation references. Read a project consistently with the supported store/CLI/MCP snapshot; a raw multi-file scan during writes is not a transactional snapshot. After an interrupted confirmation the next supported read completes journal recovery before returning. Never hand-edit the transaction or imitate a human approval through scripts/MCP.
