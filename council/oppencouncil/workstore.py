"""Transactional v5 work operations shared by CLI, site and the restricted MCP adapter."""

from __future__ import annotations

import copy
import json
import re
import secrets
from pathlib import Path

from . import workflow as wf
from .decisions import (
    all_questions,
    catalog,
    commit,
    notify_dependency_changes,
    readiness,
    review_dependencies,
)
from .definitions import approval_token, digest, state
from .store import MAX_JSON, FreezeError, now, ordinary_file, request_fingerprint, require_text


def validate_evidence(path, value):
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise FreezeError("Invalid evidence record")
    require_text(value.get("id"), "evidence ID", 100)
    if wf.SUBMISSION_PATH.fullmatch(path):
        require_text(value.get("text"), "evidence submission")
        if value.get("actor") not in {"codex", "external_ai"}:
            raise FreezeError("Invalid evidence contributor")
        if value["id"] != Path(path).stem:
            raise FreezeError("Submission identity does not match path")
        if (
            not isinstance(value.get("targets"), list)
            or any(not isinstance(t, str) or not wf.ITEM_ID.fullmatch(t) for t in value["targets"])
            or len(value["targets"]) != len(set(value["targets"]))
        ):
            raise FreezeError("Invalid evidence submission targets")
        if not isinstance(value.get("refs"), list):
            raise FreezeError("Submission references must be a list")
        return
    if not wf.EVIDENCE_PATH.fullmatch(path):
        raise FreezeError("Invalid evidence path")
    if value.get("version") != int(Path(path).stem[1:]) or value["id"] != Path(path).parent.name:
        raise FreezeError("Evidence identity does not match its path")
    if path.startswith("evidence/sources/"):
        if (
            value.get("source_type") not in wf.SOURCE_TYPES
            or value.get("verification") not in wf.VERIFICATION
        ):
            raise FreezeError("Source requires a source type and verification method")
        require_text(value.get("citation"), "source citation", 5000)
        require_text(value.get("read_scope"), "source reading scope", 5000)
        require_text(value.get("retrieved_at"), "source retrieval time", 100)
        if value.get("disclosure") not in {"local", "shared"}:
            raise FreezeError("Source must declare local or shared disclosure")
        if value["verification"] == "full_text_location":
            require_text(value.get("location"), "original text location", 5000)
    else:
        require_text(value.get("claim"), "supported judgment", 10000)
        require_text(value.get("applicability"), "applicability", 5000)
        if not isinstance(value.get("sources"), list) or not value["sources"]:
            raise FreezeError("A judgment requires source versions")
        for source in [*value["sources"], *value.get("counter_sources", [])]:
            if not isinstance(source, str) or not re.fullmatch(
                r"evidence/sources/S-[0-9]{6}/r[0-9]{6}\.json", source
            ):
                raise FreezeError("Judgments must reference explicit source versions")
        if value.get("disclosure") not in {"local", "shared"}:
            raise FreezeError("Judgment must declare local or shared disclosure")


def validate_transaction_record(path, value):
    if re.fullmatch(r"investigations/I-[0-9]{6}\.json", path):
        if value.get("id") != Path(path).stem or value.get("schema_version") != 1:
            raise FreezeError("Invalid investigation identity")
        wf.validate_record(value)
    elif wf.EVIDENCE_PATH.fullmatch(path) or wf.SUBMISSION_PATH.fullmatch(path):
        validate_evidence(path, value)
    else:
        raise FreezeError("Unsafe work transaction path")


