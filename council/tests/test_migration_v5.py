"""Migrate actual legacy helper fixtures without rewriting project history."""

import copy
import json
import subprocess
import sys

import pytest
from test_memory_v5 import legacy_module, payload

from oppencouncil import migration, project_checks
from oppencouncil import project_transaction as tx
from oppencouncil.memory import Memory
from oppencouncil.project import Project
from oppencouncil.project_registry import Registry
from oppencouncil.store import FreezeError, FreezeStore
from oppencouncil.workstore import WorkStore

CAPABILITIES = {"council": {"governance_versions": [3, 4, 5]}, "skill": {"governance_versions": [3, 4, 5]}}


@pytest.fixture(params=[("stepwise", 3), ("stepwise", 4), ("steward", 3), ("steward", 4)])
def legacy(tmp_path, request):
    kind, version = request.param
    root = tmp_path / "项目"
    root.mkdir()
    helper = legacy_module("stepwise_r_project" if kind == "stepwise" else "oppen_project_steward")
    helper.ensure_v3_project(root, create=True)
    registry = root / ("project.md" if kind == "stepwise" else ".oppen-project-steward/registry.md")
    control = registry.parent
    attention = {
        "title": "Investigate timing",
        "blocking": True,
        "observation": "Two observed timelines differ.",
        "evidence": "Audit records the difference.",
        "why_it_matters": "Interpretation may change.",
        "why_no_action_was_taken": "The issue is outside the completed task.",
        "human_decision_needed": "Determine the applicable timing rule.",
    }
    if kind == "stepwise":
        value = payload()
        value["scientific_or_technical_rationale"] = value.pop("why")
        helper.add_decision_memory(root, value)
        helper.add_attention(root, attention)
        (root / "R/analysis.R").write_text("print('existing analysis')\n")
        (root / "Results/table.csv").write_text("Label,Estimate\nExample,1.0\n")
        helper.register_result(
            root, "table-one", "Results/table.csv", "table", "publication", "R/analysis.R", replace=False
        )
    else:
        source = tmp_path / "memory.json"
        value = payload(related_topics=[], supersedes=[], invalidates=[])
        value.pop("basis")
        source.write_text(json.dumps(value))
        helper.add_memory(root, source)
        source.write_text(json.dumps(attention))
        helper.raise_attention(root, source)
    store = FreezeStore(root)
    store.add_questions(
        [
            {"title": "Effective rule", "why": "Existing authority"},
            {"title": "Pending revision", "why": "Existing discussion"},
        ],
        request_id="old-create",
    )
    for qid in ("F-000001", "F-000002"):
        q = store.read_question(qid)
        store.change(
            qid,
            "definition_draft",
            "Complete wording " + qid,
            expected_revision=q["revision"],
            request_id="draft-" + qid,
            actor="codex",
        )
    q = store.read_question("F-000001")
    store.change(
        q["id"],
        "definition_approve",
        q["definition"]["draft"]["approval_token"],
        expected_revision=q["revision"],
        request_id="confirm",
        actor="user",
    )
    q = store.read_question("F-000002")
    store.change(
        q["id"],
        "comment",
        "An unresolved human opinion",
        expected_revision=q["revision"],
        request_id="last-human",
        actor="user",
    )
    store.change_group(
        None,
        "create",
        {"title": "Review group", "purpose": "Related decision", "member_ids": ["F-000002"], "options": []},
        expected_revision=0,
        request_id="old-group",
        actor="codex",
    )
    if version == 3:
        registry.write_text(registry.read_text().replace(":v4 -->", ":v3 -->"))
        if kind == "steward":
            (control / ".managed-state.json").write_text(
                helper.render_managed_state_for_namespace(control, 4)
            )
    return root, kind, store.snapshot()


def files(root):
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in root.rglob("*")
        if p.is_file() and p.name not in {tx.LOCK, ".lock"}
    }


