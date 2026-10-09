"""The Freeze MCP boundary is distinct from free-form Discussion and Canonical."""

from pathlib import Path

import pytest
from mcp.server.fastmcp.exceptions import ToolError
from starlette.testclient import TestClient

from oppenproject.auth import FREEZE_READ, FREEZE_WRITE, SCOPE
from oppenproject.catalog import AccessDenied, Catalog
from oppenproject.freeze import Freezes
from oppenproject.server import create_app, create_mcp

from .conftest import rpc, token


def freeze_project(settings, skill="stepwise-r-project", version=3):
    project = settings.projects_file.parent / "projects" / "示例项目"
    if skill == "stepwise-r-project":
        (project / ".oppen-project-steward/registry.md").unlink()
        (project / "project.md").write_text("<!-- stepwise-r-project:v3 -->\n", encoding="utf-8")
    if version == 4:
        marker = project / (
            "project.md" if skill == "stepwise-r-project" else ".oppen-project-steward/registry.md"
        )
        marker.write_text(marker.read_text().replace(":v3 -->", ":v4 -->"))
    settings.freeze_mode = "write"
    settings.freeze_projects = [str(project)]
    catalog = Catalog(settings)
    catalog.refresh(force=True)
    return catalog, next(iter(catalog.projects))


@pytest.mark.asyncio
@pytest.mark.parametrize("skill", ["stepwise-r-project", "oppen-project-steward"])
@pytest.mark.parametrize("version", [3, 4])
async def test_stdio_freeze_tools_share_project_files_and_preserve_human_answer(settings, skill, version):
    catalog, pid = freeze_project(settings, skill, version)
    anchor = Path(catalog.projects[pid].root) / catalog.projects[pid].registry
    before = anchor.read_bytes()
    settings.transport = "stdio"
    mcp = create_mcp(settings, catalog)
    tools = {tool.name for tool in await mcp.list_tools()}
    assert {
        "freeze_snapshot",
        "freeze_read_question",
        "freeze_add_questions",
        "freeze_change_question",
    } <= tools
    items = [
        {
            "group": "结局",
            "title": "死亡如何处理？",
            "why": "影响风险解释。",
            "source_summary": "研究方案",
            "ai_position": "先讨论竞争事件。",
        }
    ]
    await mcp.call_tool(
        "freeze_add_questions", {"project_id": pid, "questions": items, "request_id": "mcp-freeze-round-1"}
    )
    store = Freezes(catalog)
    q = store.read(pid, "F-000001")
    assert q["status"] == "open" and q["created_by"] == "chatgpt"
    assert q["ai_position_by"] == "chatgpt"
    await mcp.call_tool(
        "freeze_change_question",
        {
            "project_id": pid,
            "question_id": q["id"],
            "operation": "comment",
            "value": "网页 AI 建议核对日期来源。",
            "expected_revision": q["revision"],
            "request_id": "mcp-freeze-comment-1",
        },
    )
    assert store.read(pid, q["id"])["messages"][-1]["actor"] == "chatgpt"
    current = store.read(pid, q["id"])
    store.store(pid).change(
        q["id"],
        "answer",
        "用户已保存的答复",
        expected_revision=current["revision"],
        request_id="human-answer",
        actor="user",
    )
    current = store.read(pid, q["id"])
    await mcp.call_tool(
        "freeze_change_question",
        {
            "project_id": pid,
            "question_id": q["id"],
            "operation": "ai_position",
            "value": "Codex 已核对日期实现。",
            "expected_revision": current["revision"],
            "request_id": "mcp-codex-opinion",
            "actor": "codex",
        },
    )
    assert store.read(pid, q["id"])["ai_position_by"] == "codex"
    assert store.read(pid, q["id"])["user_answer"] == "用户已保存的答复"
    current = store.read(pid, q["id"])
    await mcp.call_tool(
        "freeze_change_question",
        {
            "project_id": pid,
            "question_id": q["id"],
            "operation": "definition_draft",
            "value": "完整候选规则：保存成功后刷新共享记录；断线时保留本地修改。",
            "expected_revision": current["revision"],
            "request_id": "mcp-candidate",
            "actor": "codex",
        },
    )
    current = store.read(pid, q["id"])
    assert current["definition"]["draft"]["updated_by"] == "codex"
    assert current["definition"]["current_version"] is None
    for operation in ("definition_approve", "definition_begin", "definition_discard", "definition_publish"):
        with pytest.raises(AccessDenied):
            store.change(pid, q["id"], operation, None, current["revision"], "denied-" + operation)
    confirmed = store.store(pid).change(
        q["id"],
        "definition_approve",
        current["definition"]["draft"]["text_sha256"],
        actor="user",
        expected_revision=current["revision"],
        request_id="human-confirm",
    )
    assert store.read(pid, q["id"])["definition"] == confirmed["definition"]
    assert store.snapshot(pid)["questions"][0]["definition"]["current_version"] == 1
    await mcp.call_tool(
        "freeze_add_questions",
        {"project_id": pid, "questions": items, "request_id": "mcp-codex-round", "actor": "codex"},
    )
    assert store.read(pid, "F-000002")["created_by"] == "codex"
    with pytest.raises(ToolError):
        await mcp.call_tool(
            "freeze_change_question",
            {
                "project_id": pid,
                "question_id": q["id"],
                "operation": "comment",
                "value": "冒充用户",
                "expected_revision": 3,
                "request_id": "mcp-human-actor",
                "actor": "user",
            },
        )
    with pytest.raises(AccessDenied, match="actor must"):
        store.add(pid, items, "invalid-actor", actor="user")
    with pytest.raises(AccessDenied):
        store.change(pid, q["id"], "answer", "竞争事件", 2, "mcp-answer-forbidden")
    assert anchor.read_bytes() == before
    if skill == "oppen-project-steward":
        assert not (anchor.parent.parent / "project.md").exists()


