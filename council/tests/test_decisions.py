"""Joint decisions preserve authority across conflicts, crashes and upstream revisions."""

import copy
import json

import pytest

from oppencouncil import decisions
from oppencouncil.definitions import read_definition
from oppencouncil.store import FreezeError, FreezeStore


@pytest.fixture(params=["stepwise-r-project", "oppen-project-steward"])
def store(tmp_path, request):
    marker = tmp_path / (
        "project.md" if request.param.startswith("stepwise") else ".oppen-project-steward/registry.md"
    )
    marker.parent.mkdir(exist_ok=True)
    marker.write_text(f"<!-- {request.param}:v4 -->\n")
    s = FreezeStore(tmp_path)
    s.add_questions(
        [{"title": name, "why": "Concrete behavior"} for name in ("Timing", "Events", "Upstream")],
        request_id="round",
    )
    return s


def change(s, qid, operation, value=None, actor="codex"):
    q = s.read_question(qid)
    return s.change(
        qid,
        operation,
        value,
        expected_revision=q["revision"],
        actor=actor,
        request_id=f"{qid}-{q['revision']}-{operation}",
    )


def group(s, operation="create", value=None, actor="codex", request_id=None):
    groups = s.snapshot()["decision_groups"]
    g = groups[0] if groups else None
    return s.change_group(
        g["id"] if g else None,
        operation,
        value,
        expected_revision=g["revision"] if g else 0,
        actor=actor,
        request_id=request_id or f"group-{operation}-{g['revision'] if g else 0}",
    )


def setup_group(s):
    return group(
        s,
        value={
            "title": "Timing together",
            "purpose": "Choose the complete strategy",
            "member_ids": ["F-000001", "F-000002"],
            "options": [],
        },
    )


def draft(s, qid, deps=None, text=None):
    return change(
        s, qid, "definition_draft", {"text": text or "Full rule for " + qid, "dependencies": deps or []}
    )


def dep(qid, **extra):
    return {"question_id": qid, "reason": "Determines the event window", **extra}


def approve(s, qid):
    q = s.read_question(qid)
    return change(s, qid, "definition_approve", q["definition"]["draft"]["approval_token"], actor="user")


def confirm(s):
    return group(s, "approve", s.snapshot()["decision_groups"][0]["approval_token"], "user")


def test_joint_cycle_confirmation_reads_same_versions_and_replays(store):
    setup_group(store)
    draft(store, "F-000001", [dep("F-000002")])
    draft(store, "F-000002", [dep("F-000001")])
    with pytest.raises(FreezeError, match="等待前序"):
        approve(store, "F-000001")
    g = store.snapshot()["decision_groups"][0]
    args = dict(expected_revision=g["revision"], request_id="approve", actor="user")
    saved = store.change_group(g["id"], "approve", g["approval_token"], **args)
    assert store.change_group(g["id"], "approve", g["approval_token"], **args)["replayed"]
    assert len(saved["confirmations"]) == 1
    for qid in g["member_ids"]:
        version = read_definition(store, qid)
        assert version["number"] == 1 and version["dependencies"][0]["version"] == 1
        assert version["readiness"]["status"] == "effective"
    disk = json.loads((store.root / "decision-groups.json").read_text())
    assert "Full rule" not in json.dumps(disk)


def test_missing_member_or_external_prerequisite_blocks_every_member(store):
    setup_group(store)
    draft(store, "F-000001")
    with pytest.raises(FreezeError, match="补齐"):
        confirm(store)
    draft(store, "F-000002", [dep("F-000003")])
    with pytest.raises(FreezeError, match="等待前序"):
        confirm(store)
    assert all(not q["definition"]["current_version"] for q in store.snapshot()["questions"])


def test_stale_candidate_and_upstream_change_require_fresh_review(store):
    setup_group(store)
    draft(store, "F-000003")
    approve(store, "F-000003")
    draft(store, "F-000001", [dep("F-000003")])
    draft(store, "F-000002")
    old = store.snapshot()["decision_groups"][0]
    draft(store, "F-000001", [dep("F-000003")], text="Human correction")
    with pytest.raises(FreezeError, match="changed since read"):
        group(store, "approve", old["approval_token"], "user")
    confirm(store)
    v1 = copy.deepcopy(read_definition(store, "F-000001"))
    change(store, "F-000003", "definition_begin", actor="user")
    draft(store, "F-000003", text="New prerequisite")
    # An open upstream revision does not replace its current authority.
    assert store.read_question("F-000001")["readiness"]["status"] == "effective"
    approve(store, "F-000003")
    assert store.read_question("F-000001")["readiness"]["status"] == "needs_review"
    assert read_definition(store, "F-000001")["text"] == v1["text"]
    up = read_definition(store, "F-000003")
    change(
        store,
        "F-000001",
        "dependency_review",
        {
            "bindings": {"F-000003": [up["number"], up["text_sha256"]]},
            "reason": "Verified the changed clause does not alter the consumed event window.",
        },
    )
    assert store.read_question("F-000001")["readiness"]["status"] == "effective"
    assert read_definition(store, "F-000001")["number"] == 1


