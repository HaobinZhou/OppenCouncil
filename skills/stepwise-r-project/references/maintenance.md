# Maintenance entry — load only for the requested operation

Daily project work does not require these procedures. Use the installed skill's absolute script path. Existing helper commands are retained as compatibility tooling; do not automatically migrate projects or register network access.

## Skill Updates

Read [skill-updates.md](skill-updates.md) only for checking or installing an upstream release. Local instruction edits use the current checkout and its verification. Use `scripts/update_skill.py --check` for explicit check-only requests; otherwise follow the update workflow there, preserving dirty work. This does not migrate project data.

## MCP connection and deployment

Read [mcp-publication.md](mcp-publication.md) only for initial connection, registration/configuration or connection repair. Publication requires existing user authorization. Ordinary connected projects just refresh and verify their existing MCP view. To verify an updated skill, compare `get_skill_guide` with the installed `SKILL.md`.

## Legacy maintenance

Run the normal helper's `validate TARGET` first. Compatible native v3 requires no migration. For an authorized marker-only change, use `upgrade-v4 TARGET --check`, then `--apply`.

For a detected v2 project, read only **Existing v2 Migration** in [managed-systems.md](managed-systems.md) and use `migrate TARGET --check`; apply only its unblocked reviewed payload. That reference and the legacy converter are retained unchanged because they define existing Memory migration behavior. No routine task loads this appendix.
