# Explicit project migration

Use only for an authorized project upgrade. Updating product software or inspecting a project does not migrate it. The helper accepts native v3/v4 projects in either layout and retains their registry location, formal versions, discussion, Memory and output registrations.

```text
upgrade-v5 TARGET --check --plan OUTSIDE_PROJECT.json
upgrade-v5 TARGET --apply --plan OUTSIDE_PROJECT.json
```

Use an absolute target and a fresh plan filename outside the target. The check reports actual capabilities, project type, input hashes, exact writes and legacy items requiring later work. Apply compares the exact plan with current state; changed inputs or capabilities require a new check. Successful replay makes no further writes.

Keep `--council-directory`, `--mcp-root` and `--mcp-config` identical between check and apply. Select an optional `--project-type` during check only; apply reads it from the saved plan and rejects that flag. Connected HTTP services are probed; an old or unavailable registered service blocks application. A stdio capability probe uses a fresh process and does not establish that an existing client session has reloaded code. An unconnected project does not require optional MCP installation.

Migration translates active Attention into investigations and initializes feedback progress mechanically. Items with candidates or old open discussion need their one-time discussion reconciliation on first resumption; formal-only items do not. The resulting `processing.bootstrap` and unread inputs are exposed by `work-read`, with completion recorded through [local-council.md](local-council.md).

The plan reports unnumbered scripts, unknown data origins, old outputs lacking specifications, experimental artifacts and unassigned files. It does not decide their scientific meaning or silently reorganize them. Follow-up adoption of old scientific wording uses its existing authority and confirmation history.

The same-filesystem `.oppencouncil-migration/` journal holds durable preimages. Ordinary helper startup recovers interrupted work before reading the project generation; `--check` instead reports recovery required without writing. A conflicting later edit or corrupt preimage is reported and preserved for reconciliation. Migration does not restart services or change permissions, OAuth grants, site registration or MCP allowlists.
