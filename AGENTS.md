# Working in OppenCouncil

Use `skills/oppen-project-steward/SKILL.md` to govern this product repository. Keep existing research projects under their original governor. Load only task-relevant references.

- `skills/` owns governance instructions and helpers; `council/` owns the workbench and shared storage; `mcp/` is an optional client of that storage.
- Maintain one implementation of formal definition storage. Project `Freeze/` records, Memory, credentials and runtime registration are not product source and must not be copied into commits.
- Preserve the existing Decision Memory semantics and records. Do not migrate research projects as part of installing or updating product software.
- Use `scripts/install.py --with-mcp --no-skills --dev` and `scripts/verify.py` for product acceptance. Component tests can be selected for bounded changes.
- Installation, software verification, GitHub publication and live service deployment are separate observable states. Update the relevant contract and verification when changing a cross-component boundary.
- Keep component and skill versions unchanged during local implementation and testing. Bump each affected version once per authorized GitHub submission batch; fixes and retries within that batch do not trigger another bump. This rule governs software release versions, not project definition revisions.
