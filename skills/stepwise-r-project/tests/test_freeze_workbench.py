"""The skill delegates registration and review to external OppenCouncil."""

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from oppencouncil.registry import Registry
from oppencouncil.service import info, stop
from oppencouncil.store import FreezeStore

SOURCE = Path(__file__).resolve().parents[1] / "scripts"


def test_storage_shim_uses_the_installed_shared_store():
    spec = importlib.util.spec_from_file_location("skill_freeze_store", SOURCE / "freeze_store.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.FreezeStore is FreezeStore


def test_skill_recovery_restores_existing_canonical_without_a_human_answer(tmp_path):
    project = tmp_path / "旧项目"
    project.mkdir()
    (project / "project.md").write_text(
        "<!-- stepwise-r-project:v3 -->\n<!-- stepwise-r-project:canonical:start -->\n"
        "| time-zero | protocol.md | - | tests/contract.R |\n"
        "<!-- stepwise-r-project:canonical:end -->\n", encoding="utf-8")
    source = project / "protocol.md"
    source.write_text("Status: frozen\n首次处方日。\n", encoding="utf-8")
    history = tmp_path / "history.json"
    history.write_text(json.dumps({"records": [{
        "key": "time-zero", "kind": "frozen", "title": "时间零点",
        "summary": "首次处方日。", "canonical_topic": "time-zero", "canonical_source": 0,
        "sources": [{"path": "protocol.md", "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                     "excerpt": "首次处方日。"}],
    }]}), encoding="utf-8")
    directory = tmp_path / "site"
    command = [sys.executable, str(SOURCE / "freeze_workbench.py"), "recover", str(project),
               "--input", str(history), "--directory", str(directory)]
    result = subprocess.run(command, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["created"] == 1
    q = FreezeStore(project).snapshot()["questions"][0]
    assert q["status"] == "frozen" and q["user_answer"] is None
    assert q["canonical_ref"] == "protocol.md"
    assert len(Registry(directory).read()) == 1
    result = subprocess.run(command, text=True, capture_output=True)
    assert result.returncode == 0 and json.loads(result.stdout)["replayed"] == 1


def test_partial_item_recovery_and_in_place_correction_use_shared_cli(tmp_path):
    project = tmp_path / "部分冻结协议"
    project.mkdir()
    (project / "project.md").write_text(
        "<!-- stepwise-r-project:v3 -->\n<!-- stepwise-r-project:canonical:start -->\n"
        "| study-protocol | protocol.md | - | tests/contract.R |\n"
        "<!-- stepwise-r-project:canonical:end -->\n", encoding="utf-8")
    source = project / "protocol.md"
    source.write_text("Status: partially-frozen\n已冻结：主分析索引月不早于 2016-01。\n"
                      "随访起点仍待确认。\n", encoding="utf-8")
    before = source.read_bytes()
    history = tmp_path / "history.json"
    history.write_text(json.dumps({"records": [{
        "key": "index-floor", "kind": "frozen", "title": "索引下限",
        "summary": "主分析索引月不早于 2016-01。",
        "canonical_topic": "study-protocol", "canonical_source": 0,
        "sources": [{"path": "protocol.md", "sha256": hashlib.sha256(before).hexdigest(),
                     "excerpt": "已冻结：主分析索引月不早于 2016-01。"}],
    }]}), encoding="utf-8")
    directory = tmp_path / "site"
    result = subprocess.run([sys.executable, str(SOURCE / "freeze_workbench.py"),
        "recover", str(project), "--input", str(history), "--directory", str(directory)],
        text=True, capture_output=True)
    assert result.returncode == 2
    assert "not unambiguously frozen" in result.stderr
    assert source.read_bytes() == before
    assert FreezeStore(project).snapshot()["questions"] == []
    assert not (directory / "projects.local.json").exists()

    # 0.1.2 provides an explicit item mode; default owner validation stays strict.
    payload = json.loads(history.read_text())
    item = payload["records"][0]
    item.update(canonical_scope="item", reason="当前原文明确已冻结，后续无重新打开证据。")
    history.write_text(json.dumps(payload), encoding="utf-8")
    base = [sys.executable, str(SOURCE / "freeze_workbench.py")]
    args = [str(project), "--input", str(history), "--directory", str(directory)]
    checked = subprocess.run(base + ["recover"] + args + ["--check"], text=True, capture_output=True)
    assert checked.returncode == 0, checked.stderr
    assert json.loads(checked.stdout)["dry_run"]
    assert FreezeStore(project).snapshot()["questions"] == []
    assert not (directory / "projects.local.json").exists()

    store = FreezeStore(project)
    wrong = dict(item, key="bad-classification", kind="unconfirmed")
    from oppencouncil.recovery import recover_records
    qid = recover_records(store, [wrong])["ids"][0]
    q = store.change(qid, "answer", "保留已有答复", expected_revision=1,
                     request_id="human-answer", actor="user")
    q = store.change(qid, "comment", "仍保留分歧", expected_revision=q["revision"],
                     request_id="human-comment", actor="user")
    item.update(question_id=qid, expected_revision=q["revision"], supersedes="bad-classification")
    history.write_text(json.dumps(payload), encoding="utf-8")
    result = subprocess.run(base + ["reconcile"] + args, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["created"] == 0
    after = store.read_question(qid)
    assert after["user_answer"] == q["user_answer"]
    assert after["messages"] == q["messages"] and after["status"] == "discussing"
    assert after["recovery_classification"]["kind"] == "frozen"
    assert source.read_bytes() == before and len(store.snapshot()["questions"]) == 1
    assert len(Registry(directory).read()) == 1


def test_skill_cli_import_and_start_register_one_project(tmp_path):
    project = tmp_path / "科研项目"
    project.mkdir()
    (project / "project.md").write_text("<!-- stepwise-r-project:v3 -->\n", encoding="utf-8")
    batch = tmp_path / "batch.json"
    batch.write_text(json.dumps({"request_id": "skill-round", "questions": [{"group": "时间", "title": "时间零点？",
        "why": "改变随访", "source_summary": "合成项目", "ai_position": "先确认日期"}]}))
    directory = tmp_path / "site"
    command = [sys.executable, str(SOURCE / "freeze_workbench.py")]
    def run(*args):
        result = subprocess.run(command + list(args) + ["--directory", str(directory)],
                                text=True, capture_output=True)
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)
    imported = run("import", str(project), "--input", str(batch))
    assert imported["registered"] and len(Registry(directory).read()) == 1
    try:
        opened = run("start", str(project), "--port", "0", "--no-auth")
        assert opened["project_id"] == imported["project_id"]
        assert opened["project_url"].endswith("/projects/" + opened["project_id"] + "/freeze")
        assert run("snapshot", str(project))["questions"][0]["created_by"] == "codex"
        assert run("stop", str(project))["disabled"]
        assert info(directory) is not None
    finally:
        stop(directory)
