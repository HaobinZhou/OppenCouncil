"""Creation/adoption preserves existing project content and survives partial writes."""

import copy
import json
import subprocess
import sys

import pytest

from oppencouncil import bootstrap
from oppencouncil import project_transaction as tx
from oppencouncil.outputs import Outputs
from oppencouncil.project import Project
from oppencouncil.project_registry import Registry, read_table
from oppencouncil.store import FreezeError


@pytest.mark.parametrize("kind", ["research", "general"])
@pytest.mark.parametrize("layout", ["root", "namespace"])
def test_init_and_idempotence_independent_of_layout(tmp_path, kind, layout):
    root = tmp_path / "project"
    result = bootstrap.create(root, project_type=kind, layout=layout)
    assert result["state"] == "MANAGED_READY"
    project = Project(root)
    assert project.project_type == kind
    assert project.namespaced == (layout == "namespace")
    before = project.baseline.read_bytes()
    assert bootstrap.create(root, project_type=kind, layout=layout)["changed_paths"] == []
    assert project.baseline.read_bytes() == before
    if kind == "research":
        assert all(
            (root / p).is_dir()
            for p in ("Scripts/functions", "Data/raw", "Data/derived", "Results", "Explore", "Releases")
        )
    else:
        assert not (root / "Scripts").exists()
    with pytest.raises(FreezeError, match="explicit project-type"):
        bootstrap.create(root, project_type="general" if kind == "research" else "research", layout=layout)


def adoption_payload():
    return {
        "role_mappings": {"Source": "src", "Deliverables": "reports"},
        "initial_canonical_registrations": [
            {
                "topic": "interface.v1",
                "path": "README.md",
                "section": "Interface",
                "status": "frozen",
                "verification": "src/test.py",
            }
        ],
        "initial_deliverable_registrations": [
            {
                "id": "summary.v1",
                "path": "reports/summary.txt",
                "kind": "report",
                "audience": "reviewers",
                "producer": "src/export.py",
            }
        ],
    }


@pytest.fixture
def ordinary(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "reports").mkdir()
    for name, text in {
        "project.md": "User notes must survive\n",
        "README.md": "# Overview\n## Interface\nExisting contract\n",
        "src/test.py": "assert True\n",
        "src/export.py": "print('summary')\n",
        "reports/summary.txt": "Readable summary\n",
    }.items():
        (tmp_path / name).write_text(text)
    return tmp_path


def user_files(root):
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in root.rglob("*")
        if p.is_file() and not p.name.startswith(".oppencouncil") and ".oppen-project-steward" not in p.parts
    }


def test_check_is_read_only_and_adopt_retains_existing_files(ordinary):
    before = user_files(ordinary)
    assert bootstrap.inspect(ordinary)["state"] == "ADOPTION_REQUIRED"
    assert not (ordinary / tx.LOCK).exists()
    with pytest.raises(FreezeError, match="requires adopt"):
        bootstrap.create(ordinary, project_type="general")
    result = bootstrap.create(ordinary, project_type="general", payload=adoption_payload(), adoption=True)
    assert all(path.startswith(".oppen-project-steward/") for path in result["changed_paths"])
    assert before == user_files(ordinary)
    registry = Registry(ordinary)
    assert read_table(registry.text, "canonical")[0]["Topic"] == "interface.v1"
    assert not Outputs(ordinary).check()["errors"]
    assert not (ordinary / "Data").exists()


@pytest.mark.parametrize("phase", ["directories", "written", "verified"])
def test_init_fault_removes_new_directories_and_anchor(tmp_path, phase):
    def fail(event, path):
        if event == phase:
            raise RuntimeError("injected creation failure")

    with pytest.raises(RuntimeError, match="injected"):
        bootstrap.create(tmp_path, project_type="research", fault=fail)
    assert {p.name for p in tmp_path.iterdir()} <= {tx.LOCK}
    bootstrap.create(tmp_path, project_type="research")
    Project(tmp_path).baseline_state()


def test_adoption_failure_keeps_user_files(ordinary):
    before = user_files(ordinary)

    def fail(event, path):
        if event == "written":
            raise RuntimeError("injected adoption failure")

    with pytest.raises(RuntimeError):
        bootstrap.create(
            ordinary, project_type="general", payload=adoption_payload(), adoption=True, fault=fail
        )
    assert not (ordinary / ".oppen-project-steward").exists()
    assert before == user_files(ordinary)


