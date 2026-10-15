"""Probe actual selected service capabilities; keep check and planning read-only."""

import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
import test_migration_v5 as migration_fixtures
from test_migration_v5 import files

from oppencouncil import capabilities
from oppencouncil.registry import Registry
from oppencouncil.store import FreezeStore

legacy = migration_fixtures.legacy


@pytest.mark.parametrize("versions,expected", [(None, []), ([3, 4], [3, 4]), ([3, 4, 5], [3, 4, 5])])
def test_registered_council_probes_listener_without_exposing_credentials(
    legacy, tmp_path, versions, expected
):
    root, _, _ = legacy
    directory = tmp_path / "site"
    Registry(directory).register(root)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            assert self.path == "/api/healthz"
            assert self.headers.get("X-Council-Admin") == "private-test-token"
            result = {"app": "OppenCouncil", "version": "4.3.1"}
            if versions is not None:
                result["governance_versions"] = versions
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    (directory / ".runtime").mkdir()
    (directory / ".runtime/server.json").write_text(
        json.dumps({"port": server.server_port, "admin_token": "private-test-token"})
    )
    before = files(root)
    try:
        result = capabilities.council(root, directory)
        assert result["governance_versions"] == expected
        assert result["source"] == "running_service"
        assert "private-test-token" not in json.dumps(result)
        assert files(root) == before
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_missing_connected_service_blocks_but_unregistered_copy_uses_local_package(legacy, tmp_path):
    root, _, _ = legacy
    directory = tmp_path / "site"
    assert capabilities.council(root, directory)["governance_versions"] == [3, 4, 5]
    Registry(directory).register(root)
    assert capabilities.council(root, directory)["error"]


def test_configured_old_mcp_cannot_be_mistaken_for_optional_absence(tmp_path, monkeypatch):
    for name in list(__import__("os").environ):
        if name.startswith("OPPEN_"):
            monkeypatch.delenv(name)
    root = tmp_path / "mcp"
    root.mkdir()
    assert not capabilities.mcp(tmp_path, root)["required"]
    (root / "config.local.json").write_text("{}")
    assert capabilities.mcp(tmp_path, root)["required"]
    assert capabilities.mcp(tmp_path, root)["error"]


def test_cli_uses_exact_external_plan_and_requires_new_check_for_changed_inputs(
    legacy, tmp_path, monkeypatch
):
    root, _, _ = legacy
    for name in list(__import__("os").environ):
        if name.startswith("OPPEN_"):
            monkeypatch.delenv(name)
    plan = tmp_path / "plan.json"
    args = [
        sys.executable,
        "-m",
        "oppencouncil.governance",
        "upgrade-v5",
        str(root),
        "--plan",
        str(plan),
        "--council-directory",
        str(tmp_path / "site"),
        "--mcp-root",
        str(tmp_path / "absent-mcp"),
    ]
    before = files(root)
    checked = subprocess.run([*args, "--check"], capture_output=True, text=True, timeout=20)
    assert checked.returncode == 0, checked.stderr
    assert files(root) == before
    assert json.loads(checked.stdout) == json.loads(plan.read_text())
    applied = subprocess.run([*args, "--apply"], capture_output=True, text=True, timeout=20)
    assert applied.returncode == 0, applied.stderr
    assert FreezeStore(root).v5
    repeated = subprocess.run([*args, "--apply"], capture_output=True, text=True, timeout=20)
    assert repeated.returncode == 0, repeated.stderr
    assert json.loads(repeated.stdout)["replayed"]


def test_plan_inside_project_rejected_before_any_project_mutation(legacy):
    root, _, _ = legacy
    before = files(root)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "oppencouncil.governance",
            "upgrade-v5",
            str(root),
            "--check",
            "--plan",
            str(root / "plan.json"),
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 2
    assert "outside" in result.stderr
    assert files(root) == before