def test_check_is_read_only_and_apply_preserves_history_and_registration(legacy):
    root, kind, old = legacy
    before = files(root)
    plan = migration.check(root, CAPABILITIES)
    assert files(root) == before
    assert plan.report["blockers"] == []
    assert plan.report["project_type"] == ("research" if kind == "stepwise" else "general")
    migration.apply(root, plan.public(), CAPABILITIES)
    assert migration.apply(root, plan.public(), CAPABILITIES)["replayed"]
    assert not (root / tx.STAGING).exists()
    for path, raw in before.items():
        if "/Memory/" in "/" + path or "/Attention/entries/" in "/" + path:
            assert (root / path).read_bytes() == raw
    service = WorkStore(FreezeStore(root))
    snapshot = service.store.snapshot()
    assert snapshot["questions"][0]["definition"] == old["questions"][0]["definition"]
    assert snapshot["questions"][1]["definition"] == old["questions"][1]["definition"]
    assert snapshot["questions"][1]["messages"] == old["questions"][1]["messages"]
    assert service.read("F-000001")["work"]["phase"] == "closed"
    assert service.read("F-000002")["human_pending"]
    investigation = service.read("I-000001")
    assert investigation["title"] == "Investigate timing"
    assert investigation["work"]["blockers"] == ["Determine the applicable timing rule."]
    assert investigation["work"]["phase"] != "closed"
    assert len(service.store.snapshot()["questions"]) == len(old["questions"])
    assert Memory(root).read("M-0001")["why"] == payload()["why"]
    if kind == "stepwise":
        assert {w["kind"] for w in plan.report["warnings"]} == {
            "unnumbered_script",
            "legacy_output_without_specification",
        }
        assert (root / "R/analysis.R").read_bytes() == before["R/analysis.R"]
        assert (root / "Results/table.csv").read_bytes() == before["Results/table.csv"]
    repeated = migration.check(root, CAPABILITIES)
    assert repeated.writes == {}
    assert migration.apply(root, repeated.public(), CAPABILITIES)["changed_paths"] == []
    Project(root).baseline_state()


def test_changed_input_or_capability_invalidates_checked_plan(legacy):
    root, _, _ = legacy
    plan = migration.check(root, CAPABILITIES).public()
    changed = copy.deepcopy(CAPABILITIES)
    changed["mcp"] = {"required": True, "governance_versions": [3, 4]}
    assert migration.check(root, changed).report["blockers"]
    before = files(root)
    with pytest.raises(FreezeError, match="changed"):
        migration.apply(root, plan, changed)
    assert files(root) == before
    path = root / "Freeze/questions/F-000002.json"
    value = json.loads(path.read_bytes())
    value["title"] = "A concurrent edit"
    path.write_text(json.dumps(value))
    with pytest.raises(FreezeError, match="changed"):
        migration.apply(root, plan, CAPABILITIES)
    assert json.loads(path.read_bytes())["title"] == "A concurrent edit"


def test_nested_legacy_scripts_are_reported_without_renaming_or_new_file_errors(legacy):
    root, kind, _ = legacy
    if kind != "stepwise":
        pytest.skip("Legacy analysis numbering applies to research projects")
    scripts = {
        "R/operations/formal_control.py": "print('existing controller')\n",
        "R/reporting/refresh_current_delivery.R": "print('existing report')\n",
        "R/reporting/verify_kidney_publication.R": "stopifnot(TRUE)\n",
        "R/functions/shared.R": "shared <- function(x) x\n",
    }
    for name, text in scripts.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    plan = migration.check(root, CAPABILITIES)
    assert plan.report["blockers"] == []
    expected = {"R/analysis.R", *list(scripts)[:3]}
    assert {w["path"] for w in plan.report["warnings"] if w["kind"] == "unnumbered_script"} == expected
    migration.apply(root, plan.public(), CAPABILITIES)
    assert set(Registry(root).metadata["migration"]["legacy_unnumbered_scripts"]) == expected
    for name, text in scripts.items():
        assert (root / name).read_text(encoding="utf-8") == text
    checks = project_checks.Checks(root)
    checks.scripts()
    assert checks.errors == []
    assert {w["path"] for w in checks.warnings} == expected
    (root / "R/reporting/new_report.R").write_text("print('new')\n", encoding="utf-8")
    checks = project_checks.Checks(root)
    checks.scripts()
    assert [e["path"] for e in checks.errors] == ["R/reporting/new_report.R"]


def test_failed_application_rolls_back_all_target_files(legacy):
    root, _, _ = legacy
    plan = migration.check(root, CAPABILITIES)
    before = files(root)

    def failure(phase, _):
        if phase == "verified":
            raise RuntimeError("synthetic post-validation failure")

    with pytest.raises(RuntimeError, match="post-validation"):
        migration.apply(root, plan.public(), CAPABILITIES, fault=failure)
    assert files(root) == before


