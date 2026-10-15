"""Legacy review/Attention commands route to the single investigation store."""

from __future__ import annotations

import re

from . import project_transaction as tx
from .project import Project, json_bytes
from .store import FreezeError, FreezeStore, require_text
from .workstore import WorkStore

LEGACY_FIELDS = {
    "title",
    "blocking",
    "observation",
    "evidence",
    "why_it_matters",
    "why_no_action_was_taken",
    "human_decision_needed",
}


def listing(root, *, offset=0, limit=100, actionable=False):
    project = Project(root)
    project.baseline_state()
    if not (project.root / "Freeze").exists():
        return {"items": [], "total": 0, "next_offset": None, "inbox": [], "inbox_total": 0}
    return WorkStore(FreezeStore(project.root)).index(offset=offset, limit=limit, actionable=actionable)


def raise_issue(root, payload, *, request_id=None):
    if not isinstance(payload, dict):
        raise FreezeError("Review payload must be an object")
    if set(payload) == LEGACY_FIELDS:
        if type(payload["blocking"]) is not bool:
            raise FreezeError("Review blocking must be a JSON boolean")
        text = {k: require_text(payload[k], k, 5000) for k in LEGACY_FIELDS - {"blocking"}}
        if "\n" in text["title"] or "\r" in text["title"]:
            raise FreezeError("Review title must be a single line")
        value = {
            "title": text["title"],
            "dedupe_key": "review-title:" + " ".join(text["title"].casefold().split()),
            "why": "\n\n".join(
                k.replace("_", " ").capitalize() + ": " + text[k]
                for k in (
                    "observation",
                    "evidence",
                    "why_it_matters",
                    "why_no_action_was_taken",
                    "human_decision_needed",
                )
            ),
            "blockers": [text["human_decision_needed"]] if payload["blocking"] else [],
        }
    elif {"title", "why", "dedupe_key"} <= set(payload) and not set(payload) - {
        "title",
        "why",
        "dedupe_key",
        "blockers",
        "submission_path",
    }:
        value = payload
    else:
        raise FreezeError("Use the complete legacy Attention payload or title, why and dedupe_key")
    with tx.project_lock(root):
        Project(root).baseline_state()
        # Stable replay also covers clients using the old command without request IDs.
        request_id = request_id or "review-raise-" + tx.digest(json_bytes(payload))
        return WorkStore(FreezeStore(root)).investigation(value, request_id=request_id)


def resolve(
    root, identifier, *, reason=None, conclusion="fact_lookup", expected_revision=None, request_id=None
):
    if not isinstance(identifier, str) or not re.fullmatch(r"(?:I-[0-9]{6}|A-[0-9]{4,})", identifier):
        raise FreezeError(
            "review resolve accepts investigations or migrated Attention IDs; use Council for F/B"
        )
    reason = require_text(
        reason or "Local agent marked this issue resolved through review resolve.", "reason", 5000
    )
    if conclusion not in {"fact_lookup", "covered", "not_applicable"}:
        raise FreezeError("Resolution must state fact_lookup, covered or not_applicable")
    with tx.project_lock(root):
        project = Project(root)
        project.baseline_state()
        work = WorkStore(FreezeStore(project.root))
        if identifier.startswith("A-"):
            with work.store.locked():
                _, _, records = work.records()
                matches = [
                    r["id"] for r in records.values() if r.get("legacy_attention", {}).get("id") == identifier
                ]
            if len(matches) != 1:
                raise FreezeError("Legacy Attention ID must map to exactly one migrated investigation")
            identifier = matches[0]
        record = work.read(identifier)
        if expected_revision is not None and expected_revision != record["revision"]:
            raise FreezeError("Work changed since read; reload before resolving")
        if record["inputs"] or any(not p.get("resolved") for p in record["pending_items"]):
            raise FreezeError(
                "Use work_commit to account for unread feedback and unresolved pending items before closing"
            )
        if record["work"]["phase"] == "closed":
            return {"changed_paths": [], "id": identifier, "replayed": True}
        request_id = request_id or "review-resolve-" + tx.digest(
            json_bytes(
                {
                    "id": identifier,
                    "revision": record["revision"],
                    "reason": reason,
                    "conclusion": conclusion,
                }
            )
        )
        return work.commit_work(
            {
                "read_set": {identifier: record["revision"]},
                "changes": [
                    {
                        "id": identifier,
                        "comments": [{"text": reason}],
                        "phase": {
                            "phase": "closed",
                            "conclusion_type": conclusion,
                            "reason": reason,
                            "affected_refs": [identifier],
                            "completion_conditions": [reason],
                            "blockers": [],
                        },
                        "progress": {"bootstrap_complete": True, "bootstrap_reason": reason},
                    }
                ],
            },
            request_id=request_id,
        )
