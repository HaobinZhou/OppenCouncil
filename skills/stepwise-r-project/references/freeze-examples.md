# Comparison syntax and content examples

Read the syntax when writing inline choices; use the examples only to calibrate a difficult case. Invented values are teaching fixtures, never defaults or claims about a real project's data.

## Inline choices

Place `{{choice:stable_id;label;value1;value2}}` in discussion or comparison fields, outside code formatting. Use 2–12 distinct nonempty values, explicit units where relevant, and a stable ASCII ID starting with a letter. No field may contain braces, a newline or a semicolon. IDs are unique within each question/group; reuse an ID only for the same parameter and identical label/values. Semicolons allow use inside Markdown tables.

```text
## 重试策略

### 等待时长
{{choice:retry_seconds;重试等待;5秒;10秒;30秒}}

### 次数上限
{{choice:retry_limit;最多重试;1次;2次;3次}}
```

Explain each value's meaningful effect beside it and recommend in prose; the first value is not an accepted default. The widget does not recompute text or enforce dependencies. Offer independently compatible choices; represent coupled settings as one explained choice/route. Selection is browser-local. “添加到讨论” prepares an editable message; the human explicitly saves it. On continuation, read saved preferences, check their combined effects and revise affected candidates with concrete values and complete dependent rules.

## Necessity and scope examples

- An already-verified field mapping with zero missing/invalid values does not justify a new hypothetical missing-data policy. Recheck if the snapshot or intended scope changes. An actual gap affecting inclusion/calculation can warrant a focused decision after investigation.
- If retention duration and access permissions can be approved independently, give each necessary choice its own F and use a shared topic when useful. Keep the inseparable conditions of each rule together; do not create a question for every clause.

## Scientific comparison dimensions

A still-open evaluation horizon within a fixed route can use `{{choice:horizon_months;评价时点;36个月;60个月}}`, with population, observation-window and precision consequences explained nearby. Preserve already-confirmed horizons and primary/secondary roles rather than reopening them. Probability difference and RMST difference are distinct quantities, not unit substitutions; use an explained effect-measure row when the choices are self-contained and compatible. Coupled death-handling/model changes may instead need whole-route comparison.

## Scientific example: direction versus an inclusion rule

“Target T2D + CKD; T2D follows RAMP; CKD will be verified separately” fixes a research direction but cannot determine patient eligibility. Test it with a synthetic person having Type_2 at month M−8 and Type_1 at M−1: an “ever Type_2” reader and a “most recent label” reader can disagree while both claiming to follow RAMP. Neither rule may be adopted from this illustration. Verify the actual field, source algorithm, temporal availability and conflict policy; compare any genuinely unbound choices for the researcher.

Likewise, one abnormal kidney measurement and repeated measurements may be treated differently by different CKD rules. The relevant threshold, units, persistence, source hierarchy and pre-entry availability must be obtained from the chosen authoritative definition or explicitly proposed and decided. Do not substitute an RCT's renal eligibility range for a general CKD definition without explaining and deciding that distinction. Bind time-zero and missing-eligibility dependencies to their real owners. If those are unresolved, report that cohort membership is not yet determined.

A **synthetic**, fully specified small rule can be brief: “At the first day of index month M, consider only the six complete calendar months M−6 through M−1. Valid `flag` values are exactly 0 or 1; ignore null/invalid flags. Inspect months from newest to oldest, skipping months with no valid flag. In the first remaining month, identical valid flags count once; if both 0 and 1 occur, return unknown without looking further back. Otherwise output true for 1 and false for 0. No valid month yields unknown. Never use month M or later.” For M = 2026-07, January flag 1 alone returns true; December flag 1 alone returns unknown; February 1 followed by June 0 returns false; June 0 and 1 returns unknown; July 1 alone returns unknown. These are teaching fixtures, not a clinical phenotype or an approved project rule.
