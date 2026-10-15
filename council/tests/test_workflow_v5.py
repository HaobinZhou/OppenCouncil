"""Exercise v5 work transactions against real files and the existing recovery journal."""

import copy
import json

import pytest

from oppencouncil import decisions, workflow
from oppencouncil.project import MARKER, metadata_block
from oppencouncil.store import FreezeError, FreezeStore
from oppencouncil.workstore import WorkStore


@pytest.fixture(params=["project.md", ".oppen-project-steward/registry.md"])
def work(tmp_path, request):
    registry = tmp_path / request.param
    registry.parent.mkdir(exist_ok=True)
    registry.write_text(
        MARKER + "\n" + metadata_block({"governance_version": 5, "project_type": "research"}) + "\n",
        encoding="utf-8",
    )
    service = WorkStore(FreezeStore(tmp_path))
    service.add([{"title": "Definition", "why": "Observed decision"}], request_id="create", actor="codex")
    return service


def save(work, change, actor="codex", request_id=None):
    identifier = change.get("id", "F-000001")
    revision = work.read(identifier)["revision"]
    return work.commit_work(
        {"read_set": {identifier: revision}, "changes": [{**change, "id": identifier}]},
        request_id=request_id or f"{identifier}-{revision}-{actor}",
        actor=actor,
    )


def stage(phase="human_review", conclusion="single_recommendation"):
    return {
        "phase": phase,
        "reason": "The necessary facts have been checked",
        "affected_refs": ["F-000001"],
        "completion_conditions": ["Human decision"],
        "trigger_refs": ["observed-project-fact"],
        "conclusion_type": conclusion,
    }


def prepare(work, text="Complete current rule", identifier="F-000001"):
    save(
        work,
        {
            "id": identifier,
            "problem_type": "project_fact",
            "definition": {"operation": "definition_draft", "value": text},
            "phase": stage(),
        },
    )


def approve(work, identifier="F-000001"):
    candidate = work.read(identifier)["candidate"]
    return save(
        work,
        {
            "id": identifier,
            "definition": {"operation": "definition_approve", "value": candidate["approval_token"]},
        },
        "user",
    )


def test_feedback_reply_and_cursor_commit_together_and_retry(work):
    save(work, {"comments": ["Why this direction?"]}, "user")
    read = work.read("F-000001")
    event = read["inputs"][0]["id"]
    request = "reply-and-cursor"
    payload = {
        "read_set": read["read_set"],
        "changes": [
            {
                "id": "F-000001",
                "comments": ["The existing evidence supports it."],
                "progress": {
                    "human_cursor": event,
                    "dispositions": [{"event_id": event, "reply_id": request + ":F-000001:0"}],
                },
            }
        ],
    }
    result = work.commit_work(payload, request_id=request)
    assert not result["replayed"]
    assert work.commit_work(payload, request_id=request)["replayed"]
    assert work.index(actionable=True)["total"] == 0
    on_disk = json.loads((work.store.questions / "F-000001.json").read_text(encoding="utf-8"))
    assert len(on_disk["messages"]) == 2
    assert len(on_disk["processing"]["receipts"]) == 1
    assert on_disk["processing"]["human_cursor"] == event
    assert "status" not in on_disk


def test_new_feedback_during_processing_is_not_consumed(work):
    save(work, {"comments": ["First question"]}, "user")
    read = work.read("F-000001")
    first = read["inputs"][0]["id"]
    save(work, {"comments": ["Arrived during processing"]}, "user")
    change = {
        "id": "F-000001",
        "comments": ["Answer to first only"],
        "progress": {
            "human_cursor": first,
            "dispositions": [{"event_id": first, "reply_id": "answer:F-000001:0"}],
        },
    }
    with pytest.raises(FreezeError, match="changed since read"):
        work.commit_work({"read_set": read["read_set"], "changes": [change]}, request_id="answer")
    save(work, change, request_id="answer")
    after = work.read("F-000001")
    assert len(after["inputs"]) == 1
    assert after["messages"][0]["text"] == "Arrived during processing"


