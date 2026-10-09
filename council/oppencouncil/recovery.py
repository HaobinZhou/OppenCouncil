"""Evidence-backed local recovery of existing project decisions and discussions."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import PurePosixPath

from .store import (
    MAX_JSON,
    QUESTION_ID,
    FreezeError,
    FreezeStore,
    atomic_json,
    governance_registry,
    now,
    ordinary_file,
    request_fingerprint,
    require_text,
)


def source_text(store: FreezeStore, source: dict) -> tuple[dict, str]:
    path = require_text(source.get("path"), "source.path", 2048)
    relative = PurePosixPath(path)
    if relative.is_absolute() or ".." in relative.parts or "\\" in path or path != relative.as_posix():
        raise FreezeError("Recovery sources must be normalized paths inside this project")
    if relative.parts and relative.parts[0] == "Freeze":
        raise FreezeError("Native Freeze records are reused directly, not recovered as external quotes")
    current = store.project
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise FreezeError("Recovery source must not be linked")
    raw = ordinary_file(current, MAX_JSON)
    if raw is None:
        raise FreezeError("Recovery source is unavailable")
    digest = hashlib.sha256(raw).hexdigest()
    if source.get("sha256") != digest:
        raise FreezeError("Recovery source changed; read it again before importing")
    try:
        text = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    except UnicodeDecodeError as error:
        raise FreezeError("Recovery sources must be UTF-8 text") from error
    section = source.get("section")
    if section:
        section = require_text(section, "source.section", 300)
        headings = list(re.finditer(r"^(#{1,6})\s+(.+?)\s*$", text, re.MULTILINE))
        matches = [i for i, heading in enumerate(headings) if heading[2] == section]
        if len(matches) != 1:
            raise FreezeError("Recovery source section is missing or ambiguous")
        index = matches[0]
        heading = headings[index]
        end = next(
            (other.start() for other in headings[index + 1 :] if len(other[1]) <= len(heading[1])),
            len(text),
        )
        text = text[heading.start() : end]
    excerpt = require_text(source.get("excerpt"), "source.excerpt").replace("\r\n", "\n").replace("\r", "\n")
    if excerpt not in text:
        raise FreezeError("Recovery quote is absent from its source")
    return {"path": path, "section": section or None, "sha256": digest, "excerpt": excerpt}, text


def registered_owner(store: FreezeStore, topic: str, source: dict) -> str | None:
    registry_path, prefix = governance_registry(store.project)
    raw = ordinary_file(registry_path, MAX_JSON)
    if raw is None:
        raise FreezeError("Project registry is unavailable")
    project = raw.decode("utf-8")
    start = f"<!-- {prefix}:canonical:start -->"
    end = f"<!-- {prefix}:canonical:end -->"
    if project.count(start) != 1 or project.count(end) != 1:
        raise FreezeError("Frozen recovery requires a registered Canonical owner")
    block = project.split(start, 1)[1].split(end, 1)[0]
    rows = [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in block.splitlines()]
    width = 5 if prefix == "oppen-project-steward" else 4
    matches = [row for row in rows if len(row) == width and row[0] == topic]
    if len(matches) != 1 or matches[0][1:3] != [source["path"], source["section"] or "-"]:
        raise FreezeError("Frozen recovery must match the registered topic, path and section")
    status = matches[0][3] if width == 5 else None
    if status is not None and status not in {"draft", "partially-frozen", "frozen"}:
        raise FreezeError("Invalid Canonical registry status")
    return status


def live_text(text: str) -> str:
    """Exclude examples, comments and blockquotes from current authority checks."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    lines, fence = [], None
    for line in text.splitlines():
        marker = re.match(r"^\s*(" + chr(96) + r"{3,}|~{3,})", line)
        if marker:
            symbol = marker[1][0]
            fence = None if fence == symbol else symbol if fence is None else fence
        elif fence is None and not line.lstrip().startswith(">"):
            lines.append(line)
    return "\n".join(lines)


