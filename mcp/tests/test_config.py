import json
from dataclasses import asdict, replace

import pytest

from oppenproject.catalog import Catalog
from oppenproject.config import Settings, runtime_environment
from oppenproject.server import create_app, create_mcp


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    import os

    for key in os.environ:
        if key.startswith("OPPEN_") or key == "CONTROL_PLANE_API_KEY":
            monkeypatch.delenv(key)


def test_fresh_default_and_legacy_http(tmp_path):
    config = tmp_path / "config.local.json"
    assert Settings.load(config).transport == "stdio"
    assert Settings.load(config).state_dir == tmp_path / ".runtime"
    assert Settings.load(config).projects_file == tmp_path / "projects.local.json"
    config.write_text(json.dumps({"public_url": "https://projects.example.com"}), encoding="utf-8")
    assert Settings.load(config).transport == "http"
    assert not (tmp_path / ".runtime").exists()


def test_env_precedence_paths_and_no_shell_interpolation(tmp_path, monkeypatch):
    config = tmp_path / "config.local.json"
    config.write_text('{"port": 8880}', encoding="utf-8")
    (tmp_path / ".env").write_text(
        "OPPEN_PORT=8881\nOPPEN_TRANSPORT=stdio\nOPPEN_PROJECTS_FILE=./项目列表.json\n"
        'OPPEN_EXCLUDE_ROOTS=["./项目/private"]\nOPPEN_FREEZE_PROJECTS=["./项目"]\n'
        'OPPEN_STATE_DIR=state\nOPPEN_SKILL_ROOT=skills\n'
        "CONTROL_PLANE_API_KEY='fixture-${HOME}-$(echo literal)'\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OPPEN_PORT", "8882")
    result = Settings.load(config)
    assert result.port == 8882 and result.transport == "stdio"
    assert result.projects_file == tmp_path / "项目列表.json"
    assert result.exclude_roots == [str(tmp_path / "项目/private")]
    assert result.freeze_projects == [str(tmp_path / "项目")]
    assert result.state_dir == tmp_path / "state" and result.skill_root == tmp_path / "skills"
    assert runtime_environment(tmp_path)["CONTROL_PLANE_API_KEY"] == "fixture-${HOME}-$(echo literal)"
    assert "fixture-" not in json.dumps(asdict(result), default=str)


@pytest.mark.parametrize(
    "setting,value",
    [
        ("PORT", "garbage"),
        ("PORT", "80"),
        ("TRANSPORT", "noauth-http"),
        ("HOST", "0.0.0.0"),
        ("PUBLIC_URL", "http://public.example.com"),
        ("PUBLIC_URL", "https://example.com/mcp"),
        ("PROJECTS_FILE", ""),
        ("STATE_DIR", ""),
        ("TUNNEL_PROFILE", "../outside"),
    ],
)
def test_invalid_environment_is_rejected(tmp_path, monkeypatch, setting, value):
    monkeypatch.setenv("OPPEN_" + setting, value)
    with pytest.raises(ValueError):
        Settings.load(tmp_path / "config.local.json")


def test_http_cannot_start_without_auth_and_stdio_cannot_mount_http(tmp_path):
    stdio = Settings.load(tmp_path / "config.local.json")
    with pytest.raises(ValueError):
        create_app(stdio)
    http = replace(stdio, transport="http")
    with pytest.raises(ValueError):
        create_mcp(http, Catalog(http))


def test_missing_skills_do_not_prevent_project_discovery(tmp_path):
    settings = Settings(skill_root=tmp_path)
    with pytest.raises(ValueError, match="not installed"):
        settings.skill_guide("oppen-project-steward")
    with pytest.raises(ValueError, match="Unknown skill"):
        settings.skill_guide("../../.env")


def test_default_guides_are_the_skills_from_the_same_product_checkout():
    from oppenproject.config import ROOT

    settings = Settings()
    for skill in ("oppen-project-steward", "stepwise-r-project"):
        expected = ROOT.parent / "skills" / skill / "SKILL.md"
        assert settings.skill_guide(skill).resolve() == expected.resolve()
        assert settings.skill_guide(skill).read_bytes() == expected.read_bytes()


