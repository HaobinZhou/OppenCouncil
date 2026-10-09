"""Historical recovery must preserve current authority, human edits and provenance."""

import copy
import hashlib

import pytest

from oppencouncil.recovery import recover_records
from oppencouncil.store import FreezeError, FreezeStore


@pytest.fixture
def legacy(tmp_path):
    (tmp_path / "Protocol").mkdir()
    (tmp_path / "Discussion").mkdir()
    (tmp_path / "project.md").write_text(
        "<!-- stepwise-r-project:v3 -->\n"
        "<!-- stepwise-r-project:canonical:start -->\n"
        "| Topic | Canonical path | Section | Contract test |\n"
        "| --- | --- | --- | --- |\n"
        "| time-zero | Protocol/design.md | 时间零点 | tests/contract.R |\n"
        "<!-- stepwise-r-project:canonical:end -->\n",
        encoding="utf-8",
    )
    (tmp_path / "Protocol/design.md").write_text(
        "# 方案\nStatus: partially-frozen\n## 时间零点\nStatus: frozen\n首次处方日作为时间零点。\n"
        "## 尚待讨论\nStatus: draft\n随访结束尚未确定。\n",
        encoding="utf-8",
    )
    (tmp_path / "Discussion/prior.md").write_text(
        "用户：我选择首次处方日。\nChatGPT：也可比较首次配药日。\n未署名：尚需核对月份。\n", encoding="utf-8"
    )
    return FreezeStore(tmp_path)


def source(store, path, excerpt, section=None):
    raw = (store.project / path).read_bytes()
    return {"path": path, "sha256": hashlib.sha256(raw).hexdigest(), "section": section, "excerpt": excerpt}


def frozen(store):
    return {
        "key": "canonical-time-zero",
        "kind": "frozen",
        "group": "时间与策略",
        "title": "时间零点",
        "summary": "首次处方日作为时间零点。",
        "canonical_topic": "time-zero",
        "canonical_source": 0,
        "sources": [
            source(store, "Protocol/design.md", "首次处方日作为时间零点。", "时间零点"),
            source(store, "Discussion/prior.md", "用户：我选择首次处方日。\nChatGPT：也可比较首次配药日。"),
        ],
        "messages": [
            {"actor": "user", "text": "我选择首次处方日。", "source": 1},
            {"actor": "chatgpt", "text": "也可比较首次配药日。", "source": 1},
        ],
    }


def discussion(store):
    return {
        "key": "prior-month-discussion",
        "kind": "discussion",
        "title": "月份如何核对？",
        "summary": "历史讨论仍需要核对月份；具体选择未恢复。",
        "sources": [source(store, "Discussion/prior.md", "未署名：尚需核对月份。")],
        "messages": [{"text": "尚需核对月份。", "source": 0}],
    }


def files(store):
    return {p.name: p.read_bytes() for p in store.root.rglob("*.json")}


def test_crlf_sources_preserve_raw_hash_and_match_multiline_quotes(legacy):
    for path in (legacy.project / "Protocol/design.md", legacy.project / "Discussion/prior.md"):
        raw = path.read_bytes().replace(b"\r\n", b"\n")
        path.write_bytes(raw.replace(b"\n", b"\r\n"))
    item = frozen(legacy)
    expected = item["sources"][1]["sha256"]
    result = recover_records(legacy, [item])
    recovered = legacy.read_question(result["ids"][0])["recovered_records"][0]
    assert recovered["sources"][1]["sha256"] == expected
    assert expected == hashlib.sha256((legacy.project / "Discussion/prior.md").read_bytes()).hexdigest()


def test_restore_frozen_discussion_and_uncertain_without_inventing_human_answer(legacy):
    before = (legacy.project / "Protocol/design.md").read_bytes()
    uncertain = copy.deepcopy(discussion(legacy))
    uncertain.update(key="uncertain", kind="unconfirmed", title="未确认的历史依据")
    result = recover_records(legacy, [frozen(legacy), discussion(legacy), uncertain])
    assert result["created"] == 3 and result["round"] == 1
    first, second, third = legacy.snapshot()["questions"]
    assert [q["status"] for q in [first, second, third]] == ["frozen", "discussing", "open"]
    assert all(q["user_answer"] is None for q in [first, second, third])
    assert first["canonical_ref"] == "Protocol/design.md#时间零点"
    assert [m["actor"] for m in first["messages"]] == ["user", "chatgpt"]
    assert all(m["recovered"] and m["at"] is None for m in first["messages"])
    assert second["messages"][0]["actor"] == "unknown"
    assert first["recovered_records"][0]["recovered_by"] == "codex"
    assert before == (legacy.project / "Protocol/design.md").read_bytes()
    saved = files(legacy)
    assert recover_records(legacy, [frozen(legacy), discussion(legacy), uncertain])["replayed"] == 3
    assert saved == files(legacy)


