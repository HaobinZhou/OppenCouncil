# OppenCouncil setup and payload details

Read for first-time website registration, service discovery/configuration, forwarding, MCP access troubleshooting or a full import example. The ordinary round workflow is [freeze-workbench.md](freeze-workbench.md).

## First-time website registration

Creating Council records for web review includes registering the project in the intended site. Resolve that site's directory from the existing deployment configuration, service arguments or `OPPEN_COUNCIL_DIRECTORY`; verify it with `oppencouncil --directory SITE status`. Use this same `SITE` for import, registration and opening. The package's default directory may differ from a running deployment; do not silently create a second site or use a default port as proof of the intended one. If the destination is ambiguous, resolve it before registering. When no site exists, select its directory as part of the requested workbench setup and follow the startup instructions below.

- For a new batch, use `oppencouncil --directory SITE import TARGET --input batch.json`; it creates records and registers the project in that site.
- For existing records, including records created through MCP or the storage API, use `oppencouncil --directory SITE register TARGET`. This registers the project without importing duplicate questions or moving its files.
- Use `oppencouncil --directory SITE open TARGET` to register and start/reuse the selected site, then `oppencouncil --directory SITE status TARGET` to check the enabled entry and obtain its URLs. Preserve the running site's address and login mode; use the configured public URL when applicable.
- Verify that the site's project directory includes the project and that its questions and prepared candidates are readable there before handing over the link. A login page alone does not verify the project content. Follow the content and web-handoff checks in [freeze-workbench.md](freeze-workbench.md).

An MCP-only client cannot perform site registration with Freeze tools. If the project is not yet registered and local site commands are unavailable, report the remaining site-registration step; do not claim web delivery is complete. Website registration does not grant MCP access or authorize changing its project allowlist or OAuth scopes.

## Application discovery and commands

OppenCouncil owns the page, listener and storage. Use an installed `oppencouncil` executable, or the Python environment containing the package with `python -m oppencouncil`. The product checkout provides `council/.venv/bin/oppencouncil` on macOS/Linux or `council/.venv/Scripts/oppencouncil.exe` on Windows. From its root, `uv run --project council oppencouncil` uses the same component. Discover the actual installation and keep the selected environment consistent across commands. If missing, report the required OppenCouncil installation instead of recreating its server inside this skill.

```text
oppencouncil --version
oppencouncil --directory SITE import TARGET --input batch.json
oppencouncil --directory SITE open TARGET
oppencouncil --directory SITE open TARGET --port 5322 --public-origin https://council.example.com
oppencouncil --directory SITE status TARGET
oppencouncil snapshot TARGET
oppencouncil ai-change TARGET --input update.json
oppencouncil group-change TARGET --input group.json
oppencouncil definition TARGET --question F-000001
oppencouncil --directory SITE recover TARGET --input history.json --check
oppencouncil --directory SITE recover TARGET --input history.json
oppencouncil --directory SITE reconcile TARGET --input corrections.json --check
oppencouncil --directory SITE reconcile TARGET --input corrections.json
oppencouncil --directory SITE disable TARGET
oppencouncil --directory SITE stop
```

`import` automatically registers the target in the selected site directory. `register` registers existing records without starting a listener; `open` registers the target and starts or reuses that site's shared listener; `disable TARGET` disables only that project's site entry, while `stop` stops the entire site. For an explicit site directory, place the global option before the command: `oppencouncil --directory SITE open TARGET`. `OPPEN_COUNCIL_DIRECTORY` also selects the site registry. Neither setting moves project records.

The default loopback port is 5322. A reachable forwarding proxy supplies remote access; `--public-origin` alone does not create a tunnel. Default access uses one site password without usernames: the user sets it on first visit, then enters it on later visits. Return the ordinary URL; do not invent a password or append a login key. Passwords persist in the site directory across restarts; browser sessions expire after 12 hours or restart. Use `--no-auth` only for explicitly requested open access on a site without a configured password; a configured site rejects it. Anyone reaching an open site can view enabled projects, discuss, edit candidates and confirm definitions. Reuse the running site's address and login mode. Changing those settings requires a site restart affecting all registered projects. The listener continues after the Codex turn ends, but depends on the host and forwarding connection remaining available.

An import batch uses a stable request ID for retries:

