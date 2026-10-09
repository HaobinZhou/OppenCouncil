"""Explicit local project membership, independent of MCP authorization."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .store import MAX_JSON, FreezeError, FreezeStore, atomic_json, file_lock, ordinary_file


def default_directory() -> Path:
    configured = os.environ.get("OPPEN_COUNCIL_DIRECTORY")
    if configured:
        return Path(configured).expanduser().absolute()
    checkout = Path(__file__).resolve().parents[1]
    return checkout if (checkout / "pyproject.toml").is_file() else Path.home() / ".local/share/OppenCouncil"


def project_identity(root: str | Path) -> str:
    return hashlib.sha256(str(root).encode()).hexdigest()[:20]


class Registry:
    def __init__(self, directory: str | Path):
        self.directory = Path(directory).expanduser().absolute()
        self.path = self.directory / "projects.local.json"

    def read(self) -> list[dict]:
        raw = ordinary_file(self.path, MAX_JSON)
        if raw is None:
            return []
        try:
            payload = json.loads(raw)
        except (ValueError, UnicodeError) as error:
            raise FreezeError("Invalid site project registry") from error
        if not isinstance(payload, dict) or payload.get("schema_version") != 1:
            raise FreezeError("Unsupported site project registry")
        items = payload.get("projects")
        if not isinstance(items, list) or len(items) > 1000:
            raise FreezeError("Invalid site project list")
        seen = set()
        for item in items:
            if (
                not isinstance(item, dict)
                or set(item) != {"id", "name", "root", "enabled"}
                or not isinstance(item["root"], str)
                or not Path(item["root"]).is_absolute()
                or not isinstance(item["id"], str)
                or not re.fullmatch(r"[0-9a-f]{20}", item["id"])
                or project_identity(item["root"]) != item["id"]
                or item["id"] in seen
                or not isinstance(item["name"], str)
                or not 0 < len(item["name"]) <= 200
                or type(item["enabled"]) is not bool
            ):
                raise FreezeError("Invalid site project entry")
            seen.add(item["id"])
        return items

    @contextmanager
    def locked(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        if self.directory.is_symlink():
            raise FreezeError("Site directory must not be linked")
        with file_lock(self.directory / ".projects.lock"):
            yield

    def register(self, project: str | Path, name: str | None = None) -> dict:
        lexical = Path(project).expanduser().absolute()
        if lexical.is_symlink():
            raise FreezeError("Project root must not be linked")
        root = lexical.resolve(strict=True)
        FreezeStore(root)
        name = name or root.name
        if not isinstance(name, str) or not 0 < len(name) <= 200:
            raise FreezeError("Project name must contain 1–200 characters")
        item = {"id": project_identity(root), "name": name, "root": str(root), "enabled": True}
        with self.locked():
            items = self.read()
            old = next((p for p in items if p["id"] == item["id"]), None)
            if old is not None and name == root.name:
                item["name"] = old["name"]
            if old == item:
                return item
            if old is None:
                if len(items) >= 1000:
                    raise FreezeError("Site project limit reached")
                items.append(item)
            else:
                items[items.index(old)] = item
            atomic_json(self.path, {"schema_version": 1, "projects": items})
        return item

    def disable(self, project: str | Path) -> dict:
        root = Path(project).expanduser().absolute()
        # An unavailable disk can still be disabled using its registered absolute path.
        identity = project_identity(root.resolve() if root.exists() else root)
        with self.locked():
            items = self.read()
            item = next((p for p in items if p["id"] == identity), None)
            if item is None:
                raise FreezeError("Project is not registered")
            item["enabled"] = False
            atomic_json(self.path, {"schema_version": 1, "projects": items})
        return item

    def project(self, identity: str) -> dict:
        item = next((p for p in self.read() if p["id"] == identity and p["enabled"]), None)
        if item is None:
            raise FreezeError("Project is not enabled in this site")
        return item

    def store(self, identity: str) -> FreezeStore:
        return self._store(self.project(identity))

    @staticmethod
    def _store(item: dict) -> FreezeStore:
        root = Path(item["root"])
        if not stat.S_ISDIR(root.lstat().st_mode) or root.is_symlink():
            raise FreezeError("Project root is unavailable or linked")
        return FreezeStore(root)

    def summaries(self) -> list[dict]:
        summaries = []
        for item in self.read():
            if not item["enabled"]:
                continue
            value = {"id": item["id"], "name": item["name"], "url": f"/projects/{item['id']}/freeze"}
            try:
                store = self._store(item)
                snapshot = store.snapshot()
                questions = snapshot["questions"]
                value.update(
                    available=True,
                    round=snapshot["round"],
                    total=len(questions),
                    open=sum(q["status"] == "open" for q in questions),
                    discussing=sum(q["status"] == "discussing" for q in questions),
                    formal=sum(bool(q.get("definition", {}).get("current_version")) for q in questions),
                    answered=sum(q["status"] == "answered" for q in questions),
                    frozen=sum(q["status"] == "frozen" for q in questions),
                    historical=sum(q["status"] == "historical" for q in questions),
                    updated_at=datetime.fromtimestamp(
                        max((store.questions / (q["id"] + ".json")).lstat().st_mtime for q in questions),
                        timezone.utc,
                    ).isoformat()
                    if questions
                    else "",
                )
            except (FreezeError, OSError, ValueError):
                value.update(available=False)
            summaries.append(value)
        return summaries
