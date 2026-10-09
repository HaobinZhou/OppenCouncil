"""Detached service lifecycle, with one process per explicit site directory."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from .registry import Registry
from .server import create_server, public_origin
from .store import FreezeError, atomic_json, ordinary_file


def runtime(directory: Path) -> Path:
    path = directory / ".runtime"
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink() or directory.is_symlink():
        raise FreezeError("Site runtime must not be linked")
    os.chmod(path, 0o700)
    return path


def info(directory: Path) -> dict | None:
    raw = ordinary_file(directory / ".runtime/server.json", 16384)
    if raw is None:
        return None
    try:
        value = json.loads(raw)
        port = value["port"]
        if type(port) is not int or not 0 < port < 65536:
            return None
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/healthz", headers={"X-Council-Admin": value["admin_token"]}
        )
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=1) as response:
            return value if json.load(response).get("app") == "OppenCouncil" else None
    except (KeyError, ValueError, OSError, urllib.error.URLError):
        return None


def urls(value: dict, identity: str | None = None) -> dict:
    path = f"/projects/{identity}/freeze" if identity else "/"
    # Older running listeners keep working until an explicit restart upgrades them.
    suffix = "#key=" + value["login_token"] if not value["no_auth"] and value.get("login_token") else ""
    local = f"http://127.0.0.1:{value['port']}"
    remote = value.get("public_origin", "")
    return {
        "running": True,
        "pid": value["pid"],
        "port": value["port"],
        "host": value["host"],
        "auth_required": not value["no_auth"],
        "site_url": (remote or local) + "/" + suffix,
        "local_url": local + path + suffix,
        "remote_url": remote + path + suffix if remote else None,
        "project_url": (remote or local) + path + suffix if identity else None,
        "forward_target": "127.0.0.1:" + str(value["port"]),
    }


def serve(directory: Path, host: str, port: int, origin: str, no_auth: bool, legacy_project_id: str = ""):
    private = runtime(directory)
    server = create_server(directory, host, port, origin, no_auth, legacy_project_id)
    value = {
        "pid": os.getpid(),
        "port": server.server_address[1],
        "host": host,
        "public_origin": server.public_origin,
        "no_auth": no_auth,
        "legacy_project_id": legacy_project_id,
        "auth_mode": "none" if no_auth else "password",
        "admin_token": server.admin_token,
    }
    state = private / "server.json"
    atomic_json(state, value)
    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()
        try:
            if json.loads(state.read_text(encoding="utf-8")).get("pid") == os.getpid():
                state.unlink()
        except (FileNotFoundError, ValueError):
            pass


def start(
    directory: Path,
    host: str | None = None,
    port: int | None = None,
    origin: str | None = None,
    no_auth: bool | None = None,
    legacy_project_id: str | None = None,
) -> dict:
    if origin is not None:
        origin = public_origin(origin)
    if port is not None and not 0 <= port <= 65535:
        raise FreezeError("Invalid listener port")
    with Registry(directory).locked():
        if legacy_project_id:
            Registry(directory).project(legacy_project_id)
        private = runtime(directory)
        current = info(directory)
        if current:
            for key, requested in {
                "host": host,
                "port": port,
                "public_origin": origin,
                "no_auth": no_auth,
                "legacy_project_id": legacy_project_id,
            }.items():
                if requested is not None and current[key] != requested:
                    raise FreezeError("Site is running with different settings; stop it before restarting")
            return {**urls(current), "already_running": True}
        command = [
            sys.executable,
            "-m",
            "oppencouncil",
            "--directory",
            str(directory),
            "_serve",
            "--host",
            host or "127.0.0.1",
            "--port",
            str(port if port is not None else 5322),
            "--public-origin",
            origin or "",
        ]
        if no_auth:
            command.append("--no-auth")
        if legacy_project_id:
            command += ["--legacy-project", Registry(directory).project(legacy_project_id)["root"]]
        with (private / "server.log").open("ab") as output:
            process = subprocess.Popen(
                command, stdin=subprocess.DEVNULL, stdout=output, stderr=output, start_new_session=True
            )
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            current = info(directory)
            if current:
                return {**urls(current), "already_running": False}
            if process.poll() is not None:
                break
            time.sleep(0.1)
        raise FreezeError(f"Site failed to start; inspect {private / 'server.log'}")


def stop(directory: Path) -> dict:
    with Registry(directory).locked():
        current = info(directory)
        if not current:
            return {"stopped": False, "reason": "No running site"}
        request = urllib.request.Request(
            f"http://127.0.0.1:{current['port']}/api/stop",
            data=b"{}",
            headers={"X-Council-Admin": current["admin_token"], "Content-Type": "application/json"},
        )
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=2) as response:
            response.read()
        deadline = time.monotonic() + 3
        while info(directory) and time.monotonic() < deadline:
            time.sleep(0.1)
        return {"stopped": info(directory) is None, "port": current["port"]}
