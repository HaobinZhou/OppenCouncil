"""Password persistence, first-run races and browser-session boundaries."""

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from oppencouncil.auth import AuthError, SiteAuth
from oppencouncil.server import create_server
from oppencouncil.service import urls
from oppencouncil.store import FreezeError

PASSWORD = "synthetic-test-password"


def test_password_survives_restart_without_reusing_sessions(tmp_path):
    first = SiteAuth(tmp_path)
    token = first.enter(PASSWORD, "local", setup=True, confirmation=PASSWORD)
    header = first.cookie(token)
    assert first.authenticated(header)
    saved = first.path.read_text()
    assert PASSWORD not in saved and token not in saved
    if os.name != "nt":
        assert first.path.stat().st_mode & 0o777 == 0o600
        assert first.path.parent.stat().st_mode & 0o777 == 0o700
    second = SiteAuth(tmp_path)
    assert second.record and not second.authenticated(header)
    assert second.authenticated(second.cookie(second.enter(PASSWORD, "local")))
    assert first.path.read_text() == saved
    with pytest.raises(FreezeError, match="remove --no-auth"):
        create_server(tmp_path, no_auth=True)


def test_setup_is_once_only_even_across_auth_instances(tmp_path):
    instances = [SiteAuth(tmp_path), SiteAuth(tmp_path)]

    def setup(auth):
        try:
            auth.enter(PASSWORD, "local", setup=True, confirmation=PASSWORD)
            return 200
        except AuthError as error:
            return error.status

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(setup, instances)) == [200, 409]
    original = instances[0].path.read_bytes()
    with pytest.raises(AuthError, match="已设置"):
        instances[0].enter("replacement-password", "local", setup=True, confirmation="replacement-password")
    assert instances[0].path.read_bytes() == original


@pytest.mark.parametrize("password,confirmation", [("short", "short"), (" " * 8, " " * 8),
    ("a" * 129, "a" * 129), (PASSWORD, "different"), (None, None), ("a\x00" * 8, "a\x00" * 8)])
def test_invalid_setup_never_writes_credentials(tmp_path, password, confirmation):
    auth = SiteAuth(tmp_path)
    with pytest.raises(AuthError):
        auth.enter(password, "local", setup=True, confirmation=confirmation)
    assert not auth.path.exists()


def test_sessions_expire_and_different_sites_have_different_cookie_names(tmp_path):
    auth = SiteAuth(tmp_path)
    token = auth.enter(PASSWORD, "local", setup=True, confirmation=PASSWORD)
    assert auth.cookie_name != SiteAuth(tmp_path / "other-site").cookie_name
    assert not auth.authenticated("not-a-cookie;")
    auth.sessions[auth.digest(token)] = time.monotonic() - 1
    assert not auth.authenticated(auth.cookie(token))
    assert not auth.sessions


def test_invalid_password_file_fails_closed(tmp_path):
    auth = SiteAuth(tmp_path)
    auth.enter(PASSWORD, "local", setup=True, confirmation=PASSWORD)
    record = json.loads(auth.path.read_text())
    record["iterations"] = 1
    auth.path.write_text(json.dumps(record))
    with pytest.raises(FreezeError, match="invalid"):
        create_server(tmp_path)


def test_new_service_urls_have_no_login_secret():
    result = urls({"pid": 1, "port": 5322, "host": "127.0.0.1", "no_auth": False,
                   "auth_mode": "password", "public_origin": "https://council.example.com"}, "a" * 20)
    assert result["auth_required"] is True
    assert result["site_url"] == "https://council.example.com/"
    assert result["project_url"].endswith("/projects/" + "a" * 20 + "/freeze")
    assert "#key=" not in json.dumps(result)