def test_attach_preserves_user_answer_messages_and_disagreement_and_replays_after_edits(legacy):
    qid = legacy.add_questions(
        [
            {
                "title": "时间零点？",
                "why": "已有问题",
                "source_summary": "原讨论",
            }
        ],
        request_id="initial",
    )["ids"][0]
    q = legacy.change(
        qid, "answer", "等待日级数据核对", expected_revision=1, request_id="human-answer", actor="user"
    )
    q = legacy.change(
        qid,
        "comment",
        "保留我的疑问",
        expected_revision=q["revision"],
        request_id="human-comment",
        actor="user",
    )
    item = frozen(legacy)
    item.update(question_id=qid, expected_revision=q["revision"])
    result = recover_records(legacy, [item])
    after = legacy.read_question(qid)
    assert result["created"] == 0 and result["attached"] == 1
    assert after["status"] == q["status"] == "discussing"
    assert after["user_answer"] == q["user_answer"]
    assert after["messages"][:1] == q["messages"]
    legacy.change(
        qid,
        "comment",
        "仍保留分歧",
        expected_revision=after["revision"],
        request_id="new-comment",
        actor="user",
    )
    saved = files(legacy)
    assert recover_records(legacy, [item])["replayed"] == 1
    assert saved == files(legacy)


def test_recovered_frozen_can_be_reopened_but_never_resolved_or_answered_by_ai(legacy):
    qid = recover_records(legacy, [frozen(legacy)])["ids"][0]
    q = legacy.read_question(qid)
    for operation in ["answer", "resolve", "recover", "freeze"]:
        with pytest.raises(FreezeError, match="unavailable"):
            legacy.change(
                qid,
                operation,
                "不能代答",
                expected_revision=q["revision"],
                request_id=operation,
                actor="chatgpt",
            )
    q = legacy.change(
        qid,
        "answer",
        "我希望讨论配药日起点",
        expected_revision=q["revision"],
        request_id="human-revision",
        actor="user",
    )
    assert q["status"] == "discussing"
    assert q["recovered_records"][0]["summary"] == "首次处方日作为时间零点。"
    assert q["canonical_ref"] == "Protocol/design.md#时间零点"


@pytest.mark.parametrize(
    "mutation",
    [
        "wrong-hash",
        "invented-quote",
        "invented-message",
        "invented-date",
        "wrong-topic",
        "wrong-section",
        "wrong-summary",
        "traversal",
        "duplicate-key",
        "stale-revision",
    ],
)
def test_invalid_batch_does_not_change_question_files(legacy, mutation):
    qid = recover_records(legacy, [discussion(legacy)])["ids"][0]
    saved = files(legacy)
    item = frozen(legacy)
    if mutation == "wrong-hash":
        item["sources"][0]["sha256"] = "0" * 64
    elif mutation == "invented-quote":
        item["sources"][0]["excerpt"] = "没有发生过的确认"
    elif mutation == "invented-message":
        item["messages"][0]["text"] = "从未说过的话"
    elif mutation == "invented-date":
        item["messages"][0]["at"] = "2025-01-01"
    elif mutation == "wrong-topic":
        item["canonical_topic"] = "not-registered"
    elif mutation == "wrong-section":
        item["sources"][0]["section"] = None
    elif mutation == "wrong-summary":
        item["summary"] = "不是原口径"
    elif mutation == "traversal":
        item["sources"][0]["path"] = "../project.md"
    elif mutation == "stale-revision":
        item.update(question_id=qid, expected_revision=0)
    batch = [item, copy.deepcopy(item)] if mutation == "duplicate-key" else [item]
    with pytest.raises(FreezeError):
        recover_records(legacy, batch)
    assert saved == files(legacy)


