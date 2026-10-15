# Product maintenance

Use for a requested skill/product update or connection repair. Run `python ABSOLUTE_SKILL/scripts/update_skill.py --check` to inspect the product Git checkout and available update. `--apply` performs the supported verified fast-forward update; the updater checks all three skill names and preserves unrelated dirty work. `--skill-dir PATH` selects the actual installed skill directory. Product version and project governance generation are separate.

Installation uses the product's `scripts/install.py`: `--with-mcp` includes the optional MCP package; `--no-skills` leaves installed skill links alone. `--check` previews installation. A requested link replacement is handled as one three-name operation with rollback. Product verification uses `scripts/verify.py`; individual component tests can verify a bounded repair.

For an existing connection, the installed Council CLI's `--directory SITE status TARGET` reports the site and project registration. OppenCouncil MCP retains its existing service identifiers, environment configuration, OAuth grants and authorization scopes. Its read/write surface is documented in [council.md](council.md); webpage registration does not grant MCP access. A new connection or changed permission scope follows the requested [MCP publication workflow](mcp-publication.md).

An installed package, passing tests, an updated running process and a reachable authorized client are separate observed states. Project conversion uses [migration.md](migration.md), rather than the product updater.
