"""Shared validation catches real file/registration drift without reading archives."""

import json
import subprocess
import sys

import pytest
import test_script_ops_v5 as fixtures

from oppencouncil import bootstrap, project_checks, script_ops
from oppencouncil.outputs import Outputs
from oppencouncil.project import Project
from oppencouncil.project_registry import Registry, read_table, write_table

project = fixtures.project


def renumber(root):
    script_ops.apply(root, script_ops.check(root, "renumber", fixtures.ordered()).public())


def test_shared_validate_and_index_after_renumber(project):
    initial = project_checks.validate(project)
    assert not initial["errors"], initial
    assert any("execution prefix" in item["reason"] for item in initial["warnings"])
    renumber(project)
    before = fixtures.snapshot(project)
    result = project_checks.validate(project)
    assert result["state"] == "MANAGED_READY", result
    assert not any("execution prefix" in item["reason"] for item in result["warnings"])
    view = project_checks.index(project)
    assert view["outputs"][0]["producer"] == "R/02_report.py"
    assert len(view["memory"]) == 1
    assert view["work"]["total"] == 1
    assert fixtures.snapshot(project) == before


def test_new_unnumbered_script_is_an_error(project):
    renumber(project)
    (project / "R/extra.py").write_text("print(1)\n")
    result = project_checks.validate(project)
    assert any("execution prefix" in item["reason"] for item in result["errors"])


@pytest.mark.parametrize("rename_directory", [False, True])
def test_shared_script_numbers_preserve_paths_and_registrations(project, rename_directory):
    renumber(project)
    (project / "R/formal").mkdir()
    scripts = {
        "R/01_helpers.py": "factor = 3\n",
        "R/01_summary.jl": "println(1)\n",
        "R/formal/01_contract.R": "stopifnot(TRUE)\n",
    }
    for name, text in scripts.items():
        (project / name).write_text(text)
    before = fixtures.snapshot(project)
    result = project_checks.validate(project)
    assert result["state"] == "MANAGED_READY", result
    assert fixtures.snapshot(project) == before

    area = "R"
    if rename_directory:
        plan = script_ops.check(project, "rename-directory", {"to": "Scripts"})
        script_ops.apply(project, plan.public())
        area = "Scripts"
    result = project_checks.validate(project)
    assert result["state"] == "MANAGED_READY", result
    assert not any("execution" in item["reason"] for item in result["warnings"])
    view = project_checks.index(project)
    assert view["outputs"][0]["producer"] == f"{area}/02_report.py"
    assert read_table(Registry(project).text, "canonical")[0]["Verification"] == f"{area}/01_clean.py"
    for name, text in scripts.items():
        assert (project / (area + name[1:])).read_text() == text


def test_legacy_topics_sharing_one_formal_source_are_not_duplicate_authority(project):
    registry = Registry(project)
    rows = read_table(registry.text, "canonical")
    formal = project / rows[0]["Canonical path"]
    original = formal.read_bytes()
    rows.append({**rows[0], "Topic": "another-scope-on-the-same-definition"})
    registry.text = write_table(registry.text, "canonical", tuple(rows[0]), rows)
    registry.commit()
    assert not project_checks.validate(project)["errors"]
    assert formal.read_bytes() == original
    # A repeated topic is still ambiguous, even when it names the same F.
    rows[-1]["Topic"] = rows[0]["Topic"]
    registry = Registry(project)
    registry.text = write_table(registry.text, "canonical", tuple(rows[0]), rows)
    registry.commit()
    assert any("Duplicate canonical topic" in e["reason"] for e in project_checks.validate(project)["errors"])


@pytest.mark.parametrize("source", ["R/01_clean.py", "R/functions/helpers.py"])
def test_explore_dependency_in_formal_execution_chain_is_rejected(project, source):
    renumber(project)
    (project / source).write_text('source = "Explore/trial/output.csv"\n')
    result = project_checks.validate(project)
    assert any(item.get("path") == source and "Explore" in item["reason"] for item in result["errors"])


def test_unassigned_file_is_reported_and_archive_content_is_not_loaded(project, monkeypatch):
    (project / "loose.md").write_text("Needs a current owner\n")
    archive = project / "Explore/_archive/001-old"
    archive.mkdir(parents=True)
    secret = archive / "notes.md"
    secret.write_bytes(b"\xff\xfe not a current input")
    original = type(secret).read_bytes

    def guarded(path):
        assert not path.is_relative_to(archive)
        return original(path)

    monkeypatch.setattr(type(secret), "read_bytes", guarded)
    result = project_checks.validate(project)
    assert "loose.md" in result["unassigned_files"]
    assert not result["errors"], result


def test_data_hash_drift_and_missing_verification_are_reported(project):
    Outputs(project).register_data(
        {"path": "Data/raw/input.csv", "kind": "raw", "source": "Synthetic fixture", "version": "1"}
    )
    (project / "Data/raw/input.csv").write_text("x\n3\n")
    (project / "R/clean.py").unlink()
    result = project_checks.validate(project)
    assert any("Data changed" in item["reason"] for item in result["errors"])
    assert any("does not exist" in item["reason"] for item in result["errors"])


def test_general_project_does_not_apply_research_script_rules(tmp_path):
    bootstrap.create(tmp_path, project_type="general")
    (tmp_path / "analysis.R").write_text('source("Explore/trial.R")\n')
    result = project_checks.validate(tmp_path)
    assert result["state"] == "MANAGED_READY", result
    assert not result["unassigned_files"]


def test_baseline_drift_is_reported_without_resetting_it(project):
    registry = Registry(project)
    with registry.project.registry.open("a") as handle:
        handle.write("Unexplained edit\n")
    before = registry.project.baseline.read_bytes()
    result = project_checks.validate(project)
    assert any("MANAGED_STATE_CONFLICT" in item["reason"] for item in result["errors"])
    assert registry.project.baseline.read_bytes() == before


def test_cli_plan_apply_validate_and_review(project, tmp_path_factory):
    temporary = tmp_path_factory.mktemp("cli")
    payload, plan = temporary / "input.json", temporary / "plan.json"
    payload.write_text(json.dumps(fixtures.ordered()))
    prefix = [sys.executable, "-m", "oppencouncil.governance"]
    run = subprocess.run(
        [
            *prefix,
            "scripts",
            "renumber",
            str(project),
            "--check",
            "--input",
            str(payload),
            "--plan",
            str(plan),
        ],
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stderr
    assert (project / "R/clean.py").exists()
    mismatch = subprocess.run(
        [*prefix, "scripts", "rename-directory", str(project), "--apply", "--plan", str(plan)],
        capture_output=True,
        text=True,
    )
    assert mismatch.returncode == 2 and "does not match" in mismatch.stderr
    assert (project / "R/clean.py").exists()
    run = subprocess.run(
        [*prefix, "scripts", "renumber", str(project), "--apply", "--plan", str(plan)],
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stderr
    for command in (["validate"], ["index"], ["review", "list"]):
        run = subprocess.run([*prefix, *command, str(project)], capture_output=True, text=True)
        assert run.returncode == 0, run.stderr + run.stdout
        assert isinstance(json.loads(run.stdout), dict)
    (project / "R/01_clean.py").unlink()
    run = subprocess.run([*prefix, "validate", str(project)], capture_output=True, text=True)
    assert run.returncode == 2 and json.loads(run.stdout)["errors"]
    Project(project).baseline_state()