@pytest.mark.parametrize(
    "status",
    [
        "Status: draft",
        "> Status: frozen",
        "~~~\nStatus: frozen\n~~~",
        "<!-- Status: frozen -->",
        "Status: frozen\nStatus: draft",
    ],
)
def test_quoted_or_ambiguous_status_cannot_restore_a_frozen_definition(legacy, status):
    path = legacy.project / "Protocol/design.md"
    path.write_text("# 方案\n## 时间零点\n" + status + "\n首次处方日作为时间零点。\n", encoding="utf-8")
    with pytest.raises(FreezeError, match="unambiguously frozen"):
        recover_records(legacy, [frozen(legacy)])
    assert legacy.snapshot()["questions"] == []


def test_changed_recovery_key_and_symlink_are_rejected(legacy):
    item = frozen(legacy)
    recover_records(legacy, [item])
    changed = copy.deepcopy(item)
    changed["title"] = "不应重复恢复为另一个问题"
    with pytest.raises(FreezeError, match="different evidence"):
        recover_records(legacy, [changed])
    linked = legacy.project / "linked.md"
    try:
        linked.symlink_to(legacy.project / "Discussion/prior.md")
    except OSError:
        pytest.skip("Symlink privilege unavailable")
    item = discussion(legacy)
    item["sources"][0]["path"] = "linked.md"
    with pytest.raises(FreezeError, match="linked"):
        recover_records(legacy, [item])


def test_resume_interrupted_publication_reuses_receipt(legacy, monkeypatch):
    import oppencouncil.recovery as module

    write = module.atomic_json

    def interrupt(path, value):
        if path == legacy.manifest:
            raise OSError("interrupted publication")
        write(path, value)

    monkeypatch.setattr(module, "atomic_json", interrupt)
    with pytest.raises(OSError):
        recover_records(legacy, [frozen(legacy)])
    assert legacy.snapshot()["questions"] == []
    monkeypatch.setattr(module, "atomic_json", write)
    result = recover_records(legacy, [frozen(legacy)])
    assert result["ids"] == ["F-000001"] and result["replayed"] == 1
    assert len(legacy.snapshot()["questions"]) == 1


def partial_item(store):
    (store.project / "project.md").write_text(
        "<!-- stepwise-r-project:v3 -->\n<!-- stepwise-r-project:canonical:start -->\n"
        "| study-protocol | Protocol/design.md | - | tests/contract.R |\n"
        "<!-- stepwise-r-project:canonical:end -->\n", encoding="utf-8"
    )
    (store.project / "Protocol/design.md").write_text(
        "Status: partially-frozen\n已冻结：主分析索引月不早于 2016-01。\n随访起点仍待确认。\n",
        encoding="utf-8"
    )
    return {
        "key": "index-floor-verified", "kind": "frozen", "title": "索引下限", "group": "时间",
        "summary": "主分析索引月不早于 2016-01。", "canonical_topic": "study-protocol",
        "canonical_source": 0, "canonical_scope": "item",
        "reason": "当前条目明确冻结；核对后续记录未发现重新打开。整体协议仍有待确认事项。",
        "sources": [source(store, "Protocol/design.md", "已冻结：主分析索引月不早于 2016-01。")],
    }


def incorrect_record(store):
    item = discussion(store)
    item.update(key="wrong-index-classification", kind="unconfirmed", title="错误待核")
    return item


def correction(store, qid):
    item = partial_item(store)
    item.update(question_id=qid, expected_revision=store.read_question(qid)["revision"],
                supersedes="wrong-index-classification")
    return item


def test_partial_item_explicit_evidence_without_promoting_entire_protocol(legacy):
    item = partial_item(legacy)
    protocol = (legacy.project / "Protocol/design.md").read_bytes()
    result = recover_records(legacy, [item], dry_run=True)
    assert result["dry_run"] and result["created"] == 1
    assert not legacy.root.exists()
    qid = recover_records(legacy, [item])["ids"][0]
    q = legacy.read_question(qid)
    assert q["status"] == "frozen" and q["user_answer"] is None
    assert q["canonical_ref"] == "Protocol/design.md"
    assert protocol == (legacy.project / "Protocol/design.md").read_bytes()


