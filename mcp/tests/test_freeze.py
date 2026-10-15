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
async def test_legacy_projects_remain_readable_but_old_write_tools_are_removed(settings, skill, version):
    catalog, pid = freeze_project(settings, skill, version)
    settings.transport = "stdio"
    mcp = create_mcp(settings, catalog)
    adapter = Freezes(catalog)
    store = adapter.store(pid)
    store.add_questions(
        [{"title": "Existing decision", "why": "Existing context"}], request_id="local-create", actor="codex"
    )
    before = store.snapshot()
    tools = {tool.name for tool in await mcp.list_tools()}
    assert {"freeze_snapshot", "freeze_read_question", "council_submit_evidence", "council_comment"} <= tools
    removed = {"freeze_add_questions", "freeze_change_question", "freeze_change_group"}
    assert not removed & tools
    for name in removed:
        with pytest.raises(ToolError):
            await mcp.call_tool(name, {"project_id": pid})
    result = await mcp.call_tool("freeze_read_question", {"project_id": pid, "question_id": "F-000001"})
    assert result[1]["title"] == "Existing decision"
    with pytest.raises(AccessDenied, match="upgrade-v5"):
        adapter.submit_evidence(pid, "A suggestion", [], [], "external-create")
    assert store.snapshot() == before


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
        assert by_name["council_comment"]["securitySchemes"][0]["scopes"] == [
            SCOPE,
            FREEZE_READ,
            FREEZE_WRITE,
        ]
        assert by_name["council_submit_evidence"]["securitySchemes"][0]["scopes"] == [
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
