# Maintenance entry — load only for the requested operation

Daily project work does not require these procedures. Use the installed skill's absolute script path. Existing helper commands are retained as compatibility tooling; do not automatically migrate projects or register network access.

## Skill Updates

Read [skill-updates.md](skill-updates.md) only for checking or installing an upstream release. Local instruction edits use the current checkout and its verification. Use `scripts/update_skill.py --check` for explicit check-only requests; otherwise follow the update workflow there, preserving dirty work. This does not migrate project data.

## MCP connection and deployment

Read [mcp-publication.md](mcp-publication.md) only for initial connection, registration/configuration or connection repair. Publication requires existing user authorization. Ordinary connected projects just refresh and verify their existing MCP view. To verify an updated skill, compare `get_skill_guide` with the installed `SKILL.md`.

## Legacy maintenance

Run the normal helper's `validate TARGET` first. Compatible native v3 requires no migration. For an authorized marker-only change, use `upgrade-v4 TARGET --check`, then `--apply`.

For `LEGACY_STEWARD_LAYOUT`, run `upgrade-layout TARGET --check`, then `--apply` only when ownership is mechanically proven. Never infer ownership from root filenames alone. Existing-project adoption remains normal `adopt` work, not a layout migration.

## Managed-state recovery details

Read the following only for a detected recovery/continuity problem or when modifying the helper itself.

## Runtime State And Managed Writes

- Treat valid current Steward state as `MANAGED_READY`.
- Treat an ordinary existing project with no Steward state as `ADOPTION_REQUIRED`; use `ADOPTION_BLOCKED` only for a concrete adoption conflict.
- Treat deterministic operational blockers as `BLOCKED_RECOVERABLE`; report the blocker, affected paths, and recovery action. Recoverable residue is not governance damage.
- Reserve `DAMAGED` for authority or metadata that cannot be interpreted without semantic or manual repair.
- Use `audit recover` only for clearly failed or incomplete staging. Let the helper verify the external recovery copy and manifest before removing the source; never move `current/` or create an in-project archive.
- Let every mutation use its Managed Operation Write Set. Permit unrelated tracked or untracked Git work and leave it byte-for-byte untouched.
- Stage transaction content and rollback only for the declared Managed Operation Write Set. Never clone, recursively copy, hardlink, reflink, or otherwise materialize the full project. Read unchanged project content in place through a read-only candidate overlay when candidate validation needs it.
- Support cross-filesystem transactions without widening their scope. Treat `EXDEV` as permission to copy only an individual managed file, never the project tree.
- Stop with `MANAGED_WRITESET_CONFLICT` when dirty user-owned paths overlap operation-owned paths. Reconcile only those paths; never stash the whole repository automatically.

## Steward-Owned State

`.oppen-project-steward/**` is Steward-owned managed state except for MCP-owned `Discussion/**`. Steward continuity is determined by the helper-managed `.oppen-project-steward/.managed-state.json` baseline, not by comparison with Git HEAD.

- Continue normal Steward operations when managed files match the last successful baseline, whether Git sees them as committed, staged, modified, or untracked. A Git commit is never required merely to continue governance.
- Stop with `MANAGED_STATE_CONFLICT` when `registry.md`, `Memory/**`, `Attention/**`, or `Audit/Contracts/**` differs from the baseline. Inspect and reconcile only the reported paths; never reset them from Git or overwrite unexplained drift.
- Keep user-owned project paths under Managed Operation Write Set Git conflict protection. Referencing a dirty user-owned Canonical owner is allowed; writing a dirty user-owned path is not.
- Exclude `.managed-state.json`, `Audit/Runs/**`, `Discussion/**` (including its MCP-maintained index), and user project content from the baseline. Let Audit retain its own evidence-integrity checks.
- For an otherwise valid managed project missing only the baseline, run `managed-state TARGET --check`, then `managed-state TARGET --bootstrap`. Bootstrap creates generation 1 without re-adoption, Git mutation, or a required commit. Never bootstrap a damaged or otherwise blocked namespace.