@pytest.mark.parametrize("skill", ["stepwise-r-project", "oppen-project-steward"])
def test_oauth_freeze_scopes_are_separate_from_governance(settings, skill):
    freeze_project(settings, skill)
    app = create_app(settings)
    app.state.catalog.refresh()
    pid = next(iter(app.state.catalog.projects))
    with TestClient(app, base_url=settings.public_url, follow_redirects=False) as client:
        access = token(client)["access_token"]
        listed = rpc(client, access, "tools/list")["result"]["tools"]
        by_name = {tool["name"]: tool for tool in listed}
        assert by_name["freeze_snapshot"]["securitySchemes"][0]["scopes"] == [SCOPE, FREEZE_READ]
        assert by_name["freeze_change_group"]["securitySchemes"][0]["scopes"] == [
            SCOPE,
            FREEZE_READ,
            FREEZE_WRITE,
        ]
        assert by_name["freeze_add_questions"]["securitySchemes"][0]["scopes"] == [
            SCOPE,
            FREEZE_READ,
            FREEZE_WRITE,
        ]
        denied = rpc(
            client, access, "tools/call", {"name": "freeze_snapshot", "arguments": {"project_id": pid}}
        )["result"]
        assert denied["isError"] and "mcp/www_authenticate" in denied["_meta"]
        overview = rpc(
            client, access, "tools/call", {"name": "project_overview", "arguments": {"project_id": pid}}
        )["result"]["structuredContent"]
        assert overview["freeze_access"] == {"available": True, "can_read": False, "can_write": False}
        settings.freeze_projects = []
        overview = rpc(
            client, access, "tools/call", {"name": "project_overview", "arguments": {"project_id": pid}}
        )["result"]["structuredContent"]
        assert overview["freeze_access"] == {"available": False, "can_read": False, "can_write": False}


@pytest.mark.parametrize("skill", ["stepwise-r-project", "oppen-project-steward"])
def test_freeze_requires_exact_project_allowlist(settings, skill):
    catalog, pid = freeze_project(settings, skill)
    store = Freezes(catalog)
    settings.freeze_projects = []
    with pytest.raises(AccessDenied, match="not enabled"):
        store.snapshot(pid)
    settings.freeze_projects = [str(settings.projects_file.parent / "projects" / "another")]
    with pytest.raises(AccessDenied, match="not enabled"):
        store.snapshot(pid)
    settings.freeze_projects = [str(Path(catalog.projects[pid].root))]
    assert store.snapshot(pid)["questions"] == []


def test_mcp_reads_recovered_authority_but_cannot_restore_or_declare_a_freeze(settings):
    import hashlib

    from oppencouncil.recovery import recover_records

    catalog, pid = freeze_project(settings)
    adapter = Freezes(catalog)
    root = Path(catalog.projects[pid].root)
    protocol = root / "protocol.md"
    protocol.write_text("Status: frozen\n首次处方日。\n", encoding="utf-8")
    (root / "project.md").write_text(
        "<!-- stepwise-r-project:v3 -->\n<!-- stepwise-r-project:canonical:start -->\n"
        "| time-zero | protocol.md | - | tests/contract.R |\n"
        "<!-- stepwise-r-project:canonical:end -->\n",
        encoding="utf-8",
    )
    result = recover_records(
        adapter.store(pid),
        [
            {
                "key": "time-zero",
                "kind": "frozen",
                "title": "时间零点",
                "summary": "首次处方日。",
                "canonical_topic": "time-zero",
                "canonical_source": 0,
                "sources": [
                    {
                        "path": "protocol.md",
                        "sha256": hashlib.sha256(protocol.read_bytes()).hexdigest(),
                        "excerpt": "首次处方日。",
                    }
                ],
            }
        ],
    )
    q = adapter.read(pid, result["ids"][0])
    assert q["status"] == "frozen" and q["user_answer"] is None
    assert q["recovered_records"][0]["sources"][0]["path"] == "protocol.md"
    before = protocol.read_bytes()
    for operation in ["recover", "reconcile", "freeze", "answer", "resolve"]:
        with pytest.raises(AccessDenied):
            adapter.change(pid, q["id"], operation, "不可代答", q["revision"], operation)
    assert protocol.read_bytes() == before
    assert adapter.read(pid, q["id"]) == q


