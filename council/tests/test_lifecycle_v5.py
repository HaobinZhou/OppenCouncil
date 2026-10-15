"""Real experiment moves and streamed ZIP snapshots in both governed layouts."""

import json
import os
import subprocess
import sys
import zipfile

import pytest
from test_outputs_v5 import payload as output_payload
from test_workflow_v5 import approve, evidence_records, research_change

from oppencouncil import bootstrap, explore, project_checks, releases
from oppencouncil import project_transaction as tx
from oppencouncil.outputs import Outputs, fingerprint
from oppencouncil.project import Project
from oppencouncil.project_registry import Registry
from oppencouncil.store import FreezeError, FreezeStore
from oppencouncil.workstore import WorkStore


@pytest.fixture(params=["root", "namespace"])
def project(tmp_path, request):
    bootstrap.create(tmp_path, project_type="research", layout=request.param)
    return tmp_path


def perform(root, operation, payload):
    plan = explore.check(root, operation, payload).public()
    return explore.apply(root, plan), plan


def snapshot(root):
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in root.rglob("*")
        if p.is_file() and ".git" not in p.parts and p.name not in {tx.LOCK, ".freeze.lock"}
    }


def test_experiment_create_retain_archive_and_index(project):
    result, plan = perform(project, "create", {"slug": "model-check", "question": "Does another model fit?"})
    assert result["changed_paths"]
    assert explore.apply(project, plan)["replayed"]
    item = explore.index(project)[0]
    directory = project / item["path"]
    (directory / "trial.py").write_text("print('trial')\n")
    (directory / "result.csv").write_text("value\n1\n")
    perform(
        project,
        "update",
        {
            "id": item["id"],
            "status": "retained",
            "scripts": [item["path"] + "/trial.py"],
            "outputs": [item["path"] + "/result.csv"],
            "conclusion": "Keep for comparison",
        },
    )
    before = snapshot(project)
    plan = explore.check(
        project, "archive", {"id": item["id"], "conclusion": "Rejected after comparison"}
    ).public()
    assert snapshot(project) == before
    explore.apply(project, plan)
    archived = explore.index(project)[0]
    assert archived["status"] == "abandoned" and "_archive/" in archived["path"]
    assert not directory.exists()
    assert (project / archived["path"] / "result.csv").read_text() == "value\n1\n"
    assert "Rejected after comparison" in (project / "Explore/index.md").read_text()
    # An archive index read never decodes archived experimental files.
    (project / archived["path"] / "trial.py").write_bytes(b"\xff historical binary")
    assert explore.index(project)[0]["conclusion"] == "Rejected after comparison"
    assert not explore.validate(project)["errors"]
    with pytest.raises(FreezeError, match="immutable"):
        explore.check(project, "update", {"id": item["id"], "status": "in_progress"})


def test_archive_failure_restores_experiment_and_index(project):
    perform(project, "create", {"slug": "trial", "question": "Test a candidate"})
    item = explore.index(project)[0]
    (project / item["path"] / "large.bin").write_bytes(b"x" * 2 * 1024 * 1024)
    before = snapshot(project)
    plan = explore.check(project, "archive", {"id": item["id"], "conclusion": "Not useful"}).public()

    def fail(phase, path):
        if phase == "removed_directories":
            raise RuntimeError("archive interrupted")

    with pytest.raises(RuntimeError):
        explore.apply(project, plan, fault=fail)
    assert snapshot(project) == before
    Project(project).baseline_state()


def test_new_experiment_file_after_check_invalidates_archive_plan(project):
    perform(project, "create", {"slug": "trial", "question": "Compare models"})
    item = explore.index(project)[0]
    plan = explore.check(project, "archive", {"id": item["id"], "conclusion": "Discard"}).public()
    (project / item["path"] / "new.txt").write_text("An independent new result")
    with pytest.raises(FreezeError, match="changed"):
        explore.apply(project, plan)
    assert (project / item["path"] / "new.txt").exists()