def test_cursor_cannot_skip_feedback_or_use_an_unrelated_old_reply(work):
    save(work, {"comments": ["Old unrelated explanation"]}, request_id="old")
    save(work, {"comments": ["New question", "Another question"]}, "user")
    before = (work.store.questions / "F-000001.json").read_bytes()
    inputs = work.read("F-000001")["inputs"]
    for dispositions in [[], [{"event_id": e["id"], "reply_id": "old:F-000001:0"} for e in inputs]]:
        with pytest.raises(FreezeError, match="reply|pending|transaction"):
            save(work, {"progress": {"human_cursor": inputs[-1]["id"], "dispositions": dispositions}})
        assert (work.store.questions / "F-000001.json").read_bytes() == before


def test_external_comments_are_actionable_but_not_human_feedback(work):
    save(work, {"comments": ["A source may contradict this assumption"]}, "external_ai")
    read = work.read("F-000001")
    assert read["actionable"] and not read["human_pending"]
    assert read["messages"][0]["label"] == "外部 AI · 未经本地核查"
    assert work.index()["items"][0]["pending_human_count"] == 0
    before = (work.store.questions / "F-000001.json").read_bytes()
    with pytest.raises(FreezeError):
        save(work, {"phase": stage()}, "external_ai")
    with pytest.raises(FreezeError):
        save(work, {"definition": {"operation": "definition_draft", "value": "Unauthorized"}}, "external_ai")
    assert (work.store.questions / "F-000001.json").read_bytes() == before


def test_pending_wakes_on_dependency_without_a_new_comment(work):
    work.add([{"title": "Prerequisite", "why": "Needed"}], request_id="prereq", actor="codex")
    save(
        work,
        {
            "pending": [
                {
                    "id": "P1",
                    "question": "Wait for prerequisite",
                    "reason": "Not confirmed",
                    "continue_when": {"kind": "definition_confirmed", "question_id": "F-000002"},
                }
            ]
        },
    )
    assert not work.read("F-000001")["actionable"]
    prepare(work, identifier="F-000002")
    approve(work, "F-000002")
    assert work.read("F-000001")["ready_pending_ids"] == ["P1"]


def test_pending_candidate_waits_for_next_version_and_survives_withdrawal(work):
    prepare(work)
    approve(work)
    prepare(work, "Revised complete rule")
    save(
        work,
        {
            "pending": [
                {
                    "id": "P1",
                    "question": "Regenerate after confirmation",
                    "reason": "Candidate changed",
                    "continue_when": {"kind": "definition_confirmed", "question_id": "F-000001"},
                }
            ]
        },
    )
    record = work.read("F-000001")
    assert record["pending_items"][0]["continue_when"]["min_version"] == 2
    assert record["ready_pending_ids"] == []
    save(work, {"definition": {"operation": "definition_discard"}}, "user")
    save(work, {"pending": [{"id": "P1", "reason": "Still waiting for a confirmed revision"}]})
    assert work.read("F-000001")["ready_pending_ids"] == []
    prepare(work, "Another complete revised rule")
    approve(work)
    assert work.read("F-000001")["ready_pending_ids"] == ["P1"]


def test_pending_explicit_current_version_can_use_existing_formal_rule(work):
    prepare(work)
    approve(work)
    prepare(work, "A separate proposed revision")
    save(
        work,
        {
            "pending": [
                {
                    "id": "P1",
                    "question": "Use confirmed v1",
                    "reason": "Existing rule applies",
                    "continue_when": {
                        "kind": "definition_confirmed",
                        "question_id": "F-000001",
                        "min_version": 1,
                    },
                }
            ]
        },
    )
    assert work.read("F-000001")["ready_pending_ids"] == ["P1"]


