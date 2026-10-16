"""Conversation actions use the same state, prerequisites and atomic writes as the webpage."""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
from test_workflow_v5 import approve, prepare, research_handoff, save, stage
from test_workflow_v5 import work as work_fixture

from oppencouncil import decisions
from oppencouncil.human_actions import execute
from oppencouncil.store import FreezeError, FreezeStore

work = work_fixture


def action(work, operation, value=None, identifier="F-000001", instruction="确认刚才展示的完整口径"):
    revision = work.read(identifier)["revision"]
    return {
        "request_id": f"chat-{identifier}-{revision}-{operation}", "id": identifier,
        "operation": operation, "value": value, "expected_revision": revision,
        "authorization": {"source": "conversation", "instruction": instruction,
                          "thread_id": "synthetic-thread", "message_id": "synthetic-message"},
    }


def confirm(work):
    return action(work, "definition_approve", work.read("F-000001")["candidate"]["approval_token"])


def files(store):
    return {p.relative_to(store.root).as_posix(): p.read_bytes()
            for p in store.root.rglob("*.json") if p.is_file()}


def test_chat_confirmation_shared_readback_replay_and_provenance(work):
    prepare(work)
    payload = confirm(work)
    execute(work.store, payload)
    record = work.store.snapshot()["questions"][0]
    version = record["definition"]["versions"][0]
    assert version["text"] == "Complete current rule"
    assert version["approval"]["by"] == "user"
    assert version["approval"]["authorization"]["executed_by"] == "codex"
    assert version["approval"]["authorization"]["instruction"] == payload["authorization"]["instruction"]
    assert work.read(record["id"])["human_actions"][0]["version"] == 1
    before = files(work.store)
    assert execute(work.store, payload)["result"]["replayed"]
    assert files(work.store) == before
    altered = copy.deepcopy(payload)
    altered["authorization"]["instruction"] = "Different instruction"
    with pytest.raises(FreezeError, match="request_id"):
        execute(work.store, altered)
    assert files(work.store) == before


@pytest.mark.parametrize("authorization", [None, {}, {"source": "external_ai", "instruction": "yes"},
                                          {"source": "conversation", "instruction": "  "}])
def test_missing_or_external_authorization_cannot_mutate(work, authorization):
    prepare(work)
    payload = confirm(work)
    payload["authorization"] = authorization
    before = files(work.store)
    with pytest.raises(FreezeError):
        execute(work.store, payload)
    assert files(work.store) == before


def test_authorization_cannot_override_actor_or_curate_work(work):
    prepare(work)
    payload = confirm(work)
    before = files(work.store)
    with pytest.raises(FreezeError):
        execute(work.store, {**payload, "actor": "user"})
    for operation in ("work", "create", "update", "evidence_submit"):
        with pytest.raises(FreezeError):
            execute(work.store, {**payload, "operation": operation})
    with pytest.raises(FreezeError):
        work.commit_work(
            {"read_set": {"F-000001": payload["expected_revision"]},
             "changes": [{"id": "F-000001", "definition": {
                 "operation": "definition_approve", "value": payload["value"]}}]},
            request_id="ordinary-ai", actor="codex",
        )
    assert files(work.store) == before


def test_stale_candidate_and_stale_evidence_tokens_cannot_be_reused(work):
    prepare(work)
    payload = confirm(work)
    prepare(work, "Changed complete rule")
    before = files(work.store)
    with pytest.raises(FreezeError, match="changed since read"):
        execute(work.store, payload)
    payload["expected_revision"] = work.read("F-000001")["revision"]
    with pytest.raises(FreezeError, match="changed since read"):
        execute(work.store, payload)
    assert files(work.store) == before
    payload = confirm(work)
    save(work, {"review_basis": {"claims": [], "summary": "New basis"}, "phase": stage()})
    payload["expected_revision"] = work.read("F-000001")["revision"]
    with pytest.raises(FreezeError, match="changed since read"):
        execute(work.store, payload)


