# Historical recovery and reconciliation

Read only to recover missing existing decisions/discussion or repair a prior recovery import. Use `project.md` for current Canonical registrations. Do not reread this for ordinary rounds whose history is already present.

## Historical recovery for existing projects

Opening discussion on an old project includes recovery by default:

Check the selected installation with `oppencouncil --version` and its `recover` / `reconcile` commands. An installation lacking these operations needs a software update; do not emulate recovery by editing project records. The project must have its supported native Stepwise or Steward v3/v4 marker. Use its existing governing skill for any authorized layout migration, preserving definitions and evidence.

1. Read existing `Freeze/` when present. An absent or empty directory means first use, not failed migration or missing scientific decisions. Reuse existing IDs, answers, messages and examples directly; its format remains compatible. Match source topics to existing questions before creating new IDs.
2. Read all relevant current registered Canonical owners, active Decision Memory, saved Discussion and accessible authorized conversations. Consult Git where needed to understand a changed decision. Separate current frozen authority, recoverable discussion and unresolved reconstruction. A superseded agreement is history, not a current frozen definition.
3. Apply the preflight below, then build a UTF-8 recovery batch and run `recover PROJECT --input history.json` for records the installed application can represent faithfully. Include exact quotes, project-relative source paths, full-file SHA-256 and known original authors/timestamps. Default owner recovery requires an exact registered topic/path/section with an unambiguous frozen status and a verbatim definition. Explicit item recovery can mirror a frozen definition inside a partially-frozen owner; see the preflight below. This API requirement is separate from the scientific classification of an individual item. Discussion summaries may be reconstructed, but historical messages are exact quotations. Use `unknown` for uncertain authors, omit missing dates, and use `unconfirmed` only when the scientific evidence or reconstruction is genuinely incomplete or contradictory.
4. For authorized conversation or historical Git evidence outside project files, retain a bounded faithful transcript/receipt through the project's normal Audit staging and promotion flow, including original thread/ref/path provenance. Quote that project-owned evidence file. Do not invent inaccessible conversations or edit the original Discussion documents.
5. Attach to an existing question using `question_id` and its latest `expected_revision`. Preserve human answers and active disputes. A verified frozen definition may classify an unanswered open question as already frozen. Use `reconcile` for an earlier incorrect recovery classification; do not overwrite its receipt. Use the same stable topic/source key and identical evidence on retries; report created, attached and replayed counts, plus items that remain unrecoverable.
6. Read back the snapshot and reconcile it with the scientific classification, then add all genuinely new questions. Existing frozen definitions need no repeated questionnaire unless current evidence warrants reopening. Report imported, pending and technically unmapped items separately; validation success alone does not prove faithful recovery.

Use the installed `oppencouncil recover` and `reconcile` CLI commands with the target root and `--input` JSON; preview with `--check`.

Local recovery records Codex as the restorer. Historical user messages are quotations, not new browser answers. `frozen` mirrors Canonical at recovery time; it does not freeze a new decision. A new answer starts discussion. Generic AI/MCP changes still cannot answer, resolve or declare a freeze. Before later rounds, compare current authority with recovered source hashes and reopen or supplement when needed.

## Partial protocols and recovery preflight

Use this check before writing recovery records, especially when one registered protocol contains both settled and unresolved definitions:

1. Classify each item from its current definition, exact confirmation/freeze evidence and subsequent changes. Distinguish **current frozen definitions**, **historical discussion already settled or superseded**, and **questions genuinely needing confirmation**. Read the item's nearby qualifications and relevant current Decision Memory; a historical “已冻结” quote cannot override a later reopening. Whole-document `partially-frozen` describes the aggregate scope and does not revoke already frozen items.
2. Check the installed recovery capability separately. The default mode requires an exactly matching registered frozen owner/section. For an individually frozen definition in a partially-frozen owner, use `canonical_scope: "item"`, the registered `canonical_topic`, its `canonical_source`, a bounded live excerpt explicitly stating the item is frozen, and a verbatim `summary` within that excerpt. The source path/section still matches the registered owner. Supply `reason` explaining the evidence association and later-decision check. Source/hash/quote checks do not replace your semantic review of qualifications and subsequent reopening. Do not alter the protocol status or fabricate confirmations to meet the API.
3. Preview the entire batch with `recover --check` or `reconcile --check` before applying. If the installed version or evidence cannot represent an item faithfully, retain its definition and confirmation in normal recovery Audit and report the specific gap, topics/IDs and count. Do not submit an evidenced frozen item as `unconfirmed`, label it “待核”, or create another questionnaire.
4. Recover settled historical exchanges as provenance on the corresponding settled question when possible. If an existing standalone historical question was wrongly marked as ongoing, reconcile it to `kind: "historical"`, with the matching current Canonical topic/source, a verbatim `resolution` and `reason` showing why it is settled or superseded. This classification means historical record, not a scientific freeze. Preserve its original messages and authors. Genuinely ongoing discussions remain active.
5. Deduplicate unresolved topics across new batches and ongoing discussions. Compare the snapshot's current review states, recovery classification, and page counts. Do not call an erroneous `open` label harmless or call recovery complete while known definitions remain incorrectly pending.

### Correct an earlier import in place

When the project task authorizes repairing its recovery, read the existing IDs, sources, answers and later messages. Use `reconcile PROJECT --input corrections.json --check`, inspect the preview, then apply the same batch without `--check`. Each record uses a **new stable key**, the existing `question_id`, latest `expected_revision`, `supersedes` naming the prior recovery record key on that same question, the corrected kind/evidence and a specific `reason`. The old key/evidence remain immutable; retries use the same new key. To revise a subsequent correction, supersede the latest recovery classification receipt rather than branching from an already superseded one.

Reconciliation appends its evidence, before/after states and rationale, preserves the question ID/round, answers, authors, messages, examples and original receipts, and may correct the title/group (with their originals retained). It does not create another question or advance the round. If any saved human answer or review operation exists, the application conservatively preserves the current review state and stores the evidenced scientific classification separately in `recovery_classification`; the page displays both. Inspect these preserved cases individually. Never clear a real dispute to make counts look settled. `frozen` is an existing Canonical mirror; `historical` is settled/superseded provenance. Neither operation grants AI permission to answer or resolve for the researcher.

Report corrected, replayed, and review-preserved cases separately, then read back and confirm the IDs, original answers/messages, classifications and actual unresolved count. Do not delete/rebuild or hand-edit Freeze JSON. Updating the skill/application does not itself authorize repairing a particular scientific project's records.

Example payload:

```json
{
  "records": [
    {
      "key": "canonical-time-zero",
      "kind": "frozen",
      "group": "时间与策略",
      "title": "时间零点",
      "summary": "首次处方日作为时间零点。",
      "canonical_topic": "time-zero",
      "canonical_source": 0,
      "sources": [
        {
          "path": "Protocol/design.md",
          "section": "时间零点",
          "sha256": "REPLACE_WITH_THE_ACTUAL_FULL_FILE_SHA256",
          "excerpt": "首次处方日作为时间零点。"
        }
      ],
      "messages": []
    }
  ]
}
```

For `discussion` or `unconfirmed`, omit canonical fields. For `historical`, supply the registered canonical topic/source, a verbatim `resolution` and `reason`; an owner may remain partially frozen. A message has `actor`, exact `text`, a zero-based `source` index and optional original `at` present in the source. Preserve alternatives, rationale, human objections and decision order where evidence permits. Keys remain stable per recovered topic; changed evidence requires reconciliation and a distinct key, normally attached to the same question.