@pytest.mark.parametrize("reverse", [False, True])
def test_pending_binds_after_all_candidate_changes_regardless_of_order(work, reverse):
    work.add([{"title": "Prerequisite", "why": "Needed"}], request_id="prereq", actor="codex")
    prepare(work, identifier="F-000002")
    approve(work, "F-000002")
    changes = [
        {
            "id": "F-000001",
            "pending": [
                {
                    "id": "P1",
                    "question": "Wait",
                    "reason": "Revision needed",
                    "continue_when": {"kind": "definition_confirmed", "question_id": "F-000002"},
                }
            ],
        },
        {
            "id": "F-000002",
            "definition": {
                "operation": "definition_draft",
                "value": "Revised complete prerequisite",
            },
        },
    ]
    work.commit_work(
        {
            "read_set": {c["id"]: work.read(c["id"])["revision"] for c in changes},
            "changes": changes[::-1] if reverse else changes,
        },
        request_id="candidate-and-wait",
    )
    saved = work.read("F-000001")
    assert saved["pending_items"][0]["continue_when"]["min_version"] == 2
    assert saved["ready_pending_ids"] == []
    prepare(work, "Revised complete prerequisite", identifier="F-000002")
    approve(work, "F-000002")
    assert work.read("F-000001")["ready_pending_ids"] == ["P1"]


@pytest.mark.parametrize("minimum", [0, -1, True, "2", 1.5])
def test_pending_rejects_invalid_version_without_writes(work, minimum):
    path = work.store.questions / "F-000001.json"
    before = path.read_bytes()
    with pytest.raises(FreezeError, match="positive min_version"):
        save(
            work,
            {
                "pending": [
                    {
                        "id": "P1",
                        "question": "Wait",
                        "reason": "Not confirmed",
                        "continue_when": {
                            "kind": "definition_confirmed",
                            "question_id": "F-000001",
                            "min_version": minimum,
                        },
                    }
                ]
            },
        )
    assert path.read_bytes() == before


def test_evidence_only_reconfirmation_preserves_version_and_dependency_bindings(work):
    prepare(work)
    approve(work)
    before = copy.deepcopy(work.read("F-000001")["current"])
    save(
        work,
        {
            "evidence_impact": {"classification": "weakened", "reason": "New measurement"},
            "review_basis": {"claims": [], "summary": "Newly verified project facts"},
        },
    )
    token = work.read("F-000001")["reconfirmation_token"]
    with pytest.raises(FreezeError, match="review|prepared"):
        save(work, {"definition": {"operation": "definition_reconfirm", "value": token}}, "user")
    save(work, {"phase": stage()})
    token = work.read("F-000001")["reconfirmation_token"]
    with pytest.raises(FreezeError, match="Only the user"):
        save(work, {"definition": {"operation": "definition_reconfirm", "value": token}})
    save(work, {"definition": {"operation": "definition_reconfirm", "value": token}}, "user")
    current = work.read("F-000001")["current"]
    assert {k: v for k, v in current.items() if k != "reconfirmations"} == before
    assert len(current["reconfirmations"]) == 1
    assert current["reconfirmations"][0]["evidence_basis"]["summary"] == "Newly verified project facts"
    assert work.read("F-000001")["work"]["phase"] == "closed"