def test_readers_recover_committed_group_after_interrupted_write(store, monkeypatch):
    setup_group(store)
    draft(store, "F-000001")
    draft(store, "F-000002")
    original = decisions.atomic_json
    writes = []

    def interrupted(path, value):
        writes.append(path)
        if len(writes) == 2:
            raise OSError("simulated process interruption")
        return original(path, value)

    monkeypatch.setattr(decisions, "atomic_json", interrupted)
    with pytest.raises(OSError):
        confirm(store)
    assert (store.root / decisions.JOURNAL).exists()
    monkeypatch.setattr(decisions, "atomic_json", original)
    snapshot = store.snapshot()
    assert all(q["definition"]["current_version"] == 1 for q in snapshot["questions"][:2])
    assert not (store.root / decisions.JOURNAL).exists()
    assert len(snapshot["decision_groups"][0]["confirmations"]) == 1


def test_conditional_and_reference_relationships_do_not_overblock(store):
    draft(store, "F-000001", [dep("F-000003", kind="reference")])
    approve(store, "F-000001")
    draft(
        store, "F-000002", [dep("F-000003", kind="conditional", active=False, condition="Only for route B")]
    )
    approve(store, "F-000002")
    assert store.read_question("F-000002")["readiness"]["status"] == "effective"


def test_ai_permissions_group_membership_and_human_messages(store):
    setup_group(store)
    group(store, "comment", {"text": "My concern", "question_id": "F-000001"}, "user")
    for op in ("begin", "approve", "select_option"):
        with pytest.raises(FreezeError, match="Only the user"):
            group(store, op)
    before = store.snapshot()["decision_groups"][0]
    update = {k: before[k] for k in ("title", "purpose", "member_ids", "options")}
    update["title"] = "Revised group title"
    group(store, "update", update)
    assert store.snapshot()["decision_groups"][0]["messages"] == before["messages"]
    with pytest.raises(FreezeError, match="another decision group"):
        store.change_group(None, "create", update, expected_revision=0, request_id="overlap", actor="codex")


def test_presentation_updates_choices_and_keeps_checks_out_of_discussion(store):
    change(
        store, "F-000001", "presentation", {"text": "Compare the actual outcomes.", "suggestions": ["A", "B"]}
    )
    q = change(store, "F-000001", "review_note", "SHA and inspected evidence")
    assert q["suggestions"] == ["A", "B"]
    assert "SHA" not in str(q["messages"])
    assert q["review_notes"][0]["text"].startswith("SHA")


def test_group_revision_only_advances_changed_members_and_bound_consumers(store):
    setup_group(store)
    draft(store, "F-000001")
    draft(store, "F-000002")
    confirm(store)
    group(store, "begin", actor="user")
    draft(store, "F-000001", text="Revised first rule")
    confirm(store)
    assert read_definition(store, "F-000001")["number"] == 2
    assert read_definition(store, "F-000002")["number"] == 1
    assert store.read_question("F-000002")["definition"]["draft"] is None
    group(store, "begin", actor="user")
    draft(store, "F-000002", [dep("F-000001")])
    confirm(store)
    group(store, "begin", actor="user")
    draft(store, "F-000001", text="Changed upstream within group")
    confirm(store)
    assert read_definition(store, "F-000001")["number"] == 3
    second = read_definition(store, "F-000002")
    assert second["number"] == 3 and second["dependencies"][0]["version"] == 3


def test_unrelated_question_edit_does_not_invalidate_group_approval(store):
    setup_group(store)
    draft(store, "F-000001")
    draft(store, "F-000002")
    token = store.snapshot()["decision_groups"][0]["approval_token"]
    change(store, "F-000003", "comment", "Unrelated discussion")
    assert store.snapshot()["decision_groups"][0]["approval_token"] == token
    group(store, "approve", token, "user")


def test_individual_dependency_change_requires_new_human_approval_token(store):
    draft(store, "F-000003")
    approve(store, "F-000003")
    draft(store, "F-000001")
    token = store.read_question("F-000001")["definition"]["draft"]["approval_token"]
    draft(store, "F-000001", [dep("F-000003")])
    with pytest.raises(FreezeError):
        change(store, "F-000001", "definition_approve", token, "user")
    assert store.read_question("F-000001")["definition"]["current_version"] is None


