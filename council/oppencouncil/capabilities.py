"""Read-only capability checks for the exact project and selected installations."""

from __future__ import annotations

import json
import os
import subprocess
import urllib.request
from pathlib import Path

from .project import unique_object
from .registry import Registry, default_directory
from .store import GOVERNANCE_VERSIONS, FreezeError, ordinary_file


def get_json(url, *, headers=None):
    # A local probe never inherits proxy settings or follows a redirect with credentials.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    request = urllib.request.Request(url, headers=headers or {})
    with opener.open(request, timeout=3) as response:
        raw = response.read(65537)
    if len(raw) > 65536:
        raise ValueError("Capability response exceeds the limit")
    result = json.loads(raw, object_pairs_hook=unique_object)
    if not isinstance(result, dict):
        raise ValueError("Invalid capability response")
    return result


def council(project, directory):
    result = {"required": True, "directory": str(directory), "governance_versions": []}
    try:
        registered = any(
            p["enabled"] and Path(p["root"]).resolve() == project for p in Registry(directory).read()
        )
        if not registered:
            result.update(source="local_package", governance_versions=list(GOVERNANCE_VERSIONS))
            return result
        result["source"] = "running_service"
        raw = ordinary_file(directory / ".runtime/server.json", 16384)
        value = json.loads(raw, object_pairs_hook=unique_object) if raw else {}
        port, token = value.get("port"), value.get("admin_token")
        if type(port) is not int or not 0 < port < 65536 or not isinstance(token, str) or not token:
            raise ValueError("The registered Council service has no usable runtime state")
        response = get_json(f"http://127.0.0.1:{port}/api/healthz", headers={"X-Council-Admin": token})
        if response.get("app") != "OppenCouncil":
            raise ValueError("The listener is not an OppenCouncil service")
        result.update(port=port, governance_versions=response.get("governance_versions", []))
    except (OSError, ValueError, FreezeError):
        # Do not echo private server state, headers or arbitrary response text.
        result["error"] = "Cannot verify the registered Council service; upgrade/start it before migration"
    return result


def mcp(project, root, config=None):
    result = {"required": True, "root": str(root), "governance_versions": []}
    config = config or root / "config.local.json"
    configured = (
        config.exists()
        or (config.parent / ".env").exists()
        or (config.parent / "projects.local.json").exists()
        or any(key.startswith("OPPEN_") and not key.startswith("OPPEN_COUNCIL_") for key in os.environ)
    )
    if not configured:
        return {**result, "required": False, "source": "not_configured"}
    python = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    command = [
        str(python),
        str(root / "run.py"),
        "--config",
        str(config),
        "capabilities",
        "--project",
        str(project),
    ]
    try:
        process = subprocess.run(command, capture_output=True, timeout=15, check=False)
        if process.returncode or len(process.stdout) > 65536:
            raise ValueError("MCP probe failed")
        response = json.loads(process.stdout, object_pairs_hook=unique_object)
        if not isinstance(response, dict) or type(response.get("required")) is not bool:
            raise ValueError("Invalid MCP capability response")
        result.update(response)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        result["error"] = "Cannot verify the configured MCP installation; upgrade it before migration"
    return result


def inspect(project, *, council_directory=None, mcp_root=None, mcp_config=None):
    project = Path(project).expanduser().resolve(strict=True)
    directory = Path(council_directory or default_directory()).expanduser().resolve()
    root = Path(mcp_root or Path(__file__).resolve().parents[2] / "mcp").expanduser().resolve()
    config = Path(mcp_config).expanduser().resolve() if mcp_config else None
    return {
        "skill": {"source": "shared_helper", "governance_versions": list(GOVERNANCE_VERSIONS)},
        "council": council(project, directory),
        "mcp": mcp(project, root, config),
    }
