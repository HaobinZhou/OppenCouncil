"""Actual compatibility entrypoints select by project generation, not their name."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from test_memory_v5 import legacy_module, payload

from oppencouncil import bootstrap
from oppencouncil.project import Project
from oppencouncil.project_transaction import LOCK, STAGING

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ("oppencouncil", "stepwise-r-project", "oppen-project-steward")
CAPABILITIES = {"council": {"governance_versions": [3, 4, 5]}, "skill": {"governance_versions": [3, 4, 5]}}


def command(skill, *args):
    script = ROOT / "skills" / skill / "scripts" / (skill.replace("-", "_") + ".py")
    return subprocess.run([sys.executable, str(script), *map(str, args)], capture_output=True, text=True)


def files(root):
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in root.rglob("*")
        if p.is_file() and p.name not in {LOCK, ".lock"}
    }


@pytest.mark.parametrize("skill", SKILLS)
@pytest.mark.parametrize("kind,layout", [("research", "namespace"), ("general", "root")])
def test_alias_respects_declared_type_independent_of_layout(tmp_path, skill, kind, layout):
    root = tmp_path / "project"
    bootstrap.create(root, project_type=kind, layout=layout)
    result = command(skill, "project-type", root)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["project_type"] == kind
    before = files(root)
    result = command(skill, "init", root)
    assert result.returncode == 0 and not json.loads(result.stdout)["changed_paths"], result.stderr
    assert files(root) == before
    data = payload(related_topics=[], supersedes=[], invalidates=[])
    data.pop("basis")
    source = tmp_path / "memory.json"
    source.write_text(json.dumps(data))
    before = files(root)
    result = command(skill, "memory", "add", root, "--input", source)
    if kind == "research":
        assert result.returncode == 2 and "basis" in result.stderr
        assert files(root) == before
        data["basis"] = "A measured synthetic failure motivates the confirmed redesign."
        source.write_text(json.dumps(data))
        result = command(skill, "memory", "add", root, "--input", source)
    assert result.returncode == 0, result.stderr
    assert source.exists()
    result = command(skill, "memory", "index", root)
    assert result.returncode == 0 and len(json.loads(result.stdout)) == 1, result.stderr
    Project(root).baseline_state()


@pytest.mark.parametrize(
    "skill,kind", [("stepwise-r-project", "research"), ("oppen-project-steward", "general")]
)
def test_alias_init_creates_v5_with_compatible_default_type(tmp_path, skill, kind):
    root = tmp_path / "new"
    result = command(skill, "init", root)
    assert result.returncode == 0, result.stderr
    assert Project(root).project_type == kind
    assert json.loads(result.stdout)["project"] == str(root.resolve())


@pytest.mark.parametrize("skill", SKILLS)
@pytest.mark.parametrize("old", ["stepwise-r-project", "oppen-project-steward"])
def test_legacy_project_keeps_original_engine_and_rejects_v5_only_commands(tmp_path, skill, old):
    root = tmp_path / "legacy"
    root.mkdir()
    original = legacy_module(old.replace("-", "_"))
    original.ensure_v3_project(root, create=True)
    original.refresh_index(root)
    before = files(root)
    result = command(skill, "validate", root)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "validation" in result.stdout.lower() and '"project_type"' not in result.stdout
    assert files(root) == before
    result = command(skill, "project-type", root, "--set", "general", "--reason", "Not a migration")
    assert result.returncode == 2 and "upgrade-v5" in result.stderr
    assert files(root) == before


@pytest.mark.parametrize("old", ["stepwise-r-project", "oppen-project-steward"])
def test_alias_recovers_interrupted_upgrade_before_selecting_engine(tmp_path, old):
    root = tmp_path / "legacy"
    root.mkdir()
    original = legacy_module(old.replace("-", "_"))
    original.ensure_v3_project(root, create=True)
    original.refresh_index(root)
    before = files(root)
    code = """
import os, sys
from oppencouncil import migration
capabilities = {'council': {'governance_versions': [3,4,5]}, 'skill': {'governance_versions': [3,4,5]}}
def die(phase, path):
    if phase == 'verified': os._exit(73)
plan = migration.check(sys.argv[1], capabilities).public()
migration.apply(sys.argv[1], plan, capabilities, fault=die)
"""
    run = subprocess.run([sys.executable, "-c", code, str(root)], capture_output=True, text=True)
    assert run.returncode == 73, run.stderr
    assert (root / STAGING).exists()
    interrupted = files(root)
    checked = command("oppencouncil", "upgrade-v5", root, "--check")
    assert checked.returncode == 2 and "RECOVERY_REQUIRED" in checked.stderr
    assert files(root) == interrupted
    result = command("oppencouncil", "validate", root)
    assert result.returncode == 0, result.stderr + result.stdout
    assert not (root / STAGING).exists() and files(root) == before


def test_v5_legacy_audit_aliases_and_retired_commands(tmp_path):
    root = tmp_path / "research"
    bootstrap.create(root, project_type="research")
    (root / "source.py").write_text("assert True\n")
    result = command(
        "stepwise-r-project",
        "module-audit",
        root,
        "--module",
        "logic",
        "--source",
        "source.py",
        "--risk-reason",
        "Result correctness",
    )
    assert result.returncode == 0 and json.loads(result.stdout)["status"] == "draft", result.stderr
    before = files(root)
    result = command(
        "stepwise-r-project",
        "function-audit",
        root,
        "--function",
        "logic",
        "--source",
        "source.py",
        "--risk-reason",
        "Result correctness",
    )
    assert result.returncode == 2 and "retired" in result.stderr
    assert files(root) == before
    result = command("stepwise-r-project", "audit-recover", root, "--stage", "model")
    assert result.returncode == 0, result.stderr


def test_option_order_and_ambiguous_anchors_cannot_select_another_governor(tmp_path):
    root = tmp_path / "project"
    bootstrap.create(root, project_type="research")
    result = command(
        "oppen-project-steward", "project-type", "--set", "general", root, "--reason", "Explicit change"
    )
    assert result.returncode == 0 and Project(root).project_type == "general", result.stderr
    directory = root / ".oppen-project-steward"
    directory.mkdir()
    (directory / "registry.md").write_text("<!-- oppen-project-steward:v4 -->\n")
    before = files(root)
    result = command("oppen-project-steward", "index", root)
    assert result.returncode == 2 and "Multiple project anchors" in result.stderr
    assert files(root) == before
