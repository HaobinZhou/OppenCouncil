"""Real current-tree replacement, evidence drift and immutable formal/history records."""

import copy
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from test_workflow_v5 import approve, evidence_records, research_change

from oppencouncil import audits, bootstrap, canonical, project_checks
from oppencouncil.project import Project
from oppencouncil.project_registry import Registry, read_table
from oppencouncil.store import FreezeError, FreezeStore
from oppencouncil.workstore import WorkStore


@pytest.fixture(
    params=[("research", "root"), ("research", "namespace"), ("general", "root"), ("general", "namespace")]
)
def project(tmp_path, request):
    root = tmp_path / "project"
    root.mkdir()
    kind, layout = request.param
    bootstrap.create(root, project_type=kind, layout=layout)
    (root / "source.py").write_text("def identity(value):\n    return value\n")
    (root / "test_source.py").write_text("from source import identity\nassert identity(3) == 3\n")
    subprocess.run([sys.executable, str(root / "test_source.py")], check=True)
    return root


def snapshot(root):
    # Native Windows enumeration can briefly expose inaccessible, pending-delete
    # .tmp names after an atomic replace. Retry the whole snapshot; never omit
    # files from the comparison or suppress a persistent access failure.
    for attempt in range(6):
        try:
            return {
                p.relative_to(root).as_posix(): p.read_bytes()
                for p in root.rglob("*")
                if p.is_file() and p.name not in {".lock", ".oppencouncil-project.lock"}
            }
        except OSError as exc:
            if os.name != "nt" or getattr(exc, "winerror", None) not in {2, 3, 5, 32} or attempt == 5:
                raise
            time.sleep(0.02 * 2**attempt)


def completion(root):
    if Project(root).project_type == "research":
        return {
            "summary": "Identity must preserve values.",
            "checks": ["test_source.py"],
            "verification": "Ran test_source.py with exit 0 on this synthetic fixture.",
            "limits": "Only the specified identity contract was checked.",
        }
    return {
        "purpose_and_risk": "Identity must preserve values.",
        "contract": "Input equals output.",
        "edge_cases_and_verification": "test_source.py ran with exit 0.",
        "known_limits": "Only the specified identity contract was checked.",
    }


def test_contract_creation_completion_drift_and_idempotence(project):
    args = {"source": "source.py", "risk_reason": "A wrong transformation changes results."}
    result = audits.contract(project, "transform", **args)
    assert result["status"] == "draft"
    assert any("incomplete" in item["reason"] for item in project_checks.validate(project)["errors"])
    audits.contract(project, "transform", payload=completion(project))
    assert audits.validate(project) == {"errors": []}
    before = snapshot(project)
    assert not audits.contract(project, "transform", payload=completion(project))["changed_paths"]
    assert not audits.contract(project, "transform", **args)["changed_paths"]
    assert snapshot(project) == before
    (project / "source.py").write_text("def identity(value):\n    return value + 1\n")
    assert "stale" in audits.validate(project)["errors"][0]["reason"]
    with pytest.raises(FreezeError, match="different source"):
        audits.contract(project, "transform", source="test_source.py", risk_reason=args["risk_reason"])


def test_research_check_file_changes_invalidate_review(project):
    if Project(project).project_type != "research":
        return
    audits.contract(project, "test", source="source.py", risk_reason="Changes results")
    bad = {**completion(project), "checks": ["explanation.md"]}
    (project / "explanation.md").write_text("This is a passing check, trust me")
    with pytest.raises(FreezeError, match="executable"):
        audits.contract(project, "test", payload=bad)
    audits.contract(project, "test", payload=completion(project))
    (project / "test_source.py").write_text("assert False\n")
    assert "stale for its check" in audits.validate(project)["errors"][0]["reason"]


def test_legacy_audits_remain_unchanged(project):
    registry = Registry(project)
    area = registry.roles()["audit"]
    legacy = {
        area + "/Contracts/audit_transform.md": b"Old audit: source hash then was different.\n",
        area + "/Functions/old.Rmd": b"Old function audit remains readable.\n",
    }
    registry.commit(writes=legacy)
    audits.contract(project, "transform", source="source.py", risk_reason="Changes results")
    audits.contract(project, "transform", payload=completion(project))
    for name, original in legacy.items():
        assert (project / name).read_bytes() == original
    assert not project_checks.validate(project)["errors"]


def staging(root, name="staging"):
    path = root.parent / name
    path.mkdir()
    (path / "nested").mkdir()
    (path / "nested/evidence.bin").write_bytes(os.urandom(2 * 1024 * 1024))
    (path / "empty").mkdir()
    (path / "run.json").write_text('{"passed":true}\n')
    return path


