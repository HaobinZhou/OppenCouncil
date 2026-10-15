"""External Council boundary: shared reads, evidence submissions and comments only."""

from __future__ import annotations

import copy
import os
from pathlib import Path

from oppencouncil.store import FreezeStore
from oppencouncil.workstore import WorkStore

from .catalog import AccessDenied

GOVERNANCE_VERSIONS = (3, 4, 5)


def public_definition(value):
    if not value:
        return None
    keys = {"number", "text", "text_sha256", "base_version", "dependencies", "confirmed_at", "confirmed_by"}
    return {key: copy.deepcopy(item) for key, item in value.items() if key in keys}


def page(items, offset, limit):
    if type(offset) is not int or type(limit) is not int or offset < 0 or not 1 <= limit <= 1000:
        raise AccessDenied("Invalid pagination")
    return {
        "items": items[offset : offset + limit],
        "total": len(items),
        "next_offset": offset + limit if offset + limit < len(items) else None,
    }


class Freezes:
    def __init__(self, catalog):
        self.catalog = catalog
        self.settings = catalog.settings

    def allowed_path(self, project_id, relative):
        project = self.catalog.project(project_id)
        return not self.catalog.excluded(Path(project.root) / "Freeze" / relative)

    def check_path(self, project_id, relative):
        if not self.allowed_path(project_id, relative):
            raise AccessDenied("Council resource is excluded in the server configuration")

    @staticmethod
    def item_path(identifier):
        if identifier.startswith("F-"):
            return "questions/" + identifier + ".json"
        if identifier.startswith("I-"):
            return "investigations/" + identifier + ".json"
        return "decision-groups.json"

    @staticmethod
    def supported(project) -> bool:
        return (project.skill == "oppencouncil" and project.version == "v5") or (
            project.skill in {"stepwise-r-project", "oppen-project-steward"}
            and project.version in {"v3", "v4"}
        )

    def store(self, project_id: str):
        project = self.catalog.project(project_id)
        if not self.supported(project):
            raise AccessDenied("Freeze requires a registered native v3/v4/v5 project")
        if not self.settings.freeze_allowed(project.root):
            raise AccessDenied("Freeze is not enabled for this project")
        root = Path(project.root)
        if self.catalog.excluded(root / "Freeze"):
            raise AccessDenied("Freeze workspace is excluded")
        stat = os.stat(root, follow_symlinks=False)
        if (stat.st_dev, stat.st_ino) != (project.device, project.inode):
            raise AccessDenied("Project root changed during access")
        return FreezeStore(root)

    def work(self, project_id, *, write=False):
        store = self.store(project_id)
        if not store.v5:
            raise AccessDenied(
                "This operation requires explicit project upgrade-v5; legacy reads remain available"
            )
        if write and self.settings.freeze_mode != "write":
            raise AccessDenied("Freeze write mode is not enabled")
        return WorkStore(store)

    @staticmethod
    def question_view(record):
        keys = {"id", "title", "group", "revision", "messages", "suggestions", "status", "historical"}
        result = {key: copy.deepcopy(value) for key, value in record.items() if key in keys}
        definition = record.get("definition", {})
        result["definition"] = {
            "current_version": definition.get("current_version"),
            "draft": public_definition(definition.get("draft")),
            "versions": [public_definition(v) for v in definition.get("versions", [])],
        }
        result["external_brief"] = copy.deepcopy(record.get("external_brief"))
        return result

    def snapshot(self, project_id: str):
        store = self.store(project_id)
        result = store.snapshot()
        if store.v5:
            return {
                "governance_version": 5,
                "questions": [
                    self.question_view(q)
                    for q in result["questions"]
                    if self.allowed_path(project_id, self.item_path(q["id"]))
                ],
                "decision_groups": [
                    {
                        k: copy.deepcopy(g[k])
                        for k in ("id", "title", "revision", "member_ids", "messages")
                        if k in g
                    }
                    for g in result.get("decision_groups", [])
                    if self.allowed_path(project_id, "decision-groups.json")
                ],
            }
        return result

    def read(self, project_id: str, question_id: str, include_example: bool = False):
        store = self.store(project_id)
        self.check_path(project_id, self.item_path(question_id))
        record = store.read_question(question_id, include_example if not store.v5 else False)
        return self.question_view(record) if store.v5 else record

    def work_index(self, project_id, offset=0, limit=100):
        work = self.work(project_id)
        visible, cursor = [], 0
        while True:
            index = work.index(offset=cursor, limit=100)
            for item in index["items"]:
                if not self.allowed_path(project_id, self.item_path(item["id"])):
                    continue
                if item["id"].startswith("I-") and not work.read(item["id"]).get("external_brief"):
                    continue
                keys = {"id", "title", "revision", "phase", "human_pending", "category"}
                visible.append({key: value for key, value in item.items() if key in keys})
            cursor += len(index["items"])
            if cursor >= index["total"]:
                break
        return page(visible, offset, limit)

    def read_work(self, project_id, item_id):
        work = self.work(project_id)
        self.check_path(project_id, self.item_path(item_id))
        record = work.read(item_id)
        if item_id.startswith("I-") and not record.get("external_brief"):
            raise AccessDenied("Investigation has no shared brief")
        shared = [
            p
            for p in record.get("evidence_refs", [])
            if self.allowed_path(project_id, p) and work.evidence(p).get("disclosure") == "shared"
        ]
        return {
            "id": item_id,
            "title": record["title"],
            "revision": record["revision"],
            "phase": record["work"]["phase"],
            "member_ids": record["member_ids"],
            "candidate": public_definition(record["candidate"]),
            "current": public_definition(record["current"]),
            "external_brief": record.get("external_brief"),
            "evidence_refs": shared,
            "messages": record["messages"],
            "inputs": [e for e in record["inputs"] if e["actor"] in {"user", "external_ai"}],
            "review_required": bool(record.get("review_required")),
        }

    def evidence_index(self, project_id, offset=0, limit=100):
        work = self.work(project_id)
        with work.store.locked(create=False):
            paths = work.store._manifest().get("evidence_paths", [])
            records = [(p, work.read_json(p)) for p in paths]
        visible = [
            {
                "path": path,
                "id": value["id"],
                "version": value["version"],
                "kind": "source" if "/sources/" in path else "claim",
            }
            for path, value in records
            if self.allowed_path(project_id, path) and value.get("disclosure") == "shared"
        ]
        return page(visible, offset, limit)

    def read_evidence(self, project_id, path):
        work = self.work(project_id)
        self.check_path(project_id, path)
        value = work.evidence(path)
        if value.get("disclosure") != "shared":
            raise AccessDenied("Evidence version is not shared with external clients")
        keys = {
            "id",
            "version",
            "source_type",
            "verification",
            "citation",
            "read_scope",
            "retrieved_at",
            "location",
            "claim",
            "applicability",
            "disclosure",
        }
        result = {k: copy.deepcopy(v) for k, v in value.items() if k in keys}
        restricted = False
        for key in ("sources", "counter_sources"):
            if key in value:
                result[key] = []
                for ref in value[key]:
                    if (
                        self.allowed_path(project_id, ref)
                        and work.evidence(ref).get("disclosure") == "shared"
                    ):
                        result[key].append(ref)
                    else:
                        restricted = True
        result["has_undisclosed_sources"] = restricted
        return result

    def submit_evidence(self, project_id, text, targets, refs, request_id):
        if any(not isinstance(ref, str) for ref in refs):
            raise AccessDenied("Evidence references must be citation strings")
        for target in targets:
            self.check_path(project_id, self.item_path(target))
            if target.startswith("I-"):
                self.read_work(project_id, target)
        return self.work(project_id, write=True).evidence_submit(
            {"text": text, "targets": targets, "refs": refs}, request_id=request_id, actor="external_ai"
        )

    def comment(self, project_id, item_id, text, expected_revision, request_id, question_id=None):
        if not item_id.startswith(("F-", "B-")):
            raise AccessDenied("External comments require an existing F or group")
        self.check_path(project_id, self.item_path(item_id))
        return self.work(project_id, write=True).commit_work(
            {
                "read_set": {item_id: expected_revision},
                "changes": [
                    {
                        "id": item_id,
                        "comments": [{"text": text, **({"question_id": question_id} if question_id else {})}],
                    }
                ],
            },
            request_id=request_id,
            actor="external_ai",
        )

    def add(self, *args, **kwargs):
        raise AccessDenied("MCP cannot create F records; submit evidence for local triage")

    def change(self, *args, **kwargs):
        raise AccessDenied("Generic MCP question mutation has been removed")

    def change_group(self, *args, **kwargs):
        raise AccessDenied("Generic MCP group mutation has been removed")