```json
{
  "request_id": "round-1-research-design",
  "questions": [
    {
      "group": "数据与复现",
      "title": "本轮采用已审阅的 9 月快照，还是更新至 10 月后固定新快照？",
      "why": "本轮需要确定输入数据；版本不同会改变需要重新核对的记录和结果。",
      "source_summary": "合成示例：假设 9 月快照有 100 条记录，10 月仅新增 2 条；不是实际项目统计。",
      "ai_position": "A：使用已审阅的 9 月快照及其校验值，本轮固定这 100 条记录，新增 2 条留待后续研究更新；便于复现已审阅结果，但本轮不覆盖新增记录。\nB：重新提取并固定 10 月快照，记录提取规则和校验值，对 102 条记录重新执行质量检查和分析；覆盖新增记录，但既有结果需重新核对，不能预先断言结论会如何变化。\n同一示例对比：A 的输入为原 100 条，B 为原 100 条加新增 2 条；两者在本轮分析时都使用固定文件。若目标是复现已审阅结果，建议 A；若目标是纳入最新记录并接受重新审阅，建议 B。请选择本轮目标对应的方案。",
      "suggestions": ["A：固定已审阅的 9 月快照", "B：更新并固定 10 月快照，重新核对结果"]
    }
  ]
}
```

`ai-change` takes `question_id`, `operation`, `value`, latest `expected_revision` and a stable `request_id`. Use the question operations described in [freeze-workbench.md](freeze-workbench.md); current operations include `comment`, `presentation`, `review_note`, `definition_draft`, `dependency_review` and `reopen`. Legacy `ai_position` does not update suggestion buttons. Group operations have their own payload and command in [freeze-groups.md](freeze-groups.md). Reopening discussion preserves earlier replies and does not open a formal revision.


## Saved records, drafts and MCP

The native project root contains:

```text
Freeze/manifest.json
Freeze/questions/F-000001.json
Freeze/decision-groups.json  # present when joint groups are used
```

UTF-8 JSON is the source for AI/MCP reading. The manifest identifies current rounds and stable question IDs. Question files separate the current formal version, candidate document, append-only discussion, author provenance, review status and revisions. Legacy human-answer fields are historical discussion, not current authority. Shared storage locks writes, checks revisions and makes retries idempotent. It leaves the governance registry unchanged; the confirmed definition in the question JSON is itself the v4 Canonical owner.

OppenSteward-MCP uses the same OppenCouncil package. A native Steward v3/v4 or Stepwise R v3/v4 project must be explicitly registered in MCP and separately included in `OPPEN_FREEZE_PROJECTS`. `OPPEN_FREEZE_MODE=read` provides `freeze_snapshot` and `freeze_read_question`; `write` also provides `freeze_add_questions`, `freeze_change_question` and `freeze_change_group`, subject to existing OAuth scopes. Website registration grants no MCP access. Keep the current project's authorization; do not change a global allowlist merely to open a webpage.

Local CLI writes record Codex. MCP writers declare `actor: "codex"` for Codex or `"chatgpt"` for ChatGPT. AI may add questions, update discussion/options, manage groups/dependencies and edit candidate wording or reopen discussion. It cannot confirm a candidate, open or withdraw its next revision, publish formal versions, write human answers, resolve disagreements, recover/reconcile history or overwrite effective definition versions. Reading an existing discussion does not authorize an AI reply; use the user's current request to determine whether to contribute. Free-form MCP Discussion and structured Freeze remain distinct. MCP can access project records independently of the web listener.


## Legacy Stepwise wrapper

Existing callers may still use `python ABSOLUTE_SKILL/scripts/freeze_workbench.py`. Its `start TARGET` delegates to `open TARGET`, and `stop TARGET` disables only that project; `oppencouncil stop` stops the shared site. Prefer the product CLI above for new work. `OPPEN_COUNCIL_PYTHON` can select an existing interpreter containing the package. The wrapper preserves old entrypoints; it does not provide a separate server.

## Native v3/v4 compatibility and adoption

New `init`/Steward `adopt` operations create v4 projects. Native v3 remains compatible with existing operations and Council; indexing does not silently change its schema marker. For an authorized upgrade use the governing helper's `upgrade-v4 TARGET --check`, then `upgrade-v4 TARGET --apply`. This changes only the governance marker (and Steward's managed baseline), preserves project files and uses the existing write protections. It is idempotent. Stepwise v2 first uses the established semantic `migrate` workflow to v3, then `upgrade-v4`. Steward legacy root layouts first use `upgrade-layout`.

The marker upgrade does not convert human replies or historical summaries into formal versions. Existing Markdown Canonical owners remain authoritative until individually adopted. Reuse native definition versions directly. To adopt an older definition, read its full owned text and confirmation evidence, retain recovery provenance, prepare a complete candidate and make the ownership move explicit when the human confirms it. Do not summarize a precise older rule into a new authority or repeatedly ask settled research questions merely because the storage changed. A compatibility recovery record describes its original source and is not a v4 formal version.
