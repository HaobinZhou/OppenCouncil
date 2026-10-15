# Output specification interface

A research output F has `problem_type: output_specification`; candidate and evidence fields use [review-packet.md](review-packet.md). Registered Results bind its exact confirmed version and text hash through [project-operations.md](project-operations.md). Unchanged regeneration uses that existing specification. These bindings check identity, not visual or scientific agreement between the artifact and specification.

## Structured tables

A fenced Markdown block with language `table` stores JSON, rendered and edited by the existing review page:

```table
{
  "schema_version":1,
  "id":"example-table",
  "title":"Example table",
  "simulated":true,
  "columns":[{"id":"a","label":"Group A"}],
  "headers":[{"id":"ha","label":"Group A","column_id":"a"}],
  "rows":[{"id":"n","label":"Participants","cells":{"a":"100"}}],
  "footnotes":[]
}
```

Headers may have `children` for grouped columns; leaf `column_id` order matches `columns`. Rows may have `parent_id` referring to an earlier row. Cells are strings indexed by column ID. Footnotes have `id`, `text` and optional `refs`, an array of objects: `{"row_id":"n"}` marks a row label, `{"column_id":"a"}` a column heading, and `{"row_id":"n","column_id":"a"}` a cell. Omitting `refs` leaves an unlinked table-wide note. The page edits the same candidate text; saving preserves the current formal version and creates human feedback for local continuation.

Columns can include text `unit` and `format`, and `align: left|center|right`. Units and format descriptions appear below the column heading; format text is descriptive and does not execute formatting code or transform cell strings. Row moves carry their child rows. Column/header moves reorder siblings within the current header group; split a group before moving its columns elsewhere. Footnote text can be added, edited or removed in the table editor; reference IDs remain editable in the source text.

## Images

Markdown image references from Explore are copied by the local writer to immutable content-addressed files in `Freeze/assets/`. Candidate and formal text refer to that saved copy. The review server serves only these validated assets, so subsequent regeneration or archiving of the experimental source cannot change the saved example. The current implementation accepts PNG and static SVG. Mark simulated examples in their visible caption or table metadata.

Formal output registration and Explore lifecycle operations are in [project-operations.md](project-operations.md). Local snapshots are a separate operation in [releases.md](releases.md).