def test_mcp_reads_reconciled_partial_item_and_preserves_write_boundary(settings):
    import hashlib

    from oppencouncil.recovery import recover_records

    catalog, pid = freeze_project(settings)
    adapter = Freezes(catalog)
    store = adapter.store(pid)
    root = Path(catalog.projects[pid].root)
    (root / "project.md").write_text(
        "<!-- stepwise-r-project:v3 -->\n<!-- stepwise-r-project:canonical:start -->\n"
        "| protocol | protocol.md | - | tests/contract.R |\n"
        "<!-- stepwise-r-project:canonical:end -->\n",
        encoding="utf-8",
    )
    protocol = root / "protocol.md"
    protocol.write_text("Status: partially-frozen\n已冻结：主分析从 2016-01 开始。\n", encoding="utf-8")
    source = {
        "path": "protocol.md",
        "excerpt": "已冻结：主分析从 2016-01 开始。",
        "sha256": hashlib.sha256(protocol.read_bytes()).hexdigest(),
    }
    old = {"key": "old", "kind": "unconfirmed", "title": "索引下限", "summary": "待核", "sources": [source]}
    qid = recover_records(store, [old])["ids"][0]
    new = dict(
        old,
        key="corrected",
        kind="frozen",
        canonical_scope="item",
        canonical_source=0,
        canonical_topic="protocol",
        summary="主分析从 2016-01 开始。",
        supersedes="old",
        reason="当前逐条冻结证据；后续无重新打开。",
        question_id=qid,
        expected_revision=1,
    )
    recover_records(store, [new], reconcile=True)
    q = adapter.read(pid, qid)
    assert q["status"] == "frozen" and q["recovery_classification"]["kind"] == "frozen"
    assert q["recovered_records"][-1]["supersedes"] == "old"
    for operation in ["reconcile", "recover", "freeze", "answer", "resolve"]:
        with pytest.raises(AccessDenied):
            adapter.change(pid, qid, operation, "不授予新权限", q["revision"], operation)
    assert adapter.read(pid, qid) == q


@pytest.mark.asyncio
@pytest.mark.parametrize("skill", ["stepwise-r-project", "oppen-project-steward"])
async def test_mcp_joint_groups_share_storage_without_human_authority(settings, skill):
    catalog, pid = freeze_project(settings, skill, 4)
    settings.transport = "stdio"
    mcp = create_mcp(settings, catalog)
    adapter = Freezes(catalog)
    adapter.add(
        pid,
        [{"title": "Receipt", "why": "Durable saves"}, {"title": "Recovery", "why": "Retry safely"}],
        "round",
    )
    args = {
        "project_id": pid,
        "group_id": None,
        "operation": "create",
        "value": {
            "title": "Persistence",
            "purpose": "Decide together",
            "member_ids": ["F-000001", "F-000002"],
            "options": [],
        },
        "expected_revision": 0,
        "request_id": "new-group",
        "actor": "chatgpt",
    }
    await mcp.call_tool("freeze_change_group", args)
    g = adapter.snapshot(pid)["decision_groups"][0]
    assert g["created_by"] == "chatgpt" and g["member_ids"] == args["value"]["member_ids"]
    for operation in ("approve", "begin", "select_option"):
        with pytest.raises(ToolError):
            await mcp.call_tool(
                "freeze_change_group",
                dict(
                    args,
                    group_id=g["id"],
                    operation=operation,
                    expected_revision=g["revision"],
                    request_id="denied-" + operation,
                ),
            )
    with pytest.raises(ToolError):
        await mcp.call_tool("freeze_change_group", dict(args, actor="user"))
    settings.freeze_projects = []
    with pytest.raises(ToolError):
        await mcp.call_tool("freeze_change_group", dict(args, request_id="not-authorized"))