class WorkStore:
    def __init__(self, store):
        if not store.v5:
            raise FreezeError("This operation requires an explicitly migrated v5 project")
        self.store = store

    def read_json(self, path):
        if not (
            wf.EVIDENCE_PATH.fullmatch(path)
            or wf.SUBMISSION_PATH.fullmatch(path)
            or re.fullmatch(r"investigations/I-[0-9]{6}\.json", path)
        ):
            raise FreezeError("Invalid work resource path")
        current = self.store.root
        for part in Path(path).parts[:-1]:
            current /= part
            self.store._directory(current, False)
        raw = ordinary_file(self.store.root / path, MAX_JSON)
        if raw is None:
            raise FreezeError("Work resource not found")
        result = json.loads(raw)
        validate_transaction_record(path, result)
        return result

    def evidence(self, path):
        with self.store.locked():
            return self.read_json(path)

    def evidence_index(self, *, source_id=None, offset=0, limit=100):
        """Rebuild source → judgment → F links without interpreting the impact."""
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 200:
            raise FreezeError("Invalid evidence pagination")
        if source_id is not None and not re.fullmatch(r"S-[0-9]{6}", source_id):
            raise FreezeError("Invalid source ID")
        with self.store.locked():
            manifest = self.store._manifest()
            records = {path: self.read_json(path) for path in manifest.get("evidence_paths", [])}
            questions = all_questions(self.store)
            items = []
            for path, record in records.items():
                if (
                    source_id
                    and record["id"] != source_id
                    and not any(
                        Path(source).parent.name == source_id
                        for source in [*record.get("sources", []), *record.get("counter_sources", [])]
                    )
                ):
                    continue
                claims = [
                    p
                    for p, c in records.items()
                    if path in [*c.get("sources", []), *c.get("counter_sources", [])]
                ]
                related = [
                    qid
                    for qid, q in questions.items()
                    if any(
                        p == path or p in claims
                        for p in [
                            *q.get("evidence_refs", []),
                            *(q.get("review_basis") or {}).get("claims", []),
                        ]
                    )
                ]
                items.append(
                    {
                        "path": path,
                        "id": record["id"],
                        "version": record["version"],
                        "summary": record.get("claim", record.get("citation")),
                        "disclosure": record["disclosure"],
                        "claims": claims,
                        "question_ids": related,
                    }
                )
            return {
                "items": items[offset : offset + limit],
                "total": len(items),
                "next_offset": offset + limit if offset + limit < len(items) else None,
            }

    def records(self):
        questions = all_questions(self.store)
        groups = catalog(self.store)
        investigations = {
            iid: self.read_json(f"investigations/{iid}.json")
            for iid in self.store._manifest().get("investigation_ids", [])
        }
        return questions, groups, investigations

    def locate(self, identifier, questions, groups, investigations):
        if not isinstance(identifier, str) or not wf.ITEM_ID.fullmatch(identifier):
            raise FreezeError("Invalid work item ID")
        record = (
            questions.get(identifier)
            or investigations.get(identifier)
            or next((g for g in groups["groups"] if g["id"] == identifier), None)
        )
        if record is None:
            raise FreezeError("Work item not found")
        return record

    def index(self, *, actionable=False, offset=0, limit=100):
        if type(offset) is not int or type(limit) is not int or offset < 0 or not 1 <= limit <= 200:
            raise FreezeError("Invalid work index pagination")
        with self.store.locked():
            questions, groups, investigations = self.records()
            manifest = self.store._manifest()
            items = []
            for record in [*questions.values(), *investigations.values(), *groups["groups"]]:
                view = wf.projection(record, questions)
                if actionable and not view["actionable"]:
                    continue
                items.append(
                    {
                        "id": record["id"],
                        "title": record["title"],
                        "revision": record["revision"],
                        "phase": record["work"]["phase"],
                        **view,
                        "blockers": record["work"]["blockers"],
                        "pending_human_count": sum(e["actor"] == "user" for e in wf.unread(record)),
                        **(
                            {"legacy_id": record["legacy_attention"]["id"]}
                            if record.get("legacy_attention")
                            else {}
                        ),
                    }
                )
            inbox = []
            for path in manifest.get("submission_paths", []):
                entry = self.read_json(path)
                if not entry["targets"] and path not in manifest.get("submission_reviews", {}):
                    inbox.append({"path": path, "id": entry["id"], "summary": entry["text"][:500]})
            return {
                "items": items[offset : offset + limit],
                "total": len(items),
                "next_offset": offset + limit if offset + limit < len(items) else None,
                "inbox": inbox[offset : offset + limit],
                "inbox_total": len(inbox),
            }

    def read(self, identifier):
        with self.store.locked():
            questions, groups, investigations = self.records()
            record = self.locate(identifier, questions, groups, investigations)
            d = record.get("definition", {})
            draft = d.get("draft")
            candidate = (
                {
                    k: copy.deepcopy(draft[k])
                    for k in ("text", "text_sha256", "base_version", "dependencies", "review_basis")
                    if k in draft
                }
                if draft
                else None
            )
            if candidate:
                from .decisions import candidate_for_approval

                visible = candidate_for_approval(identifier, questions)
                candidate["dependencies"] = visible.get("dependencies", [])
                candidate["approval_token"] = approval_token(visible)
            current = d.get("versions", [])[-1] if d.get("current_version") else None
            current_view = (
                {
                    k: copy.deepcopy(current[k])
                    for k in (
                        "number",
                        "text",
                        "text_sha256",
                        "dependencies",
                        "review_basis",
                        "reconfirmations",
                    )
                    if k in current
                }
                if current
                else None
            )
            inputs = wf.unread(record)
            refs = {e["reference"] for e in inputs if isinstance(e["reference"], str)}
            pending = [p for p in record["pending_items"] if not p.get("resolved")]
            pending_refs = {ref for p in pending for ref in p.get("input_refs", [])}
            refs.update(
                e["reference"]
                for e in record["feedback_events"]
                if e["id"] in pending_refs and isinstance(e["reference"], str)
            )
            messages = [m for m in record.get("messages", []) if m["id"] in refs]
            if record["processing"]["bootstrap"] == "needs_reconciliation":
                messages = record.get("messages", [])
            return {
                "id": identifier,
                "title": record["title"],
                "why": record.get("why"),
                "legacy_attention": {
                    key: copy.deepcopy(record["legacy_attention"][key]) for key in ("id", "path", "fields")
                }
                if record.get("legacy_attention")
                else None,
                "revision": record["revision"],
                "work": copy.deepcopy(record["work"]),
                "inputs": copy.deepcopy(inputs),
                "messages": copy.deepcopy(messages),
                "pending_items": copy.deepcopy(pending),
                "candidate": candidate,
                "current": current_view,
                "review_basis": copy.deepcopy(record.get("review_basis")),
                "review_packet": copy.deepcopy(record.get("review_packet")),
                "external_brief": copy.deepcopy(record.get("external_brief")),
                "evidence_refs": copy.deepcopy(record.get("evidence_refs", [])),
                "review_required": copy.deepcopy(record.get("review_required")),
                "reconfirmation_token": wf.review_token(record) if identifier.startswith("F-") else None,
                "read_set": {identifier: record["revision"]},
                "member_ids": copy.deepcopy(record.get("member_ids", [])),
                "readiness": readiness(identifier, questions) if identifier.startswith("F-") else None,
                **wf.projection(record, questions),
            }

    def prepare_directories(self, writes):
        for path in writes:
            current = self.store.root
            for part in Path(path).parts[:-1]:
                current /= part
                self.store._directory(current, True)

    def save(self, manifest, writes, request_id, fingerprint, actor, result):
        manifest["requests"][request_id] = {"fingerprint": fingerprint, "actor": actor, "result": result}
        manifest["revision"] += 1
        writes["manifest.json"] = manifest
        self.prepare_directories(writes)
        commit(self.store, writes)
        return {**result, "replayed": False}

    @staticmethod
    def replay(manifest, request_id, fingerprint, actor):
        previous = manifest["requests"].get(request_id)
        if previous:
            if previous.get("fingerprint") != fingerprint or previous.get("actor") != actor:
                raise FreezeError("request_id was used with different content")
            return {**previous["result"], "replayed": True}
        return None

    def add(self, items, *, request_id, actor):
        if actor != "codex":
            raise FreezeError("Only the local agent may create F records")
        require_text(request_id, "request_id", 100)
        if not isinstance(items, list) or not 1 <= len(items) <= 200:
            raise FreezeError("Submit 1–200 questions")
        fp = request_fingerprint("v5:add", items)
        with self.store.locked(create=True):
            manifest = self.store._manifest()
            previous = self.replay(manifest, request_id, fp, actor)
            if previous:
                return previous
            number = max([int(i[2:]) for i in manifest["question_ids"]] + [0])
            writes, ids = {}, []
            for n, item in enumerate(items, number + 1):
                qid = f"F-{n:06d}"
                q = wf.upgrade_question(
                    {
                        "schema_version": 1,
                        "id": qid,
                        "revision": 1,
                        "title": require_text(item.get("title"), "title", 300),
                        "why": require_text(item.get("why"), "why", 5000),
                        "group": item.get("group", "其他"),
                        "suggestions": item.get("suggestions", []),
                        "source_summary": item.get("source_summary", "待核查"),
                        "round": manifest["round"] + 1,
                        "messages": [],
                        "requests": {},
                        "created_by": actor,
                        "created_at": now(),
                    }
                )
                q["processing"]["bootstrap"] = "complete"
                q["problem_type"] = item.get("problem_type", "unknown")
                q["work"]["trigger_refs"] = copy.deepcopy(item.get("trigger_refs", []))
                if item.get("ai_position"):
                    q["messages"].append(
                        {
                            "id": request_id + ":" + qid,
                            "actor": actor,
                            "text": item["ai_position"],
                            "kind": "proposal",
                            "at": now(),
                        }
                    )
                writes[f"questions/{qid}.json"] = q
                ids.append(qid)
            manifest["question_ids"].extend(ids)
            manifest["round"] += 1
            return self.save(
                manifest, writes, request_id, fp, actor, {"ids": ids, "round": manifest["round"]}
            )

    def investigation(self, payload, *, request_id, actor="codex"):
        if actor != "codex":
            raise FreezeError("External proposals require local triage before creating an investigation")
        require_text(request_id, "request_id", 100)
        if not isinstance(payload, dict) or set(payload) - {
            "title",
            "why",
            "dedupe_key",
            "blockers",
            "submission_path",
        }:
            raise FreezeError("Unknown investigation creation fields")
        blockers = payload.get("blockers", [])
        if not isinstance(blockers, list):
            raise FreezeError("Investigation blockers must be an array")
        for blocker in blockers:
            require_text(blocker, "investigation blocker", 5000)
        fp = request_fingerprint("v5:investigation", payload)
        with self.store.locked(create=True):
            manifest = self.store._manifest()
            previous = self.replay(manifest, request_id, fp, actor)
            if previous:
                return previous
            ids = manifest.setdefault("investigation_ids", [])
            iid = f"I-{max([int(i[2:]) for i in ids] + [0]) + 1:06d}"
            record = {
                "schema_version": 1,
                "id": iid,
                "revision": 1,
                "created_by": actor,
                "created_at": now(),
                "title": require_text(payload.get("title"), "title", 300),
                "why": require_text(payload.get("why"), "investigation reason", 5000),
                "dedupe_key": require_text(payload.get("dedupe_key"), "scope/deduplication key", 500),
                "question_ids": [],
                "work": wf.initial_work(),
                "messages": [],
                "evidence_refs": [],
            }
            record["work"]["blockers"] = copy.deepcopy(blockers)
            if payload.get("submission_path"):
                path = payload["submission_path"]
                self.read_json(path)
                if not wf.SUBMISSION_PATH.fullmatch(path) or path not in manifest.get("submission_paths", []):
                    raise FreezeError("Unknown external suggestion")
                if path in manifest.get("submission_reviews", {}):
                    raise FreezeError("Suggestion was already triaged; resume its existing item")
                record["work"]["trigger_refs"] = [path]
                manifest.setdefault("submission_reviews", {})[path] = {
                    "disposition": "investigation",
                    "id": iid,
                    "by": actor,
                    "at": now(),
                    "reason": record["why"],
                }
            if any(
                self.read_json(f"investigations/{prior}.json")["dedupe_key"] == record["dedupe_key"]
                for prior in ids
            ):
                raise FreezeError(
                    "An investigation with this scope already exists; resume or explicitly distinguish it"
                )
            wf.initialize_progress(record, question=False)
            ids.append(iid)
            return self.save(
                manifest, {f"investigations/{iid}.json": record}, request_id, fp, actor, {"id": iid}
            )

    def evidence_submit(self, payload, *, request_id, actor="external_ai"):
        if actor not in {"codex", "external_ai"}:
            raise FreezeError("Invalid evidence contributor")
        require_text(request_id, "request_id", 100)
        fp = request_fingerprint("v5:evidence", payload)
        with self.store.locked(create=True):
            manifest = self.store._manifest()
            previous = self.replay(manifest, request_id, fp, actor)
            if previous:
                return previous
            path = "evidence/submissions/X-" + secrets.token_hex(16) + ".json"
            record = {
                "schema_version": 1,
                "id": Path(path).stem,
                "text": payload.get("text"),
                "actor": actor,
                "at": now(),
                "refs": copy.deepcopy(payload.get("refs", [])),
                "targets": copy.deepcopy(payload.get("targets", [])),
                "request_id": request_id,
            }
            validate_evidence(path, record)
            questions, groups, investigations = self.records()
            writes = {path: record}
            for target in record["targets"]:
                item = self.locate(target, questions, groups, investigations)
                wf.event(item, request_id + ":" + target, actor, "evidence", path)
                item["revision"] += 1
                self.add_write(writes, item, groups)
            manifest.setdefault("submission_paths", []).append(path)
            return self.save(manifest, writes, request_id, fp, actor, {"path": path})

    @staticmethod
    def add_write(writes, record, groups):
        identifier = record["id"]
        if identifier.startswith("B-"):
            groups["revision"] += 1
            writes["decision-groups.json"] = groups
        else:
            directory = "questions" if identifier.startswith("F-") else "investigations"
            writes[f"{directory}/{identifier}.json"] = record

    def commit_work(self, payload, *, request_id, actor="codex"):
        require_text(request_id, "request_id", 100)
        if actor not in {"codex", "user", "external_ai"}:
            raise FreezeError("Invalid work actor")
        if (
            not isinstance(payload, dict)
            or not isinstance(payload.get("changes"), list)
            or (
                not payload["changes"]
                and not payload.get("evidence")
                and not payload.get("submission_reviews")
            )
        ):
            raise FreezeError("Work commit requires item changes")
        if set(payload) - {"changes", "read_set", "evidence", "submission_reviews"}:
            raise FreezeError("Unknown work transaction fields")
        if not isinstance(payload.get("read_set", {}), dict):
            raise FreezeError("Work read set must map item IDs to revisions")
        ids = [change.get("id") if isinstance(change, dict) else None for change in payload["changes"]]
        if any(not isinstance(i, str) for i in ids) or len(set(ids)) != len(ids):
            raise FreezeError("Combine each item's changes into one transaction entry")
        fp = request_fingerprint("v5:work", payload)
        with self.store.locked(create=True):
            manifest = self.store._manifest()
            previous = self.replay(manifest, request_id, fp, actor)
            if previous:
                return previous
            questions, groups, investigations = self.records()
            read_set = payload.get("read_set", {})
            previous_versions = {qid: state(q)["current_version"] for qid, q in questions.items()}
            for identifier, revision in read_set.items():
                if (
                    type(revision) is not int
                    or self.locate(identifier, questions, groups, investigations)["revision"] != revision
                ):
                    raise FreezeError("Work changed since read; reload before editing")
            writes, changed = {}, []
            if payload.get("submission_reviews"):
                if actor != "codex":
                    raise FreezeError("Only the local agent may triage external suggestions")
                for review in payload["submission_reviews"]:
                    path = review.get("path")
                    if path not in manifest.get("submission_paths", []):
                        raise FreezeError("Unknown submission")
                    if path in manifest.get("submission_reviews", {}):
                        raise FreezeError("Submission was already triaged")
                    if review.get("disposition") not in {"not_applicable", "covered"}:
                        raise FreezeError("Use investigation creation when further work is needed")
                    require_text(review.get("reason"), "submission triage reason", 5000)
                    manifest.setdefault("submission_reviews", {})[path] = {**review, "by": actor, "at": now()}
            if payload.get("evidence"):
                if actor != "codex":
                    raise FreezeError("Only the local agent may curate evidence versions")
                for entry in payload["evidence"]:
                    path, value = entry["path"], copy.deepcopy(entry["value"])
                    value.update(recorded_by=actor, recorded_at=now())
                    validate_evidence(path, value)
                    if self.store.root.joinpath(path).exists() or path in writes:
                        raise FreezeError("Evidence versions are append-only")
                    writes[path] = value
                for path, value in writes.items():
                    for source in [*value.get("sources", []), *value.get("counter_sources", [])]:
                        if source not in writes:
                            self.read_json(source)
                    # New versions must extend their identity's sequence; never reuse a hole.
                    earlier = [
                        p
                        for p in [*manifest.get("evidence_paths", []), *writes]
                        if Path(p).parent == Path(path).parent and p != path
                    ]
                    previous_version = max(
                        [int(Path(p).stem[1:]) for p in earlier if int(Path(p).stem[1:]) < value["version"]]
                        + [0]
                    )
                    if value["version"] != previous_version + 1:
                        raise FreezeError("Evidence versions must be consecutive")
            for change in payload["changes"]:
                identifier = change.get("id")
                if identifier not in read_set:
                    raise FreezeError("Each changed item must have a read revision")
                record = self.locate(identifier, questions, groups, investigations)
                self.apply_change(record, change, actor, request_id, questions, writes)
                if identifier not in changed:
                    record["revision"] += 1
                    changed.append(identifier)
                wf.validate_record(record)
                self.add_write(writes, record, groups)
            for identifier in changed:
                record = self.locate(identifier, questions, groups, investigations)
                wf.bind_pending_versions(record, questions, request_id)
            new_evidence = [path for path in writes if wf.EVIDENCE_PATH.fullmatch(path)]
            if new_evidence:
                self.mark_evidence_inputs(
                    manifest, new_evidence, questions, groups, investigations, writes, request_id, changed
                )
                manifest.setdefault("evidence_paths", []).extend(new_evidence)
            for qid in notify_dependency_changes(questions, previous_versions, writes, request_id):
                if qid not in changed:
                    changed.append(qid)
            return self.save(manifest, writes, request_id, fp, actor, {"ids": changed})

    def mark_evidence_inputs(
        self, manifest, new_paths, questions, groups, investigations, writes, request_id, changed
    ):
        records = {
            path: writes.get(path) or self.read_json(path)
            for path in [*manifest.get("evidence_paths", []), *new_paths]
        }
        identities = {Path(path).parent.name for path in new_paths}
        affected_claims = {
            path
            for path, record in records.items()
            if path.startswith("evidence/claims/")
            and (
                record["id"] in identities
                or any(
                    Path(p).parent.name in identities
                    for p in [*record.get("sources", []), *record.get("counter_sources", [])]
                )
            )
        }
        for record in [*questions.values(), *investigations.values()]:
            refs = [*record.get("evidence_refs", []), *(record.get("review_basis") or {}).get("claims", [])]
            if not affected_claims.intersection(refs):
                continue
            # A new basis saved in this same commit already accounts for its new records.
            basis = record.get("review_basis") or {}
            if record["id"] in changed and any(p in new_paths for p in basis.get("claims", [])):
                continue
            wf.event(
                record,
                request_id + ":evidence-change:" + record["id"],
                "system",
                "evidence_changed",
                {"paths": new_paths, "claims": sorted(affected_claims.intersection(refs))},
            )
            if record["id"] not in changed:
                record["revision"] += 1
                changed.append(record["id"])
            self.add_write(writes, record, groups)

    def apply_change(self, record, change, actor, request_id, questions, writes):
        allowed = (
            {"id", "comments"}
            if actor == "external_ai"
            else {
                "id",
                "comments",
                "definition",
                "pending",
                "phase",
                "progress",
                "review_basis",
                "review_packet",
                "external_brief",
                "evidence_impact",
                "problem_type",
                "evidence_refs",
                "verification_tests",
                "question_ids",
                "dependency_review",
            }
        )
        if set(change) - allowed:
            raise FreezeError("Unknown or unauthorized work change")
        for index, comment in enumerate(change.get("comments", [])):
            message_id = f"{request_id}:{record['id']}:{index}"
            text = require_text(comment.get("text") if isinstance(comment, dict) else comment, "comment")
            target = comment.get("question_id") if isinstance(comment, dict) else None
            if target is not None and target not in record.get("member_ids", []):
                raise FreezeError("Comment target must belong to this group")
            record.setdefault("messages", []).append(
                {
                    "id": message_id,
                    "actor": actor,
                    "at": now(),
                    "text": text,
                    "request_id": request_id,
                    **({"question_id": target} if target else {}),
                    **({"label": "外部 AI · 未经本地核查"} if actor == "external_ai" else {}),
                }
            )
            if actor in {"user", "external_ai"}:
                wf.event(record, "message:" + message_id, actor, "comment", message_id)
        if actor != "codex" and any(
            k in change for k in allowed - {"id", "comments", "definition", "dependency_review"}
        ):
            raise FreezeError("Work assessment is reserved for the local agent")
        if "pending" in change:
            wf.update_pending(record, change["pending"], request_id, questions)
            if wf.waiting_for_human_continue(record) and record["work"]["phase"] != "evidence":
                wf.automatic_phase(
                    record,
                    "evidence",
                    "Waiting for the human to continue after external research",
                    request_id,
                    actor,
                )
        if actor == "codex" and "review_packet" in change and wf.waiting_for_human_continue(record):
            raise FreezeError("Research handoff is waiting for an explicit human instruction to continue")
        if "definition" in change:
            if not record["id"].startswith("F-") or actor == "external_ai":
                raise FreezeError("Only local agents and humans may edit F wording")
            operation, value = change["definition"]["operation"], change["definition"].get("value")
            if operation in {"definition_approve", "definition_reconfirm"}:
                self.validate_review(record, writes)
            if operation == "definition_reconfirm":
                wf.reconfirm(record, value, actor)
            else:
                record["_asset_project"] = self.store.project
                wf.apply_definition(record, operation, value, actor, questions)
                record.pop("_asset_project", None)
            if actor == "user" and operation in {
                "definition_draft",
                "definition_begin",
                "definition_discard",
            }:
                wf.event(
                    record,
                    request_id + ":edit:" + record["id"],
                    actor,
                    operation,
                    {
                        "text_sha256": (state(record)["draft"] or {}).get("text_sha256"),
                        "request_id": request_id,
                    },
                )
        for key in ("problem_type", "evidence_refs", "verification_tests", "question_ids", "review_packet"):
            if key in change:
                record[key] = copy.deepcopy(change[key])
        if "external_brief" in change:
            brief = change["external_brief"]
            if not isinstance(brief, dict) or brief.get("disclosure") != "shared":
                raise FreezeError("An external brief must explicitly declare shared disclosure")
            allowed_brief = {
                "disclosure",
                "summary",
                "questions",
                "uncertainties",
                "applicability",
                "excluded_directions",
            }
            if set(brief) - allowed_brief:
                raise FreezeError("Unknown external brief fields")
            require_text(brief.get("summary"), "external brief summary")
            for key in set(brief) - {"disclosure", "summary"}:
                require_text(brief[key], "external brief " + key)
            record["external_brief"] = copy.deepcopy(brief)
        if record.get("problem_type", "unknown") not in {
            "unknown",
            "research_method",
            "project_fact",
            "engineering",
            "output_specification",
        }:
            raise FreezeError("Unknown problem type")
        if "question_ids" in change and (
            not record["id"].startswith("I-")
            or not isinstance(change["question_ids"], list)
            or any(qid not in questions for qid in change["question_ids"])
        ):
            raise FreezeError("Investigation links must reference existing F records")
        if "evidence_refs" in change:
            if not isinstance(change["evidence_refs"], list):
                raise FreezeError("Evidence references must be a list")
            for path in change["evidence_refs"]:
                if path not in writes:
                    self.read_json(path)
        if "review_basis" in change:
            self.validate_basis(change["review_basis"], record, writes)
            record["review_basis"] = copy.deepcopy(change["review_basis"])
            if record.get("definition", {}).get("draft"):
                record["definition"]["draft"]["review_basis"] = copy.deepcopy(change["review_basis"])
        if record.get("review_basis") and record.get("review_packet"):
            record["review_basis"]["packet_sha256"] = digest(
                json.dumps(record["review_packet"], sort_keys=True, ensure_ascii=False)
            )
            if record.get("definition", {}).get("draft"):
                record["definition"]["draft"]["review_basis"] = copy.deepcopy(record["review_basis"])
        if "evidence_impact" in change:
            impact = change["evidence_impact"]
            if impact.get("classification") not in {"non_material", "needs_check", "weakened", "reassessed"}:
                raise FreezeError("Unknown evidence impact")
            require_text(impact.get("reason"), "evidence impact reason", 5000)
            record.setdefault("evidence_assessments", []).append(
                {**copy.deepcopy(impact), "by": actor, "at": now()}
            )
            if impact["classification"] in {"needs_check", "weakened"}:
                record["review_required"] = copy.deepcopy(impact)
                wf.automatic_phase(
                    record, "evidence", impact["reason"], impact.get("refs", request_id), actor
                )
            elif impact["classification"] == "reassessed" and record.get("definition", {}).get("draft"):
                if "review_basis" not in change:
                    raise FreezeError("Reassessment requires the newly checked basis")
                record["review_required"] = None
        if "phase" in change:
            wf.transition(record, change["phase"], actor)
            if record["work"]["phase"] == "human_review":
                self.validate_review(record, writes)
        if "progress" in change:
            wf.save_progress(record, change["progress"], request_id)
        if "dependency_review" in change:
            if not record["id"].startswith("F-"):
                raise FreezeError("Only F records have version-bound dependencies")
            review_dependencies(record, change["dependency_review"], questions, actor, request_id)

    def validate_basis(self, basis, record, writes):
        if not isinstance(basis, dict) or not isinstance(basis.get("claims"), list):
            raise FreezeError("Review basis requires judgment versions")
        require_text(basis.get("summary"), "review basis summary", 10000)
        for path in basis["claims"]:
            if not isinstance(path, str) or not path.startswith("evidence/claims/"):
                raise FreezeError("Basis must reference judgment versions")
            claim = writes.get(path) or self.read_json(path)
            for source_path in claim["sources"]:
                source = writes.get(source_path) or self.read_json(source_path)
                if source.get("verification") == "model_claim_only":
                    raise FreezeError("Model-only source cannot support a recommendation")
                if source.get("source_type") in {"project_fact", "engineering_constraint"} and source.get(
                    "verification"
                ) not in {"full_text_location", "code_check", "data_check", "measurement"}:
                    raise FreezeError("Project facts and constraints require direct verification")
                if (
                    self.store.project_type == "research"
                    and record.get("problem_type") in {"research_method", "output_specification"}
                    and source.get("source_type") not in {"project_fact", "engineering_constraint"}
                    and source.get("verification") != "full_text_location"
                ):
                    raise FreezeError("Research recommendations require original-text verification")

    def validate_review(self, record, writes):
        if wf.waiting_for_human_continue(record):
            raise FreezeError("Research handoff is waiting for an explicit human instruction to continue")
        if not record.get("definition", {}).get("draft") and not record.get("review_required"):
            raise FreezeError("Human review requires a candidate or effective-version reassessment")
        if not record["work"]["trigger_refs"] or record["work"]["conclusion_type"] == "needs_check":
            raise FreezeError("Human review requires a trigger and concluded triage")
        if record["work"]["blockers"]:
            raise FreezeError("Resolve decisive evidence gaps before review")
        if self.store.project_type == "research" and record.get("problem_type") in {
            "research_method",
            "output_specification",
        }:
            self.validate_basis(record.get("review_basis"), record, writes)
            if not record["review_basis"]["claims"]:
                raise FreezeError("Research recommendations require evidence")
            packet = record.get("review_packet", {})
            for key in (
                "common_practice",
                "support",
                "applicability",
                "departure_check",
                "default",
                "project_reason",
            ):
                require_text(packet.get(key), "research review " + key, 10000)
            for objection in packet.get("objections", []):
                if objection.get("disposition") not in {"resolved", "explained_tradeoff"}:
                    raise FreezeError("Decisive objection needs resolution or an explained tradeoff")
                require_text(objection.get("reason"), "objection disposition reason", 5000)
        if record.get("problem_type") == "engineering":
            require_text(
                (record.get("review_packet") or {}).get("verification"),
                "verified engineering constraints",
                10000,
            )

    def change_question(self, question_id, operation, value, *, expected_revision, request_id, actor):
        if operation == "comment":
            change = {"id": question_id, "comments": [value]}
        elif operation in {
            "definition_begin",
            "definition_draft",
            "definition_approve",
            "definition_discard",
            "definition_reconfirm",
        }:
            change = {"id": question_id, "definition": {"operation": operation, "value": value}}
        elif operation == "work":
            change = {**value, "id": question_id}
        elif operation == "dependency_review":
            change = {"id": question_id, "dependency_review": value}
        else:
            raise FreezeError("Use the v5 work transaction for this operation")
        result = self.commit_work(
            {"read_set": {question_id: expected_revision}, "changes": [change]},
            request_id=request_id,
            actor=actor,
        )
        return {**self.store.read_question(question_id), "replayed": result["replayed"]}
