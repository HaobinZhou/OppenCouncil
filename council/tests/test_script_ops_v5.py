"""Execute reordered producers and verify path updates, history and crash recovery."""

import copy
import json
import os
import stat
import subprocess
import sys

import pytest
from test_memory_v5 import payload as memory_payload
from test_workflow_v5 import approve, prepare, save

from oppencouncil import bootstrap, script_ops
from oppencouncil import project_transaction as tx
from oppencouncil.memory import Memory
from oppencouncil.outputs import Outputs
from oppencouncil.project import Project
from oppencouncil.project_registry import Registry, read_table, write_table
from oppencouncil.store import FreezeError, FreezeStore
from oppencouncil.workstore import WorkStore


@pytest.fixture(params=["root", "namespace"])
def project(tmp_path, request):
    for area in ("R/functions", "R/config/empty", "Data/raw", "Data/derived", "Results", "Audit/Functions"):
        (tmp_path / area).mkdir(parents=True, exist_ok=True)
    (tmp_path / "Data/raw/input.csv").write_text("x\n2\n")
    (tmp_path / "R/functions/helpers.py").write_text("factor = 3\n")
    (tmp_path / "R/clean.py").write_text(
        "from pathlib import Path\nimport runpy\nR = 123\n"
        'factor = runpy.run_path("R/functions/helpers.py")["factor"]\n'
        'value = int(Path("Data/raw/input.csv").read_text().splitlines()[1]) * factor\n'
        'Path("Data/derived/clean.csv").write_text("x\\n" + str(value) + "\\n")\n'
    )
    (tmp_path / "R/report.py").write_text(
        "from pathlib import Path\n"
        'value = Path("Data/derived/clean.csv").read_text().splitlines()[1]\n'
        'Path("Results/estimate.csv").write_text("Estimate\\n" + value + "\\n")\n'
    )
    os.chmod(tmp_path / "R/clean.py", 0o755)
    (tmp_path / "Results/estimate.csv").write_text("Estimate\n6\n")
    (tmp_path / "Audit/Functions/audit_clean.Rmd").write_text("Historical source: R/clean.py\n")
    (tmp_path / "README.md").write_text("Run `R/clean.py` then `R/report.py`. Language R remains R.\n")
    bootstrap.create(
        tmp_path,
        project_type="research",
        layout=request.param,
        adoption=True,
        payload={
            "role_mappings": {"R": "R", "Data": "Data", "Results": "Results"},
            "initial_canonical_registrations": [],
            "initial_deliverable_registrations": [
                {
                    "id": "estimate",
                    "path": "Results/estimate.csv",
                    "kind": "table",
                    "audience": "publication",
                    "producer": "R/report.py",
                }
            ],
        },
    )
    service = WorkStore(FreezeStore(tmp_path))
    service.add(
        [{"title": "Analysis rule", "why": "Explicit observed scope"}], request_id="new", actor="codex"
    )
    prepare(service, "Historical definition mentions R/clean.py verbatim.")
    approve(service)
    save(
        service,
        {"verification_tests": [{"path": "R/clean.py", "scope": "data-import", "definition_version": 1}]},
    )
    registry = Registry(tmp_path)
    registry.text = write_table(
        registry.text,
        "canonical",
        ("Topic", "Canonical path", "Section", "Status", "Verification"),
        [
            {
                "Topic": "data-import",
                "Canonical path": "Freeze/questions/F-000001.json",
                "Section": "definition",
                "Status": "frozen",
                "Verification": "R/clean.py",
            }
        ],
    )
    registry.commit()
    Memory(tmp_path).add(memory_payload(before="Old execution used R/clean.py."))
    return tmp_path


def ordered():
    return {"order": ["R/clean.py", "R/report.py"], "start": 1, "step": 1}


def snapshot(root):
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in root.rglob("*")
        if p.is_file() and p.name not in {tx.LOCK, ".freeze.lock"}
    }


def test_renumber_updates_registration_verification_and_literal_references(project):
    before = snapshot(project)
    formal = copy.deepcopy(WorkStore(FreezeStore(project)).read("F-000001")["current"])
    plan = script_ops.check(project, "renumber", ordered())
    assert snapshot(project) == before
    assert plan.report["mapping"] == {"R/clean.py": "R/01_clean.py", "R/report.py": "R/02_report.py"}
    script_ops.apply(project, plan.public())
    assert not (project / "R/clean.py").exists()
    registry = Registry(project)
    assert registry.outputs()[0]["producer"] == "R/02_report.py"
    assert read_table(registry.text, "canonical")[0]["Verification"] == "R/01_clean.py"
    record = FreezeStore(project).read_question("F-000001")
    assert record["verification_tests"][0]["path"] == "R/01_clean.py"
    assert WorkStore(FreezeStore(project)).read("F-000001")["current"] == formal
    assert (
        project / "README.md"
    ).read_text() == "Run `R/01_clean.py` then `R/02_report.py`. Language R remains R.\n"
    for name, raw in before.items():
        if "/Memory/" in "/" + name or name.startswith("Audit/Functions/"):
            assert (project / name).read_bytes() == raw
    assert script_ops.apply(project, plan.public())["replayed"]
    assert not Outputs(project).check()["errors"]
    if os.name != "nt":
        assert stat.S_IMODE((project / "R/01_clean.py").stat().st_mode) == 0o755
    for path in ("R/01_clean.py", "R/02_report.py"):
        subprocess.run([sys.executable, str(project / path)], cwd=project, check=True)
    assert (project / "Results/estimate.csv").read_text() == "Estimate\n6\n"