def frozen_owner(store: FreezeStore, topic: str, source: dict, text: str, scope: str = "owner") -> None:
    registry_status = registered_owner(store, topic, source)
    text = live_text(text)
    if scope == "item":
        excerpt = source["excerpt"]
        if len(excerpt) > 4000 or excerpt not in text:
            raise FreezeError("Item freeze evidence must be a bounded live Canonical quote")
        # Association with the specific definition and later decisions is reviewed by
        # local Codex; this check only admits an explicit affirmative source statement.
        if not re.search(r"已冻结|(?:Status|状态)\s*[:：]\s*(?:frozen|已冻结)\b", excerpt, re.I):
            raise FreezeError("Item freeze evidence must explicitly state frozen")
        if re.search(
            r"未冻结|尚未冻结|待冻结|取消冻结|解除冻结|重新打开|待确认|待讨论|unfrozen|reopened",
            excerpt,
            re.I,
        ):
            raise FreezeError("Item freeze evidence contains an unresolved or reopened qualification")
        return
    statuses = re.findall(r"^(?:Status|状态)\s*[:：]\s*(.+?)\s*$", text, re.I | re.M)
    cleaned = [status.strip().strip("*_" + chr(96)).strip().lower() for status in statuses]
    if (registry_status is not None and registry_status != "frozen") or (
        not cleaned and registry_status != "frozen"
    ) or any(status not in {"frozen", "已冻结"} for status in cleaned):
        raise FreezeError("Canonical owner is not unambiguously frozen")


def verified_record(store: FreezeStore, item: dict, reconcile: bool = False) -> dict:
    if not isinstance(item, dict):
        raise FreezeError("Each recovery record must be an object")
    kind = item.get("kind")
    if kind not in {"frozen", "discussion", "unconfirmed", "historical"}:
        raise FreezeError("Recovery kind must be frozen, discussion, unconfirmed or historical")
    sources = item.get("sources")
    if not isinstance(sources, list) or not 1 <= len(sources) <= 20:
        raise FreezeError("Recovery records require 1–20 source quotes")
    checked = [source_text(store, source) for source in sources if isinstance(source, dict)]
    if len(checked) != len(sources):
        raise FreezeError("Each recovery source must be an object")
    summary = require_text(item.get("summary"), "recovery.summary")
    canonical_index = item.get("canonical_source")
    canonical_topic = item.get("canonical_topic")
    scope = item.get("canonical_scope", "owner")
    if scope not in {"owner", "item"}:
        raise FreezeError("canonical_scope must be owner or item")
    if kind in {"frozen", "historical"}:
        if type(canonical_index) is not int or not 0 <= canonical_index < len(checked):
            raise FreezeError("Frozen recovery requires canonical_source")
        source, text = checked[canonical_index]
        topic = require_text(canonical_topic, "canonical_topic", 100)
        if kind == "frozen":
            frozen_owner(store, topic, source, text, scope)
            if summary not in source["excerpt"]:
                raise FreezeError("Recovered frozen definition must quote the Canonical source")
        else:
            registered_owner(store, topic, source)
            resolution = require_text(item.get("resolution"), "historical.resolution")
            if resolution not in source["excerpt"] or source["excerpt"] not in live_text(text):
                raise FreezeError("Settled history requires a live current Canonical resolution quote")
            require_text(item.get("reason"), "historical.reason", 4000)
    messages = item.get("messages", [])
    if not isinstance(messages, list) or len(messages) > 100:
        raise FreezeError("Recovery messages must contain at most 100 entries")
    clean_messages = []
    for message in messages:
        if not isinstance(message, dict):
            raise FreezeError("Each recovery message must be an object")
        index = message.get("source")
        actor = message.get("actor", "unknown")
        if type(index) is not int or not 0 <= index < len(checked):
            raise FreezeError("Recovery message must reference a verified source")
        if actor not in {"user", "codex", "chatgpt", "web_ai", "unknown"}:
            raise FreezeError("Unknown historical author; use unknown when unrecoverable")
        text = require_text(message.get("text"), "recovery.message")
        if text not in checked[index][0]["excerpt"]:
            raise FreezeError("Recovered message must quote its source")
        at = message.get("at")
        if at is not None:
            at = require_text(at, "recovery.message.at", 100)
            if at not in checked[index][0]["excerpt"]:
                raise FreezeError("Historical timestamp must occur in its source")
        clean_messages.append({"actor": actor, "text": text, "source": index, "at": at})
    result = {
        "key": require_text(item.get("key"), "recovery.key", 120),
        "kind": kind,
        "group": require_text(item.get("group", "历史记录"), "group", 80),
        "title": require_text(item.get("title"), "title", 300),
        "summary": summary,
        "sources": [source for source, _ in checked],
        "messages": clean_messages,
        "canonical_topic": canonical_topic if kind in {"frozen", "historical"} else None,
        "canonical_source": canonical_index if kind in {"frozen", "historical"} else None,
        "question_id": item.get("question_id"),
    }
    if result["question_id"] is not None:
        if not isinstance(result["question_id"], str) or not QUESTION_ID.fullmatch(result["question_id"]):
            raise FreezeError("Invalid recovery target question")
        if type(item.get("expected_revision")) is not int:
            raise FreezeError("Attaching history requires the current question revision")
    # Preserve fingerprints of 0.1.1 payloads so existing receipts still replay.
    if "canonical_scope" in item:
        result["canonical_scope"] = scope
    if kind == "frozen" and scope == "item":
        result["reason"] = require_text(item.get("reason"), "item.reason", 4000)
    if kind == "historical":
        result.update(resolution=resolution, reason=item["reason"])
    if reconcile:
        if result["question_id"] is None:
            raise FreezeError("Reconciliation requires an existing question_id")
        result.update(
            supersedes=require_text(item.get("supersedes"), "reconcile.supersedes", 120),
            reason=require_text(item.get("reason"), "reconcile.reason", 4000),
            operation="reconcile",
        )
        if result["supersedes"] == result["key"]:
            raise FreezeError("Reconciliation needs a new key; original evidence is immutable")
    result["fingerprint"] = request_fingerprint("recovery", result)
    result["expected_revision"] = item.get("expected_revision")
    return result


