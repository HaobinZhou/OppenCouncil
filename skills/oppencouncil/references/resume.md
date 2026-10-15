# Continue feedback and pending work

For research review, read [research-handoff.md](research-handoff.md) and inspect saved `human_continue` waits first. An actionable input is work to inspect, not permission to close a handoff or prepare the final recommendation.

Use `work-index TARGET --actionable` to list items with unread inputs, ready pending work or migration reconciliation. `work-read TARGET --id ID` returns the current read set, relevant messages and unfinished items. Local updates use the atomic [work-commit interface](local-council.md).

`comments` append local replies. For a group, a comment may be `{text, question_id}` to identify an affected member. A saved reply ID is `REQUEST_ID:ITEM_ID:ZERO_BASED_COMMENT_INDEX`.

`pending` contains objects with a stable local `id`, `question`, `reason`, optional `input_refs` and `resolved`, and `continue_when`:

- `{kind:"definition_confirmed", question_id:"F-000001"}`
- `{kind:"new_material", after_sequence:N}`
- `{kind:"local_assessment", satisfied:false}`; a true assessment also includes `assessment` text.
- `{kind:"human_continue", satisfied:false}`; after an explicit human instruction, update the same saved item with `satisfied:true`, the actual `instruction` text, `source:"conversation"|"council"`, and `resolved:true` on the pending item. External contributions never satisfy this condition automatically. A handoff must be saved before its continuation; its condition cannot be replaced with an automatic one.

`definition_confirmed` accepts an optional positive `min_version`. When omitted, the helper saves the next version if the referenced F has a candidate, otherwise its current version (or 1 before its first confirmation). This saved threshold does not move when the candidate is edited or withdrawn. Use an explicit version when referring to an already confirmed rule, and a local assessment for conditions beyond a formal version, including evidence-only reconfirmation.

The same change can save `progress: {human_cursor: EVENT_ID, dispositions: [{event_id, reply_id}]}`; a disposition may name a `pending_id` instead. Every crossed human input needs a reply or pending item in this transaction. `handled_external` and `handled_changes` name external/system input event IDs assessed by those dispositions. `bootstrap_complete:true` also requires `bootstrap_reason` after legacy discussion reconciliation. Read back the saved item for its remaining inputs and pending work.