@pytest.mark.parametrize("second_changes_text", [False, True])
def test_group_confirmation_reconfirms_current_basis_without_new_version(work, second_changes_text):
    work.add([{"title": "Second rule", "why": "Another decision"}], request_id="second", actor="codex")
    for qid in ["F-000001", "F-000002"]:
        prepare(work, identifier=qid)
        approve(work, qid)
    group = work.store.change_group(
        None,
        "create",
        {"title": "Evidence review", "purpose": "Related facts", "member_ids": ["F-000001", "F-000002"]},
        expected_revision=0,
        request_id="group",
        actor="codex",
    )
    before = copy.deepcopy(work.store.read_question("F-000001")["definition"]["versions"])
    for qid in group["member_ids"]:
        if qid == "F-000002" and second_changes_text:
            prepare(work, "A materially revised rule", identifier=qid)
        else:
            save(
                work,
                {
                    "id": qid,
                    "evidence_impact": {"classification": "weakened", "reason": "New measurement"},
                    "review_basis": {"claims": [], "summary": "New project facts"},
                },
            )
    unprepared = work.store.read_group(group["id"])
    with pytest.raises(FreezeError, match="prepared"):
        work.store.change_group(
            group["id"],
            "approve",
            unprepared["approval_token"],
            expected_revision=unprepared["revision"],
            request_id="unprepared",
            actor="user",
        )
    for qid in group["member_ids"]:
        save(work, {"id": qid, "phase": stage()})
    ready = work.store.read_group(group["id"])
    confirmed = work.store.change_group(
        group["id"],
        "approve",
        ready["approval_token"],
        expected_revision=ready["revision"],
        request_id="confirm-group",
        actor="user",
    )
    after = work.store.read_question("F-000001")["definition"]["versions"]
    assert len(after) == 1
    assert {k: v for k, v in after[0].items() if k != "reconfirmations"} == before[0]
    assert len(after[0]["reconfirmations"]) == 1
    assert work.store.read_question("F-000002")["definition"]["current_version"] == (
        2 if second_changes_text else 1
    )
    assert confirmed["confirmations"][-1]["reconfirmed_ids"] == (
        ["F-000001"] if second_changes_text else ["F-000001", "F-000002"]
    )
    replay = work.store.change_group(
        group["id"],
        "approve",
        ready["approval_token"],
        expected_revision=ready["revision"],
        request_id="confirm-group",
        actor="user",
    )
    assert replay["replayed"]
    assert len(work.store.read_question("F-000001")["definition"]["versions"][0]["reconfirmations"]) == 1


def test_crash_after_journal_commit_recovers_reply_with_cursor(work, monkeypatch):
    save(work, {"comments": ["Question before crash"]}, "user")
    event = work.read("F-000001")["inputs"][0]["id"]
    atomic = decisions.atomic_json

    def crash(path, value):
        if path.name == "manifest.json":
            raise OSError("simulated process interruption")
        return atomic(path, value)

    with monkeypatch.context() as patch:
        patch.setattr(decisions, "atomic_json", crash)
        with pytest.raises(OSError, match="interruption"):
            save(
                work,
                {
                    "comments": ["Durable answer"],
                    "progress": {
                        "human_cursor": event,
                        "dispositions": [{"event_id": event, "reply_id": "crash:F-000001:0"}],
                    },
                },
                request_id="crash",
            )
    assert (work.store.root / decisions.JOURNAL).exists()
    assert not WorkStore(FreezeStore(work.store.project)).read("F-000001")["human_pending"]
    assert not (work.store.root / decisions.JOURNAL).exists()
    disk = json.loads((work.store.questions / "F-000001.json").read_text(encoding="utf-8"))
    assert disk["messages"][-1]["text"] == "Durable answer"


@pytest.mark.parametrize("last_actor,expected", [("user", "message:h1"), ("codex", "message:h2")])
def test_migration_cursor_uses_original_discussion_not_imported_answers(last_actor, expected):
    old = {
        "schema_version": 1,
        "id": "F-000001",
        "revision": 1,
        "status": "discussing",
        "title": "Legacy",
        "user_answer": "Historical answer field",
        "ai_position": "Historical proposal",
        "messages": [
            {"id": "h1", "actor": "user", "text": "First"},
            {"id": "h2", "actor": "user", "text": "Second"},
        ],
    }
    if last_actor == "codex":
        old["messages"].append({"id": "a1", "actor": "codex", "text": "Reply"})
    upgraded = workflow.upgrade_question(old)
    assert upgraded["processing"]["human_cursor"] == expected
    assert upgraded["processing"]["bootstrap"] == "needs_reconciliation"
    assert [e["reference"] for e in workflow.unread(upgraded)] == (["h2"] if last_actor == "user" else [])
    assert upgraded["messages"][: len(old["messages"])] == old["messages"]
    assert any(m["kind"] == "historical_answer" for m in upgraded["messages"] if "kind" in m)


