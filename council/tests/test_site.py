"""Observable registration, project isolation, and browser write contracts."""

import json
import threading
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import pytest

from oppencouncil.cli import main
from oppencouncil.registry import Registry, project_identity
from oppencouncil.server import create_server
from oppencouncil.service import info, stop
from oppencouncil.store import FreezeError, FreezeStore


def make_project(path, title="时间零点？", skill="stepwise-r-project"):
    path.mkdir()
    if skill == "oppen-project-steward":
        (path / ".oppen-project-steward").mkdir()
        anchor = path / ".oppen-project-steward/registry.md"
    else:
        anchor = path / "project.md"
    anchor.write_text(f"<!-- {skill}:v3 -->\n", encoding="utf-8")
    FreezeStore(path).add_questions(
        [
            {
                "group": "时间",
                "title": title,
                "why": "改变随访起点",
                "source_summary": "合成验证项目",
                "ai_position": "先讨论日期",
            }
        ],
        request_id="initial",
        actor="codex",
    )
    return path


@pytest.fixture(params=["stepwise-r-project", "oppen-project-steward"])
def site(tmp_path, request):
    directory = tmp_path / "site"
    registry = Registry(directory)
    first = make_project(tmp_path / "项目 A", skill=request.param)
    second = make_project(tmp_path / "项目 B", "死亡如何处理？", skill=request.param)
    a = registry.register(first)
    b = registry.register(second)
    server = create_server(directory, no_auth=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield registry, server, a, b
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def request(server, path, body=None, headers=None):
    base = f"http://127.0.0.1:{server.server_address[1]}"
    headers = {"Content-Type": "application/json", **(headers or {})}
    if body is not None:
        headers.setdefault("Origin", base)
        headers.setdefault("X-Freeze-CSRF", server.csrf_token)
    req = urllib.request.Request(
        base + path, data=json.dumps(body).encode() if body is not None else None, headers=headers
    )
    try:
        response = urllib.request.urlopen(req)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        raw = response.read()
        value = json.loads(raw) if response.headers.get_content_type() == "application/json" else raw.decode()
        return response.status, value, response.headers


def api(item, suffix="snapshot"):
    return f"/api/projects/{item['id']}/{suffix}"


def test_two_projects_same_question_id_remain_isolated(site):
    registry, server, a, b = site
    assert request(server, "/")[0] == 200
    status, page, _ = request(server, f"/projects/{a['id']}/freeze")
    assert status == 200 and a["id"] in page and "OppenCouncil" in page
    payload = {
        "operation": "answer",
        "value": "A 的答复",
        "expected_revision": 1,
        "request_id": "shared-request",
        "actor": "chatgpt",
    }
    assert request(server, api(a, "questions/F-000001/change"), payload)[0] == 200
    assert request(server, api(b))[1]["snapshot"]["questions"][0]["user_answer"] is None
    payload["value"] = "B 的答复"
    assert request(server, api(b, "questions/F-000001/change"), payload)[0] == 200
    assert registry.store(a["id"]).read_question("F-000001")["user_answer"] == "A 的答复"
    assert registry.store(b["id"]).read_question("F-000001")["user_answer"] == "B 的答复"
    payload.update(request_id="stale", expected_revision=1)
    assert request(server, api(a, "questions/F-000001/change"), payload)[0] == 409


def test_http_cannot_register_paths_or_bypass_write_checks(site):
    _, server, a, _ = site
    payload = {"operation": "answer", "value": "answer", "expected_revision": 1, "request_id": "answer"}
    assert (
        request(
            server, api(a, "questions/F-000001/change"), payload, {"Origin": "https://unrelated.example"}
        )[0]
        == 403
    )
    assert request(server, api(a, "questions/F-000001/change"), payload, {"X-Freeze-CSRF": "wrong"})[0] == 403
    assert request(server, "/api/projects/register", {"root": "/tmp"})[0] == 404
    assert request(server, "/api/projects/" + "0" * 20 + "/snapshot")[0] == 404
    assert request(server, "/api/snapshot")[0] == 404
    payload["operation"] = "ai_position"
    assert request(server, api(a, "questions/F-000001/change"), payload)[0] == 400
    payload["operation"] = "recover"
    assert request(server, api(a, "questions/F-000001/change"), payload)[0] == 400


def test_live_registry_reload_disable_and_unavailable_project(site, tmp_path):
    registry, server, a, b = site
    assert len(request(server, "/api/projects")[1]["projects"]) == 2
    third = registry.register(make_project(tmp_path / "项目 C"))
    assert len(request(server, "/api/projects")[1]["projects"]) == 3
    registry.disable(a["root"])
    assert request(server, api(a))[0] == 404
    assert len(request(server, "/api/projects")[1]["projects"]) == 2
    from pathlib import Path

    Path(b["root"]).rename(tmp_path / "disk-unavailable")
    listing = request(server, "/api/projects")[1]["projects"]
    assert next(p for p in listing if p["id"] == b["id"])["available"] is False
    assert request(server, api(b))[0] == 503
    assert request(server, api(third))[0] == 200
    registry.path.write_text("broken JSON")
    assert request(server, "/api/projects")[0] == 503
    assert request(server, api(third))[0] == 404


def test_registration_is_atomic_idempotent_and_rejects_links(tmp_path):
    registry = Registry(tmp_path / "site")
    first = make_project(tmp_path / "A")
    second = make_project(tmp_path / "B")
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(registry.register, [first, second] * 5))
    assert len(registry.read()) == 2
    assert registry.register(first)["id"] == project_identity(first)
    linked = tmp_path / "linked"
    try:
        linked.symlink_to(first, target_is_directory=True)
    except OSError:
        pytest.skip("Symlink privilege unavailable")
    with pytest.raises(FreezeError, match="linked"):
        registry.register(linked)


