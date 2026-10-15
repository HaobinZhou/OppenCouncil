# Decision groups and dependencies

Groups organize related F records while preserving each member's candidate, current version and history. A member can be confirmed independently when its prerequisites are satisfied. Explicit human batch confirmation also supports cycles inside the group. Local curation uses `python -m oppencouncil group-change TARGET --input FILE.json`; MCP clients can read groups and contribute comments, but cannot curate membership or candidates.

Example request shape:

```json
{
  "group_id":null,
  "operation":"create",
  "expected_revision":0,
  "request_id":"group-request-id",
  "value":{
    "title":"Decision topic",
    "purpose":"Effect of the linked decisions",
    "member_ids":["F-000001","F-000002"],
    "options":[{
      "label":"Proposed approach",
      "rules":{"F-000001":"Rule for the first decision","F-000002":"Rule for the second decision"},
      "consequences":"Effect of these rules",
      "tradeoffs":"Costs and alternatives"
    }]
  }
}
```

`update` uses the group's ID and current expected revision, preserving earlier membership/options in history. Options cover all member IDs. Each F belongs to at most one group. `comment` accepts text or `{text, question_id}` for a member-specific contribution. The full normative candidates remain separate `definition_draft` updates on the F records; a group option is not a formal version.

## Candidate dependencies

The `definition_draft` value can be `{text, dependencies}`. A dependency identifies `question_id`, `kind` (`required`, `conditional`, `reference`), and `reason`. A conditional dependency additionally has `condition` and boolean `active`. Omitted dependencies preserve the existing bindings; an explicit list replaces them.

The store binds the current formal version/hash. Exact bindings may supply `version` and `text_sha256`. When prerequisites change, candidate reads expose old/new bindings and current wording; human confirmation binds the exact reviewed token. Existing formal versions never advance silently.

An unchanged current definition can receive `dependency_review` with `{bindings:{"F-000001":[2,"exact-text-sha256"]}, reason}`. It records compatibility with every active required binding. A changed definition uses a new complete candidate instead. Candidate and basis fields are in [review-packet.md](review-packet.md).

## Evidence for each option

In v5, each option may include `evidence_refs`, an ordered array of exact
`evidence/claims/E-NNNNNN/rNNNNNN.json` or
`evidence/sources/S-NNNNNN/rNNNNNN.json` paths. Bind only evidence actually cited
by that option. Reusing the same source across different options is allowed;
repeat paths within one array are not. The source and claim versions must exist.
An omitted or empty array shows no option evidence: the web page does not infer
an option's references from the group, other options, or member questions.

List references in first-use order. The page expands each claim's `sources`,
then `counter_sources`, and assigns display numbers by first occurrence of an
exact source-version path. Repeated citations reuse their number; each option
starts at 1. Keep original evidence IDs and versions unchanged. The helper
stores the bindings; the page computes display numbers, so do not maintain a
second numbered bibliography by hand.

The evidence rail is read-only and is separate from expressing a preference or
confirming a definition. Existing F-level review bases remain readable when a
member is opened individually. Changing an option's citations uses `update`
with its expected group revision and preserves the previous option in history.
