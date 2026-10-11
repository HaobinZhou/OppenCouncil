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

## Engineering example: a slogan versus a save contract

“Save reliably and retry errors” leaves implementations free to duplicate messages or lose edits. A complete **synthetic proposal** for a comment-save contract is:

“For each newly submitted comment, the client creates one request ID and retains it with the exact payload until an outcome is known. The server atomically stores the comment and a receipt under (project, actor, request ID), then acknowledges success. Repeating that key with the same payload returns the original receipt and creates no second comment; the same key with a different payload is rejected without mutation. A new intentional comment, even with identical text, receives a new ID. After a lost response, the client keeps the draft and retries the original key/payload only. It displays saved and clears that draft only after a matching receipt; if the user edited the draft meanwhile, the newer text remains unsaved. Receipt retention and the supported retry horizon are bound to the retention contract; until that dependency is confirmed, long-delayed retry behavior is unresolved.”

This identifies concrete behavior without pretending its final dependency is closed. Lost acknowledgement followed by a same-key retry must yield one comment; same key with changed text must reject; a new same-text comment with a new key must yield a second comment; an edit after submission must remain unsaved. A fully ready contract must also bind the actual retention owner/version and handle retries outside that horizon. In a synthetic project with no existing retention owner, one concrete proposal would replace that dependency with: “Retain comment receipts for the entire project lifetime, including after a comment is hidden. Project deletion removes comments and receipts together and closes the endpoint; requests to the deleted project are rejected and cannot recreate it.” This closes that specific uncertainty, with the cost of retained receipt storage; it is not a mandate to change any real project's retention policy. A receipt or a passing happy-path save test alone cannot establish content completeness.