def test_interrupted_migration_is_recovered_by_council_startup(legacy, tmp_path):
    root, _, _ = legacy
    before = files(root)
    plan = migration.check(root, CAPABILITIES).public()
    source = tmp_path / "plan.json"
    source.write_text(json.dumps(plan))
    program = """
import json, os, sys
from pathlib import Path
from oppencouncil.migration import apply
def crash(phase, path):
    if phase == 'verified': os._exit(73)
plan=json.loads(Path(sys.argv[2]).read_text())
apply(sys.argv[1], plan, plan['capabilities'], fault=crash)
"""
    result = subprocess.run(
        [sys.executable, "-c", program, str(root), str(source)], capture_output=True, text=True, timeout=15
    )
    assert result.returncode == 73, result.stderr
    assert (root / tx.STAGING).is_dir()
    assert FreezeStore(root).v5 is False
    assert files(root) == before


def test_explicit_type_override_does_not_move_directories(legacy):
    root, kind, _ = legacy
    target = "general" if kind == "stepwise" else "research"
    plan = migration.check(root, CAPABILITIES, project_type=target)
    migration.apply(root, plan.public(), CAPABILITIES)
    project = Project(root)
    assert project.project_type == target
    assert project.namespaced == (kind == "steward")


def test_research_migration_reports_unclassified_outputs_data_and_experiments(legacy):
    root, kind, _ = legacy
    if kind != "stepwise":
        return
    (root / "Results/diagnostic.log").write_text("Existing diagnostic output")
    (root / "Data/unknown.csv").write_text("Value\n1\n")
    (root / "Releases").mkdir()
    (root / "Releases/submission.zip").write_bytes(b"legacy archive, do not reinterpret")
    (root / "Explore").mkdir()
    (root / "Explore/old-experiment").mkdir()
    (root / "Explore/_archive").mkdir()
    (root / "Explore/_archive/abandoned.txt").write_text("Do not inspect by default")
    (root / "unassigned.txt").write_text("Existing unexplained file")
    before = files(root)
    plan = migration.check(root, CAPABILITIES)
    paths = {item["kind"]: item["path"] for item in plan.report["warnings"]}
    assert paths["legacy_output_needs_review"] == "Results/diagnostic.log"
    assert paths["data_origin_requires_classification"] == "Data/unknown.csv"
    assert paths["legacy_release_requires_manifest"] == "Releases/submission.zip"
    assert paths["legacy_experiment_requires_status"] == "Explore/old-experiment"
    assert paths["unassigned_project_file"] == "unassigned.txt"
    assert all("_archive" not in item.get("path", "") for item in plan.report["warnings"])
    assert files(root) == before
    migration.apply(root, plan.public(), CAPABILITIES)
    for path, raw in before.items():
        if path.startswith(("Results/", "Data/", "Releases/", "Explore/")) or path == "unassigned.txt":
            assert (root / path).read_bytes() == raw


def test_legacy_data_links_are_reported_without_reading_or_changing_targets(legacy, tmp_path, monkeypatch):
    root, kind, _ = legacy
    external = tmp_path / "external"
    external.mkdir()
    private = external / "private.bin"
    private.write_bytes(b"not a migration input")
    data = root / "Data"
    data.mkdir(exist_ok=True)
    link = data / "historical-snapshot"
    try:
        link.symlink_to(external, target_is_directory=True)
    except OSError:
        pytest.skip("Symlinks unavailable")
    original_target = link.readlink()
    from pathlib import Path

    original_read = Path.read_bytes

    def read(path):
        assert path != private and external not in path.parents
        assert link not in path.parents
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", read)
    plan = migration.check(root, CAPABILITIES, project_type="research")
    assert not plan.report["blockers"]
    assert {"kind": "legacy_data_link_requires_review", "path": "Data/historical-snapshot"} in plan.report[
        "warnings"
    ]
    assert not any(name.startswith("Data/") for name in plan.report["read_set"])
    migration.apply(root, plan.public(), CAPABILITIES)
    assert link.is_symlink() and link.readlink() == original_target
    assert original_read(private) == b"not a migration input"