@pytest.mark.parametrize("excerpt", [
    "主分析索引月不早于 2016-01。",
    "> 已冻结：主分析索引月不早于 2016-01。",
    "~~~\n已冻结：主分析索引月不早于 2016-01。\n~~~",
    "<!-- 已冻结：主分析索引月不早于 2016-01。 -->",
    "已冻结：主分析索引月不早于 2016-01。现重新打开。",
    "已冻结：主分析索引月不早于 2016-01。但该问题待确认。",
])
def test_item_recovery_rejects_implicit_quoted_or_reopened_freeze(legacy, excerpt):
    item = partial_item(legacy)
    path = legacy.project / "Protocol/design.md"
    path.write_text("Status: partially-frozen\n" + excerpt + "\n", encoding="utf-8")
    item["sources"] = [source(legacy, "Protocol/design.md", excerpt)]
    with pytest.raises(FreezeError):
        recover_records(legacy, [item], dry_run=True)
    assert not legacy.root.exists()


def test_reconcile_keeps_ids_original_evidence_and_replays_without_new_round(legacy):
    original = incorrect_record(legacy)
    qid = recover_records(legacy, [original])["ids"][0]
    before = legacy.read_question(qid)
    item = correction(legacy, qid)
    saved = files(legacy)
    result = recover_records(legacy, [item], reconcile=True, dry_run=True)
    assert result["created"] == 0 and result["corrections"][0]["after"] == "frozen"
    assert saved == files(legacy)
    result = recover_records(legacy, [item], reconcile=True)
    after = legacy.read_question(qid)
    assert result["ids"] == [qid] and result["round"] == before["round"] == 1
    assert after["status"] == "frozen" and after["revision"] == before["revision"] + 1
    assert after["recovered_records"][:1] == before["recovered_records"]
    assert after["messages"] == before["messages"]
    assert after["recovery_classification"]["kind"] == "frozen"
    assert after["recovered_records"][-1]["supersedes"] == original["key"]
    assert after["recovered_records"][-1]["previous_display"]["title"] == before["title"]
    saved = files(legacy)
    assert recover_records(legacy, [item], reconcile=True)["replayed"] == 1
    # Old 0.1.1 request still replays without undoing the correction.
    assert recover_records(legacy, [original])["replayed"] == 1
    assert saved == files(legacy) and len(legacy.snapshot()["questions"]) == 1


@pytest.mark.parametrize("interaction", ["answer", "comment", "reopen", "resolve"])
def test_reconcile_preserves_saved_answer_live_author_and_dispute(legacy, interaction):
    qid = recover_records(legacy, [incorrect_record(legacy)])["ids"][0]
    q = legacy.read_question(qid)
    if interaction == "resolve":
        q = legacy.change(qid, "answer", "我的原始答复", expected_revision=q["revision"],
                          request_id="original-answer", actor="user")
    q = legacy.change(qid, interaction, "保留原文与分歧", expected_revision=q["revision"],
                      request_id="live-interaction", actor="codex" if interaction == "reopen" else "user")
    item = correction(legacy, qid)
    result = recover_records(legacy, [item], reconcile=True)
    after = legacy.read_question(qid)
    assert after["status"] == q["status"]
    assert after["user_answer"] == q["user_answer"]
    assert after["messages"] == q["messages"]
    assert after["requests"] == q["requests"]
    assert after["recovery_classification"]["kind"] == "frozen"
    assert result["corrections"][0]["review_preserved"]


@pytest.mark.parametrize("mutation", ["stale", "wrong-receipt", "same-key", "changed-source"])
def test_reconcile_rejects_conflicts_before_any_question_write(legacy, mutation):
    ids = recover_records(legacy, [incorrect_record(legacy), discussion(legacy)])["ids"]
    first = correction(legacy, ids[0])
    second = copy.deepcopy(first)
    second.update(key="other-correction", question_id=ids[1], supersedes="prior-month-discussion")
    if mutation == "stale":
        second["expected_revision"] = 0
    elif mutation == "wrong-receipt":
        second["supersedes"] = "wrong-index-classification"
    elif mutation == "same-key":
        second["key"] = second["supersedes"]
    else:
        second["sources"][0]["sha256"] = "0" * 64
    saved = files(legacy)
    with pytest.raises(FreezeError):
        recover_records(legacy, [first, second], reconcile=True)
    assert files(legacy) == saved


