# Local conversation review

## Enter this step after preparation

Complete the investigation, source appraisal, full candidates, alternatives and dependency checks in [review-packet.md](review-packet.md) before offering review. Preserve the research handoff and its explicit continuation requirement. The choice of review channel changes neither preparation nor the meaning of confirmation. Report which groups and independent questions are ready, then follow the human's chosen channel. Do not require a webpage visit to complete a conversation decision.

## Pace the conversation

Present one complete group per exchange. When only independent F records remain, present up to three per exchange. Wait for the human's response and address that batch before presenting another. A group is a discussion unit, not a requirement to freeze every member together; members may be confirmed separately when their prerequisites permit it. Follow an explicit request to change the pace.

Make the dialogue easy to follow for a human with ADHD. Use short, clear, concrete sentences, with one point per sentence and short paragraphs. Use descriptive headings and separated numbered items. Name the rule or choice instead of relying on an F ID or an ambiguous pronoun. Explain unfamiliar terms when they first appear. Put the proposed wording and the exact decision first, then the key evidence and practical differences between options. Use bold sparingly for the decision and important differences. Keep evidence and complete wording available; do not replace substance with a terse handoff or make the human decode internal logs. Answer the human's immediate question before continuing the review.

## Follow the actual authorization

The local agent may carry out any existing human review operation from the webpage when explicitly authorized in the conversation: discussion, candidate edits and saves, option preference, confirmation, reconfirmation, opening revisions, withdrawal, and group actions. An instruction can authorize one action or a clearly identified batch; do not ask again for every mechanical step within that scope.

Interpret the actual context, not a required phrase. Agreement to the complete wording just presented can authorize confirmation. A preference, permission to continue research, or an unresolved question is not automatically approval. A precise edit plus explicit confirmation can authorize the edited wording without a second approval, provided no additional substantive choice is introduced and preparation checks still pass. If the target or intended change is ambiguous, clarify only that point. Do not expand the instruction to other items or authorize yourself.

Save relevant human feedback and decisions in the corresponding F, investigation or group through the interface below. Copy the actual instruction in its authorization; preserve the relevant human words in discussion, distinguish any agent explanation, and do not copy the entire chat. AI replies and assessment still use ordinary local work updates. Check both channels for newer changes before acting. Read back the result and report the affected IDs and versions briefly. Switching channels does not create another approval or another formal version.

## Local execution

Use `python -m oppencouncil human-action TARGET --input FILE.json`, or `python ABSOLUTE_SKILL/scripts/oppencouncil.py human-action TARGET --input FILE.json`.

Example after the human has reviewed and approved this exact candidate:

```json
{
  "request_id": "unique-conversation-action",
  "id": "F-000001",
  "operation": "definition_approve",
  "value": "EXACT_APPROVAL_TOKEN_FROM_THE_REVIEWED_CANDIDATE",
  "expected_revision": 12,
  "authorization": {
    "source": "conversation",
    "instruction": "<actual human instruction>",
    "thread_id": "<actual thread ID, if available>",
    "message_id": "<actual message ID, if available>"
  }
}
```

Omit unavailable thread/message identifiers; never invent them. Save one existing item action per request. Use separate stable request IDs for separate actions within an authorized batch. Group `approve` retains atomic confirmation of its members. A failed independent action does not undo earlier successful actions; report the actual results and resolve the conflict before continuing affected work.

| Target | Operations and values |
| --- | --- |
| F | `comment`: relevant human text; `definition_draft`: complete text or `{text, dependencies}`; `definition_approve`: reviewed candidate approval token; `definition_reconfirm`: reviewed reconfirmation token; `definition_begin`: null; `definition_discard`: null or the existing unsaved-edit payload |
| B | `comment`: text or `{text, question_id}`; `select_option`: existing option index; `approve`: reviewed group approval token; `begin`: null; `discard`: `{token: reviewed group approval token, edits?: {F_ID: {text, request_id}}}` |
| I | `comment`: relevant human text |
| Legacy F | Existing `answer`, `discuss` and `resolve` operations remain available, alongside that generation's definition operations; no project migration occurs |

Read the current item first. `work-read` supplies v5 F candidate/reconfirmation tokens and revisions; `snapshot` supplies group approval tokens, option indices and legacy records. A candidate, basis or dependency change can invalidate a previously reviewed token. Do not silently substitute a new token to confirm materially different content under an old instruction. Unchanged wording with a reassessed basis uses reconfirmation on the existing version.

The helper saves the authorization, executor, action and result in the same transaction as the mutation. The webpage shows these under “对话操作记录”; conversation messages retain their human authorship and channel. This is a record of the local agent acting on the human's instruction, not independent authentication of the conversation. Do not use it for external AI contributions or inferred approval. External MCP permissions remain unchanged.
