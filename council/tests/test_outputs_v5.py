"""Real registration, formal-version binding and preserved legacy behavior."""

import copy

import pytest
import test_memory_v5 as memory_fixtures
from test_workflow_v5 import approve, evidence_records, research_change

from oppencouncil import migration
from oppencouncil.outputs import Outputs, fingerprint
from oppencouncil.project import Project
from oppencouncil.project_registry import Registry, read_table, write_table
from oppencouncil.store import FreezeError, FreezeStore
from oppencouncil.workstore import WorkStore

project = memory_fixtures.project


@pytest.fixture
def outputs(project):
    root = project.root
    for area in ("Scripts", "Results", "Data/raw", "Data/derived"):
        (root / area).mkdir(parents=True, exist_ok=True)
    (root / "Scripts/01_analysis.py").write_text("print('analysis')\n")
    (root / "Results/estimates.csv").write_text("Treatment,Estimate\nA,1.0\n")
    registry = Registry(root)
    registry.text = write_table(
        registry.text,
        "roles",
        ("Role", "Path", "Purpose"),
        [
            {"Role": "Scripts", "Path": "Scripts", "Purpose": "Analysis"},
            {
                "Role": "Results" if project.project_type == "research" else "Deliverables",
                "Path": "Results",
                "Purpose": "Human outputs",
            },
            {"Role": "Data", "Path": "Data", "Purpose": "Inputs and generated data"},
        ],
    )
    registry.commit()
    return Outputs(root)


def payload(**extra):
    return {
        "id": "estimates",
        "path": "Results/estimates.csv",
        "kind": "table",
        "audience": "publication",
        "producer": "Scripts/01_analysis.py",
        **extra,
    }


def specification(outputs, confirm=True):
    service = WorkStore(FreezeStore(outputs.root))
    service.add(
        [{"title": "Table specification", "why": "Publication output"}], request_id="new-spec", actor="codex"
    )
    change = research_change()
    change["problem_type"] = "output_specification"
    service.commit_work(
        {"read_set": {"F-000001": 1}, "changes": [change], "evidence": evidence_records()},
        request_id="prepare-spec",
    )
    if confirm:
        approve(service)
    record = service.read("F-000001")
    current = record["current"] or record["candidate"]
    return {"question_id": "F-000001", "version": 1, "text_sha256": current["text_sha256"]}


def test_new_research_output_needs_confirmation_general_output_does_not(outputs):
    before = outputs.registry.project.registry.read_bytes()
    if outputs.research:
        with pytest.raises(FreezeError, match="confirmed specification"):
            outputs.register(payload())
        assert outputs.registry.project.registry.read_bytes() == before
        ref = specification(outputs)
        result = Outputs(outputs.root).register(payload(specification=ref))
    else:
        result = outputs.register(payload())
    assert result["changed_paths"]
    assert Outputs(outputs.root).check() == {"errors": [], "warnings": []}
    assert Project(outputs.root).baseline_state()


@pytest.mark.parametrize("unverified", ["abstract_only", "code_check"])
def test_output_specification_review_uses_verified_sources(outputs, unverified):
    if not outputs.research:
        return
    service = WorkStore(FreezeStore(outputs.root))
    service.add(
        [{"title": "Table format", "why": "Publication specification"}], request_id="new", actor="codex"
    )
    change = research_change()
    change["problem_type"] = "output_specification"
    with pytest.raises(FreezeError, match="original-text"):
        service.commit_work(
            {"read_set": {"F-000001": 1}, "changes": [change], "evidence": evidence_records(unverified)},
            request_id="bad-source",
        )
    assert service.read("F-000001")["candidate"] is None
    change["review_packet"].pop("applicability")
    with pytest.raises(FreezeError, match="applicability"):
        service.commit_work(
            {"read_set": {"F-000001": 1}, "changes": [change], "evidence": evidence_records()},
            request_id="missing-applicability",
        )
    assert service.read("F-000001")["candidate"] is None


@pytest.mark.parametrize("verification", ["code_check", "data_check", "measurement"])
def test_output_specification_accepts_directly_checked_project_facts(outputs, verification):
    if not outputs.research:
        return
    service = WorkStore(FreezeStore(outputs.root))
    service.add(
        [{"title": "Human table edit", "why": "Preserve the requested layout"}],
        request_id="new",
        actor="codex",
    )
    change = research_change()
    change["problem_type"] = "output_specification"
    records = evidence_records(verification)
    records[0]["value"]["source_type"] = "project_fact"
    service.commit_work(
        {"read_set": {"F-000001": 1}, "changes": [change], "evidence": records},
        request_id="checked-fact",
    )
    saved = service.read("F-000001")
    assert saved["work"]["phase"] == "human_review"
    assert saved["current"] is None
    assert saved["candidate"] is not None


