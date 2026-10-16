# Local Council interface

Use this reference for local record operations. The CLI is `python -m oppencouncil`; the project helper is `python ABSOLUTE_SKILL/scripts/oppencouncil.py`. `TARGET` is the project root. An explicit `--directory SITE` before the Council command selects the existing site; importing questions also registers the project there. Website registration and MCP access are separate.

## Bounded reads

```text
work-index TARGET [--actionable --offset N --limit N]
work-read TARGET --id F-NNNNNN|I-NNNNNN|B-NNNNNN
evidence-index TARGET [--source-id S-NNNNNN --offset N --limit N]
evidence-read TARGET --path evidence/sources/S-NNNNNN/rNNNNNN.json
definition TARGET --question F-NNNNNN [--version-number N]
```

`work-read` returns the item's revision/read set, work phase, candidate/current definition, inputs and unresolved pending items. Its `messages` contains only discussion referenced by unread inputs or unresolved pending items; it is not the complete discussion history. `snapshot TARGET` includes saved discussion history and also supports v3/v4 recovery inspection. A group owns shared discussion; a member F owns its definition. Source and claim paths identify immutable versions.

## Investigations and new questions

`investigation-create TARGET --input FILE.json` accepts:

```json
{"request_id":"triage-unique-id","title":"Question being checked","why":"Observed trigger or missing fact and source","dedupe_key":"stable-scope-key","blockers":[]}
```

It returns an allocated I ID. An investigation can close without creating an F. New questions use `import TARGET --input FILE.json` with `{"request_id":"batch-unique-id","questions":[{"title":"Decision","why":"Observed reason"}]}` and receive allocated F IDs. Existing IDs use updates.

## Atomic work updates

`work-commit TARGET --input FILE.json` accepts a stable `request_id`, the `read_set` returned by reads, and `changes`. Each changed item appears once. Optional `evidence` and `submission_reviews` share the transaction. An identical retry returns its saved result; conflicting revisions require a new read and reconciled payload.

```json
{
  "request_id":"assessment-unique-id",
  "read_set":{"I-000001":1},
  "changes":[{
    "id":"I-000001",
    "comments":["Finding, source and effect on the question."]
  }]
}
```

The `phase` object contains `phase`, `conclusion_type`, `reason`, `trigger_refs`, nonempty `affected_refs` and `completion_conditions` arrays, and optional `blockers`. Phases: `triage`, `evidence`, `prepare_review`, `human_review`, `closed`. Conclusions: `not_applicable`, `fact_lookup`, `covered`, `single_recommendation`, `parallel_recommendations`, `departure`, `tradeoff`, `needs_check`. An unresolved check cannot close. A phase update records scope, reason and completion conditions; it does not replace the current formal version.

`human_review` requires that item's candidate or effective-definition reassessment. Investigations and groups have no definition of their own: link the prepared F records instead. A group's review queue reflects its members; its phase need not be set to `human_review`.

Fields for a candidate and its review packet are in [review-packet.md](review-packet.md). Reply dispositions, pending work and cursors are in [resume.md](resume.md). Sources and claims use [evidence.md](evidence.md).

## Authorized conversation operations

`human-action TARGET --input FILE.json` executes an explicit human instruction through the same mutation and confirmation checks as the webpage. It is also available through the Skill helper. See [local-review.md](local-review.md) for its payload, review pacing and provenance. Ordinary `work-commit`, `ai-change` and `group-change` remain AI operations.

## Site and legacy operations

`register TARGET` registers existing records without duplication. `status TARGET` reports the selected site's project state and URLs. `open TARGET` starts or reuses that site. Reading a login page alone does not establish that project review content is accessible.

For presentation matrices, selectors and structured dependencies, the compatibility payload references are [group operations](groups.md) and [selectors](selectors.md). Their local storage operations remain supported; external MCP only provides the capabilities listed in [council.md](council.md).