def test_promote_replaces_entire_tree_and_preserves_external_input(project):
    source = staging(project)
    original = snapshot(source)
    result = audits.promote(project, "model", source)
    current = project / result["current"]
    assert audits.verify_run(Registry(project), "model")["files"] == 2
    assert snapshot(source) == original
    before = snapshot(project)
    assert not audits.promote(project, "model", source)["changed_paths"]
    assert snapshot(project) == before
    (source / "nested/evidence.bin").unlink()
    (source / "nested").rmdir()
    (source / "empty").rmdir()
    (source / "replacement.csv").write_text("n\n10\n")
    audits.promote(project, "model", source)
    assert not (current / "nested").exists() and not (current / "empty").exists()
    assert (current / "replacement.csv").read_bytes() == (source / "replacement.csv").read_bytes()
    assert not project_checks.validate(project)["errors"]
    (current / "replacement.csv").write_text("n\n11\n")
    assert any("file changed" in error["reason"] for error in project_checks.validate(project)["errors"])


def test_run_failure_restores_old_files_directories_and_baseline(project):
    source = staging(project)
    audits.promote(project, "model", source)
    before = snapshot(project)
    source2 = project.parent / "new-staging"
    source2.mkdir()
    (source2 / "fresh.txt").write_text("new evidence")

    def fail(phase, _path):
        if phase == "verified":
            raise RuntimeError("injected failure")

    with pytest.raises(RuntimeError, match="injected"):
        audits.promote(project, "model", source2, fault=fail)
    assert snapshot(project) == before
    assert (project / Registry(project).roles()["audit"] / "Runs/model/current/empty").is_dir()
    assert not audits.validate(project)["errors"]


def test_run_process_death_rolls_back_on_startup(project):
    source = staging(project)
    audits.promote(project, "model", source)
    before = snapshot(project)
    (source / "extra.txt").write_text("new evidence")
    code = """
import os, sys
from oppencouncil import audits
def die(phase, _path):
    if phase == 'verified': os._exit(73)
audits.promote(sys.argv[1], 'model', sys.argv[2], fault=die)
"""
    result = subprocess.run([sys.executable, "-c", code, str(project), str(source)])
    assert result.returncode == 73
    Project(project).baseline_state()
    assert snapshot(project) == before
    assert not audits.validate(project)["errors"]


def test_changed_external_staging_rolls_back(project):
    source = staging(project)
    before = snapshot(project)

    def change(phase, _path):
        if phase == "prepared":
            (source / "run.json").write_text("changed during promotion")

    with pytest.raises(FreezeError, match="changed"):
        audits.promote(project, "model", source, fault=change)
    assert snapshot(project) == before


def test_audit_cannot_read_internal_staging_or_symlinks(project):
    with pytest.raises(FreezeError, match="external"):
        audits.promote(project, "model", project)
    source = staging(project)
    (source / "linked").symlink_to(project / "source.py")
    with pytest.raises(FreezeError, match="linked"):
        audits.promote(project, "model", source)


def test_canonical_owner_rules_and_read_dependencies(project):
    (project / "contract.md").write_text("# Contract\n\nStatus: frozen\n\nCurrent meaning.\n")
    args = {
        "topic": "contract",
        "path": "contract.md",
        "verification": "test_source.py",
        "section": "Contract",
    }
    if Project(project).project_type == "research":
        with pytest.raises(FreezeError, match="New research definitions"):
            canonical.register(project, **args)
        return
    canonical.register(project, **args)
    assert not canonical.register(project, **args)["changed_paths"]
    assert not project_checks.validate(project)["errors"]
    with pytest.raises(FreezeError, match="another topic"):
        canonical.register(project, **{**args, "topic": "second"})
    (project / "replacement.md").write_text("Status: frozen\nNew owner.\n")
    move = {**args, "path": "replacement.md", "section": None}
    with pytest.raises(FreezeError, match="--replace"):
        canonical.register(project, **move)
    canonical.register(project, **move, replace=True)
    assert read_table(Registry(project).text, "canonical")[0]["Canonical path"] == "replacement.md"


