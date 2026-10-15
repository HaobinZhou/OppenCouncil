"""Old commands reuse investigations without mutating old Attention or losing feedback."""

import json
import subprocess
import sys

import pytest
import test_audits_v5 as audit_fixtures
import test_migration_v5 as migration_fixtures

from oppencouncil import migration, project_checks, review
from oppencouncil.project import Project
from oppencouncil.store import FreezeError, FreezeStore
from oppencouncil.workstore import WorkStore

project = audit_fixtures.project
legacy = migration_fixtures.legacy
snapshot = audit_fixtures.snapshot
CAPABILITIES = migration_fixtures.CAPABILITIES


def payload():
    return {
        "title": "Investigate timeout semantics",
        "blocking": True,
        "observation": "An acknowledgement was lost.",
        "evidence": "The local check reproduced it.",
        "why_it_matters": "Duplicate work changes the output.",
        "why_no_action_was_taken": "Ownership needs investigation.",
        "human_decision_needed": "Determine the intended retry behavior.",
    }


def test_raise_preserves_legacy_payload_and_blocks_until_resolution(project):
    before = Project(project).baseline.read_bytes()
    result = review.raise_issue(project, payload())
    assert result["id"] == "I-000001"
    assert not (Project(project).control / "Attention/entries/A-0001.md").exists()
    record = WorkStore(FreezeStore(project)).read(result["id"])
    for key, text in payload().items():
        if key not in {"title", "blocking"}:
            assert text in record["why"]
    assert record["work"]["blockers"] == [payload()["human_decision_needed"]]
    assert any("Unresolved work blocker" in i["reason"] for i in project_checks.validate(project)["errors"])
    saved = snapshot(project)
    assert review.raise_issue(project, payload())["replayed"]
    assert snapshot(project) == saved
    with pytest.raises(FreezeError, match="scope already exists"):
        review.raise_issue(project, {**payload(), "observation": "Different observation, same scope"})
    review.resolve(
        project,
        "I-000001",
        reason="Verified the existing contract already covers retries.",
        conclusion="covered",
    )
    assert not project_checks.validate(project)["errors"]
    assert not review.listing(project, actionable=True)["items"]
    assert Project(project).baseline.read_bytes() == before  # Freeze has its own transaction.
    assert review.resolve(project, "I-000001")["replayed"]


def test_review_resolution_preserves_unread_human_feedback(project):
    review.raise_issue(project, payload())
    work = WorkStore(FreezeStore(project))
    work.commit_work(
        {"read_set": {"I-000001": 1}, "changes": [{"id": "I-000001", "comments": ["Explain why."]}]},
        request_id="human-question",
        actor="user",
    )
    original = snapshot(project)
    with pytest.raises(FreezeError, match="changed since read"):
        review.resolve(project, "I-000001", expected_revision=1)
    with pytest.raises(FreezeError, match="unread feedback"):
        review.resolve(project, "I-000001")
    assert snapshot(project) == original
    assert work.read("I-000001")["human_pending"]


def test_review_does_not_resolve_formal_definitions_or_accept_untyped_blockers(project):
    with pytest.raises(FreezeError, match="use Council"):
        review.resolve(project, "F-000001")
    with pytest.raises(FreezeError, match="JSON boolean"):
        review.raise_issue(project, {**payload(), "blocking": "false"})
    with pytest.raises(FreezeError, match="array"):
        review.raise_issue(
            project, {"title": "Topic", "why": "Reason", "dedupe_key": "topic", "blockers": "x"}
        )


def test_attention_alias_real_cli(project):
    path = project.parent / "attention.json"
    path.write_text(json.dumps(payload()))
    for args in (["raise", "--input", str(path)], ["list"], ["resolve", "--id", "I-000001"]):
        result = subprocess.run(
            [sys.executable, "-m", "oppencouncil.governance", "attention", args[0], str(project), *args[1:]],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        assert isinstance(json.loads(result.stdout), dict)
    assert path.exists()
    assert not project_checks.validate(project)["errors"]


def test_migrated_attention_id_resolves_investigation_and_retains_old_bytes(legacy):
    root, kind, _ = legacy
    migration.apply(root, migration.check(root, CAPABILITIES).public(), CAPABILITIES)
    path = Project(root).control / "Attention/entries/A-0001.md"
    old = path.read_bytes()
    record = WorkStore(FreezeStore(root)).read("I-000001")
    assert record["legacy_attention"]["id"] == "A-0001"
    assert record["legacy_attention"]["fields"]["Observation"] == "Two observed timelines differ."
    assert next(i for i in review.listing(root)["items"] if i["id"] == "I-000001")["legacy_id"] == "A-0001"
    review.resolve(
        root,
        "A-0001",
        reason="The verified timing definition covers the observed difference.",
        conclusion="covered",
    )
    assert path.read_bytes() == old
    record = WorkStore(FreezeStore(root)).read("I-000001")
    assert record["work"]["phase"] == "closed" and not record["bootstrap_required"]
    assert not record["work"]["blockers"]
    assert review.resolve(root, "A-0001")["replayed"]
