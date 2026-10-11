"""Project-owned discussion, candidate wording and verified definition versions.

Human confirmation publishes an immutable version in this same project record.
The web UI, MCP and project readers use that record as the sole definition source.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

MARKER = "<!-- stepwise-r-project:v3 -->"
QUESTION_ID = re.compile(r"F-[0-9]{6}\Z")
MAX_JSON = 1024 * 1024
MAX_HTML = 128 * 1024
STATUSES = {"open", "answered", "discussing", "frozen", "historical"}
AI_ACTORS = {"codex", "chatgpt", "web_ai"}  # web_ai remains readable for legacy clients.


class FreezeError(ValueError):
    """The requested draft operation would violate the storage contract."""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def require_text(value, name: str, limit: int = 20000) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise FreezeError(f"{name} must be nonempty text of at most {limit} characters")
    return value.strip()


def request_fingerprint(operation: str, payload: object) -> str:
    raw = json.dumps([operation, payload], ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def ordinary_file_info(path: Path, limit: int):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit:
        raise FreezeError(f"Unsafe or oversized freeze file: {path.name}")
    return info


def ordinary_file(path: Path, limit: int) -> bytes | None:
    info = ordinary_file_info(path, limit)
    if info is None:
        return None
    with path.open("rb") as source:
        if os.fstat(source.fileno()).st_ino != info.st_ino:
            raise FreezeError("Freeze file changed during read")
        data = source.read(limit + 1)
    if len(data) > limit:
        raise FreezeError(f"Oversized freeze file: {path.name}")
    return data


@contextmanager
def file_lock(path: Path):
    """Validate metadata without reading a byte another Windows process has locked."""
    ordinary_file_info(path, 128)
    fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    acquired = False
    try:
        info = ordinary_file_info(path, 128)
        opened = os.fstat(fd)
        if info is None or (info.st_dev, info.st_ino) != (opened.st_dev, opened.st_ino):
            raise FreezeError("Lock file changed during open")
        if os.name == "nt":
            import msvcrt

            # Windows permits byte-range locks beyond EOF; never write before locking.
            msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_EX)
        acquired = True
        yield
    finally:
        try:
            if acquired:
                if os.name == "nt":
                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def atomic_write(path: Path, data: bytes) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=".freeze-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, 0o600)
        current = ordinary_file(path, max(MAX_JSON, MAX_HTML))
        if current is not None and path.is_symlink():
            raise FreezeError("Refusing to replace a linked freeze file")
        os.replace(temporary, path)
        if os.name != "nt":
            directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic_json(path: Path, value: dict) -> None:
    data = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if len(data) > MAX_JSON:
        raise FreezeError("Freeze record exceeds 1 MiB")
    atomic_write(path, data)


def governance_registry(project: Path) -> tuple[Path, str]:
    """Read one native governance anchor without creating or converting it."""
    steward = project / ".oppen-project-steward"
    if steward.is_symlink():
        raise FreezeError("Governance directory must not be linked")
    candidates = [
        (project / "project.md", "stepwise-r-project"),
        (steward / "registry.md", "oppen-project-steward"),
    ]
    found = []
    for path, prefix in candidates:
        raw = ordinary_file(path, MAX_JSON)
        if raw is None:
            continue
        count = sum(raw.decode("utf-8").splitlines().count(f"<!-- {prefix}:v{v} -->") for v in (3, 4))
        if count > 1:
            raise FreezeError("Ambiguous project governance marker")
        if count == 1:
            found.append((path, prefix))
    if len(found) != 1:
        raise FreezeError("Exactly one native Stepwise R or Steward v3/v4 root is required")
    return found[0]


class FreezeStore:
    def __init__(self, project: str | Path):
        self.project = Path(project).expanduser().resolve(strict=True)
        governance_registry(self.project)
        self.root = self.project / "Freeze"
        self.questions = self.root / "questions"
        self.examples = self.root / "examples"
        self.manifest = self.root / "manifest.json"

    def _directory(self, path: Path, create: bool) -> bool:
        if create:
            try:
                path.mkdir(mode=0o700)
            except FileExistsError:
                pass
        try:
            info = path.lstat()
        except FileNotFoundError:
            return False
        if not stat.S_ISDIR(info.st_mode) or path.is_symlink():
            raise FreezeError(f"Unsafe freeze directory: {path.name}")
        return True

    @contextmanager
    def locked(self, create: bool = False):
        if not self._directory(self.root, create):
            yield False
            return
        self._directory(self.questions, create)
        self._directory(self.examples, create)
        lock_path = self.root / ".lock"
        if ordinary_file_info(lock_path, 128) is None and not create:
            if ordinary_file(self.root / ".decision-transaction.json", 16 * MAX_JSON) is not None:
                raise FreezeError("Decision journal is missing its project lock; recovery required")
            yield True
            return
        with file_lock(lock_path):
            from .decisions import recover_transaction

            recover_transaction(self)
            yield True

    def _manifest(self) -> dict:
        raw = ordinary_file(self.manifest, MAX_JSON)
        if raw is None:
            return {"schema_version": 1, "round": 0, "question_ids": [], "revision": 0, "requests": {}}
        value = json.loads(raw)
        if value.get("schema_version") not in {1, 2} or not isinstance(value.get("question_ids"), list):
            raise FreezeError("Unsupported Freeze manifest")
        if len(set(value["question_ids"])) != len(value["question_ids"]) or not all(
            isinstance(item, str) and QUESTION_ID.fullmatch(item) for item in value["question_ids"]
        ):
            raise FreezeError("Invalid Freeze question index")
        return value

    def _question(self, question_id: str) -> dict:
        if not QUESTION_ID.fullmatch(question_id):
            raise FreezeError("Invalid question ID")
        raw = ordinary_file(self.questions / f"{question_id}.json", MAX_JSON)
        if raw is None:
            raise FreezeError("Question not found")
        value = json.loads(raw)
        if value.get("id") != question_id or value.get("schema_version") != 1:
            raise FreezeError("Question file does not match its ID")
        from .definitions import validate_definition

        validate_definition(value)
        return value

    def snapshot(self) -> dict:
        with self.locked() as exists:
            manifest = self._manifest()
            questions = [self._question(item) for item in manifest["question_ids"]] if exists else []
            return {
                "project": str(self.project),
                "round": manifest["round"],
                "revision": manifest["revision"],
                "questions": [self._view(q, {item["id"]: item for item in questions}) for q in questions],
                "decision_groups": self._group_views({q["id"]: q for q in questions}) if exists else [],
            }

    def _group_views(self, questions):
        from .decisions import snapshot_groups

        return snapshot_groups(self, questions)

    def _view(self, question, questions):
        import copy

        from .decisions import candidate_for_approval, group_membership, readiness
        from .definitions import approval_token

        result = copy.deepcopy(question)
        result["readiness"] = readiness(question["id"], questions)
        group = group_membership(self, question["id"])
        result["decision_group_id"] = group["id"] if group else None
        if result.get("definition", {}).get("draft"):
            result["definition"]["draft"] = candidate_for_approval(question["id"], questions)
            result["definition"]["draft"]["approval_token"] = approval_token(result["definition"]["draft"])
        return result

    def change_group(self, group_id, operation, value, **kwargs):
        from .decisions import change_group

        return change_group(self, group_id, operation, value, **kwargs)

    def read_group(self, group_id, include_example=False):
        from .decisions import all_questions, catalog, group_view

        with self.locked():
            group = next((g for g in catalog(self)["groups"] if g["id"] == group_id), None)
            if group is None:
                raise FreezeError("Decision group not found")
            return group if include_example else group_view(group, all_questions(self))

    def read_question(self, question_id: str, include_example: bool = False) -> dict:
        with self.locked() as exists:
            if not exists or question_id not in self._manifest()["question_ids"]:
                raise FreezeError("Question not found")
            question = self._question(question_id)
            if include_example and question.get("example"):
                raw = ordinary_file(self.examples / f"{question_id}.html", MAX_HTML)
                question["example"] = {**question["example"], "html": raw.decode("utf-8") if raw else ""}
            from .decisions import all_questions

            return self._view(question, all_questions(self))

    def add_questions(self, items: list[dict], *, request_id: str, actor: str = "codex") -> dict:
        if actor not in AI_ACTORS:
            raise FreezeError("Questions require a recognized AI actor")
        require_text(request_id, "request_id", 100)
        if not isinstance(items, list) or not 1 <= len(items) <= 200:
            raise FreezeError("Submit 1–200 questions in one round")
        clean = []
        for item in items:
            if not isinstance(item, dict):
                raise FreezeError("Each question must be an object")
            suggestions = item.get("suggestions", [])
            if not isinstance(suggestions, list) or len(suggestions) > 8:
                raise FreezeError("suggestions must contain at most eight choices")
            clean.append(
                {
                    "group": require_text(item.get("group", "其他"), "group", 80),
                    "title": require_text(item.get("title"), "title", 300),
                    "why": require_text(item.get("why"), "why", 5000),
                    "source_summary": require_text(
                        item.get("source_summary", "尚待核对来源"), "source_summary", 5000
                    ),
                    "ai_position": str(item.get("ai_position", "")).strip()[:10000],
                    "suggestions": [require_text(value, "suggestion", 300) for value in suggestions],
                }
            )
        fingerprint = request_fingerprint("add_questions", clean)
        with self.locked(create=True):
            manifest = self._manifest()
            previous = manifest["requests"].get(request_id)
            if previous:
                previous_actor = previous.get("actor") or self._question(previous["ids"][0]).get("created_by")
                if previous["fingerprint"] != fingerprint or previous_actor != actor:
                    raise FreezeError("request_id was used with different questions")
                return {"round": previous["round"], "ids": previous["ids"], "replayed": True}
            existing_numbers = [int(value[2:]) for value in manifest["question_ids"]]
            existing_numbers += [
                int(path.stem[2:])
                for path in self.questions.glob("F-*.json")
                if QUESTION_ID.fullmatch(path.stem)
            ]
            first = max(existing_numbers, default=0) + 1
            round_number = manifest["round"] + 1
            ids = [f"F-{first + number:06d}" for number in range(len(clean))]
            for question_id, item in zip(ids, clean, strict=True):
                created_at = now()
                atomic_json(
                    self.questions / f"{question_id}.json",
                    {
                        "schema_version": 1,
                        "id": question_id,
                        "round": round_number,
                        **item,
                        "created_by": actor,
                        "created_at": created_at,
                        "ai_position_by": actor,
                        "ai_position_at": created_at,
                        "status": "open",
                        "user_answer": None,
                        "messages": [
                            {
                                "id": f"{request_id}:{question_id}:proposal",
                                "actor": actor,
                                "text": item["ai_position"],
                                "round": round_number,
                                "at": created_at,
                                "kind": "proposal",
                            }
                        ]
                        if item["ai_position"]
                        else [],
                        "definition": {"draft": None, "versions": [], "current_version": None},
                        "example": None,
                        "canonical_ref": None,
                        "revision": 1,
                        "requests": {},
                    },
                )
            manifest["round"] = round_number
            manifest["revision"] += 1
            manifest["question_ids"].extend(ids)
            manifest["requests"][request_id] = {
                "fingerprint": fingerprint,
                "round": round_number,
                "ids": ids,
                "actor": actor,
            }
            atomic_json(self.manifest, manifest)
            return {"round": round_number, "ids": ids, "replayed": False}

    def change(
        self,
        question_id: str,
        operation: str,
        value: object,
        *,
        expected_revision: int,
        request_id: str,
        actor: str,
    ) -> dict:
        if actor not in AI_ACTORS | {"user"}:
            raise FreezeError("Operation is unavailable to this actor")
        require_text(request_id, "request_id", 100)
        fingerprint = request_fingerprint(operation, value)
        with self.locked(create=True):
            if question_id not in self._manifest()["question_ids"]:
                raise FreezeError("Question not found")
            question = self._question(question_id)
            previous = question["requests"].get(request_id)
            if previous:
                previous_actor = question.get("request_actors", {}).get(request_id)
                if previous != fingerprint or (previous_actor is not None and previous_actor != actor):
                    raise FreezeError("request_id was used with different content")
                from .decisions import all_questions

                return {**self._view(question, all_questions(self)), "replayed": True}
            if question["revision"] != expected_revision:
                raise FreezeError("Question changed since read; reload before editing")
            if operation in {
                "definition_begin",
                "definition_draft",
                "definition_approve",
                "definition_discard",
            }:
                from .decisions import (
                    all_questions,
                    bind_dependencies,
                    candidate_for_approval,
                    check_approval,
                )
                from .definitions import approval_token, change_definition

                questions = all_questions(self)
                questions[question_id] = question
                if operation == "definition_draft" and isinstance(value, dict):
                    value = {
                        "text": value.get("text"),
                        "dependencies": bind_dependencies(
                            value.get("dependencies", []), questions, question_id
                        ),
                    }
                if operation == "definition_approve":
                    candidate = candidate_for_approval(question_id, questions)
                    if candidate and value != approval_token(candidate):
                        raise FreezeError(
                            "Candidate wording or prerequisites changed since read; review again"
                        )
                    if candidate:
                        question["definition"]["draft"] = candidate
                    check_approval(question_id, questions)
                change_definition(question, operation, value, actor)
            elif operation == "presentation" and actor in AI_ACTORS:
                if not isinstance(value, dict):
                    raise FreezeError("Presentation requires text and suggestions")
                text = require_text(value.get("text"), "discussion", 10000)
                options = value.get("suggestions", [])
                if not isinstance(options, list) or len(options) > 8:
                    raise FreezeError("At most eight suggestions")
                context = {
                    key: require_text(value[key], key, 5000)
                    for key in ("why", "source_summary") if key in value
                }
                changed = {key: question.get(key, "") for key in context if question.get(key) != context[key]}
                if changed:
                    question.setdefault("review_notes", []).append({
                        "id": request_id + ":context", "actor": actor, "at": now(),
                        "text": "Presentation context updated; prior values retained for provenance.",
                        "previous_context": changed,
                    })
                    question.update(context)
                previous = question.get("ai_position")
                earlier = [
                    m["id"]
                    for m in question["messages"]
                    if m.get("text") == previous and m.get("actor") in AI_ACTORS
                ]
                question["superseded_presentations"] = list(
                    dict.fromkeys(question.get("superseded_presentations", []) + earlier)
                )
                question.update(
                    ai_position=text,
                    ai_position_by=actor,
                    ai_position_at=now(),
                    suggestions=[require_text(x, "suggestion", 300) for x in options],
                )
                question["messages"].append(
                    {"id": request_id, "actor": actor, "text": text, "at": now(), "kind": "proposal"}
                )
            elif operation == "review_note" and actor in AI_ACTORS:
                note = {"id": request_id, "actor": actor, "at": now()}
                if isinstance(value, dict):
                    message_id = value.get("source_message_id")
                    message = next((m for m in question["messages"] if m["id"] == message_id), None)
                    if not message or message.get("actor") not in AI_ACTORS:
                        raise FreezeError("Only AI discussion can separate machine evidence for display")
                    display = require_text(value.get("discussion_text"), "human discussion", 10000)
                    note.update(source_message_id=message_id, discussion_text=display)
                    question.setdefault("discussion_display", {})[message_id] = display
                    value = value.get("text")
                note["text"] = require_text(value, "verification note")
                question.setdefault("review_notes", []).append(note)
            elif operation == "dependency_review" and actor in AI_ACTORS | {"user"}:
                from .decisions import all_questions, blocking, current, readiness, requirements

                questions = all_questions(self)
                owner = current(question)
                if not owner or question.get("definition", {}).get("draft"):
                    raise FreezeError("Review requires an effective definition without an open draft")
                bindings = {}
                for dep in requirements(question):
                    if not blocking(dep):
                        continue
                    up = questions[dep["question_id"]]
                    version = current(up)
                    if not version or readiness(up["id"], questions, use_draft=False)["status"] in {
                        "waiting",
                        "needs_review",
                    }:
                        raise FreezeError("Resolve upstream prerequisites before recording compatibility")
                    bindings[up["id"]] = [version["number"], version["text_sha256"]]
                if not isinstance(value, dict) or value.get("bindings") != bindings:
                    raise FreezeError("Dependency versions changed since read; reload before reviewing")
                question.setdefault("dependency_reviews", []).append(
                    {
                        "id": request_id,
                        "by": actor,
                        "at": now(),
                        "owner_version": owner["number"],
                        "bindings": bindings,
                        "reason": require_text(value.get("reason"), "compatibility explanation"),
                    }
                )
            elif operation == "answer" and actor == "user":
                question["user_answer"] = require_text(value, "answer")
                if question["status"] in {"frozen", "historical"}:
                    question["status"] = "discussing"
                elif question["status"] != "discussing":
                    question["status"] = "answered"
            elif operation == "discuss" and actor == "user":
                question["status"] = "discussing"
            elif operation == "resolve" and actor == "user":
                if not question["user_answer"]:
                    raise FreezeError("Save an answer before resolving the discussion")
                question["status"] = "answered"
            elif operation == "comment" and actor in AI_ACTORS | {"user"}:
                text = require_text(value, "message")
                question["messages"].append(
                    {
                        "id": request_id,
                        "actor": actor,
                        "text": text,
                        "round": self._manifest()["round"],
                        "at": now(),
                    }
                )
                if actor == "user":
                    question["status"] = "discussing"
            elif operation == "ai_position" and actor in AI_ACTORS:
                text = require_text(value, "ai_position", 10000)
                question["ai_position"] = text
                question["ai_position_by"] = actor
                question["ai_position_at"] = now()
                question["messages"].append(
                    {
                        "id": request_id,
                        "actor": actor,
                        "text": text,
                        "round": self._manifest()["round"],
                        "at": now(),
                    }
                )
            elif operation == "reopen" and actor in AI_ACTORS:
                text = require_text(value, "reason", 10000)
                question["status"] = "discussing"
                question["messages"].append(
                    {
                        "id": request_id,
                        "actor": actor,
                        "text": "重新讨论：" + text,
                        "round": self._manifest()["round"],
                        "at": now(),
                    }
                )
            elif operation == "example" and actor in AI_ACTORS:
                if not isinstance(value, dict):
                    raise FreezeError("example must be an object")
                title = require_text(value.get("title"), "example.title", 300)
                summary = require_text(value.get("summary"), "example.summary", 2000)
                html = require_text(value.get("html"), "example.html", MAX_HTML)
                if len(html.encode("utf-8")) > MAX_HTML:
                    raise FreezeError("example.html exceeds 128 KiB")
                atomic_write(self.examples / f"{question_id}.html", html.encode("utf-8"))
                question["example"] = {
                    "title": title,
                    "summary": summary,
                    "updated_by": actor,
                    "updated_at": now(),
                }
            else:
                raise FreezeError("Operation is unavailable to this actor")
            if question["status"] not in STATUSES:
                raise FreezeError("Invalid question status")
            if operation in {"discuss", "reopen"} or (operation in {"answer", "comment"} and actor == "user"):
                candidate = question.get("definition", {}).get("draft")
                if candidate:
                    candidate["approval"] = None
            question["revision"] += 1
            question["requests"][request_id] = fingerprint
            question.setdefault("request_actors", {})[request_id] = actor
            from .decisions import all_questions, commit

            writes = {f"questions/{question_id}.json": question}
            if any(v.get("dependencies") for v in question.get("definition", {}).get("versions", [])) or (
                question.get("definition", {}).get("draft") or {}
            ).get("dependencies"):
                manifest = self._manifest()
                manifest.update(schema_version=2, revision=manifest["revision"] + 1)
                writes["manifest.json"] = manifest
                commit(self, writes)
            else:
                atomic_json(self.questions / f"{question_id}.json", question)
            return self._view(question, all_questions(self))