def test_directory_rename_preserves_shared_files_and_executable_order(project):
    before = snapshot(project)
    plan = script_ops.check(project, "rename-directory", {"to": "Scripts"})
    script_ops.apply(project, plan.public())
    assert not (project / "R").exists()
    assert (project / "Scripts/config/empty").is_dir()
    assert Registry(project).roles()["scripts"] == "Scripts"
    code = (project / "Scripts/clean.py").read_text()
    assert 'run_path("Scripts/functions/helpers.py")' in code
    assert "R = 123" in code
    assert "Language R remains R." in (project / "README.md").read_text()
    assert (project / "Audit/Functions/audit_clean.Rmd").read_bytes() == before[
        "Audit/Functions/audit_clean.Rmd"
    ]
    for path in ("Scripts/clean.py", "Scripts/report.py"):
        subprocess.run([sys.executable, str(project / path)], cwd=project, check=True)
    assert not Outputs(project).check()["errors"]


@pytest.mark.parametrize("phase", ["written", "removed_directories", "verified"])
def test_directory_rename_failure_restores_original_tree(project, phase):
    before = snapshot(project)
    plan = script_ops.check(project, "rename-directory", {"to": "Scripts"})

    def fail(event, path):
        if event == phase:
            raise RuntimeError("injected relocation failure")

    with pytest.raises(RuntimeError, match="injected"):
        script_ops.apply(project, plan.public(), fault=fail)
    assert snapshot(project) == before
    assert not (project / "Scripts").exists()
    assert (project / "R/config/empty").is_dir()
    Project(project).baseline_state()


def test_real_crash_after_directory_removal_recovers_on_startup(project, tmp_path_factory):
    before = snapshot(project)
    payload = tmp_path_factory.mktemp("plans") / "plan.json"
    payload.write_text(json.dumps(script_ops.check(project, "rename-directory", {"to": "Scripts"}).public()))
    code = """
import json, os, sys
from pathlib import Path
from oppencouncil import script_ops
def crash(phase, path):
    if phase == "removed_directories": os._exit(73)
script_ops.apply(sys.argv[1], json.loads(Path(sys.argv[2]).read_text()), fault=crash)
"""
    run = subprocess.run(
        [sys.executable, "-c", code, str(project), str(payload)], capture_output=True, text=True
    )
    assert run.returncode == 73, run.stderr
    assert not (project / "R").exists()
    Project(project)
    assert snapshot(project) == before
    assert not (project / "Scripts").exists()


@pytest.mark.parametrize("change", ["new-script", "new-reference", "file-content", "plan"])
def test_changed_plan_inputs_are_rejected(project, change):
    plan = script_ops.check(project, "renumber", ordered()).public()
    if change == "new-script":
        (project / "R/extra.py").write_text("print(3)\n")
    elif change == "new-reference":
        (project / "runner.py").write_text('import runpy; runpy.run_path("R/clean.py")\n')
    elif change == "file-content":
        with (project / "R/clean.py").open("a") as handle:
            handle.write("# Independent edit\n")
    else:
        plan["mapping"]["R/clean.py"] = "R/99_clean.py"
    before = snapshot(project)
    with pytest.raises(FreezeError):
        script_ops.apply(project, plan)
    assert snapshot(project) == before


def test_numbering_interval_and_shared_files(project):
    plan = script_ops.check(project, "renumber", {**ordered(), "step": 10})
    assert plan.report["mapping"]["R/report.py"] == "R/11_report.py"
    assert "R/functions/helpers.py" not in plan.report["mapping"]
    with pytest.raises(FreezeError, match="two digits"):
        script_ops.check(project, "renumber", {**ordered(), "start": 99})
    with pytest.raises(FreezeError, match="Shared"):
        script_ops.check(project, "renumber", {"order": [*ordered()["order"], "R/functions/helpers.py"]})


@pytest.mark.parametrize("change", ["registry", "script"])
def test_concurrent_change_during_read_only_planning_is_not_overwritten(project, monkeypatch, change):
    original = script_ops.Planner.reference_files

    def concurrent(planner, area):
        paths = original(planner, area)
        if change == "registry":
            registry = Registry(project)
            registry.metadata["independent_update"] = "Keep this newer registration"
            registry.commit()
        else:
            with (project / "R/clean.py").open("a") as handle:
                handle.write("# Independently saved change\n")
        return paths

    monkeypatch.setattr(script_ops.Planner, "reference_files", concurrent)
    with pytest.raises(FreezeError, match="changed while planning"):
        script_ops.check(project, "renumber", ordered())
    assert (project / "R/clean.py").exists()
    if change == "registry":
        assert Registry(project).metadata["independent_update"] == "Keep this newer registration"
    else:
        assert "Independently saved" in (project / "R/clean.py").read_text()
    Project(project).baseline_state()
