# Security

The authoritative exposure and authentication rules are the registered
[README contracts](README.md#gpt-能看到哪些文件). This server is intended for
one local owner. Only exact project roots in the local registration file are
accessible; a missing or invalid file disables project access. Governance document bodies can contain sensitive information;
the file allowlist does not redact their contents. The optional Discussion tools
also expose their text bodies. Discussion writes are limited to its documents and index. Separately enabled Freeze tools
allow discussion, option and candidate edits only for explicitly allowed projects; AI cannot
confirm or overwrite effective definitions. Neither write path executes document text.
Skill guides expose only the installed entry and named references; they grant no project file access.

For a suspected authorization bypass or unintended file disclosure, use the
repository's private vulnerability reporting feature if enabled. If no private
reporting channel is available, open an issue requesting a private channel
without posting exploit details, private documents or credentials. There is no
guaranteed response-time commitment.

Use synthetic fixtures for a report. Include the affected commit, OS, transport
and the smallest reproduction. Do not attach `.env`, `config.local.json`, `projects.local.json`,
`.runtime`, tunnel profiles with secrets, or live OAuth messages. If a deployed
credential is exposed, revoke it locally and rotate the appropriate credential
through its owner (this server's OAuth or OpenAI's Tunnel runtime key).

CI exercises native filesystem, authorization and protocol behavior on Windows,
macOS and Linux. Actual ChatGPT account connection has only been tested on macOS.
Reports about native path, ACL, process or account integration behavior are welcome.