@pytest.fixture
def formal(project):
    (project / "Scripts/functions").mkdir(exist_ok=True)
    (project / "Scripts/functions/format.py").write_text(
        'def render(value): return f"Estimate\\n{value}\\n"\n'
    )
    (project / "Scripts/01_import.py").write_text(
        "from pathlib import Path\n"
        'value=int(Path("Data/raw/input.csv").read_text().splitlines()[1])*2\n'
        'Path("Data/derived/analysis.csv").write_text("value\\n"+str(value)+"\\n")\n'
    )
    (project / "Scripts/02_analysis.py").write_text(
        "from pathlib import Path\nimport runpy\n"
        'value=Path("Data/derived/analysis.csv").read_text().splitlines()[1]\n'
        'render=runpy.run_path("Scripts/functions/format.py")["render"]\n'
        'Path("Results/estimates.csv").write_text(render(value))\n'
    )
    (project / "Data/raw/input.csv").write_text("x\n3\n")
    for path in ("Scripts/01_import.py", "Scripts/02_analysis.py"):
        subprocess.run([sys.executable, str(project / path)], cwd=project, check=True)
    (project / "Data/derived/extra.bin").write_bytes(b"Model output unrelated to a single table" * 100)
    demo = project / "Explore/demo"
    demo.mkdir()
    (demo / "example.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="10">'
        '<rect width="20" height="10" fill="blue"/></svg>'
    )
    service = WorkStore(FreezeStore(project))
    service.add(
        [{"title": "Output specification", "why": "Formal table"}], request_id="new-spec", actor="codex"
    )
    change = research_change()
    change.update(
        problem_type="output_specification",
        verification_tests=[{"path": "Scripts/02_analysis.py", "scope": "table", "definition_version": 1}],
    )
    change["definition"]["value"] = (
        "One Estimate column with an integer value.\n\n![Simulated example](Explore/demo/example.svg)"
    )
    service.commit_work(
        {"read_set": {"F-000001": 1}, "changes": [change], "evidence": evidence_records()},
        request_id="prepare",
    )
    approve(service)
    current = service.read("F-000001")["current"]
    Outputs(project).register(
        output_payload(
            producer="Scripts/02_analysis.py",
            specification={"question_id": "F-000001", "version": 1, "text_sha256": current["text_sha256"]},
        )
    )
    Outputs(project).register_data(
        {"path": "Data/raw/input.csv", "kind": "raw", "source": "Synthetic input", "version": "1"}
    )
    for name in ("analysis.csv", "extra.bin"):
        Outputs(project).register_data(
            {
                "path": "Data/derived/" + name,
                "kind": "derived",
                "producer": "Scripts/01_import.py",
                "version": "1",
            }
        )
    subprocess.run(["git", "init", "-q", str(project)], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(project),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "--allow-empty",
            "-qm",
            "Fixture code version",
        ],
        check=True,
    )
    assert not project_checks.validate(project)["errors"]
    return project


def release_payload():
    return {
        "purpose": "submission",
        "label": "Synthetic submission snapshot",
        "human_request": "Create a submission snapshot for this synthetic acceptance fixture",
        "environment": {"languages": {"python": sys.version}, "packages": {}},
        "article_numbers": {"estimates": "Table 2"},
    }


