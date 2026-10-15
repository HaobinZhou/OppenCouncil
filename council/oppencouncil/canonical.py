"""Compatibility registration: general owners, or verification attached to an F."""

from __future__ import annotations

import re
from pathlib import PurePosixPath

from . import project_transaction as tx
from .outputs import fingerprint
from .project import json_bytes
from .project_registry import Registry, read_table, relative_path, stable_key, write_table
from .store import FreezeError, FreezeStore

STATUSES = {"draft", "partially-frozen", "frozen"}
HEADERS = ("Topic", "Canonical path", "Section", "Status", "Verification")


def owned_section(text, section):
    if not section:
        return text
    matches = list(re.finditer(r"^(#{1,6})\s+" + re.escape(section) + r"\s*$", text, re.M))
    if len(matches) != 1:
        raise FreezeError("Registered section must occur exactly once")
    start = matches[0]
    end = re.search(r"^#{1," + str(len(start[1])) + r"}\s+", text[start.end() :], re.M)
    return text[start.end() : start.end() + end.start()] if end else text[start.end() :]


def register(root, *, topic, path, verification, section=None, status=None, replace=False, fault=None):
    with tx.project_lock(root):
        registry = Registry(root)
        root = registry.root
        topic = stable_key(topic, "Canonical topic")
        owner = relative_path(root, path, required=True)
        checked = fingerprint(root, verification)
        if not checked["bytes"]:
            raise FreezeError("Verification must not be empty")
        reads = {path: fingerprint(root, path)["sha256"], verification: checked["sha256"]}
        if re.fullmatch(r"Freeze/questions/F-[0-9]{6}\.json", path):
            if section != "definition":
                raise FreezeError("Council ownership must reference the definition scope")
            store = FreezeStore(root)
            with store.locked():
                question = store._question(PurePosixPath(path).stem)
                if not question["definition"]["current_version"]:
                    raise FreezeError("Canonical registration requires a human-confirmed F")
                if status not in {None, "frozen"}:
                    raise FreezeError("Council current version determines frozen status")
                if any(t["path"] == verification for t in question.get("verification_tests", [])):
                    return {"changed_paths": [], "question_id": question["id"]}
                question.setdefault("verification_tests", []).append({"path": verification})
                question["revision"] += 1
                manifest = store._manifest()
                manifest["revision"] += 1
                reads["Freeze/manifest.json"] = tx.file_digest(root / "Freeze/manifest.json")
                # This changes live verification metadata only, never definition versions.
            result = registry.project.commit(
                {path: json_bytes(question), "Freeze/manifest.json": json_bytes(manifest)},
                read_set=reads,
                verify=lambda: FreezeStore(root, recover_project=False).snapshot(),
                fault=fault,
            )
            return {**result, "question_id": question["id"]}
        if registry.project.project_type == "research":
            raise FreezeError(
                "New research definitions belong in Council; technical conventions belong in code/tests. "
                "Existing Markdown owners remain readable pending explicit adoption into Council."
            )
        scope = owned_section(owner.read_text(encoding="utf-8"), section)
        if status is None:
            found = re.findall(r"^Status:\s*(\S+)\s*$", scope, re.M | re.I)
            if len(found) != 1:
                raise FreezeError("Supply --status or exactly one Status field in the owned scope")
            status = found[0].lower()
        if status not in STATUSES:
            raise FreezeError("Invalid canonical status")
        rows = read_table(registry.text, "canonical")
        matches = [row for row in rows if row["Topic"] == topic]
        if len(matches) > 1:
            raise FreezeError("Duplicate canonical topic")
        old = matches[0] if matches else None
        headers = tuple(rows[0]) if rows else HEADERS
        test_column = "Contract test" if "Contract test" in headers else "Verification"
        value = {
            "Topic": topic,
            "Canonical path": path,
            "Section": section or "",
            "Status": status,
            test_column: verification,
        }
        if old == value:
            return {"changed_paths": []}
        if old and (old["Canonical path"], old["Section"]) != (path, section or "") and not replace:
            raise FreezeError("Ownership move requires --replace")
        if any(
            r["Topic"] != topic and (r["Canonical path"], r["Section"]) == (path, section or "") for r in rows
        ):
            raise FreezeError("Canonical owner already belongs to another topic")
        rows = [r for r in rows if r["Topic"] != topic] + [value]
        registry.text = write_table(
            registry.text, "canonical", headers, sorted(rows, key=lambda r: r["Topic"])
        )
        return registry.commit(reads=reads, fault=fault)