def test_old_scan_config_never_registers_roots(tmp_path, monkeypatch, caplog):
    config = tmp_path / "config.local.json"
    config.write_text(json.dumps({"scan_roots": [str(tmp_path)], "scan_interval": 10}), encoding="utf-8")
    monkeypatch.setenv("OPPEN_SCAN_ROOTS", '["~"]')
    settings = Settings.load(config)
    catalog = Catalog(settings)
    assert catalog.refresh()["status"] == "config_missing"
    assert not catalog.projects
    assert "Automatic scanning has been removed" in caplog.text


def test_service_relocation_keeps_explicit_config_location(tmp_path):
    import importlib.util

    from oppenproject.config import ROOT

    spec = importlib.util.spec_from_file_location('relocated_service', ROOT / 'service.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    config = tmp_path / 'existing config' / 'config.local.json'
    command = module.service_command(config)
    assert command == [str(ROOT / '.venv/bin/python'), str(ROOT / 'run.py'),
                       '--config', str(config), 'serve']
    assert module.service_command()[-1] == 'serve'


def installed_guides(tmp_path):
    root = tmp_path / "skills"
    skill = root / "stepwise-r-project"
    (skill / "references").mkdir(parents=True)
    (skill / "SKILL.md").write_text("# Entry\nSee references/freeze-workbench.md\n")
    (skill / "references/freeze-workbench.md").write_text("# Round\nComplete candidate rules.\n")
    return Settings(skill_root=root), skill


def test_skill_references_use_selected_installation_and_support_skill_symlinks(tmp_path):
    settings, skill = installed_guides(tmp_path)
    expected = skill / "references/freeze-workbench.md"
    assert settings.skill_guide("stepwise-r-project") == skill / "SKILL.md"
    assert settings.skill_guide("stepwise-r-project", "references/freeze-workbench.md") == expected
    aliases = tmp_path / "aliases"
    aliases.mkdir()
    try:
        (aliases / skill.name).symlink_to(skill, target_is_directory=True)
    except OSError:
        pytest.skip("Directory symlinks unavailable")
    assert Settings(skill_root=aliases).skill_guide(
        skill.name, "references/freeze-workbench.md"
    ) == expected.resolve()
    # A missing reference must not come from the same-named skill in another checkout.
    with pytest.raises(ValueError, match="not installed in the selected skill"):
        settings.skill_guide(skill.name, "references/maintenance.md")


@pytest.mark.parametrize("resource", [
    "../SKILL.md", "/etc/passwd", "references/../../.env", "references/../SKILL.md",
    "references/nested/file.md", "references/file.txt", "scripts/run.py", ".env",
    "references\\freeze-workbench.md", "references/%2e%2e/private.md",
])
def test_skill_reference_access_excludes_arbitrary_files(tmp_path, resource):
    settings, skill = installed_guides(tmp_path)
    with pytest.raises(ValueError, match="Only SKILL.md"):
        settings.skill_guide(skill.name, resource)


@pytest.mark.parametrize("directory", [False, True])
def test_skill_reference_symlinks_cannot_expose_other_files(tmp_path, directory):
    settings, skill = installed_guides(tmp_path)
    outside = tmp_path / "private"
    outside.mkdir()
    (outside / "private.md").write_text("not a skill guide")
    try:
        if directory:
            (skill / "references/freeze-workbench.md").unlink()
            (skill / "references").rmdir()
            (skill / "references").symlink_to(outside, target_is_directory=True)
        else:
            (skill / "references/private.md").symlink_to(outside / "private.md")
    except OSError:
        pytest.skip("Symlinks unavailable")
    with pytest.raises(ValueError, match="symlinks"):
        settings.skill_guide(skill.name, "references/private.md")


@pytest.mark.asyncio
async def test_mcp_skill_guide_follows_a_reference_without_project_file_access(tmp_path):
    from mcp.server.fastmcp.exceptions import ToolError

    settings, skill = installed_guides(tmp_path)
    settings.transport = "stdio"
    mcp = create_mcp(settings, Catalog(settings))
    entry = await mcp.call_tool("get_skill_guide", {"skill": skill.name})
    reference = await mcp.call_tool("get_skill_guide", {
        "skill": skill.name, "resource": "references/freeze-workbench.md",
    })
    # FastMCP returns content blocks plus structured output for annotated dict tools.
    assert entry[1]["content"] == (skill / "SKILL.md").read_text()
    assert reference[1]["resource"] == "references/freeze-workbench.md"
    assert reference[1]["content"] == (skill / "references/freeze-workbench.md").read_text()
    with pytest.raises(ToolError):
        await mcp.call_tool("get_skill_guide", {"skill": skill.name, "resource": "../project.md"})
