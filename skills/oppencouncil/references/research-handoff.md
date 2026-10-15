# Research review handoff

The default research review round has a real handoff before literature appraisal and synthesis. A request to update the project, follow the latest skill, or prepare Council does not authorize completing every stage in one turn. An explicit request to research literature and complete the round locally overrides the default for that stated scope.

For an existing v3/v4 project, follow the same handoff timing through its [legacy interface](legacy-projects.md): save the facts, research questions and instruction to await human continuation in the existing Council discussion, then return control. The structured wait and programmatic gates below require v5; do not migrate a project to obtain them.

## Check facts and hand off

Read the affected items and existing pending work. Check data, code, existing definitions and implementation facts. Exclude questions those facts settle and retain the reasons. For decisions still needing research, prepare the question, verified project facts, unresolved points, applicable constraints and literature-search questions. Existing literature may be identified as leads; leave new literature searches and source appraisal to the web AI at this stage.

Save an `external_brief` with `disclosure: "shared"` on each affected F, and shared source/claim versions for the facts the web AI needs. Group related questions when useful. Keep existing candidates and formal definitions as context; do not finish the new recommendation or review packet. Save phase `evidence`, conclusion `needs_check`, and this pending condition on every affected F (including group members), using one stable ID per item's round:

```json
{
  "id": "research-handoff-round-1",
  "question": "Await web literature contributions and the human's instruction to continue",
  "reason": "Local facts and the shared research brief are ready; the human will arrange web AI research.",
  "continue_when": {"kind": "human_continue", "satisfied": false}
}
```

Use [local-council.md](local-council.md) to save and read back the handoff. Return the existing Council link, affected item IDs and a short pasteable request for the web AI: read the shared briefs, find relevant original sources, explain applicability and counterevidence, and append contributions through MCP. Verify the existing MCP connection can expose the intended items; report a connection gap if present. Finish this turn here. A progress message followed by more local work is not a handoff, and waiting a fixed number of seconds is not human authorization.

## Resume when the human asks

On subsequent entry, read the saved wait before acting on an actionable index. Incoming literature, comments or a web AI saying it has finished do not authorize synthesis or sending the item for human review. Other independent work can continue within its own scope.

Once the human explicitly asks to continue this review round, update the same pending item with `resolved: true` and `continue_when: {kind: "human_continue", satisfied: true, instruction: "<actual human words>", source: "conversation"}`. Use source `council` for an actual human instruction saved there. Record the instruction, not a paraphrase of an external AI's message or an inferred permission. This acknowledges permission to resume, not that the literature is sufficient or any definition is confirmed.

Then read the contributed sources, check their original text and project applicability, address disagreements, and prepare the review packet through [evidence.md](evidence.md) and [review-packet.md](review-packet.md). Missing or contradictory evidence stays pending. Formal definition confirmation remains the separate human review action. A later research round needs a new handoff unless the human explicitly assigns it to local completion.
