"""Native Steward workbench commands operate through the optional shared application."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("oppencouncil", reason="Workbench integration needs the installed OppenCouncil package")
from oppencouncil.cli import main
from oppencouncil.registry import Registry
from oppencouncil.store import FreezeStore

HELPER = Path(__file__).parents[1] / "scripts/oppen_project_steward.py"


def steward(*arguments):
    result = subprocess.run([sys.executable, str(HELPER), *map(str, arguments)],
                            capture_output=True, text=True, encoding="utf-8", check=False)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "软件项目"
    steward("init", root)
    (root / "docs").mkdir()
    (root / "tests").mkdir()
    (root / "docs/cache-policy.md").write_text(
        "# 缓存规则\nStatus: frozen\n写入后立即使缓存失效。\n", encoding="utf-8")
    (root / "tests/test_policy.py").write_text("assert '写入后' in '写入后立即使缓存失效。'\n", encoding="utf-8")
    steward("canonical", root, "--topic", "cache-policy", "--path", "docs/cache-policy.md",
            "--status", "frozen", "--verification", "tests/test_policy.py")
    return root


def governance(root):
    return {str(p.relative_to(root)): p.read_bytes()
            for p in (root / ".oppen-project-steward").rglob("*") if p.is_file()}


def cli(capsys, directory, *arguments, payload=None, code=0):
    args = ["--directory", str(directory), *map(str, arguments)]
    if payload is not None:
        temporary = directory.parent / "input.json"
        temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        args.extend(["--input", str(temporary)])
    assert main(args) == code
    output = capsys.readouterr()
    return json.loads(output.out) if code == 0 else output.err


def test_native_steward_batch_rounds_and_ai_changes_preserve_human_and_governance(project, tmp_path, capsys):
    directory = tmp_path / "site"
    before = governance(project)
    batch = {"request_id": "round-1", "questions": [{
        "group": "接口", "title": "刷新窗口应多长？", "why": "决定新内容可见时间。",
        "source_summary": "缓存规则的下一轮评审", "ai_position": "建议先确认刷新上限。",
    }]}
    created = cli(capsys, directory, "import", project, payload=batch)
    assert created["ids"] == ["F-000001"] and created["registered"]
    assert cli(capsys, directory, "import", project, payload=batch)["replayed"]
    store = FreezeStore(project)
    q = store.change("F-000001", "answer", "30 秒", expected_revision=1,
                     request_id="human-answer", actor="user")
    update = {"question_id": q["id"], "operation": "ai_position", "value": "还需确定失败时的重试规则。",
              "expected_revision": q["revision"], "request_id": "position-1"}
    changed = cli(capsys, directory, "ai-change", project, payload=update)
    assert changed["user_answer"] == "30 秒" and changed["messages"][-1]["actor"] == "codex"
    update.update(operation="answer", value="不能代答", expected_revision=changed["revision"], request_id="ai-answer")
    assert "unavailable" in cli(capsys, directory, "ai-change", project, payload=update, code=2)
    batch["request_id"] = "round-2"
    batch["questions"][0]["title"] = "失败时采用什么重试规则？"
    assert cli(capsys, directory, "import", project, payload=batch)["round"] == 2
    snapshot = cli(capsys, directory, "snapshot", project)
    assert len(snapshot["questions"]) == 2 and snapshot["questions"][0]["user_answer"] == "30 秒"
    assert len(Registry(directory).read()) == 1
    assert governance(project) == before and not (project / "project.md").exists()
    steward("validate", project)


def test_native_steward_recovery_mirrors_frozen_owner_without_new_answers(project, tmp_path, capsys):
    before = governance(project)
    source = project / "docs/cache-policy.md"
    original = source.read_bytes()
    directory = tmp_path / "site"
    payload = {"records": [{
        "key": "cache-policy", "kind": "frozen", "title": "缓存失效规则",
        "summary": "写入后立即使缓存失效。", "canonical_topic": "cache-policy", "canonical_source": 0,
        "sources": [{"path": "docs/cache-policy.md", "sha256": hashlib.sha256(original).hexdigest(),
                     "excerpt": "写入后立即使缓存失效。"}],
    }]}
    checked = cli(capsys, directory, "recover", project, "--check", payload=payload)
    assert checked["dry_run"] and not (project / "Freeze").exists()
    assert not directory.exists()
    result = cli(capsys, directory, "recover", project, payload=payload)
    q = FreezeStore(project).read_question(result["ids"][0])
    assert q["status"] == "frozen" and q["user_answer"] is None
    assert q["canonical_ref"] == "docs/cache-policy.md"
    assert cli(capsys, directory, "recover", project, payload=payload)["replayed"] == 1
    assert source.read_bytes() == original and governance(project) == before
    steward("validate", project)