@pytest.mark.parametrize("change", ["duplicate-role", "missing-verification", "overlap", "owner", "path"])
def test_bad_adoption_cannot_partially_claim_project(ordinary, change):
    payload = adoption_payload()
    if change == "duplicate-role":
        payload["role_mappings"]["source"] = "src"
    elif change == "missing-verification":
        payload["initial_canonical_registrations"][0]["verification"] = "src/missing.py"
    elif change == "overlap":
        payload["initial_deliverable_registrations"].append(
            copy.deepcopy(payload["initial_deliverable_registrations"][0])
        )
    elif change == "owner":
        payload["initial_canonical_registrations"][0]["section"] = "Absent"
    else:
        payload["role_mappings"]["Source"] = "../outside"
    with pytest.raises(FreezeError):
        bootstrap.create(ordinary, project_type="general", adoption=True, payload=payload)
    assert not (ordinary / ".oppen-project-steward").exists()


def test_research_adoption_legacy_output_remains_warning_only(ordinary):
    (ordinary / "reports/summary.txt").rename(ordinary / "reports/summary.md")
    payload = adoption_payload()
    payload["role_mappings"] = {"Scripts": "src", "Results": "reports"}
    payload["initial_deliverable_registrations"][0].update(path="reports/summary.md", audience="publication")
    bootstrap.create(ordinary, project_type="research", layout="namespace", payload=payload, adoption=True)
    check = Outputs(ordinary).check()
    assert not check["errors"] and len(check["warnings"]) == 1
    result = Outputs(ordinary).register(payload["initial_deliverable_registrations"][0])
    assert result["legacy_without_specification"]


def test_unrecognized_namespace_and_existing_root_document_are_not_overwritten(ordinary):
    with pytest.raises(FreezeError, match="user-owned"):
        bootstrap.create(ordinary, project_type="research", adoption=True)
    namespace = ordinary / ".oppen-project-steward"
    namespace.mkdir()
    (namespace / "notes.md").write_text("user-owned")
    assert bootstrap.inspect(ordinary)["state"] == "ADOPTION_BLOCKED"
    with pytest.raises(FreezeError, match="ADOPTION_BLOCKED"):
        bootstrap.create(ordinary, project_type="general", adoption=True)


def cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "oppencouncil.governance", *map(str, args)], capture_output=True, text=True
    )


def test_actual_cli_check_adopt_and_registration(ordinary, tmp_path_factory):
    payload = tmp_path_factory.mktemp("inputs") / "adopt.json"
    payload.write_text(json.dumps(adoption_payload()))
    run = cli("adopt", ordinary, "--check", "--project-type", "general", "--input", payload)
    assert run.returncode == 0, run.stderr
    assert len(json.loads(run.stdout)["write_paths"]) == 2
    assert not (ordinary / ".oppen-project-steward").exists()
    assert not (ordinary / tx.LOCK).exists()
    run = cli("adopt", ordinary, "--apply", "--project-type", "general", "--input", payload)
    assert run.returncode == 0, run.stderr
    run = cli(
        "deliverable",
        ordinary,
        "--id",
        "summary.v1",
        "--path",
        "reports/summary.txt",
        "--kind",
        "report",
        "--audience",
        "reviewers",
        "--producer",
        "src/export.py",
    )
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout)["changed_paths"] == []
    assert payload.exists()


def test_actual_cli_init_and_data_registration(tmp_path):
    root = tmp_path / "new"
    run = cli("init", root, "--project-type", "research", "--layout", "namespace")
    assert run.returncode == 0, run.stderr
    (root / "Data/raw/input.csv").write_text("x\n1\n")
    payload = tmp_path / "data.json"
    payload.write_text(
        json.dumps(
            {"path": "Data/raw/input.csv", "kind": "raw", "source": "Synthetic fixture", "version": "1"}
        )
    )
    run = cli("data", "register", root, "--input", payload)
    assert run.returncode == 0, run.stderr
    run = cli("data", "register", root, "--input", payload)
    assert run.returncode == 0 and json.loads(run.stdout)["changed_paths"] == [], run.stderr
    assert cli("result", root, "--id", "incomplete").returncode == 2
