"""One authority: confirmation, readers, independent versions and no silent migration."""

import copy
import hashlib
import json

import pytest

from oppencouncil.definitions import read_definition, render_definition
from oppencouncil.recovery import recover_records
from oppencouncil.store import FreezeError, FreezeStore


@pytest.fixture(params=[(skill, version) for skill in ("stepwise-r-project", "oppen-project-steward")
                        for version in (3, 4)])
def store(tmp_path, request):
    skill, version = request.param
    marker = tmp_path / ("project.md" if skill == "stepwise-r-project"
                         else ".oppen-project-steward/registry.md")
    marker.parent.mkdir(exist_ok=True)
    marker.write_text(f"<!-- {skill}:v{version} -->\n")
    result = FreezeStore(tmp_path)
    result.add_questions([{"title": "何时刷新？", "why": "决定可见性", "ai_position": "比较刷新方案"},
                          {"title": "失败如何恢复？", "why": "独立决策"}], request_id="round")
    return result


def change(store, operation, value=None, actor="user", qid="F-000001", request_id=None):
    q = store.read_question(qid)
    return store.change(qid, operation, value, actor=actor, expected_revision=q["revision"],
                        request_id=request_id or f"{operation}-{q['revision']}")


def approve(store, text):
    q = change(store, "definition_draft", text, actor="codex")
    return change(store, "definition_approve", q["definition"]["draft"]["text_sha256"])


def test_confirm_immediately_makes_exact_text_the_only_source(store):
    text = "保存后通知在线页面刷新。\n断线恢复时重新读取项目记录。"
    q = approve(store, text)
    assert q["definition"]["current_version"] == 1
    assert q["definition"]["draft"] is None
    assert q["status"] == "frozen"
    version = read_definition(store, q["id"])
    assert version["text"] == text and version["effective"]
    assert render_definition(version).endswith(text + "\n")
    assert store.snapshot()["questions"][0]["definition"]["versions"][0]["text"] == text
    disk = json.loads((store.questions / f"{q['id']}.json").read_text())
    assert disk["definition"] == q["definition"]
    assert q["canonical_ref"] == f"Freeze/questions/{q['id']}.json#/definition"
    assert not (store.project / "policy.md").exists()


def test_independent_revisions_preserve_effective_version_until_next_confirmation(store):
    first = approve(store, "第一版完整规则。")
    old = copy.deepcopy(first["definition"]["versions"][0])
    assert store.read_question("F-000002")["definition"]["current_version"] is None
    with pytest.raises(FreezeError, match="Open a revision"):
        change(store, "definition_draft", "悄悄替换", actor="chatgpt")
    change(store, "reopen", "讨论另一种策略", actor="codex")
    assert read_definition(store, first["id"])["text"] == old["text"]
    change(store, "definition_begin")
    change(store, "definition_draft", "第二版完整规则。", actor="chatgpt")
    assert read_definition(store, first["id"])["text"] == old["text"]
    second = approve(store, "第二版完整规则。")
    assert second["definition"]["current_version"] == 2
    assert second["definition"]["versions"][0] == old
    assert second["definition"]["versions"][1]["supersedes"] == 1
    assert not read_definition(store, first["id"], 1)["effective"]
    assert store.read_question("F-000002")["definition"]["current_version"] is None


def test_ai_cannot_confirm_begin_or_withdraw_and_stale_writes_fail(store):
    q = change(store, "definition_draft", "完整候选。", actor="codex")
    for actor in ("codex", "chatgpt"):
        for operation in ("definition_approve", "definition_begin", "definition_discard"):
            with pytest.raises(FreezeError, match="Only the user"):
                change(store, operation, q["definition"]["draft"]["text_sha256"], actor=actor)
    change(store, "definition_draft", "人类修改后的候选。")
    with pytest.raises(FreezeError, match="changed since read"):
        store.change(q["id"], "definition_draft", "陈旧 AI 覆盖", actor="codex",
                     expected_revision=q["revision"], request_id="stale")
    with pytest.raises(FreezeError, match="changed since read"):
        change(store, "definition_approve", q["definition"]["draft"]["text_sha256"])


def test_confirmation_retry_is_idempotent_and_withdrawal_keeps_current(store):
    q = change(store, "definition_draft", "完整候选。", actor="codex")
    args = dict(expected_revision=q["revision"], request_id="confirm", actor="user")
    value = q["definition"]["draft"]["text_sha256"]
    first = store.change(q["id"], "definition_approve", value, **args)
    retry = store.change(q["id"], "definition_approve", value, **args)
    assert retry["replayed"] and retry["definition"] == first["definition"]
    opened = change(store, "definition_begin")
    with pytest.raises(FreezeError, match="unchanged"):
        change(store, "definition_approve", opened["definition"]["draft"]["text_sha256"])
    change(store, "definition_draft", "撤回的候选", actor="codex")
    q = change(store, "definition_discard")
    assert q["definition"]["withdrawn_drafts"][0]["text"] == "撤回的候选"
    assert read_definition(store, q["id"])["text"] == "完整候选。"


def test_legacy_answers_and_suggestions_remain_discussion(store):
    q = change(store, "answer", "选 A")
    assert not q["definition"]["versions"]
    assert q["messages"][0]["text"] == "比较刷新方案"
    assert q["messages"][0]["kind"] == "proposal"
    with pytest.raises(FreezeError, match="no effective"):
        read_definition(store, q["id"])
    first = change(store, "definition_draft", "完整规则。", actor="codex", request_id="draft-save")
    retry = store.change(q["id"], "definition_draft", "完整规则。", actor="codex",
                         expected_revision=q["revision"], request_id="draft-save")
    assert retry["replayed"] and retry["definition"] == first["definition"]
    assert retry["user_answer"] == "选 A"


@pytest.mark.parametrize("damage", ["text", "approval", "pointer"])
def test_every_reader_rejects_corrupted_formal_records(store, damage):
    q = approve(store, "完整已确认规则。")
    if damage == "text":
        q["definition"]["versions"][0]["text"] = "另一个版本"
    elif damage == "approval":
        q["definition"]["versions"][0]["approval"]["by"] = "codex"
    else:
        q["definition"]["current_version"] = 0
    (store.questions / f"{q['id']}.json").write_text(json.dumps(q))
    readers = (store.snapshot, lambda: store.read_question(q["id"]),
               lambda: read_definition(store, q["id"]))
    for read in readers:
        with pytest.raises(FreezeError, match="Invalid definition"):
            read()


def test_recovering_old_discussion_cannot_replace_the_formal_source(store):
    q = approve(store, "当前完整规则。")
    original = copy.deepcopy(q["definition"])
    note = store.project / "note.md"
    note.write_text("旧的讨论")
    recover_records(store, [{
        "key": "older-note", "kind": "discussion", "title": "旧讨论",
        "question_id": q["id"], "expected_revision": q["revision"], "summary": "旧的讨论",
        "sources": [{"path": "note.md", "sha256": hashlib.sha256(note.read_bytes()).hexdigest(),
                     "excerpt": "旧的讨论"}], "messages": [],
    }])
    after = store.read_question(q["id"])
    assert after["definition"] == original
    assert after["canonical_ref"] == q["canonical_ref"]
