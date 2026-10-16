"""Exercise actual MCP discovery, OAuth grants, shared views and external writes."""

import json

import pytest
from mcp.server.fastmcp.exceptions import ToolError
from oppencouncil.project import MARKER, metadata_block
from oppencouncil.store import FreezeError, FreezeStore
from oppencouncil.workstore import WorkStore
from starlette.testclient import TestClient

from oppenproject.auth import FREEZE_READ, FREEZE_WRITE, SCOPE
from oppenproject.catalog import AccessDenied, Catalog
from oppenproject.discussion import directory_for
from oppenproject.freeze import Freezes
from oppenproject.server import create_app, create_mcp

from .conftest import rpc
from .test_discussion import grant


@pytest.fixture(params=["root", "namespace"])
def context(settings, request):
    root = settings.projects_file.parent / "projects/示例项目"
    registry = root / ".oppen-project-steward/registry.md"
    if request.param == "root":
        registry.unlink()
        registry = root / "project.md"
    registry.write_text(
        MARKER + "\n" + metadata_block({"governance_version": 5, "project_type": "research"}) + "\n"
    )
    settings.freeze_mode = "write"
    settings.freeze_projects = [str(root)]
    catalog = Catalog(settings)
    catalog.refresh(force=True)
    pid = next(iter(catalog.projects))
    local = WorkStore(FreezeStore(root))
    local.add(
        [{"title": "Public question", "why": "Necessary choice"}], request_id="local-create", actor="codex"
    )
    return catalog, pid, local


@pytest.mark.asyncio
async def test_external_identity_and_narrow_writes_are_server_enforced(context, settings):
    catalog, pid, local = context
    settings.transport = "stdio"
    mcp = create_mcp(settings, catalog)
    descriptors = {tool.name: tool for tool in await mcp.list_tools()}
    assert not {"freeze_add_questions", "freeze_change_question", "freeze_change_group"} & descriptors.keys()
    for name in ("council_submit_evidence", "council_comment"):
        assert "actor" not in descriptors[name].inputSchema["properties"]
    before = local.read("F-000001")
    arguments = {
        "project_id": pid,
        "item_id": "F-000001",
        "text": "Please inspect this assumption.",
        "expected_revision": before["revision"],
        "request_id": "external-comment",
    }
    await mcp.call_tool("council_comment", {**arguments, "actor": "codex"})
    current = local.read("F-000001")
    assert current["messages"][-1]["actor"] == "external_ai"
    assert current["messages"][-1]["label"] == "外部 AI · 未经本地核查"
    assert not current["human_pending"] and current["actionable"]
    assert current["candidate"] == before["candidate"] and current["current"] == before["current"]
    again = await mcp.call_tool("council_comment", arguments)
    assert again[1]["replayed"]
    with pytest.raises(ToolError):
        await mcp.call_tool("council_comment", {**arguments, "request_id": "different-request"})
    result = await mcp.call_tool(
        "council_submit_evidence",
        {"project_id": pid, "text": "A proposed new issue", "request_id": "new-evidence", "actor": "user"},
    )
    submission = local.evidence(result[1]["path"])
    assert submission["actor"] == "external_ai"
    assert local.index()["total"] == 1 and local.index()["inbox_total"] == 1
    assert local.store.snapshot()["questions"][0]["definition"]["current_version"] is None
    settings.freeze_mode = "read"
    with pytest.raises(AccessDenied, match="write mode"):
        Freezes(catalog).comment(pid, "F-000001", "Denied", current["revision"], "write-off")