def recover_records(
    store: FreezeStore, records: list[dict], *, reconcile: bool = False, dry_run: bool = False
) -> dict:
    """Recover quoted evidence without writing a human answer or Canonical file."""
    if not isinstance(records, list) or not 1 <= len(records) <= 200:
        raise FreezeError("Recover 1–200 records per batch")
    with store.locked(create=not dry_run):
        verified = [verified_record(store, item, reconcile) for item in records]
        if len({item["key"] for item in verified}) != len(verified):
            raise FreezeError("Recovery keys must be unique within a batch")
        manifest = store._manifest()
        original_ids = set(manifest["question_ids"])
        saved = {qid: store._question(qid) for qid in manifest["question_ids"]}
        for path in store.questions.glob("F-*.json"):
            if path.stem not in saved:
                saved[path.stem] = store._question(path.stem)
        receipts = {}
        for qid, question in saved.items():
            for record in question.get("recovered_records", []):
                if record["key"] in receipts:
                    raise FreezeError("Ambiguous historical recovery key")
                receipts[record["key"]] = (qid, record["fingerprint"])
        next_number = max((int(qid[2:]) for qid in saved), default=0) + 1
        new_round = manifest["round"] + 1
        changed, ids = {}, []
        created = attached = replayed = 0
        corrections = []
        for item in verified:
            receipt = receipts.get(item["key"])
            if receipt:
                if receipt[1] != item["fingerprint"]:
                    raise FreezeError("Recovery key was used with different evidence")
                qid = receipt[0]
                replayed += 1
            else:
                qid = item["question_id"]
                if qid:
                    if qid not in original_ids or qid in changed:
                        raise FreezeError("Attach one recovery record per existing question in a batch")
                    question = copy.deepcopy(saved[qid])
                    if question["revision"] != item["expected_revision"]:
                        raise FreezeError("Question changed since read; reload before recovery")
                    if reconcile:
                        history = question.get("recovered_records", [])
                        if not any(record["key"] == item["supersedes"] for record in history):
                            raise FreezeError(
                                "Correction must supersede recovery evidence on the same question"
                            )
                        if any(record.get("supersedes") == item["supersedes"] for record in history):
                            raise FreezeError(
                                "Recovery classification was already superseded; read its latest record"
                            )
                        previous_status = question["status"]
                        protected = bool(question["user_answer"] or question["requests"]) or any(
                            not message.get("recovered")
                            and (message["actor"] == "user" or message["text"].startswith("重新讨论："))
                            for message in question["messages"]
                        )
                        if not protected:
                            question["status"] = recovery_status(item["kind"])
                        corrections.append(
                            {
                                "id": qid,
                                "before": previous_status,
                                "after": question["status"],
                                "classification": item["kind"],
                                "review_preserved": protected,
                            }
                        )
                        question["group"], question["title"] = item["group"], item["title"]
                    elif (
                        item["kind"] == "frozen"
                        and question["status"] == "open"
                        and not question["user_answer"]
                    ):
                        question["status"] = "frozen"
                    attached += 1
                else:
                    qid = f"F-{next_number:06d}"
                    next_number += 1
                    question = {
                        "schema_version": 1,
                        "id": qid,
                        "round": new_round,
                        "group": item["group"],
                        "title": item["title"],
                        "why": "恢复旧项目口径与讨论记录",
                        "source_summary": "；".join(source["path"] for source in item["sources"]),
                        "ai_position": "",
                        "ai_position_by": None,
                        "suggestions": [],
                        "created_by": "codex",
                        "created_at": now(),
                        "status": recovery_status(item["kind"]),
                        "user_answer": None,
                        "messages": [],
                        "example": None,
                        "canonical_ref": None,
                        "revision": 0,
                        "requests": {},
                    }
                    created += 1
                record = {
                    key: value
                    for key, value in item.items()
                    if key not in {"question_id", "expected_revision", "messages"}
                }
                record.update(recovered_by="codex", recovered_at=now())
                if reconcile:
                    record["correction"] = corrections[-1]
                    record["previous_display"] = {
                        "group": saved[qid]["group"],
                        "title": saved[qid]["title"],
                    }
                if item["kind"] in {"frozen", "historical"} or reconcile:
                    source = (
                        item["sources"][item["canonical_source"]]
                        if item["canonical_source"] is not None
                        else None
                    )
                    canonical_ref = (
                        source["path"] + ("#" + source["section"] if source["section"] else "")
                        if source
                        else None
                    )
                    question["recovery_classification"] = {
                        "kind": item["kind"],
                        "key": item["key"],
                        "canonical_ref": canonical_ref,
                        "summary": item["summary"],
                        "at": record["recovered_at"],
                    }
                    if not question.get("definition", {}).get("current_version"):
                        question["canonical_ref"] = canonical_ref
                question.setdefault("recovered_records", []).append(record)
                for number, message in enumerate(item["messages"]):
                    question["messages"].append(
                        {
                            "id": "history-"
                            + hashlib.sha256((item["key"] + ":" + str(number)).encode()).hexdigest()[:24],
                            "actor": message["actor"],
                            "text": message["text"],
                            "round": question["round"],
                            "at": message["at"],
                            "recovered": True,
                            "recovered_by": "codex",
                            "recovered_at": record["recovered_at"],
                            "source": item["sources"][message["source"]],
                        }
                    )
                question["revision"] += 1
                changed[qid] = question
            ids.append(qid)
            if qid not in manifest["question_ids"]:
                manifest["question_ids"].append(qid)
                manifest["round"] = max(manifest["round"], changed.get(qid, saved.get(qid))["round"])
        if changed or any(qid not in original_ids for qid in ids):
            manifest["revision"] += 1
            for value in [manifest, *changed.values()]:
                if len(json.dumps(value, ensure_ascii=False).encode("utf-8")) > MAX_JSON:
                    raise FreezeError("Recovered records exceed the file size limit")
            if not dry_run:
                for qid, question in changed.items():
                    atomic_json(store.questions / f"{qid}.json", question)
                atomic_json(store.manifest, manifest)
        return {
            "ids": ids,
            "created": created,
            "attached": attached,
            "replayed": replayed,
            "round": manifest["round"],
            "corrections": corrections,
            "dry_run": dry_run,
        }


def recovery_status(kind: str) -> str:
    return {
        "frozen": "frozen",
        "discussion": "discussing",
        "unconfirmed": "open",
        "historical": "historical",
    }[kind]