def test_login_required_for_directory_and_project_data(site):
    _, server, a, _ = site
    server.no_auth = False
    assert "OppenCouncil 登录" in request(server, "/")[1]
    assert request(server, "/api/projects")[0] == 401
    assert request(server, api(a))[0] == 401
    assert request(server, "/api/auth")[1]["setup_required"] is True
    status, _, headers = request(server, "/api/setup",
        {"password": "synthetic-password", "confirmation": "synthetic-password"})
    assert status == 200 and "HttpOnly" in headers["Set-Cookie"]
    cookie = headers["Set-Cookie"].split(";", 1)[0]
    assert request(server, api(a), headers={"Cookie": cookie})[0] == 200
    assert request(server, "/api/auth")[1]["setup_required"] is False
    assert request(server, "/api/login", {"password": "wrong-password"})[0] == 403
    assert request(server, "/api/login", {"password": "synthetic-password"})[0] == 200


def test_password_gate_covers_assets_routes_and_logout_revokes_only_one_session(site):
    _, server, a, _ = site
    server.no_auth = False
    for path in ("/api/projects", api(a), "/api/snapshot", "/workbench.js", "/index.js"):
        assert request(server, path)[0] == 401
    assert 'id="login-form"' in request(server, f"/projects/{a['id']}/freeze?question=F-000001")[1]
    setup = {"password": "synthetic-password", "confirmation": "synthetic-password"}
    assert request(server, "/api/setup", setup, {"Origin": "https://unrelated.example"})[0] == 403
    assert request(server, "/api/setup", setup, {"Content-Type": "text/plain"})[0] == 415
    status, _, headers = request(server, "/api/setup", setup)
    first = {"Cookie": headers["Set-Cookie"].split(";", 1)[0]}
    assert status == 200
    assert request(server, "/api/setup", setup)[0] == 409
    server.public_origin = "https://council.example.com"
    status, _, headers = request(server, "/api/login", {"password": "synthetic-password"})
    second = {"Cookie": headers["Set-Cookie"].split(";", 1)[0]}
    assert status == 200 and "Secure" in headers["Set-Cookie"] and "Max-Age=43200" in headers["Set-Cookie"]
    assert first != second
    assert request(server, "/api/logout", {}, {**first, "X-Freeze-CSRF": "wrong"})[0] == 403
    status, _, headers = request(server, "/api/logout", {}, first)
    assert status == 200 and "Max-Age=0" in headers["Set-Cookie"]
    assert request(server, api(a), headers=first)[0] == 401
    assert request(server, api(a), headers=second)[0] == 200
    assert request(server, "/api/auth", headers=second)[1]["authenticated"] is True


def test_password_login_rate_limit_and_no_legacy_key_bypass(site):
    _, server, a, _ = site
    server.no_auth = False
    request(server, "/api/setup", {"password": "synthetic-password", "confirmation": "synthetic-password"})
    for _ in range(9):
        assert request(server, "/api/login", {"password": "wrong-password"})[0] == 403
    assert request(server, "/api/login", {"password": "synthetic-password"})[0] == 429
    assert request(server, api(a), headers={"Cookie": "oppencouncil=old-token"})[0] == 401
    assert request(server, "/api/auth")[0] == 200


def test_legacy_routes_only_target_explicit_enabled_project(site):
    registry, server, a, b = site
    assert request(server, "/api/snapshot")[0] == 404
    server.legacy_project_id = a["id"]
    assert request(server, "/api/snapshot")[1]["snapshot"]["project"] == a["root"]
    body = {
        "operation": "answer",
        "value": "旧页面答复",
        "expected_revision": 1,
        "request_id": "legacy-answer",
        "project_id": b["id"],
    }
    assert request(server, "/api/questions/F-000001/change", body)[0] == 200
    assert registry.store(b["id"]).read_question("F-000001")["user_answer"] is None
    registry.disable(a["root"])
    assert request(server, "/api/snapshot")[0] == 404
    assert request(server, api(b))[0] == 200


