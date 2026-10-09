"""Both standalone governance helpers accept the same authoritative Council record."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
from oppencouncil.definitions import read_definition
from oppencouncil.store import FreezeStore

BASE = Path(__file__).parents[2] / "skills"


@pytest.fixture(params=["oppen-project-steward", "stepwise-r-project"])
def helper(request):
    name = request.param.replace("-", "_")
    spec = importlib.util.spec_from_file_location(name + "_v4_test", BASE / request.param / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def init(helper, root):
    helper.ensure_v3_project(root, create=True)
    helper.refresh_index(root)
    return root / helper.COUNCIL_REGISTRY


def downgrade_fixture(helper, root, registry):
    content = registry.read_text().replace(helper.V4_SCHEMA_MARKER, helper.SCHEMA_MARKER)
    if hasattr(helper, "managed_file_transaction"):
        with helper.project_write_lock(root):
            write_set = helper.managed_write_set(root, "v3 test fixture", exact=(registry,))
            helper.managed_file_transaction(root, write_set, {registry: content})
    else:
        helper.atomic_write(registry, content)


def test_v4_init_and_v3_explicit_upgrade_preserve_all_project_content(helper, tmp_path):
    root = tmp_path / "project"
    registry = init(helper, root)
    assert helper.V4_SCHEMA_MARKER in registry.read_text()
    downgrade_fixture(helper, root, registry)
    (root / "unrelated.txt").write_text("Existing work stays here.")
    store = FreezeStore(root)
    store.add_questions([{"title": "旧答复仍是讨论", "why": "禁止自动提升"}], request_id="round")
    store.change("F-000001", "answer", "选择 A", actor="user", expected_revision=1, request_id="answer")
    before = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    helper.refresh_index(root)
    assert helper.SCHEMA_MARKER in registry.read_text()  # No silent upgrade on index.
    checked = helper.upgrade_v4(root)
    assert checked["from"] == "v3" and not checked["changed"]
    assert helper.upgrade_v4(root, apply=True)["changed"]
    assert not helper.upgrade_v4(root, apply=True)["changed"]
    for path, content in before.items():
        if path != registry.relative_to(root) and path.name != ".managed-state.json":
            assert (root / path).read_bytes() == content
    assert helper.validate_project(root).ok
    assert not store.read_question("F-000001")["definition"]["versions"]


def test_canonical_reads_exact_confirmed_version_and_detects_corruption(helper, tmp_path):
    root = tmp_path / "project"
    init(helper, root)
    store = FreezeStore(root)
    store.add_questions([{"title": "刷新规则", "why": "确保一致"}], request_id="round")
    q = store.change("F-000001", "definition_draft", "保存成功后读取项目记录。\n断线时保留本地输入。",
                     actor="codex", expected_revision=1, request_id="candidate")
    owner = "Freeze/questions/F-000001.json"
    (root / "verify.py").write_text("assert 1 == 1\n")
    with pytest.raises(helper.ProjectError, match="Invalid Council"):
        helper.register_canonical(root, "refresh", owner, "definition", "verify.py", replace=False)
    q = store.change(q["id"], "definition_approve", q["definition"]["draft"]["text_sha256"],
                     actor="user", expected_revision=q["revision"], request_id="confirm")
    assert not helper.validate_project(root).ok  # Formal text is effective; ownership mapping must catch up.
    helper.register_canonical(root, "refresh", owner, "definition", "verify.py", replace=False)
    helper.refresh_index(root)
    assert helper.validate_project(root).ok
    assert helper.council_definition(root, root / owner, "definition") == read_definition(store, q["id"])["text"]
    q = store.change(q["id"], "definition_begin", None, actor="user",
                     expected_revision=q["revision"], request_id="revision")
    assert helper.validate_project(root).ok  # Candidate does not revoke the current authority.
    q["definition"]["versions"][0]["text"] = "Changed outside version management"
    (root / owner).write_text(json.dumps(q))
    assert not helper.validate_project(root).ok


def test_upgrade_preserves_unrelated_dirty_work_and_refuses_control_plane_drift(helper, tmp_path):
    root = tmp_path / "project"
    registry = init(helper, root)
    downgrade_fixture(helper, root, registry)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                    "commit", "-qm", "fixture"], check=True)
    (root / "dirty.txt").write_text("Keep this untracked file")
    assert helper.upgrade_v4(root)["from"] == "v3"
    registry.write_text(registry.read_text() + "\nUnexplained registry edit\n")
    with pytest.raises(helper.ProjectError):
        helper.upgrade_v4(root, apply=True)
    assert (root / "dirty.txt").read_text() == "Keep this untracked file"


def test_cli_entry_points_complete_a_v4_council_owner_workflow(helper, tmp_path):
    root = tmp_path / "项目"
    def invoke(*args):
        result = subprocess.run([sys.executable, helper.__file__, *map(str, args)],
                                capture_output=True, text=True, encoding="utf-8")
        assert result.returncode == 0, result.stderr + result.stdout
        return result.stdout
    invoke("init", root)
    assert helper.V4_SCHEMA_MARKER in (root / helper.COUNCIL_REGISTRY).read_text()
    batch = tmp_path / "batch.json"
    batch.write_text(json.dumps({"request_id": "cli-round", "questions": [
        {"title": "共同项目口径", "why": "唯一来源", "ai_position": "建议保存完整规则并由人类确认。"}
    ]}))
    run = subprocess.run([sys.executable, "-m", "oppencouncil", "--directory", str(tmp_path / "site"),
                          "import", str(root), "--input", str(batch)], capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 0, run.stderr
    store = FreezeStore(root)
    q = store.change("F-000001", "definition_draft", "所有读取者使用项目内的当前确认版本。",
                     actor="codex", expected_revision=1, request_id="draft")
    store.change(q["id"], "definition_approve", q["definition"]["draft"]["text_sha256"],
                 actor="user", expected_revision=q["revision"], request_id="approve")
    result = subprocess.run([sys.executable, "-m", "oppencouncil", "definition", str(root),
                             "--question", q["id"]], capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    exact = json.loads(result.stdout)
    assert exact["text"] == read_definition(store, q["id"])["text"]
    (root / "verify.py").write_text("assert True\n")
    invoke("canonical", root, "--topic", "sole-source", "--path", "Freeze/questions/F-000001.json",
           "--section", "definition", "--verification", "verify.py")
    invoke("index", root)
    assert "PASS" in invoke("validate", root)


def test_pending_view_exposes_changed_dependency_with_formal_text_intact(helper, tmp_path):
    root = tmp_path / 'project'
    init(helper, root)
    store = FreezeStore(root)
    store.add_questions([{'title': 'Upstream', 'why': 'Shared rule'},
                         {'title': 'Consumer', 'why': 'Uses upstream'}], request_id='round')
    def change(qid, operation, value=None, actor='codex'):
        q = store.read_question(qid)
        return store.change(qid, operation, value, expected_revision=q['revision'],
                            actor=actor, request_id=f'{qid}-{q["revision"]}-{operation}')
    def approve(qid):
        token = store.read_question(qid)['definition']['draft']['approval_token']
        return change(qid, 'definition_approve', token, 'user')
    change('F-000001', 'definition_draft', 'Initial upstream')
    approve('F-000001')
    change('F-000002', 'definition_draft', {'text': 'Exact consumer', 'dependencies': [
        {'question_id': 'F-000001', 'reason': 'Controls assignment'}]})
    approve('F-000002')
    assert helper.list_pending_decisions(root)['count'] == 0
    change('F-000001', 'definition_begin', actor='user')
    change('F-000001', 'definition_draft', 'Updated upstream')
    approve('F-000001')
    item = next(x for x in helper.list_pending_decisions(root)['items'] if x['id'] == 'F-000002')
    assert item['next_action'] == 'review_dependencies' and item['readiness'] == 'needs_review'
    assert store.read_question('F-000002')['definition']['versions'][0]['text'] == 'Exact consumer'