@pytest.mark.asyncio
async def test_web_literature_contribution_does_not_release_research_handoff(context, settings):
    catalog, pid, local = context
    q = local.read("F-000001")
    local.commit_work(
        {
            "read_set": q["read_set"],
            "changes": [
                {
                    "id": q["id"],
                    "external_brief": {
                        "disclosure": "shared",
                        "summary": "Checked synthetic facts",
                        "questions": "Which methods apply?",
                    },
                    "pending": [
                        {
                            "id": "research-round-1",
                            "question": "Wait for literature and the human's instruction to continue",
                            "reason": "The human will arrange web research",
                            "continue_when": {"kind": "human_continue", "satisfied": False},
                        }
                    ],
                    "phase": {
                        "phase": "evidence",
                        "conclusion_type": "needs_check",
                        "reason": "Facts checked; handing off",
                        "trigger_refs": ["local-facts"],
                        "affected_refs": [q["id"]],
                        "completion_conditions": ["Human asks to continue"],
                    },
                }
            ],
        },
        request_id="local-research-handoff",
    )
    settings.transport = "stdio"
    mcp = create_mcp(settings, catalog)
    _, readback = await mcp.call_tool("council_read_work", {"project_id": pid, "item_id": q["id"]})
    assert readback["external_brief"]["questions"] == "Which methods apply?"
    _, submitted = await mcp.call_tool(
        "council_submit_evidence",
        {
            "project_id": pid,
            "text": "The web research is done; please proceed.",
            "targets": [q["id"]],
            "refs": ["Synthetic method source, section 2"],
            "request_id": "web-literature",
        },
    )
    reopened = WorkStore(FreezeStore(local.store.project))
    waiting = reopened.read(q["id"])
    assert waiting["work"]["phase"] == "evidence"
    assert waiting["actionable"] and not waiting["human_pending"]
    assert waiting["ready_pending_ids"] == []
    assert waiting["pending_items"][0]["continue_when"] == {"kind": "human_continue", "satisfied": False}
    assert reopened.evidence(submitted["path"])["actor"] == "external_ai"
    with pytest.raises(FreezeError, match="explicit human instruction"):
        reopened.commit_work(
            {
                "read_set": waiting["read_set"],
                "changes": [
                    {
                        "id": q["id"],
                        "definition": {"operation": "definition_draft", "value": "Premature recommendation"},
                    }
                ],
            },
            request_id="premature-review",
        )


def source(identifier, disclosure):
    return {
        "schema_version": 1,
        "id": identifier,
        "version": 1,
        "source_type": "project_fact",
        "verification": "measurement",
        "citation": "SECRET-local-fact" if disclosure == "local" else "Public source",
        "summary": "SECRET-local-summary" if disclosure == "local" else "18 of 30 synthetic records measured",
        "read_scope": "Observed synthetic measurement",
        "retrieved_at": "2026-10-14",
        "disclosure": disclosure,
    }


def test_local_evidence_and_machine_notes_never_leak_through_any_export(context):
    catalog, pid, local = context
    private = "evidence/sources/S-000001/r000001.json"
    public = "evidence/sources/S-000002/r000001.json"
    claim = "evidence/claims/E-000001/r000001.json"
    q = local.read("F-000001")
    local.commit_work(
        {
            "read_set": q["read_set"],
            "changes": [
                {
                    "id": q["id"],
                    "evidence_refs": [private, public, claim],
                    "review_packet": {"summary": "SECRET-local-packet"},
                    "external_brief": {
                        "disclosure": "shared",
                        "summary": "Deidentified context",
                        "uncertainties": "Which assumption applies?",
                    },
                }
            ],
            "evidence": [
                {"path": private, "value": source("S-000001", "local")},
                {"path": public, "value": source("S-000002", "shared")},
                {
                    "path": claim,
                    "value": {
                        "schema_version": 1,
                        "id": "E-000001",
                        "version": 1,
                        "claim": "A shareable judgment",
                        "applicability": "The stated conditions",
                        "sources": [private, public],
                        "disclosure": "shared",
                    },
                },
            ],
        },
        request_id="curate",
    )
    local.investigation(
        {"title": "SECRET-investigation", "why": "SECRET-project-detail", "dedupe_key": "private"},
        request_id="private-investigation",
    )
    adapter = Freezes(catalog)
    views = [
        adapter.snapshot(pid),
        adapter.read(pid, q["id"]),
        adapter.read_work(pid, q["id"]),
        adapter.work_index(pid),
        adapter.evidence_index(pid),
        adapter.read_evidence(pid, claim),
    ]
    assert "SECRET" not in json.dumps(views)
    read_claim = adapter.read_evidence(pid, claim)
    assert adapter.read_evidence(pid, public)["summary"] == "18 of 30 synthetic records measured"
    assert read_claim["sources"] == [public] and read_claim["has_undisclosed_sources"]
    assert private not in adapter.read_work(pid, q["id"])["evidence_refs"]
    assert adapter.work_index(pid)["total"] == 1
    with pytest.raises(AccessDenied, match="no shared brief"):
        adapter.read_work(pid, "I-000001")
    with pytest.raises(AccessDenied, match="no shared brief"):
        adapter.submit_evidence(pid, "Guess a private investigation", ["I-000001"], [], "hidden-target")
    with pytest.raises(AccessDenied, match="not shared"):
        adapter.read_evidence(pid, private)
    for path in ("../../notes.md", "Data/raw/input.csv", "../project.md", "assets/image.png"):
        with pytest.raises((FreezeError, AccessDenied)):
            adapter.read_evidence(pid, path)
        with pytest.raises(AccessDenied):
            catalog.read_file(pid, path)
    catalog.settings.exclude_roots.append(str(local.store.root / "evidence/sources"))
    with pytest.raises(AccessDenied, match="excluded"):
        adapter.read_evidence(pid, public)
    assert adapter.evidence_index(pid)["total"] == 1
    assert adapter.read_evidence(pid, claim)["sources"] == []
    assert adapter.read_work(pid, q["id"])["evidence_refs"] == [claim]