def test_snapshot_contains_all_derived_data_and_reproduces_results(formal, tmp_path_factory):
    before = snapshot(formal)
    plan = releases.check(formal, release_payload())
    assert snapshot(formal) == before
    result = releases.apply(formal, plan)
    entry = result["release"]
    archive = formal / entry["path"]
    assert archive.is_file() and archive.stat().st_size == entry["bytes"]
    if os.name != "nt":
        assert archive.stat().st_mode & 0o222 == 0
    assert releases.apply(formal, plan)["replayed"]
    with zipfile.ZipFile(archive) as bundle:
        names = set(bundle.namelist())
        assert {
            "Results/estimates.csv",
            "Scripts/functions/format.py",
            "Data/derived/analysis.csv",
            "Data/derived/extra.bin",
            "Freeze/questions/F-000001.json",
            "manifest.json",
        } <= names
        assert "Data/raw/input.csv" not in names
        assert any(name.startswith("Freeze/assets/") for name in names)
        manifest = json.loads(bundle.read("manifest.json"))
        assert manifest["raw_inputs"][0]["sha256"] == fingerprint(formal, "Data/raw/input.csv")["sha256"]
        assert manifest["outputs"][0]["article_number"] == "Table 2"
        assert manifest["git"]["commit"] and manifest["environment"]["languages"]["python"]
        restored = tmp_path_factory.mktemp("restored")
        bundle.extractall(restored)
    (restored / "Data/raw").mkdir(parents=True)
    (restored / "Data/raw/input.csv").write_bytes((formal / "Data/raw/input.csv").read_bytes())
    (restored / "Results/estimates.csv").unlink()
    for script in sorted((restored / "Scripts").glob("[0-9][0-9]_*.py")):
        subprocess.run([sys.executable, str(script)], cwd=restored, check=True)
    assert (restored / "Results/estimates.csv").read_bytes() == before["Results/estimates.csv"]
    assert not releases.validate(formal)["errors"]
    assert not project_checks.validate(formal)["errors"]
    assert "/Releases/*.zip" in (formal / ".gitignore").read_text()
    ledger = json.loads((formal / "Releases/index.json").read_text())
    assert ledger["releases"][0]["sha256"] == entry["sha256"]
    subprocess.run(["git", "-C", str(formal), "add", "--", "Releases/index.json"], check=True)
    tracked = subprocess.run(
        ["git", "-C", str(formal), "ls-files", "--error-unmatch", "Releases/index.json"], capture_output=True
    )
    assert tracked.returncode == 0
    second = releases.apply(formal, releases.check(formal, release_payload()))["release"]
    assert second["path"] != entry["path"]


def test_snapshot_needs_human_request_and_complete_classification(formal):
    payload = release_payload()
    del payload["human_request"]
    with pytest.raises(FreezeError, match="human snapshot request"):
        releases.check(formal, payload)
    (formal / "Data/derived/unclassified.bin").write_bytes(b"another generated object")
    with pytest.raises(FreezeError, match="Classify every Data file"):
        releases.check(formal, release_payload())
    assert not list((formal / "Releases").iterdir())


def test_release_tamper_and_loss_are_reported(formal):
    entry = releases.apply(formal, releases.check(formal, release_payload()))["release"]
    archive = formal / entry["path"]
    os.chmod(archive, 0o600)
    with archive.open("ab") as handle:
        handle.write(b"tampered")
    assert releases.validate(formal)["errors"]
    assert any("Release" in item["reason"] for item in project_checks.validate(formal)["errors"])
    archive.unlink()
    assert releases.validate(formal)["errors"]


def test_release_failure_removes_zip_and_restores_registration(formal):
    before = snapshot(formal)
    plan = releases.check(formal, release_payload())

    def fail(phase, path):
        if phase == "verified":
            raise RuntimeError("Interrupted release")

    with pytest.raises(RuntimeError):
        releases.apply(formal, plan, fault=fail)
    assert snapshot(formal) == before
    assert not Registry(formal).metadata.get("releases")


def test_promote_experiment_requires_confirmed_formal_outputs(formal):
    perform(formal, "create", {"slug": "table-design", "question": "Can this layout become formal?"})
    item = explore.index(formal)[0]
    with pytest.raises(FreezeError, match="not registered"):
        explore.check(formal, "promote", {"id": item["id"], "result_ids": ["missing"], "conclusion": "Ready"})
    perform(
        formal,
        "promote",
        {
            "id": item["id"],
            "result_ids": ["estimates"],
            "conclusion": "Confirmed layout and numbered producer",
        },
    )
    assert explore.index(formal)[0]["status"] == "promoted"
    assert explore.index(formal)[0]["result_ids"] == ["estimates"]