@pytest.mark.parametrize("verification", ["model_claim_only", "abstract_only"])
def test_project_fact_label_does_not_make_unverified_material_reviewable(outputs, verification):
    if not outputs.research:
        return
    service = WorkStore(FreezeStore(outputs.root))
    service.add([{"title": "Table", "why": "Requested layout"}], request_id="new", actor="codex")
    change = research_change()
    change["problem_type"] = "output_specification"
    records = evidence_records(verification)
    records[0]["value"]["source_type"] = "project_fact"
    with pytest.raises(FreezeError, match="verification|Model-only"):
        service.commit_work(
            {"read_set": {"F-000001": 1}, "changes": [change], "evidence": records},
            request_id="unverified-fact",
        )
    assert service.read("F-000001")["candidate"] is None


def test_changed_confirmed_specification_rejects_old_binding(outputs):
    if not outputs.research:
        return
    previous = specification(outputs)
    Outputs(outputs.root).register(payload(specification=previous))
    service = WorkStore(FreezeStore(outputs.root))
    change = research_change()
    change["problem_type"] = "output_specification"
    change["definition"]["value"] = "Revised specification with a new table element"
    service.commit_work(
        {"read_set": {"F-000001": service.read("F-000001")["revision"]}, "changes": [change]},
        request_id="revise-spec",
    )
    approve(service)
    before = Registry(outputs.root).project.registry.read_bytes()
    with pytest.raises(FreezeError, match="current confirmed version"):
        Outputs(outputs.root).register(payload(specification=previous))
    assert Registry(outputs.root).project.registry.read_bytes() == before
    current = service.read("F-000001")["current"]
    replacement = {
        "question_id": "F-000001",
        "version": current["number"],
        "text_sha256": current["text_sha256"],
    }
    assert Outputs(outputs.root).register(payload(specification=replacement))["changed_paths"]


def test_unconfirmed_candidate_cannot_authorize_a_research_output(outputs):
    if not outputs.research:
        return
    ref = specification(outputs, confirm=False)
    with pytest.raises(FreezeError, match="human-confirmed"):
        Outputs(outputs.root).register(payload(specification=ref))
    assert Registry(outputs.root).outputs() == []


def test_group_member_added_during_registration_rolls_back_registry(outputs):
    group = outputs.root / "Results/comparison"
    group.mkdir()
    (group / "estimates.csv").write_text("Treatment,Estimate\nA,1.0\n")
    extra = (
        {"member_specifications": {"Results/comparison/estimates.csv": specification(outputs)}}
        if outputs.research
        else {}
    )
    project = Project(outputs.root)
    before = project.registry.read_bytes(), project.baseline.read_bytes()

    def add_member(event, path):
        if event == "written":
            (group / "extra.csv").write_text("unexpected\n")

    with pytest.raises(FreezeError, match="membership changed"):
        Outputs(outputs.root).register(
            payload(path="Results/comparison", kind="group", **extra), fault=add_member
        )
    assert (project.registry.read_bytes(), project.baseline.read_bytes()) == before
    assert (group / "extra.csv").exists()


def test_unchanged_specification_allows_regeneration_and_duplicate_registration_is_noop(outputs):
    ref = {"specification": specification(outputs)} if outputs.research else {}
    Outputs(outputs.root).register(payload(**ref))
    before = FreezeStore(outputs.root).snapshot() if outputs.research else None
    (outputs.root / "Results/estimates.csv").write_text("Treatment,Estimate\nA,1.4\n")
    assert Outputs(outputs.root).register(payload(**ref))["changed_paths"] == []
    assert not Outputs(outputs.root).check()["errors"]
    if outputs.research:
        assert FreezeStore(outputs.root).snapshot() == before