def test_group_feedback_has_one_owner_and_external_comment_is_not_human(work):
    work.add([{"title": "Second member", "why": "Related decision"}], request_id="second", actor="codex")
    group = work.store.change_group(
        None,
        "create",
        {"title": "Review together", "purpose": "Coherent choices", "member_ids": ["F-000001", "F-000002"]},
        expected_revision=0,
        request_id="group",
        actor="codex",
    )
    group = work.store.change_group(
        group["id"],
        "comment",
        {"text": "Human shared feedback", "question_id": "F-000002"},
        expected_revision=group["revision"],
        request_id="group-human",
        actor="user",
    )
    assert work.read(group["id"])["human_pending"]
    assert not any(work.read(q)["human_pending"] for q in group["member_ids"])
    save(
        work,
        {
            "id": group["id"],
            "comments": [{"text": "Addressed", "question_id": "F-000002"}],
            "progress": {
                "human_cursor": "group-human",
                "dispositions": [{"event_id": "group-human", "reply_id": "group-reply:B-000001:0"}],
            },
        },
        request_id="group-reply",
    )
    current = work.store.read_group(group["id"])
    work.store.change_group(
        group["id"],
        "comment",
        "External concern",
        expected_revision=current["revision"],
        request_id="group-external",
        actor="external_ai",
    )
    read = work.read(group["id"])
    assert read["actionable"] and not read["human_pending"]
    assert read["messages"][0]["label"] == "外部 AI · 未经本地核查"
    assert json.loads(work.store.manifest.read_text(encoding="utf-8"))["schema_version"] == 3


def test_joint_confirmation_requires_prepared_members_and_preserves_cycles(work):
    work.add([{"title": "Second member", "why": "Related decision"}], request_id="second", actor="codex")
    group = work.store.change_group(
        None,
        "create",
        {
            "title": "Joint timing",
            "purpose": "Mutually dependent choices",
            "member_ids": ["F-000001", "F-000002"],
        },
        expected_revision=0,
        request_id="group",
        actor="codex",
    )
    for qid, upstream in [("F-000001", "F-000002"), ("F-000002", "F-000001")]:
        save(
            work,
            {
                "id": qid,
                "definition": {
                    "operation": "definition_draft",
                    "value": {
                        "text": "Complete rule " + qid,
                        "dependencies": [{"question_id": upstream, "reason": "Same timeline"}],
                    },
                },
            },
        )
    before = work.store.read_group(group["id"])
    with pytest.raises(FreezeError, match="review packet"):
        work.store.change_group(
            group["id"],
            "approve",
            before["approval_token"],
            expected_revision=before["revision"],
            request_id="unprepared",
            actor="user",
        )
    for qid in group["member_ids"]:
        save(work, {"id": qid, "phase": stage()})
    ready = work.store.read_group(group["id"])
    work.store.change_group(
        group["id"],
        "approve",
        ready["approval_token"],
        expected_revision=ready["revision"],
        request_id="confirm",
        actor="user",
    )
    for qid in group["member_ids"]:
        record = work.store.read_question(qid)
        assert record["work"]["phase"] == "closed"
        assert record["definition"]["current_version"] == 1
        assert record["definition"]["versions"][0]["dependencies"][0]["version"] == 1
        assert "status" not in json.loads((work.store.questions / f"{qid}.json").read_text(encoding="utf-8"))


def test_external_evidence_wakes_suspended_item_without_human_pending(work):
    save(
        work,
        {
            "pending": [
                {
                    "id": "P1",
                    "question": "Wait for requested source",
                    "reason": "Unavailable",
                    "continue_when": {"kind": "new_material", "after_sequence": 0},
                }
            ]
        },
    )
    assert not work.read("F-000001")["actionable"]
    result = work.evidence_submit(
        {"text": "Located source for local verification", "targets": ["F-000001"]},
        request_id="source-arrives",
    )
    read = work.read("F-000001")
    assert read["ready_pending_ids"] == ["P1"]
    assert not read["human_pending"]
    assert work.evidence(result["path"])["actor"] == "external_ai"