def test_conflicting_edit_after_group_token_does_not_partially_commit(store):
    setup_group(store)
    draft(store, "F-000001")
    draft(store, "F-000002")
    token = store.snapshot()["decision_groups"][0]["approval_token"]
    change(store, "F-000002", "definition_draft", "Human revision", "user")
    with pytest.raises(FreezeError, match="changed since read"):
        group(store, "approve", token, "user")
    assert all(q["definition"]["current_version"] is None for q in store.snapshot()["questions"])
    assert not (store.root / decisions.JOURNAL).exists()


def test_machine_evidence_separation_preserves_original_and_rejects_human_rewrite(store):
    q = change(
        store, "F-000001", "presentation", {"text": "Option A. SHA source receipt", "suggestions": ["A"]}
    )
    original = copy.deepcopy(q["messages"][-1])
    q = change(
        store,
        "F-000001",
        "review_note",
        {"text": "SHA source receipt", "source_message_id": original["id"], "discussion_text": "Option A."},
    )
    assert q["messages"][-1] == original
    assert q["discussion_display"][original["id"]] == "Option A."
    q = change(store, "F-000001", "comment", "Human rule", actor="user")
    with pytest.raises(FreezeError, match="Only AI discussion"):
        change(
            store,
            "F-000001",
            "review_note",
            {
                "text": "Private",
                "source_message_id": q["messages"][-1]["id"],
                "discussion_text": "Altered human rule",
            },
        )


def test_cancel_group_archives_candidates_and_keeps_formal_history_and_discussion(store):
    setup_group(store)
    draft(store, 'F-000001')
    draft(store, 'F-000002')
    confirm(store)
    group(store, 'comment', {'text': 'Keep this discussion'}, 'user')
    group(store, 'begin', actor='user')
    draft(store, 'F-000001', text='Saved revision')
    before = store.snapshot()
    g = before['decision_groups'][0]
    value = {
        'token': g['approval_token'],
        'edits': {'F-000001': {'text': '', 'request_id': 'unfinished-edit'}},
    }
    args = dict(expected_revision=g['revision'], request_id='cancel', actor='user')
    store.change_group(g['id'], 'discard', value, **args)
    assert store.change_group(g['id'], 'discard', value, **args)['replayed']
    after = store.snapshot()
    for old, new in zip(before['questions'][:2], after['questions'][:2], strict=True):
        assert new['definition']['draft'] is None
        assert new['definition']['versions'] == old['definition']['versions']
        assert new['definition']['current_version'] == 1
        assert new['status'] == 'frozen'
        assert len(new['definition']['withdrawn_drafts']) == 1
    withdrawn = after['questions'][0]['definition']['withdrawn_drafts'][0]
    assert withdrawn['text'] == 'Saved revision'
    assert withdrawn['local_edit'] == {'text': '', 'request_id': 'unfinished-edit', 'by': 'user'}
    assert after['decision_groups'][0]['messages'] == g['messages']
    assert after['decision_groups'][0]['confirmations'] == g['confirmations']


def test_cancel_rejects_stale_members_and_invalid_edits_without_partial_writes(store):
    setup_group(store)
    draft(store, 'F-000001')
    draft(store, 'F-000002')
    old = store.snapshot()['decision_groups'][0]
    draft(store, 'F-000002', text='Newer AI draft')
    before = store.snapshot()
    with pytest.raises(FreezeError, match='changed since read'):
        group(store, 'discard', {'token': old['approval_token']}, 'user')
    token = before['decision_groups'][0]['approval_token']
    for edits in ({'F-000003': {}}, {'F-000002': {'text': 'missing request'}}):
        with pytest.raises(FreezeError):
            group(store, 'discard', {'token': token, 'edits': edits}, 'user')
    assert store.snapshot() == before
    for actor in ('codex', 'chatgpt'):
        with pytest.raises(FreezeError, match='Only the user'):
            group(store, 'discard', {'token': token}, actor)


def test_cancel_recovery_is_atomic_after_interrupted_write(store, monkeypatch):
    setup_group(store)
    draft(store, 'F-000001')
    draft(store, 'F-000002')
    g = store.snapshot()['decision_groups'][0]
    original = decisions.atomic_json
    writes = []

    def interrupted(path, value):
        writes.append(path)
        if len(writes) == 2:
            raise OSError('interrupted cancel')
        return original(path, value)

    monkeypatch.setattr(decisions, 'atomic_json', interrupted)
    with pytest.raises(OSError):
        group(store, 'discard', {'token': g['approval_token']}, 'user')
    monkeypatch.setattr(decisions, 'atomic_json', original)
    recovered = store.snapshot()
    for q in recovered['questions'][:2]:
        assert q['definition']['draft'] is None
        assert q['definition']['current_version'] is None
        assert len(q['definition']['withdrawn_drafts']) == 1