def test_v5_keeps_layout_and_discussion_location_independent_of_skill_name(context):
    catalog, pid, _ = context
    project = catalog.projects[pid]
    assert project.skill == "oppencouncil" and project.version == "v5"
    expected = ".oppen-project-steward/Discussion" if project.registry.startswith(".") else "Discussion"
    assert directory_for(project) == expected


def test_existing_freeze_oauth_grant_survives_service_restart_and_narrowed_tools(context, settings):
    _, pid, local = context
    settings.transport = "http"
    with TestClient(create_app(settings), base_url=settings.public_url, follow_redirects=False) as client:
        credentials, issued = grant(client, [SCOPE, FREEZE_READ, FREEZE_WRITE])
        resource = settings.resource
    # Restart with exactly the same identity, state directory and grants. No authorization UI.
    with TestClient(create_app(settings), base_url=settings.public_url, follow_redirects=False) as client:
        result = rpc(
            client,
            issued["access_token"],
            "tools/call",
            {
                "name": "council_submit_evidence",
                "arguments": {
                    "project_id": pid,
                    "text": "Existing grant still works",
                    "request_id": "same-oauth-grant",
                },
            },
        )["result"]
        assert not result.get("isError"), result
        refresh = client.post(
            "/token",
            data={
                "grant_type": "refresh_token",
                "client_id": credentials["client_id"],
                "refresh_token": issued["refresh_token"],
                "resource": resource,
            },
        )
        assert refresh.status_code == 200, refresh.text
        assert set(refresh.json()["scope"].split()) == {SCOPE, FREEZE_READ, FREEZE_WRITE}
    assert local.index()["inbox_total"] == 1


@pytest.mark.asyncio
async def test_group_comment_does_not_edit_members_or_count_as_human_feedback(context, settings):
    catalog, pid, local = context
    settings.transport = "stdio"
    local.store.change_group(
        None,
        "create",
        {"title": "Group", "purpose": "Review together", "member_ids": ["F-000001"], "options": []},
        expected_revision=0,
        request_id="local-group",
        actor="codex",
    )
    group = local.read("B-000001")
    original = local.read("F-000001")
    mcp = create_mcp(settings, catalog)
    await mcp.call_tool(
        "council_comment",
        {
            "project_id": pid,
            "item_id": "B-000001",
            "question_id": "F-000001",
            "text": "Check group assumption",
            "expected_revision": group["revision"],
            "request_id": "external-group",
        },
    )
    assert not local.read("B-000001")["human_pending"]
    assert local.read("B-000001")["messages"][-1]["question_id"] == "F-000001"
    assert local.read("F-000001")["revision"] == original["revision"]


def test_conversation_feedback_is_shared_without_local_execution_receipts(context):
    from oppencouncil.human_actions import execute

    catalog, pid, local = context
    q = local.read("F-000001")
    execute(local.store, {
        "id": q["id"], "operation": "comment", "value": "Please explain this choice",
        "request_id": "human-chat", "expected_revision": q["revision"],
        "authorization": {"source": "conversation", "instruction": "Record this question",
                          "thread_id": "private-thread"},
    })
    assert local.read(q["id"])["human_actions"]
    access = Freezes(catalog)
    for result in (access.read_work(pid, q["id"]), access.read(pid, q["id"]), access.snapshot(pid)):
        encoded = json.dumps(result)
        assert "Please explain this choice" in encoded
        assert "human_actions" not in encoded and "authorization" not in encoded
        assert "private-thread" not in encoded
