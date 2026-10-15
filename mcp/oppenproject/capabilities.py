"""Inspect capability of a configured connection without starting or configuring it."""

from pathlib import Path

from oppencouncil.capabilities import get_json

from .catalog import Catalog
from .config import APP_NAME
from .freeze import GOVERNANCE_VERSIONS


def inspect(settings, project):
    root = Path(project).expanduser().resolve(strict=True)
    catalog = Catalog(settings)
    result = {"required": True, "governance_versions": [], "transport": settings.transport}
    try:
        try:
            signature = catalog.configuration_signature()
        except FileNotFoundError:
            return {**result, "required": False, "source": "not_registered"}
        roots = catalog.registered_roots(signature)
        if not any(Path(p).resolve() == root for p in roots):
            return {**result, "required": False, "source": "not_registered"}
        if settings.transport == "stdio":
            # This probe is a fresh child of the selected installation, using the
            # same interpreter/config as serve. Clients own stdio process lifetime.
            return {
                **result,
                "source": "stdio_launch",
                "governance_versions": list(GOVERNANCE_VERSIONS),
                "reconnect_existing_session": True,
            }
        host = "[::1]" if settings.host == "::1" else settings.host
        response = get_json(f"http://{host}:{settings.port}/healthz")
        if response.get("service") != APP_NAME or response.get("status") != "ok":
            raise ValueError("Unsupported MCP service")
        result.update(source="running_service", governance_versions=response.get("governance_versions", []))
    except (OSError, ValueError):
        result["error"] = "Cannot verify the registered MCP service; upgrade/start it before migration"
    return result