def test_cli_import_registers_and_open_reuses_one_service(tmp_path, capsys):
    directory = tmp_path / "site"
    first = make_project(tmp_path / "A")
    second = make_project(tmp_path / "B")
    batch = tmp_path / "batch.json"
    batch.write_text(
        json.dumps(
            {
                "request_id": "round-2",
                "questions": [
                    {
                        "group": "时间",
                        "title": "换药？",
                        "why": "改变归属",
                        "source_summary": "合成项目",
                        "ai_position": "先确认策略",
                    }
                ],
            }
        )
    )
    prefix = ["--directory", str(directory)]
    assert main(prefix + ["import", str(first), "--input", str(batch)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["registered"] and result["round"] == 2
    assert len(Registry(directory).read()) == 1
    try:
        assert main(prefix + ["open", str(first), "--port", "0", "--no-auth"]) == 0
        first_info = json.loads(capsys.readouterr().out)
        assert first_info["project_url"].endswith(f"/projects/{result['project_id']}/freeze")
        assert main(prefix + ["open", str(second)]) == 0
        second_info = json.loads(capsys.readouterr().out)
        assert second_info["pid"] == first_info["pid"] and second_info["port"] == first_info["port"]
        assert second_info["project_url"] != first_info["project_url"]
        assert main(prefix + ["open", str(second), "--host", "0.0.0.0"]) == 2
        assert "different settings" in capsys.readouterr().err
        assert info(directory)["host"] == "127.0.0.1"
        assert main(prefix + ["disable", str(first)]) == 0
        capsys.readouterr()
        assert info(directory) is not None
    finally:
        stop(directory)


def test_directory_counts_only_confirmed_formal_versions(site):
    registry, server, a, _ = site
    store = registry.store(a["id"])
    q = store.read_question("F-000001")
    q = store.change(
        q["id"],
        "definition_draft",
        "完整正式规则",
        actor="codex",
        expected_revision=q["revision"],
        request_id="count-draft",
    )
    summaries = request(server, "/api/projects")[1]["projects"]
    assert next(p for p in summaries if p["id"] == a["id"])["formal"] == 0
    q = store.change(
        q["id"],
        "definition_approve",
        q["definition"]["draft"]["text_sha256"],
        actor="user",
        expected_revision=q["revision"],
        request_id="count-approve",
    )
    store.change(
        q["id"],
        "comment",
        "正式口径生效后仍可讨论",
        actor="user",
        expected_revision=q["revision"],
        request_id="count-comment",
    )
    value = next(p for p in request(server, "/api/projects")[1]["projects"] if p["id"] == a["id"])
    assert value["formal"] == 1
    assert value["discussing"] == 1


def test_group_http_checks_origin_and_commits_shared_versions(site):
    registry, server, a, b = site
    store = registry.store(a["id"])
    q = store.read_question("F-000001")
    store.change(
        q["id"],
        "definition_draft",
        "Complete timing rule",
        actor="codex",
        expected_revision=q["revision"],
        request_id="candidate",
    )
    body = {
        "operation": "create",
        "value": {
            "title": "One reviewed decision",
            "purpose": "Joint confirmation API",
            "member_ids": [q["id"]],
            "options": [],
        },
        "expected_revision": 0,
        "request_id": "new-group",
    }
    assert request(server, api(a, "groups/change"), body, {"X-Freeze-CSRF": "wrong"})[0] == 403
    assert request(server, api(a, "groups/change"), body, {"Origin": "https://unrelated.example"})[0] == 403
    status, result, _ = request(server, api(a, "groups/change"), body)
    assert status == 200
    g = result["group"]
    body = {
        "operation": "approve",
        "value": g["approval_token"],
        "expected_revision": g["revision"],
        "request_id": "confirm",
    }
    assert request(server, api(b, "groups/" + g["id"] + "/change"), body)[0] == 409
    status, result, _ = request(server, api(a, "groups/" + g["id"] + "/change"), body)
    assert status == 200 and result["snapshot"]["questions"][0]["definition"]["current_version"] == 1
    assert not request(server, api(b))[1]["snapshot"]["decision_groups"]


def test_markdown_assets_are_local_and_loaded_before_workbench(site):
    _, server, a, _ = site
    status, page, _ = request(server, f"/projects/{a['id']}/freeze")
    assert status == 200
    assert page.index('/markdown-it.js') < page.index('/markdown.js') < page.index('/decision-groups.js')
    for asset in ("/markdown-it.js", "/markdown.js"):
        status, body, headers = request(server, asset)
        assert status == 200 and body
        assert headers.get_content_type() == "application/javascript"