def test_unprepared_candidate_and_handoff_still_block_confirmation(work):
    save(work, {"definition": {"operation": "definition_draft", "value": "Complete proposal"}})
    before = files(work.store)
    with pytest.raises(FreezeError, match="review|trigger"):
        execute(work.store, confirm(work))
    assert files(work.store) == before
    prepare(work)
    save(work, {"pending": [research_handoff()]})
    before = files(work.store)
    with pytest.raises(FreezeError, match="review|handoff|trigger"):
        execute(work.store, confirm(work))
    assert files(work.store) == before


def test_dialogue_comment_is_human_feedback_and_edit_requires_preparation(work):
    prepare(work)
    execute(work.store, action(work, "comment", "请解释这个窗口的依据", instruction="请解释这个窗口的依据"))
    read = work.read("F-000001")
    assert read["messages"][-1]["actor"] == "user"
    assert read["messages"][-1]["authorization"]["source"] == "conversation"
    assert any(e["actor"] == "user" for e in read["inputs"])
    execute(work.store, action(work, "definition_draft", "Explicit edited wording",
                               instruction="改成刚才展示的新规则并保存候选"))
    assert work.read("F-000001")["candidate"]["text"] == "Explicit edited wording"
    with pytest.raises(FreezeError):
        execute(work.store, confirm(work))
    save(work, {"phase": stage()})
    execute(work.store, confirm(work))
    original = copy.deepcopy(work.store.read_question("F-000001")["definition"]["versions"])
    execute(work.store, action(work, "definition_begin", instruction="开启修订"))
    execute(work.store, action(work, "definition_discard", instruction="撤回这次修订"))
    assert work.store.read_question("F-000001")["definition"]["versions"] == original
    assert work.read("F-000001")["candidate"] is None


def test_reconfirmation_keeps_version_and_original_approval(work):
    prepare(work)
    approve(work)
    before = copy.deepcopy(work.store.read_question("F-000001")["definition"]["versions"][0])
    save(work, {"evidence_impact": {"classification": "weakened", "reason": "New fact"},
                "review_basis": {"claims": [], "summary": "Reassessed"}})
    save(work, {"phase": stage()})
    payload = action(work, "definition_reconfirm", work.read("F-000001")["reconfirmation_token"])
    execute(work.store, payload)
    versions = work.store.read_question("F-000001")["definition"]["versions"]
    assert len(versions) == 1
    assert {k: v for k, v in versions[0].items() if k != "reconfirmations"} == before
    assert versions[0]["reconfirmations"][0]["authorization"]["source"] == "conversation"
    execute(work.store, payload)
    assert len(work.read("F-000001")["current"]["reconfirmations"]) == 1


def setup_group(work):
    work.add([{"title": "Second", "why": "Related decision"}], request_id="second", actor="codex")
    for identifier in ("F-000001", "F-000002"):
        prepare(work, identifier=identifier)
    return work.store.change_group(None, "create", {
        "title": "Related decisions", "purpose": "Discuss together",
        "member_ids": ["F-000001", "F-000002"],
        "options": [{"label": "A", "rules": {"F-000001": "Rule 1", "F-000002": "Rule 2"},
                     "consequences": "Effect", "tradeoffs": "Cost"}],
    }, expected_revision=0, request_id="create-group", actor="codex")


def test_group_preference_discussion_confirmation_begin_discard(work):
    group = setup_group(work)
    identifier = group["id"]
    execute(work.store, action(work, "select_option", 0, identifier, "倾向 A，暂不确认"))
    assert all(q["definition"]["current_version"] is None for q in work.store.snapshot()["questions"])
    execute(work.store, action(work, "comment", {"text": "这组确认刚才的完整口径", "question_id": "F-000001"},
                               identifier, "这组确认刚才的完整口径"))
    group = work.store.read_group(identifier)
    payload = action(work, "approve", group["approval_token"], identifier)
    execute(work.store, payload)
    group = work.store.read_group(identifier)
    assert group["confirmations"][-1]["authorization"]["executed_by"] == "codex"
    for q in work.store.snapshot()["questions"]:
        assert q["definition"]["current_version"] == 1
        assert q["human_actions"][-1]["group_id"] == identifier
        assert q["definition"]["versions"][0]["approval"]["authorization"]["source"] == "conversation"
    before = files(work.store)
    execute(work.store, payload)
    assert files(work.store) == before
    execute(work.store, action(work, "begin", None, identifier, "开启整组修订"))
    token = work.store.read_group(identifier)["approval_token"]
    execute(work.store, action(work, "discard", {"token": token}, identifier, "撤回整组修订"))
    assert all(q["definition"]["draft"] is None for q in work.store.snapshot()["questions"])