def test_human_revision_keeps_formal_version_until_separate_confirmation(work):
    prepare(work)
    approve(work)
    current = copy.deepcopy(work.read("F-000001")["current"])
    save(work, {"definition": {"operation": "definition_draft", "value": "Human changed candidate"}}, "user")
    read = work.read("F-000001")
    assert read["human_pending"] and read["candidate"]["text"] == "Human changed candidate"
    assert read["current"] == current
    with pytest.raises(FreezeError, match="review packet"):
        approve(work)


def evidence_records(verification="full_text_location", version=1):
    source = f"evidence/sources/S-000001/r{version:06d}.json"
    claim = f"evidence/claims/E-000001/r{version:06d}.json"
    return [
        {
            "path": source,
            "value": {
                "schema_version": 1,
                "id": "S-000001",
                "version": version,
                "source_type": "method_paper",
                "verification": verification,
                "citation": "Synthetic source",
                "location": "Section 2, sentence 3",
                "read_scope": "Methods and limitations",
                "retrieved_at": "2026-10-14T00:00:00Z",
                "disclosure": "shared",
            },
        },
        {
            "path": claim,
            "value": {
                "schema_version": 1,
                "id": "E-000001",
                "version": version,
                "claim": "Method fits the stated design",
                "applicability": "Synthetic design assumptions",
                "sources": [source],
                "disclosure": "shared",
            },
        },
    ]


def research_change():
    return {
        "id": "F-000001",
        "problem_type": "research_method",
        "definition": {"operation": "definition_draft", "value": "Complete synthetic method"},
        "review_basis": {
            "claims": ["evidence/claims/E-000001/r000001.json"],
            "summary": "Original text checked",
        },
        "review_packet": {
            key: "Synthetic checked explanation"
            for key in (
                "common_practice",
                "support",
                "applicability",
                "departure_check",
                "default",
                "project_reason",
            )
        },
        "phase": stage(),
    }


@pytest.mark.parametrize("verification", ["model_claim_only", "abstract_only"])
def test_unverified_source_cannot_support_recommendation_and_nothing_is_committed(work, verification):
    before = work.store.manifest.read_bytes()
    with pytest.raises(FreezeError, match="Model-only|original-text"):
        work.commit_work(
            {
                "read_set": {"F-000001": 1},
                "changes": [research_change()],
                "evidence": evidence_records(verification),
            },
            request_id="unverified",
        )
    assert work.store.manifest.read_bytes() == before
    assert not (work.store.root / decisions.JOURNAL).exists()
    assert work.read("F-000001")["candidate"] is None


def test_source_claim_and_review_are_atomic_and_later_source_only_targets_related_items(work):
    work.add([{"title": "Unrelated", "why": "Separate"}], request_id="unrelated", actor="codex")
    payload = {"read_set": {"F-000001": 1}, "changes": [research_change()], "evidence": evidence_records()}
    work.commit_work(payload, request_id="curate")
    approve(work)
    formal = copy.deepcopy(work.read("F-000001")["current"])
    unrelated = (work.store.questions / "F-000002.json").read_bytes()
    source_path = evidence_records()[0]["path"]
    assert work.evidence_index(source_id="S-000001")["items"][0]["question_ids"] == ["F-000001"]
    work.commit_work(
        {"changes": [], "evidence": [evidence_records(version=2)[0]]}, request_id="source-update"
    )
    read = work.read("F-000001")
    assert read["actionable"] and not read["human_pending"]
    assert read["inputs"][0]["kind"] == "evidence_changed"
    assert read["work"]["phase"] == "closed"  # Association alone does not invalidate a decision.
    assert read["current"] == formal
    assert (work.store.questions / "F-000002.json").read_bytes() == unrelated
    old_source = work.evidence(source_path)
    with pytest.raises(FreezeError, match="append-only"):
        work.commit_work({"changes": [], "evidence": [evidence_records()[0]]}, request_id="overwrite")
    assert work.evidence(source_path) == old_source