def test_presentation_context_is_atomic_and_preserves_formal_and_user_history(store):
    before = change(store, "F-000001", "comment", "User discussion", actor="user")
    draft(store, "F-000001", text="Existing formal rule")
    q = store.read_question("F-000001")
    change(store, q["id"], "definition_approve", q["definition"]["draft"]["approval_token"], actor="user")
    before = store.read_question(q["id"])
    payload = {"text": "Current options", "suggestions": ["A", "B"],
               "why": "Current practical consequence", "source_summary": "Study design evidence"}
    after = change(store, q["id"], "presentation", payload)
    assert after["why"] == payload["why"] and after["source_summary"] == payload["source_summary"]
    assert after["ai_position"] == payload["text"] and after["suggestions"] == ["A", "B"]
    assert after["definition"] == before["definition"]
    assert all(m in after["messages"] for m in before["messages"])
    assert after["review_notes"][-1]["previous_context"]["why"] == before["why"]
    with pytest.raises(FreezeError):
        change(store, q["id"], "presentation", {**payload, "source_summary": ""})
    assert store.read_question(q["id"]) == after
    # Existing clients may omit these fields; later simple edits preserve them.
    simple = change(store, q["id"], "presentation", {"text": "Another proposal", "suggestions": []})
    assert simple["why"] == after["why"] and simple["source_summary"] == after["source_summary"]


def test_group_member_can_freeze_independently_with_unprepared_sibling(store):
    setup_group(store)
    draft(store, "F-000001")
    sibling = (store.root / "questions/F-000002.json").read_bytes()
    groups = (store.root / "decision-groups.json").read_bytes()
    q = store.read_question("F-000001")
    args = dict(expected_revision=q["revision"], request_id="member-confirm", actor="user")
    token = q["definition"]["draft"]["approval_token"]
    saved = store.change(q["id"], "definition_approve", token, **args)
    assert saved["definition"]["current_version"] == 1
    assert store.change(q["id"], "definition_approve", token, **args)["replayed"]
    assert (store.root / "questions/F-000002.json").read_bytes() == sibling
    assert (store.root / "decision-groups.json").read_bytes() == groups


def test_sequential_member_confirmation_resolves_initial_upstream_binding_on_review(store):
    setup_group(store)
    draft(store, "F-000001")
    draft(store, "F-000002", [dep("F-000001")])
    waiting = store.read_question("F-000002")
    with pytest.raises(FreezeError, match="等待前序"):
        approve(store, "F-000002")
    raw_before = (store.root / "questions/F-000002.json").read_bytes()
    approve(store, "F-000001")
    reviewed = store.read_question("F-000002")
    assert reviewed["readiness"]["status"] == "ready"
    assert reviewed["definition"]["draft"]["dependencies"][0]["version"] == 1
    assert (store.root / "questions/F-000002.json").read_bytes() == raw_before
    with pytest.raises(FreezeError, match="changed since read"):
        change(
            store, "F-000002", "definition_approve",
            waiting["definition"]["draft"]["approval_token"], "user",
        )
    approve(store, "F-000002")
    final = read_definition(store, "F-000002")
    assert final["text"] == reviewed["definition"]["draft"]["text"]
    assert final["dependencies"][0]["version"] == 1
    assert final["readiness"]["status"] == "effective"
    assert not store.snapshot()["decision_groups"][0]["confirmations"]


def test_initial_binding_rejects_upstream_change_after_individual_review(store):
    setup_group(store)
    draft(store, "F-000001")
    draft(store, "F-000002", [dep("F-000001")])
    approve(store, "F-000001")
    token = store.read_question("F-000002")["definition"]["draft"]["approval_token"]
    change(store, "F-000001", "definition_begin", actor="user")
    draft(store, "F-000001", text="Updated upstream rule")
    approve(store, "F-000001")
    with pytest.raises(FreezeError, match="changed since read"):
        change(store, "F-000002", "definition_approve", token, "user")
    assert store.read_question("F-000002")["definition"]["current_version"] is None


def test_existing_member_dependency_binding_is_not_silently_advanced(store):
    setup_group(store)
    draft(store, "F-000001")
    approve(store, "F-000001")
    draft(store, "F-000002", [dep("F-000001")])
    change(store, "F-000001", "definition_begin", actor="user")
    draft(store, "F-000001", text="Updated upstream rule")
    approve(store, "F-000001")
    q = store.read_question("F-000002")
    assert q["definition"]["draft"]["dependencies"][0]["version"] == 1
    assert q["readiness"]["status"] == "needs_review"
    with pytest.raises(FreezeError, match="前序口径已变化"):
        approve(store, "F-000002")


def test_optional_batch_after_individual_confirmation_keeps_existing_version(store):
    setup_group(store)
    draft(store, "F-000001")
    draft(store, "F-000002")
    approve(store, "F-000001")
    before = (store.root / "questions/F-000001.json").read_bytes()
    confirm(store)
    assert (store.root / "questions/F-000001.json").read_bytes() == before
    assert read_definition(store, "F-000002")["number"] == 1