def test_group_conflict_or_incomplete_member_does_not_partially_confirm(work):
    group = setup_group(work)
    payload = action(work, "approve", group["approval_token"], group["id"])
    save(work, {"id": "F-000002", "definition": {"operation": "definition_draft", "value": "New rule"}})
    before = files(work.store)
    with pytest.raises(FreezeError):
        execute(work.store, payload)
    payload["value"] = work.store.read_group(group["id"])["approval_token"]
    with pytest.raises(FreezeError, match="prepared"):
        execute(work.store, payload)
    assert files(work.store) == before


def test_receipt_and_confirmation_recover_together_after_interrupted_write(work, monkeypatch):
    prepare(work)
    payload = confirm(work)
    original = decisions.atomic_json

    def interrupted(*args, **kwargs):
        raise OSError("Synthetic interrupted publish")

    monkeypatch.setattr(decisions, "atomic_json", interrupted)
    with pytest.raises(OSError):
        execute(work.store, payload)
    monkeypatch.setattr(decisions, "atomic_json", original)
    recovered = execute(work.store, payload)
    assert recovered["result"]["replayed"]
    q = work.store.read_question("F-000001")
    assert len(q["definition"]["versions"]) == len(q["human_actions"]) == 1


def test_investigation_feedback_uses_same_human_queue(work):
    result = work.investigation({"title": "Check", "why": "Missing fact", "dedupe_key": "one"},
                                request_id="investigate", actor="codex")
    identifier = result["id"]
    execute(work.store, action(work, "comment", "先核查来源", identifier, "先核查来源"))
    record = work.read(identifier)
    assert record["messages"][-1]["actor"] == "user"
    assert record["human_actions"][-1]["operation"] == "comment"


@pytest.mark.parametrize("generation", [3, 4])
def test_legacy_human_actions_preserve_generation(tmp_path, generation):
    marker = tmp_path / "project.md"
    marker.write_text(f"<!-- stepwise-r-project:v{generation} -->\n")
    store = FreezeStore(tmp_path)
    store.add_questions([{"title": "Rule", "why": "Choice"}], request_id="create")
    q = store.read_question("F-000001")
    payload = {"request_id": "comment", "id": q["id"], "operation": "comment", "value": "继续讨论",
               "expected_revision": q["revision"],
               "authorization": {"source": "conversation", "instruction": "继续讨论"}}
    execute(store, payload)
    q = store.read_question(q["id"])
    assert q["messages"][-1]["authorization"]["source"] == "conversation"
    for operation, value in [("definition_draft", "Complete legacy rule"), ("definition_approve", None)]:
        if operation == "definition_approve":
            value = q["definition"]["draft"]["approval_token"]
        payload.update(
            request_id=operation, operation=operation, value=value, expected_revision=q["revision"]
        )
        execute(store, payload)
        q = store.read_question(q["id"])
    assert q["definition"]["current_version"] == 1
    assert marker.read_text() == f"<!-- stepwise-r-project:v{generation} -->\n"


def test_actual_skill_entrypoint_and_cli_share_results(work, tmp_path):
    prepare(work)
    payload = confirm(work)
    path = tmp_path / "action.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    root = Path(__file__).resolve().parents[2]
    script = root / "skills/oppencouncil/scripts/oppencouncil.py"
    run = subprocess.run([sys.executable, str(script), "human-action", str(work.store.project),
                          "--input", str(path)], capture_output=True, encoding="utf-8")
    assert run.returncode == 0, run.stderr
    result = json.loads(run.stdout)
    assert result["channel"] == "conversation"
    assert result["result"]["human_actions"][0]["instruction"] == payload["authorization"]["instruction"]
    assert work.read("F-000001")["current"]["number"] == 1
