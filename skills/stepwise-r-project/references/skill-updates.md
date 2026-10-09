# Skill update procedure

Read only when checking or installing a published update to this skill. A request to revise, audit or fix the skill instructions in the current checkout is local authoring: edit and validate those files, without running the upstream updater unless the user also requests installation from GitHub.

When the user invokes this skill and says “check the update”, “check for updates”, “检查更新”, or “更新技能”, check its GitHub source and install an available update in the same task. This request authorizes the available skill update; do not ask again merely because a newer commit exists. If the user explicitly says “check only”, “只检查，不更新”, or equivalent, only report availability.

Run the bundled updater with the active Python 3 interpreter and the **absolute path of this installed skill**:

```text
python ABSOLUTE_SKILL_PATH/scripts/update_skill.py --apply
python ABSOLUTE_SKILL_PATH/scripts/update_skill.py --check
```

- Use `--apply` for the default check-and-update request and `--check` for an explicit read-only check. On Windows, `py -3` is also suitable. Python and Git must be available.
- The source is [HaobinZhou/OppenCouncil](https://github.com/HaobinZhou/OppenCouncil), directory `skills/stepwise-r-project`. The updater resolves GitHub's current default branch and pins its commit; it never guesses a version from governance markers such as v3/v4.
- This supports the repository's documented Git clone installation, including symlinked skills. It resolves this skill's location independently of the working project. A shared checkout updates **all upstream changed paths in OppenCouncil**, including both skills, Council and the optional MCP source; report that scope. If the user restricts changes to only one skill, do not use the shared-checkout updater.
- Checks may fetch Git objects and metadata but do not change installed files or the local branch. Apply uses only a fast-forward, preserves unrelated dirty work, and blocks overlapping tracked, staged, untracked, or ignored files. Never reset, force, stash, rebase, or discard local changes to obtain an update. For a copied installation, source mismatch, divergence, detached HEAD, network failure, or conflict, report the concrete blocker and preserve the installation; do not claim it is current.
- Report `UP_TO_DATE`, `UPDATE_AVAILABLE`, `UPDATED`, `LOCAL_AHEAD`, or `UPDATE_BLOCKED`, the before/upstream/after commits when available, and changed paths or conflicts. `LOCAL_AHEAD` means local commits are ahead of upstream and no downgrade was performed. After `UPDATED`, reread the installed `SKILL.md` before using its new instructions.
- Skill maintenance uses this workflow directly. It does not require initializing, indexing, or migrating the working R project, and does not rerun analyses. Scientific definitions and project migrations use the authorized workflow in [SKILL.md](../SKILL.md).
- After `UPDATED`, if OppenSteward-MCP is available, follow the skill-guide refresh check in [MCP publication and refresh](mcp-publication.md).

After `UPDATED`, run the product `scripts/install.py` using the installation’s previous components (add `--with-mcp` only if MCP is already installed). This refreshes locked runtime dependencies; it does not restart services or change project permissions. A requested skill update does not authorize project data migration. Old academic-skills installations follow the product `docs/migration.md`; do not reset local commits or replace copied skills.