def test_bad_format_machine_output_and_unregistered_files_are_reported(outputs):
    (outputs.root / "Results/model.rds").write_bytes(b"machine state")
    with pytest.raises(FreezeError, match="human-facing"):
        outputs.register(payload(path="Results/model.rds"))
    (outputs.root / "Results/debug-table.csv").write_text("value\n1\n")
    with pytest.raises(FreezeError, match="process output"):
        outputs.register(payload(path="Results/debug-table.csv"))
    errors = outputs.check()["errors"]
    assert {e["path"] for e in errors} == {
        "Results/estimates.csv",
        "Results/model.rds",
        "Results/debug-table.csv",
    }


def test_non_r_producer_and_group_members_each_require_specification(outputs):
    ref = specification(outputs) if outputs.research else None
    (outputs.root / "Results/tables").mkdir()
    for name in ("first.csv", "second.csv"):
        (outputs.root / "Results/tables" / name).write_text("Label,Value\nA,1\n")
    value = payload(path="Results/tables", kind="group")
    if outputs.research:
        with pytest.raises(FreezeError, match="Every output group member"):
            Outputs(outputs.root).register({**value, "specification": ref})
        value["member_specifications"] = {"Results/tables/first.csv": ref, "Results/tables/second.csv": ref}
    Outputs(outputs.root).register(value)
    (outputs.root / "Results/tables/third.csv").write_text("Label,Value\nB,2\n")
    if outputs.research:
        assert any("membership changed" in e["reason"] for e in Outputs(outputs.root).check()["errors"])


def test_registry_commit_failure_rolls_back_and_preserves_unrelated_content(outputs):
    ref = {"specification": specification(outputs)} if outputs.research else {}
    project = Project(outputs.root)
    before, baseline = project.registry.read_bytes(), project.baseline.read_bytes()
    (outputs.root / "unrelated.txt").write_text("User owned")

    def fail(phase, path):
        if phase == "written" and path == project.registry_name:
            raise RuntimeError("simulated interruption")

    with pytest.raises(RuntimeError, match="simulated"):
        Outputs(outputs.root).register(payload(**ref), fault=fail)
    assert project.registry.read_bytes() == before and project.baseline.read_bytes() == baseline
    assert (outputs.root / "unrelated.txt").read_text() == "User owned"


def test_data_classification_records_provenance_and_rejects_wrong_directory(outputs):
    (outputs.root / "Data/raw/source.csv").write_text("raw\n1\n")
    (outputs.root / "Data/derived/clean.csv").write_text("clean\n1\n")
    outputs.register_data(
        {"path": "Data/raw/source.csv", "kind": "raw", "source": "Synthetic source", "version": "input-1"}
    )
    Outputs(outputs.root).register_data(
        {
            "path": "Data/derived/clean.csv",
            "kind": "derived",
            "producer": "Scripts/01_analysis.py",
            "version": "run-1",
        }
    )
    saved = Registry(outputs.root).metadata["data"]
    assert (
        saved["Data/raw/source.csv"]["sha256"] == fingerprint(outputs.root, "Data/raw/source.csv")["sha256"]
    )
    with pytest.raises(FreezeError, match="conflicts"):
        Outputs(outputs.root).register_data(
            {
                "path": "Data/raw/source.csv",
                "kind": "derived",
                "producer": "Scripts/01_analysis.py",
                "version": "run-1",
            }
        )


def test_legacy_output_registration_survives_and_allows_regenerated_values(tmp_path):
    helper = memory_fixtures.legacy_module("stepwise_r_project")
    helper.ensure_v3_project(tmp_path, create=True)
    (tmp_path / "R/analysis.R").write_text("print(1)\n")
    (tmp_path / "Results/estimates.csv").write_text("Label,Estimate\nA,1\n")
    helper.register_result(
        tmp_path, "estimates", "Results/estimates.csv", "table", "publication", "R/analysis.R", replace=False
    )
    caps = {"council": {"governance_versions": [5]}, "skill": {"governance_versions": [5]}}
    migration.apply(tmp_path, migration.check(tmp_path, caps).public(), caps)
    saved = copy.deepcopy(read_table(Registry(tmp_path).text, "results"))
    (tmp_path / "Results/estimates.csv").write_text("Label,Estimate\nA,3\n")
    report = Outputs(tmp_path).check()
    assert not report["errors"] and report["warnings"]
    value = payload(producer="R/analysis.R")
    Outputs(tmp_path).register(value)
    assert read_table(Registry(tmp_path).text, "results") == saved
    with pytest.raises(FreezeError, match="structure changes"):
        Outputs(tmp_path).register({**value, "structure_changed": True})
