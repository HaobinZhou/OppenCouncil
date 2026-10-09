# MCP Publication And Refresh

Use this procedure for requested first-time publication or connection maintenance, or to verify an already-published project/updated skill. The agent handles tool discovery and human consent; the Python project `init` helper remains local, deterministic, and noninteractive.

## Availability And Existing Publication

1. Discover the connected **OppenSteward-MCP** tools. They may appear as `project_list_projects`, `project_refresh_projects`, `project_project_overview`, and `project_get_skill_guide` with provider prefixes; use their actual callable schemas. The Codex app's sidebar project list is a different service.
2. Call `list_projects` with the target's exact root as the query, follow pagination, and compare returned normalized absolute roots. A matching name alone is insufficient. A successful, complete response with a healthy catalog and no matching root means unpublished; tool absence, authentication failure, an incomplete/error catalog, or a timeout means unavailable or unverified.
3. If a matching root exists, retain its stable project ID and confirm `project_overview` can read the expected registry. Do not ask to republish it or add a duplicate registration.

When MCP is unavailable, complete local initialization and report publication as unavailable/unverified. Do not install a server, edit credentials, or create Attention merely for this optional integration.

## Requested First-Time Publication

When the user requests connection and local validation succeeds, if MCP is available and this exact project is unpublished, ask only if publication authorization is still missing:

> 本项目已在本地初始化，尚未发布到 OppenSteward-MCP。是否现在发布，让已授权的 MCP 客户端读取项目治理文档？

Explain that first-time publication requests the choice because publication changes project visibility. Default publication exposes the governance registry and indexed Memory/Attention; existing Discussion permissions also apply. It does not grant generic access to source, Data, Results/Deliverables, or Audit bodies. It is access through the configured MCP service, not a public website.

- A prior explicit request to publish this project is sufficient; do not ask again.
- If the user declines, leave MCP registration unchanged. Do not repeat the offer in the same task.
- If no answer has arrived, keep publication pending. Continue independent local work; silence is not consent.
- Existing-project adoption or migration does not itself grant publication permission. Refresh an existing registration; offer first-time publication when the user asks to connect that project.

## Register Only After Consent

Current OppenSteward-MCP uses an explicit project list. **`refresh_projects` reloads registered paths; it does not register projects or recursively scan parent directories.** Read the installed server's current configuration contract if its live behavior differs. Do not invent a publish MCP tool or assume an older scan-based server supports this configuration.

1. Identify the configuration used by the running MCP instance, on its actual host. Resolve `OPPEN_PROJECTS_FILE` / `projects_file` using that instance's configuration; the default is `projects.local.json` beside its configuration. Relative paths are relative to that configuration directory. Do not guess a second server checkout or print credentials while locating the non-secret path setting.
2. Inspect the current JSON and prepare the exact addition of the validated project root. The current schema is `{"projects": ["/absolute/project/root"]}`. Preserve every existing entry and its order, normalize paths for duplicate detection, and add only this root. A parent directory does not register its children. Do not broaden `exclude_roots`, Discussion permissions, or other server settings.
3. With the user's publication consent, update that one configuration file atomically, after checking it has not changed since inspection. Validate JSON/schema before replacement and preserve file permissions. Do not replace malformed configuration with an empty list, follow a configuration symlink, or overwrite concurrent edits. If the active server's configuration is inaccessible, report the exact registration needed and leave publication pending; do not silently write a local substitute.
4. Call `refresh_projects`, then `list_projects` for the exact root and `project_overview` for its returned stable ID. Require a healthy response, matching root and skill, and a readable expected registry before reporting **published**. For Steward the current registry is `.oppen-project-steward/registry.md`; for Stepwise it is `project.md`.

The server hot-reloads a valid project-list change. A registration change alone requires no service restart or OAuth reauthorization. If registration is saved but verification fails, distinguish **registered, visibility unverified** from **published** and report the failing step; do not keep retrying unchanged failures or silently undo granted access.

## Refresh Existing Projects And Updated Skills

- After authorized governance changes or migration to an already-published project, finish local `index`/`validate`, then `refresh_projects` → `list_projects` → `project_overview`. Confirm the exact root, current skill/layout, registry, and index references. Reuse its registration and stable ID.
- After a skill update, call `get_skill_guide` for the updated skill(s) and compare the returned guide with the installed `SKILL.md`; for a Council task, also check `get_skill_guide(skill, resource="references/freeze-workbench.md")`. Only the named guide is loaded, not all references. The server reads guides from `OPPEN_SKILL_ROOT` / `skill_root`, or its documented installed-skill locations. A Git update in one checkout does not prove the server uses that checkout. If the guide is stale or missing, locate the actual configured skill root and report the mismatch; change server configuration or another installation only within the user's authorization.
- Keep **local skill updated**, **local project validated**, and **MCP publication/refresh verified** separate in the final report. An MCP failure does not undo successful local work. Do not claim a skill update upgrades the MCP server software, changes its tool inventory, or migrates projects.
