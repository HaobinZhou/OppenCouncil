"""A single HTTP listener serving explicitly registered project workspaces."""

from __future__ import annotations

import hmac
import html
import json
import re
import secrets
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from . import __version__
from .auth import AuthError, SiteAuth
from .registry import Registry
from .store import FreezeError

ASSETS = Path(__file__).parent / "assets"
MAX_BODY = 128 * 1024
PROJECT_ROUTE = re.compile(r"/projects/([0-9a-f]{20})/freeze/?")
API_ROUTE = re.compile(r"/api/projects/([0-9a-f]{20})/(snapshot|questions/(F-\d{6})/(example|change))")


def public_origin(value: str) -> str:
    if not value:
        return ""
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
    ):
        raise FreezeError("Public origin must be an HTTP(S) origin without a path or credentials")
    try:
        _ = parsed.port
    except ValueError as error:
        raise FreezeError("Invalid public origin port") from error
    return value.rstrip("/")


GROUP_ROUTE = re.compile(r"/api/projects/([0-9a-f]{20})/groups(?:/(B-\d{6}))?/(change|example)")


class CouncilHandler(BaseHTTPRequestHandler):
    server_version = "OppenCouncil/" + __version__

    def log_message(self, format, *args):
        # Request paths and bodies can contain scientific text or login fragments.
        return

    @property
    def app(self):
        return self.server

    def send_data(self, data: bytes, kind: str, status: int = 200, cookie: str | None = None):
        self.send_response(status)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-src 'self'; "
            "base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
        )
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, value: object, status: int = 200, cookie: str | None = None):
        self.send_data(
            json.dumps(value, ensure_ascii=False).encode("utf-8"),
            "application/json; charset=utf-8",
            status,
            cookie,
        )

    def authenticated(self) -> bool:
        if self.app.no_auth:
            return True
        return self.app.auth.authenticated(self.headers.get("Cookie", ""))

    def admin(self) -> bool:
        return hmac.compare_digest(self.headers.get("X-Council-Admin", ""), self.app.admin_token)

    def same_origin(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin:
            return True
        host = self.headers.get("Host", "")
        return origin in {f"http://{host}", f"https://{host}", self.app.public_origin}

    def require_auth(self) -> bool:
        if not self.authenticated():
            self.send_json({"error": "Login required"}, HTTPStatus.UNAUTHORIZED)
            return False
        return True

    def request_path(self) -> str:
        path = urlsplit(self.path).path
        identity = self.app.legacy_project_id
        if identity and (
            path == "/api/snapshot" or re.fullmatch(r"/api/questions/F-\d{6}/(example|change)", path)
        ):
            return f"/api/projects/{identity}" + path[4:]
        return path

    def project_store(self, identity: str):
        try:
            self.app.registry.project(identity)
        except FreezeError as error:
            self.send_json({"error": str(error)}, HTTPStatus.NOT_FOUND)
            return None
        try:
            return self.app.registry.store(identity)
        except (FreezeError, OSError, ValueError):
            self.send_json({"error": "Project is temporarily unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)
            return None

    def do_GET(self):
        path = self.request_path()
        if path == "/api/healthz":
            return self.send_json(
                {"app": "OppenCouncil", "version": __version__} if self.admin() else {"error": "Forbidden"},
                200 if self.admin() else 403,
            )
        if path == "/login.js":
            return self.send_data(
                (ASSETS / "freeze_login.js").read_bytes(), "application/javascript; charset=utf-8"
            )
        if path == "/api/auth":
            return self.send_json({"required": not self.app.no_auth,
                                   "setup_required": not self.app.no_auth and self.app.auth.record is None,
                                   "authenticated": self.authenticated()})
        if (path == "/" or PROJECT_ROUTE.fullmatch(path)) and not self.authenticated():
            page = (ASSETS / "login.html").read_bytes()
            return self.send_data(page, "text/html; charset=utf-8")
        if not self.require_auth():
            return
        assets = {"/": "index.html", "/index.js": "index.js", "/workbench.js": "freeze_workbench.js",
                  "/decision-groups.js": "decision_groups.js", "/markdown.js": "markdown.js",
                  "/markdown-it.js": "vendor/markdown-it.min.js"}
        if path in assets:
            content_type = (
                "text/html; charset=utf-8" if path == "/" else "application/javascript; charset=utf-8"
            )
            return self.send_data((ASSETS / assets[path]).read_bytes(), content_type)
        if path == "/api/projects":
            try:
                return self.send_json({"projects": self.app.registry.summaries(),
                                       "csrf": self.app.csrf_token, "auth_required": not self.app.no_auth})
            except (FreezeError, OSError, ValueError):
                return self.send_json({"error": "Site registry is unavailable"}, 503)
        match = PROJECT_ROUTE.fullmatch(path)
        if match:
            identity = match[1]
            if self.project_store(identity) is None:
                return
            item = self.app.registry.project(identity)
            page = (ASSETS / "freeze_workbench.html").read_text(encoding="utf-8")
            page = page.replace("__PROJECT_ID__", identity).replace(
                "__PROJECT_NAME__", html.escape(item["name"])
            )
            return self.send_data(page.encode("utf-8"), "text/html; charset=utf-8")
        group_match = GROUP_ROUTE.fullmatch(path)
        if group_match and group_match[3] == "example":
            store = self.project_store(group_match[1])
            if store is None:
                return
            try:
                group = store.read_group(group_match[2], include_example=True)
                return self.send_json({"html": (group.get("example") or {}).get("html", "")})
            except FreezeError as error:
                return self.send_json({"error": str(error)}, 400)
        match = API_ROUTE.fullmatch(path)
        if match and match[2] != "questions/" + str(match[3]) + "/change":
            store = self.project_store(match[1])
            if store is None:
                return
            try:
                if match[2] == "snapshot":
                    return self.send_json({"snapshot": store.snapshot(), "csrf": self.app.csrf_token,
                                           "auth_required": not self.app.no_auth})
                if match[4] == "example":
                    question = store.read_question(match[3], include_example=True)
                    return self.send_json({"html": (question.get("example") or {}).get("html", "")})
            except FreezeError as error:
                return self.send_json({"error": str(error)}, 404)
        return self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        path = self.request_path()
        if not self.same_origin():
            return self.send_json({"error": "Untrusted Origin"}, 403)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY:
                return self.send_json({"error": "Invalid request size"}, 413)
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise FreezeError("JSON object required")
        except (ValueError, UnicodeError) as error:
            return self.send_json({"error": str(error)}, 400)
        if path in {"/api/login", "/api/setup"}:
            if self.app.no_auth:
                return self.send_json({"error": "Login is disabled"}, 404)
            if self.headers.get_content_type() != "application/json":
                return self.send_json({"error": "JSON request required"}, 415)
            try:
                token = self.app.auth.enter(body.get("password"), self.client_address[0],
                    setup=path == "/api/setup", confirmation=body.get("confirmation"))
                # Re-login replaces this browser's old session without affecting other devices.
                self.app.auth.logout(self.headers.get("Cookie", ""))
                return self.send_json({"ok": True}, cookie=self.app.auth.cookie(
                    token, self.app.public_origin.startswith("https://")))
            except AuthError as error:
                return self.send_json({"error": str(error)}, error.status)
            except (FreezeError, OSError):
                return self.send_json({"error": "密码设置暂时无法保存，请检查站点目录后重试。"}, 503)
        if path == "/api/stop":
            if not self.admin():
                return self.send_json({"error": "Forbidden"}, 403)
            self.send_json({"stopping": True})
            threading.Thread(target=self.app.shutdown, daemon=True).start()
            return
        if not self.require_auth():
            return
        if not hmac.compare_digest(self.headers.get("X-Freeze-CSRF", ""), self.app.csrf_token):
            return self.send_json({"error": "CSRF check failed"}, 403)
        if path == "/api/logout":
            self.app.auth.logout(self.headers.get("Cookie", ""))
            return self.send_json({"ok": True}, cookie=self.app.auth.cookie(
                "", self.app.public_origin.startswith("https://")))
        group_match = GROUP_ROUTE.fullmatch(path)
        if group_match and group_match[3] == "change":
            store = self.project_store(group_match[1])
            if store is None:
                return
            try:
                group = store.change_group(group_match[2], body.get("operation"), body.get("value"),
                    expected_revision=body.get("expected_revision"), request_id=body.get("request_id"),
                    actor="user")
                return self.send_json({"group": group, "snapshot": store.snapshot()})
            except (FreezeError, OSError) as error:
                return self.send_json({"error": str(error)}, 409)
        match = API_ROUTE.fullmatch(path)
        if match is None or match[4] != "change":
            return self.send_json({"error": "Not found"}, 404)
        store = self.project_store(match[1])
        if store is None:
            return
        try:
            question = store.change(
                match[3],
                body.get("operation"),
                body.get("value"),
                expected_revision=body.get("expected_revision"),
                request_id=body.get("request_id"),
                actor="user",
            )
            return self.send_json({"question": question})
        except FreezeError as error:
            return self.send_json({"error": str(error)}, 409 if "changed since read" in str(error) else 400)


def create_server(
    directory: Path,
    host: str = "127.0.0.1",
    port: int = 0,
    origin: str = "",
    no_auth: bool = False,
    legacy_project_id: str = "",
) -> ThreadingHTTPServer:
    registry = Registry(directory)
    registry.read()
    if legacy_project_id:
        registry.project(legacy_project_id)
    origin = public_origin(origin)
    auth = SiteAuth(directory)
    if no_auth and auth.record is not None:
        raise FreezeError("This site has a password; remove --no-auth to start it")
    server = ThreadingHTTPServer((host, port), CouncilHandler)
    server.daemon_threads = True
    server.registry = registry
    server.public_origin = origin
    server.no_auth = no_auth
    server.legacy_project_id = legacy_project_id
    server.auth = auth
    server.csrf_token = secrets.token_urlsafe(32)
    server.admin_token = secrets.token_urlsafe(32)
    return server
