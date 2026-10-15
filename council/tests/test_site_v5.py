"""Authenticated immutable assets and human investigation feedback over actual HTTP."""

import hashlib
import http.client
import json
import threading

import pytest
import test_workflow_v5 as work_fixtures
from test_assets_v5 import SVG

from oppencouncil.assets import freeze_images
from oppencouncil.registry import Registry
from oppencouncil.server import create_server

work = work_fixtures.work


@pytest.fixture
def site(work, tmp_path):
    directory = tmp_path / "local-site"
    entry = Registry(directory).register(work.store.project)
    server = create_server(directory)
    token = server.auth.enter("synthetic-password", "local", setup=True, confirmation="synthetic-password")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield work, server, entry["id"], server.auth.cookie(token)
    server.shutdown()
    server.server_close()
    thread.join()


def request(server, path, cookie=None, body=None, **headers):
    headers = {"Cookie": cookie or "", **headers}
    if body is not None:
        headers.update(
            {
                "Content-Type": "application/json",
                "X-Freeze-CSRF": server.csrf_token,
                "Origin": f"http://127.0.0.1:{server.server_port}",
            }
        )
    conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
    try:
        conn.request(
            "POST" if body is not None else "GET",
            path,
            json.dumps(body) if body is not None else None,
            headers,
        )
        response = conn.getresponse()
        raw = response.read()
        value = json.loads(raw) if response.getheader("Content-Type").startswith("application/json") else raw
        return response.status, value, dict(response.getheaders())
    finally:
        conn.close()


def test_images_require_login_and_only_serve_verified_project_asset_bytes(site):
    work, server, identity, cookie = site
    root = work.store.project
    (root / "Explore").mkdir()
    (root / "Explore/synthetic.svg").write_bytes(SVG)
    freeze_images(root, "![模拟数据，仅示意](Explore/synthetic.svg)")
    name = hashlib.sha256(SVG).hexdigest() + ".svg"
    url = f"/api/projects/{identity}/assets/{name}"
    assert request(server, url)[0] == 401
    status, raw, headers = request(server, url, cookie)
    assert status == 200 and raw == SVG
    assert headers["Content-Type"] == "image/svg+xml"
    assert "img-src 'self'" in headers["Content-Security-Policy"]
    for relative in ["../project.md", "Data/raw.svg", "%2e%2e%2fproject.md", "file.svg"]:
        assert request(server, f"/api/projects/{identity}/assets/" + relative, cookie)[0] == 404
    assert request(server, url.replace(identity, "0" * 20), cookie)[0] == 404
    (root / "Freeze/assets" / name).write_bytes(SVG.replace(b"blue", b"red"))
    assert request(server, url, cookie)[0] == 404


def test_human_investigation_comment_is_incremental_and_cannot_curate_work(site):
    work, server, identity, cookie = site
    identifier = work.investigation(
        {"title": "Check the source", "why": "Observed discrepancy", "dedupe_key": "source"},
        request_id="investigation",
    )["id"]
    url = f"/api/projects/{identity}/work/{identifier}"
    assert request(server, url)[0] == 401
    before = request(server, url, cookie)[1]
    body = {
        "expected_revision": before["revision"],
        "request_id": "human-comment",
        "text": "Please check the upstream exclusions",
        "actor": "external_ai",
        "phase": "closed",
        "definition": "unauthorized",
    }
    status, result, _ = request(server, url + "/comment", cookie, body)
    assert status == 200
    assert result["item"]["human_pending"]
    assert result["item"]["work"] == before["work"]
    assert result["item"]["messages"][-1]["actor"] == "user"
    listed = request(server, f"/api/projects/{identity}/work?actionable=true", cookie)[1]
    assert identifier in [item["id"] for item in listed["items"]]
    assert request(server, url + "/comment", cookie, {**body, "request_id": "stale"})[0] == 409
    assert request(server, url + "/comment", cookie, body)[0] == 200


def test_v5_hides_legacy_html_without_deleting_historical_files(site):
    work, server, identity, cookie = site
    path = work.store.project / "Freeze/examples/F-000001.html"
    path.parent.mkdir(exist_ok=True)
    path.write_text("<p>Historical example</p>")
    assert request(server, f"/api/projects/{identity}/questions/F-000001/example", cookie)[0] == 404
    assert path.read_text() == "<p>Historical example</p>"