def test_large_release_streams_every_file_and_archive(formal, monkeypatch):
    large = formal / "Data/derived/extra.bin"
    with large.open("wb") as handle:
        for _ in range(17):
            handle.write(os.urandom(1024 * 1024))
    Outputs(formal).register_data(
        {
            "path": "Data/derived/extra.bin",
            "kind": "derived",
            "producer": "Scripts/01_import.py",
            "version": "2",
        }
    )
    original = tx.read_bytes

    def bounded(path):
        assert not path.exists() or path.stat().st_size <= 1024 * 1024, "Large files must be streamed"
        return original(path)

    monkeypatch.setattr(tx, "read_bytes", bounded)
    result = releases.apply(formal, releases.check(formal, release_payload()))
    assert result["release"]["bytes"] > 16 * 1024 * 1024
    assert not releases.validate(formal)["errors"]


def test_release_real_process_crash_recovers_read_only_zip(formal, tmp_path_factory):
    before = snapshot(formal)
    plan = tmp_path_factory.mktemp("plans") / "release.json"
    plan.write_text(json.dumps(releases.check(formal, release_payload())))
    code = """
import json, os, sys
from pathlib import Path
from oppencouncil import releases
def crash(phase, path):
    if phase == "verified": os._exit(73)
releases.apply(sys.argv[1], json.loads(Path(sys.argv[2]).read_text()), fault=crash)
"""
    run = subprocess.run([sys.executable, "-c", code, str(formal), str(plan)], capture_output=True, text=True)
    assert run.returncode == 73, run.stderr
    assert list((formal / "Releases").glob("*.zip"))
    Project(formal)
    assert snapshot(formal) == before


def test_release_rejects_changed_input_and_wrong_plan_domain(formal):
    plan = releases.check(formal, release_payload())
    (formal / "Data/raw/input.csv").write_text("x\n9\n")
    with pytest.raises(FreezeError, match="validation errors"):
        releases.apply(formal, plan)
    experiment = explore.check(
        formal, "create", {"slug": "one", "question": "A different operation"}
    ).public()
    with pytest.raises(FreezeError):
        releases.apply(formal, experiment)
    assert not list((formal / "Releases").glob("*.zip"))


def test_legacy_output_is_marked_in_release_manifest(formal):
    registry = Registry(formal)
    registry.metadata["output_details"]["estimates"].pop("specification")
    registry.metadata["adoption"] = {"legacy_outputs_without_specification": ["estimates"]}
    registry.commit()
    plan = releases.check(formal, release_payload())
    assert plan["manifest"]["outputs"][0]["legacy_without_specification"]
    assert releases.apply(formal, plan)["release"]["bytes"] > 0


def test_lifecycle_cli_plan_apply_verify(formal, tmp_path_factory):
    directory = tmp_path_factory.mktemp("cli")
    payload, plan = directory / "input.json", directory / "plan.json"
    payload.write_text(json.dumps(release_payload()))
    prefix = [sys.executable, "-m", "oppencouncil.governance"]
    for args in (
        ["release", "create", str(formal), "--check", "--input", str(payload), "--plan", str(plan)],
        ["release", "create", str(formal), "--apply", "--plan", str(plan)],
        ["release", "verify", str(formal)],
        ["explore", "index", str(formal)],
    ):
        run = subprocess.run([*prefix, *args], capture_output=True, text=True)
        assert run.returncode == 0, run.stderr
        json.loads(run.stdout)


def test_ignored_release_ledger_is_not_silently_left_out_of_git(formal):
    (formal / ".gitignore").write_text("/Releases/\n")
    with pytest.raises(FreezeError, match="eligible for Git"):
        releases.check(formal, release_payload())
    assert not list((formal / "Releases").iterdir())