def test_missing_review_fields_block_research_but_explained_disagreement_does_not(work):
    change = research_change()
    change["review_packet"].pop("project_reason")
    payload = {"read_set": {"F-000001": 1}, "changes": [change], "evidence": evidence_records()}
    with pytest.raises(FreezeError, match="project_reason"):
        work.commit_work(payload, request_id="missing")
    change["review_packet"]["project_reason"] = "Comparable with the primary comparison study"
    change["review_packet"]["objections"] = [
        {
            "disposition": "explained_tradeoff",
            "reason": "Two credible designs have different interpretation; both are explained",
        }
    ]
    work.commit_work(payload, request_id="explained")
    first_token = work.read("F-000001")["candidate"]["approval_token"]
    revised_packet = {**change["review_packet"], "project_reason": "A different project condition"}
    save(work, {"review_packet": revised_packet})
    assert work.read("F-000001")["candidate"]["approval_token"] != first_token


def test_external_suggestion_waits_for_local_triage_before_becoming_an_investigation(work):
    submitted = work.evidence_submit({"text": "Please investigate a new concern"}, request_id="suggestion")
    assert not work.store.snapshot()["investigations"]
    assert work.index(actionable=True)["inbox_total"] == 1
    result = work.investigation(
        {
            "title": "New concern",
            "why": "Local check found it relevant",
            "dedupe_key": "new-concern",
            "submission_path": submitted["path"],
        },
        request_id="triage",
    )
    assert work.index()["inbox_total"] == 0
    assert work.read(result["id"])["work"]["trigger_refs"] == [submitted["path"]]


def test_invalid_journal_is_rejected_before_commit_and_linked_parent_cannot_escape(work, tmp_path):
    before = work.store.manifest.read_bytes()
    with work.store.locked():
        with pytest.raises(FreezeError):
            decisions.commit(
                work.store, {"investigations/I-000001.json": {"schema_version": 1, "id": "I-000001"}}
            )
    assert work.store.manifest.read_bytes() == before
    assert not (work.store.root / decisions.JOURNAL).exists()
    outside = tmp_path / "outside"
    outside.mkdir()
    evidence = work.store.root / "evidence"
    try:
        evidence.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Directory symlinks unavailable")
    journal = {"schema_version": 1, "writes": {evidence_records()[0]["path"]: evidence_records()[0]["value"]}}
    (work.store.root / decisions.JOURNAL).write_text(json.dumps(journal))
    with pytest.raises(FreezeError, match="Unsafe freeze directory"):
        work.store.snapshot()
    assert list(outside.iterdir()) == []


def test_pending_retains_original_feedback_after_cursor_advances(work):
    save(work, {"comments": ["Need the original source"]}, "user")
    first = work.read("F-000001")["inputs"][0]["id"]
    save(
        work,
        {
            "pending": [
                {
                    "id": "P1",
                    "question": "Obtain original source",
                    "reason": "Unavailable",
                    "continue_when": {"kind": "local_assessment", "satisfied": False},
                }
            ],
            "progress": {"human_cursor": first, "dispositions": [{"event_id": first, "pending_id": "P1"}]},
        },
    )
    save(work, {"comments": ["A second independent clarification"]}, "user")
    second = work.read("F-000001")["inputs"][0]["id"]
    save(
        work,
        {
            "comments": ["Second answer"],
            "progress": {
                "human_cursor": second,
                "dispositions": [{"event_id": second, "reply_id": "second-answer:F-000001:0"}],
            },
        },
        request_id="second-answer",
    )
    read = work.read("F-000001")
    assert read["inputs"] == []
    assert [m["text"] for m in read["messages"]] == ["Need the original source"]
    assert not read["actionable"]
    save(
        work,
        {
            "pending": [
                {
                    "id": "P1",
                    "continue_when": {
                        "kind": "local_assessment",
                        "satisfied": True,
                        "assessment": "Local agent obtained and checked the original source",
                    },
                }
            ]
        },
    )
    assert work.read("F-000001")["actionable"]