def test_council_test_registration_preserves_formal_versions(project):
    service = WorkStore(FreezeStore(project))
    service.add([{"title": "Definition", "why": "Scope"}], request_id="new", actor="codex")
    change = research_change()
    service.commit_work(
        {"read_set": {"F-000001": 1}, "changes": [change], "evidence": evidence_records()},
        request_id="candidate",
    )
    args = {
        "topic": "definition",
        "path": "Freeze/questions/F-000001.json",
        "section": "definition",
        "verification": "test_source.py",
    }
    with pytest.raises(FreezeError, match="human-confirmed"):
        canonical.register(project, **args)
    approve(service)
    original = copy.deepcopy(service.store.read_question("F-000001")["definition"])
    canonical.register(project, **args)
    question = service.store.read_question("F-000001")
    assert question["definition"] == original
    assert question["verification_tests"] == [{"path": "test_source.py"}]
    assert read_table(Registry(project).text, "canonical") == []
    before = snapshot(project)
    assert not canonical.register(project, **args)["changed_paths"]
    assert snapshot(project) == before


def test_real_cli_completion_and_promotion(project):
    payload = project.parent / "payload.json"
    payload.write_text(json.dumps(completion(project)))
    source = staging(project)
    commands = [
        [
            "contract-audit",
            str(project),
            "--topic",
            "transform",
            "--source",
            "source.py",
            "--risk-reason",
            "Changes results",
        ],
        ["contract-audit", str(project), "--topic", "transform", "--input", str(payload)],
        ["audit", "promote", str(project), "--stage", "model", "--input", str(source)],
    ]
    for command in commands:
        result = subprocess.run(
            [sys.executable, "-m", "oppencouncil.governance", *command], capture_output=True, text=True
        )
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["changed_paths"]
    assert payload.is_file()
    assert not project_checks.validate(project)["errors"]


def test_recovery_preserves_current_and_copies_residue_before_removal(project, monkeypatch):
    source = staging(project)
    result = audits.promote(project, "model", source)
    current = project / result["current"]
    original = snapshot(current)
    failed = current.parent / "failed-attempt"
    failed.mkdir()
    (failed / "empty").mkdir()
    (failed / "evidence.bin").write_bytes(os.urandom(2 * 1024 * 1024))
    failed_bytes = (failed / "evidence.bin").read_bytes()
    mkdtemp = audits.tempfile.mkdtemp
    monkeypatch.setattr(audits.tempfile, "mkdtemp", lambda **kw: mkdtemp(dir=project.parent, **kw))
    with pytest.raises(FreezeError, match="legacy residue"):
        audits.promote(project, "model", source)
    result = audits.recover(project, "model")
    recovered = Path(result["recovery_path"])
    assert (recovered / "failed-attempt/evidence.bin").read_bytes() == failed_bytes
    assert (recovered / "failed-attempt/empty").is_dir()
    assert json.loads((recovered / "recovery.json").read_text())["files"]
    assert not failed.exists() and snapshot(current) == original
    assert not audits.recover(project, "model")["changed_paths"]
    assert not project_checks.validate(project)["errors"]


def test_recovery_refuses_ambiguous_or_registered_artifacts(project, monkeypatch):
    result = audits.promote(project, "model", staging(project))
    area = (project / result["current"]).parent
    (area / "important.txt").write_text("Unclassified user-owned data")
    before = snapshot(project)
    with pytest.raises(FreezeError, match="unclassified"):
        audits.recover(project, "model")
    assert snapshot(project) == before
    (area / "important.txt").unlink()
    failed = area / "failed"
    failed.mkdir()
    (failed / "check.py").write_text("assert True\n")
    audits.contract(
        project,
        "protected",
        source=(failed / "check.py").relative_to(project).as_posix(),
        risk_reason="Registered source cannot be swept away",
    )
    with pytest.raises(FreezeError, match="registered owner"):
        audits.recover(project, "model")
    assert (failed / "check.py").is_file()


def test_recovery_failure_keeps_external_copy_and_restores_source(project, monkeypatch):
    result = audits.promote(project, "model", staging(project))
    failed = (project / result["current"]).parent / "staging-old"
    failed.mkdir()
    (failed / "result.txt").write_text("Original failed-run trace")
    before = snapshot(project)
    mkdtemp = audits.tempfile.mkdtemp
    monkeypatch.setattr(audits.tempfile, "mkdtemp", lambda **kw: mkdtemp(dir=project.parent, **kw))

    def fail(phase, _path):
        if phase == "verified":
            raise RuntimeError("interrupted")

    with pytest.raises(RuntimeError, match="interrupted"):
        audits.recover(project, "model", fault=fail)
    assert snapshot(project) == before
    copies = list(project.parent.glob("oppencouncil-audit-recovery-*/staging-old/result.txt"))
    assert len(copies) == 1 and copies[0].read_bytes() == (failed / "result.txt").read_bytes()