def test_settled_history_is_not_pending_and_can_be_reopened(legacy):
    qid = recover_records(legacy, [discussion(legacy)])["ids"][0]
    item = frozen(legacy)
    item.update(key="settled-month-history", kind="historical", question_id=qid,
                expected_revision=legacy.read_question(qid)["revision"], supersedes="prior-month-discussion",
                resolution="首次处方日作为时间零点。", reason="原讨论已由现行方案取代；不再是待回答问题。")
    recover_records(legacy, [item], reconcile=True)
    q = legacy.read_question(qid)
    assert q["status"] == "historical" and not q["user_answer"]
    assert q["messages"][0]["actor"] == "unknown"
    q = legacy.change(qid, "answer", "我希望重新讨论", expected_revision=q["revision"],
                      request_id="reopen-history", actor="user")
    assert q["status"] == "discussing"
    assert q["recovery_classification"]["kind"] == "historical"


def test_reconcile_retry_after_interrupted_manifest_keeps_correction(legacy, monkeypatch):
    import oppencouncil.recovery as module
    qid = recover_records(legacy, [incorrect_record(legacy)])["ids"][0]
    item = correction(legacy, qid)
    write = module.atomic_json
    def interrupt(path, value):
        if path == legacy.manifest:
            raise OSError("interrupted publication")
        write(path, value)
    monkeypatch.setattr(module, "atomic_json", interrupt)
    with pytest.raises(OSError):
        recover_records(legacy, [item], reconcile=True)
    monkeypatch.setattr(module, "atomic_json", write)
    assert recover_records(legacy, [item], reconcile=True)["replayed"] == 1
    assert legacy.read_question(qid)["status"] == "frozen"
    assert len(legacy.read_question(qid)["recovered_records"]) == 2


@pytest.mark.parametrize("status", ["frozen", "partially-frozen", "draft"])
def test_steward_recovery_uses_native_status_and_exact_owner(tmp_path, status):
    native = tmp_path / ".oppen-project-steward"
    native.mkdir()
    registry = native / "registry.md"
    registry.write_text(
        "<!-- oppen-project-steward:v3 -->\n"
        "<!-- oppen-project-steward:canonical:start -->\n"
        f"| time-zero | design.md | 时间零点 | {status} | test.py |\n"
        "<!-- oppen-project-steward:canonical:end -->\n"
    , encoding="utf-8")
    (tmp_path / "design.md").write_text("# 方案\n## 时间零点\n首次处方日作为时间零点。\n", encoding="utf-8")
    store = FreezeStore(tmp_path)
    item = {
        "key": "canonical-time-zero", "kind": "frozen", "group": "时间与策略",
        "title": "时间零点", "summary": "首次处方日作为时间零点。",
        "canonical_topic": "time-zero", "canonical_source": 0,
        "sources": [source(store, "design.md", "首次处方日作为时间零点。", "时间零点")],
        "messages": [],
    }
    before = registry.read_bytes()
    if status == "frozen":
        assert recover_records(store, [item])["created"] == 1
        assert store.snapshot()["questions"][0]["status"] == "frozen"
        assert recover_records(store, [item])["replayed"] == 1
        # Registry approval cannot override a conflicting live owner status.
        (tmp_path / "design.md").write_text(
            "# 方案\n## 时间零点\nStatus: draft\n首次处方日作为时间零点。\n", encoding="utf-8"
        )
        item["key"] = "conflicting-current-status"
        item["sources"] = [source(store, "design.md", "首次处方日作为时间零点。", "时间零点")]
        with pytest.raises(FreezeError, match="not unambiguously frozen"):
            recover_records(store, [item])
    else:
        with pytest.raises(FreezeError, match="not unambiguously frozen"):
            recover_records(store, [item])
        item.update(
            kind="historical", resolution=item["summary"],
            reason="Already settled source direction; full analysis pending.",
        )
        assert recover_records(store, [item])["created"] == 1
        assert store.snapshot()["questions"][0]["status"] == "historical"
    assert registry.read_bytes() == before and not (tmp_path / "project.md").exists()
    wrong = copy.deepcopy(item)
    wrong["key"] = "wrong-native-topic"
    wrong["canonical_topic"] = "not-registered"
    with pytest.raises(FreezeError, match="must match"):
        recover_records(store, [wrong])
