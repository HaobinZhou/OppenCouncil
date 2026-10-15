import json

import pytest

from oppenproject.capabilities import inspect
from oppenproject.config import Settings


@pytest.mark.parametrize("versions", [[], [3, 4], [3, 4, 5]])
def test_http_checks_selected_running_service(tmp_path, monkeypatch, versions):
    projects = tmp_path / "projects.json"
    projects.write_text(json.dumps({"projects": [str(tmp_path)]}))
    settings = Settings(projects_file=projects)
    monkeypatch.setattr(
        "oppenproject.capabilities.get_json",
        lambda url: {"service": "OppenCouncil MCP", "status": "ok", "governance_versions": versions},
    )
    result = inspect(settings, tmp_path)
    assert result["required"]
    assert result["governance_versions"] == versions


def test_stdio_probes_installed_launch_and_preserves_configuration(tmp_path):
    projects = tmp_path / "projects.json"
    projects.write_text(json.dumps({"projects": [str(tmp_path)]}))
    before = projects.read_bytes()
    settings = Settings(transport="stdio", projects_file=projects, state_dir=tmp_path / "runtime")
    result = inspect(settings, tmp_path)
    assert result["governance_versions"] == [3, 4, 5]
    assert result["reconnect_existing_session"]
    assert projects.read_bytes() == before
    assert not settings.state_dir.exists()


def test_other_project_is_not_a_connection_and_malformed_registry_blocks(tmp_path):
    projects = tmp_path / "projects.json"
    projects.write_text('{"projects": []}')
    settings = Settings(projects_file=projects)
    assert inspect(settings, tmp_path)["required"] is False
    projects.write_text('{"projects": 1}')
    assert inspect(settings, tmp_path)["error"]