def test_dependency_change_wakes_only_dependents_and_compatible_review_preserves_formal_text(work):
    prepare(work)
    approve(work)
    work.add([{"title": "Dependent", "why": "Version-bound"}], request_id="dependent", actor="codex")
    save(
        work,
        {
            "id": "F-000002",
            "definition": {
                "operation": "definition_draft",
                "value": {
                    "text": "Dependent rule",
                    "dependencies": [{"question_id": "F-000001", "reason": "Required event rule"}],
                },
            },
            "phase": stage(),
        },
    )
    approve(work, "F-000002")
    before = copy.deepcopy(work.read("F-000002")["current"])
    prepare(work, "Changed upstream rule")
    approve(work)
    read = work.read("F-000002")
    assert read["actionable"] and read["inputs"][0]["kind"] == "dependencies_changed"
    assert not read["human_pending"]
    assert read["readiness"]["status"] == "needs_review"
    current = work.read("F-000001")["current"]
    save(
        work,
        {
            "id": "F-000002",
            "dependency_review": {
                "bindings": {"F-000001": [2, current["text_sha256"]]},
                "reason": "Unchanged dependent interpretation",
            },
        },
    )
    assert work.read("F-000002")["readiness"]["status"] == "effective"
    assert work.read("F-000002")["current"] == before


def test_excluded_investigation_can_be_reopened_without_losing_reason(work):
    iid = work.investigation(
        {"title": "Possible issue", "why": "Observed trigger", "dedupe_key": "scope"},
        request_id="investigate",
    )["id"]
    save(
        work,
        {"id": iid, "phase": {**stage("closed", "not_applicable"), "reason": "Verified no affected records"}},
    )
    closed = work.read(iid)
    assert closed["review_category"] == "excluded"
    assert closed["work"]["phase"] == "closed"
    views = [
        closed,
        work.read("F-000001"),
        *work.index()["items"],
        *work.store.snapshot()["questions"],
        *work.store.snapshot()["investigations"],
    ]
    for view in views:
        assert "status" not in view
        assert view["historical"] is False
    save(work, {"id": iid, "comments": ["Please reconsider with the new scope"]}, "user")
    save(
        work,
        {"id": iid, "phase": {**stage("triage", "needs_check"), "reason": "Human requested a changed scope"}},
    )
    read = work.read(iid)
    assert read["work"]["revision_id"] == 2
    assert read["work"]["transitions"][0]["reason"] == "Verified no affected records"
    assert read["human_pending"]


def test_local_work_cli_requires_stable_request_id_and_cannot_confirm(work, tmp_path, capsys):
    from oppencouncil.cli import main

    prefix = ["--directory", str(tmp_path / "unused-site")]
    project = str(work.store.project)
    payload = tmp_path / "input.json"
    payload.write_text(
        json.dumps(
            {"read_set": {"F-000001": 1}, "changes": [{"id": "F-000001", "comments": ["Local reply"]}]}
        )
    )
    assert main(prefix + ["work-commit", project, "--input", str(payload)]) == 2
    assert "request_id" in capsys.readouterr().err
    data = json.loads(payload.read_text(encoding="utf-8"))
    data["request_id"] = "cli-reply"
    payload.write_text(json.dumps(data))
    assert main(prefix + ["work-commit", project, "--input", str(payload)]) == 0
    assert not json.loads(capsys.readouterr().out)["replayed"]
    assert main(prefix + ["work-commit", project, "--input", str(payload)]) == 0
    assert json.loads(capsys.readouterr().out)["replayed"]
    prepare(work)
    data = {
        "request_id": "cli-confirm",
        "read_set": work.read("F-000001")["read_set"],
        "changes": [
            {
                "id": "F-000001",
                "definition": {
                    "operation": "definition_approve",
                    "value": work.read("F-000001")["candidate"]["approval_token"],
                },
            }
        ],
    }
    payload.write_text(json.dumps(data))
    assert main(prefix + ["work-commit", project, "--input", str(payload)]) == 2
    assert "Only the user" in capsys.readouterr().err
    assert work.read("F-000001")["current"] is None
    assert not (tmp_path / "unused-site").exists()
