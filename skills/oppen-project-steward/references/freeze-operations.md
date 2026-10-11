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
  "request_id": "cache-policy-round-1",
  "questions": [
    {
      "group": "接口与状态",
      "title": "其他审阅者何时看到已保存的共享记录？",
      "why": "更新方式影响多人协作时的等待时间和服务开销。",
      "source_summary": "合成示例：假设保存已可靠写入项目，三种方案均保留本地草稿，并在冲突时要求比较。",
      "ai_position": "A：保存后通知其他在线页面重新读取记录；正常连接下可很快看到更新，需要维护通知连接及断线后的补读。\nB：在线页面每 5 分钟读取一次；实现较简单，但刚错过一次读取的更新可能要等近 5 分钟，且无变化时也会发出读取请求。\nC：由审阅者点击刷新才重新读取；自动请求最少，但旧内容可能一直停留到用户主动刷新。\n同一示例：另一位审阅者在 10:01 保存，而我上次在 10:00 读取。A 在收到通知后显示新记录；B 在 10:05 读取后显示；C 等我点击刷新后显示。以上时间为演示，A 的真实延迟需测量。若目标是多人及时审阅，建议 A；若可接受几分钟延迟且希望实现简单，选 B；仅在明确接受手动更新时选 C。",
      "suggestions": ["A：保存后通知在线页面刷新", "B：每 5 分钟自动读取", "C：用户点击刷新时读取"]
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


## Native v3/v4 compatibility and adoption

New `init`/Steward `adopt` operations create v4 projects. Native v3 remains compatible with existing operations and Council; indexing does not silently change its schema marker. For an authorized upgrade use the governing helper's `upgrade-v4 TARGET --check`, then `upgrade-v4 TARGET --apply`. This changes only the governance marker (and Steward's managed baseline), preserves project files and uses the existing write protections. It is idempotent. Stepwise v2 first uses the established semantic `migrate` workflow to v3, then `upgrade-v4`. Steward legacy root layouts first use `upgrade-layout`.

The marker upgrade does not convert human replies or historical summaries into formal versions. Existing Markdown Canonical owners remain authoritative until individually adopted. Reuse native definition versions directly. To adopt an older definition, read its full owned text and confirmation evidence, retain recovery provenance, prepare a complete candidate and make the ownership move explicit when the human confirms it. Do not summarize a precise older rule into a new authority or repeatedly ask settled research questions merely because the storage changed. A compatibility recovery record describes its original source and is not a v4 formal version.
