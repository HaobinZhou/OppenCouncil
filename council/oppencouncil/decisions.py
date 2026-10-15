"""Joint review groups, version-bound prerequisites and recoverable atomic confirmation."""

from __future__ import annotations

import copy
import json
import os
import re

from .definitions import change_definition, state, validate_definition
from .store import (
    AI_ACTORS,
    MAX_HTML,
    MAX_JSON,
    FreezeError,
    atomic_json,
    atomic_write,
    now,
    ordinary_file,
    request_fingerprint,
    require_text,
)

GROUP_ID = re.compile(r"B-[0-9]{6}\Z")
JOURNAL = ".decision-transaction.json"
MAX_TRANSACTION = 16 * MAX_JSON


def catalog(store):
    raw = ordinary_file(store.root / "decision-groups.json", MAX_JSON)
    if raw is None:
        return {"schema_version": 1, "groups": [], "requests": {}, "revision": 0}
    result = json.loads(raw)
    validate_catalog(result, v5=store.v5)
    return result


def validate_catalog(result, *, v5=False):
    if result.get("schema_version") != 1 or not isinstance(result.get("groups"), list):
        raise FreezeError("Invalid decision groups")
    ids, members = set(), set()
    for group in result["groups"]:
        if not GROUP_ID.fullmatch(group["id"]) or group["id"] in ids:
            raise FreezeError("Invalid decision group ID")
        if members.intersection(group["member_ids"]):
            raise FreezeError("A question can belong to only one decision group")
        ids.add(group["id"])
        members.update(group["member_ids"])
        if v5:
            from .workflow import validate_record

            validate_record(group)


def validate_writes(store, writes):
    """Validate all destinations and records before the journal becomes committed."""
    if not isinstance(writes, dict) or not writes:
        raise FreezeError("Invalid decision transaction writes")
    for name, value in writes.items():
        if name == "manifest.json":
            if not isinstance(value, dict) or value.get("schema_version") not in (
                {3} if store.v5 else {1, 2}
            ):
                raise FreezeError("Invalid transaction manifest")
            ids = value.get("question_ids")
            if not isinstance(ids, list) or any(
                not isinstance(i, str) or not re.fullmatch(r"F-[0-9]{6}", i) for i in ids
            ):
                raise FreezeError("Invalid transaction question index")
            if len(ids) != len(set(ids)):
                raise FreezeError("Duplicate transaction question index")
        elif name == "decision-groups.json":
            validate_catalog(value, v5=store.v5)
        elif re.fullmatch(r"questions/F-[0-9]{6}\.json", name):
            if not isinstance(value, dict) or value.get("id") != name.split("/")[-1][:-5]:
                raise FreezeError("Question identity does not match transaction path")
            validate_definition(value)
            if store.v5:
                from .workflow import validate_record

                validate_record(value)
        elif store.v5:
            from .workstore import validate_transaction_record

            validate_transaction_record(name, value)
        else:
            raise FreezeError("Unsafe decision transaction path")
        if len((json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()) > MAX_JSON:
            raise FreezeError("Decision record exceeds 1 MiB")
        parent = store.root
        for part in name.split("/")[:-1]:
            parent /= part
            if not store._directory(parent, False):
                raise FreezeError("Transaction destination directory is missing")
        raw = ordinary_file(store.root / name, MAX_JSON)
        if name.startswith("evidence/") and raw is not None and json.loads(raw) != value:
            raise FreezeError("Evidence versions are immutable")


def recover_transaction(store):
    """Called only under the project Freeze lock, before any supported read/write."""
    raw = ordinary_file(store.root / JOURNAL, MAX_TRANSACTION)
    if raw is None:
        return
    payload = json.loads(raw)
    writes = payload.get("writes")
    if payload.get("schema_version") != 1 or not isinstance(writes, dict):
        raise FreezeError("Invalid decision transaction; recovery required")
    # Re-check parents on recovery: a child directory may have been replaced since commit.
    validate_writes(store, writes)
    for name, value in writes.items():
        atomic_json(store.root / name, value)
    (store.root / JOURNAL).unlink()
    if os.name != "nt":
        descriptor = os.open(store.root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def commit(store, writes):
    # This fsynced journal is the commit point. A crash rolls forward, never publishes half a group.
    validate_writes(store, writes)
    raw = json.dumps({"schema_version": 1, "writes": writes}, ensure_ascii=False).encode()
    if len(raw) > MAX_TRANSACTION:
        raise FreezeError("Decision transaction exceeds 16 MiB")
    atomic_write(store.root / JOURNAL, raw)
    recover_transaction(store)


def all_questions(store):
    return {qid: store._question(qid) for qid in store._manifest()["question_ids"]}


def current(q):
    d = state(q)
    return d["versions"][-1] if d["current_version"] else None


def bind_dependencies(value, questions, own_id):
    if not isinstance(value, list) or len(value) > 100:
        raise FreezeError("dependencies must be a list of at most 100 records")
    result, seen = [], set()
    for item in value:
        if not isinstance(item, dict):
            raise FreezeError("Each dependency must be an object")
        qid, kind = item.get("question_id"), item.get("kind", "required")
        if qid not in questions or qid == own_id or qid in seen:
            raise FreezeError("Dependency must reference a different, existing question once")
        if kind not in {"required", "conditional", "reference"}:
            raise FreezeError("Unknown dependency kind")
        active = item.get("active", True)
        if type(active) is not bool:
            raise FreezeError("Dependency active must be boolean")
        if kind == "required" and not active:
            raise FreezeError("Required dependencies cannot be disabled")
        reason = require_text(item.get("reason"), "dependency reason", 1500)
        condition = (
            require_text(item.get("condition"), "dependency condition", 1500) if kind == "conditional" else ""
        )
        version = current(questions[qid])
        number = item.get("version", version["number"] if version else None)
        if number is not None:
            version = next((v for v in state(questions[qid])["versions"] if v["number"] == number), None)
            if not version or type(number) is not int:
                raise FreezeError("Dependency version does not exist")
        else:
            version = None
        hash_value = version["text_sha256"] if version else None
        if "text_sha256" in item and item["text_sha256"] != hash_value:
            raise FreezeError("Dependency hash does not match the cited version")
        result.append(
            dict(
                question_id=qid,
                kind=kind,
                active=active,
                reason=reason,
                condition=condition,
                version=number,
                text_sha256=hash_value,
            )
        )
        seen.add(qid)
    return result


def blocking(dep):
    return dep["kind"] != "reference" and dep.get("active", True)


def requirements(q, draft=True):
    d = state(q)
    record = d["draft"] if draft and d["draft"] is not None else current(q)
    return (record or {}).get("dependencies", [])


def candidate_for_approval(qid, questions):
    """Prepare current prerequisite bindings for explicit human review, without writes.

    Views disclose changed bindings beside the candidate. Only confirmation stores
    them; the token prevents an upstream change from silently changing that choice.
    """
    candidate = copy.deepcopy(state(questions[qid])["draft"])
    if candidate:
        for dep in candidate.get("dependencies", []):
            live = current(questions[dep["question_id"]])
            if blocking(dep) and live:
                dep.update(version=live["number"], text_sha256=live["text_sha256"])
    return candidate


def candidate_dependency_updates(qid, questions):
    original = state(questions[qid])["draft"]
    candidate = candidate_for_approval(qid, questions)
    updates = []
    if candidate:
        for old, new in zip(original.get("dependencies", []), candidate.get("dependencies", []), strict=True):
            if old["version"] == new["version"] and old["text_sha256"] == new["text_sha256"]:
                continue
            upstream = questions[new["question_id"]]
            prior = next((v for v in state(upstream)["versions"] if v["number"] == old["version"]), None)
            updates.append(
                {
                    "question_id": new["question_id"],
                    "title": upstream["title"],
                    "from_version": old["version"],
                    "to_version": new["version"],
                    "from_text": prior["text"] if prior else "此前尚未确认前序版本。",
                    "to_text": current(upstream)["text"],
                }
            )
    return updates


def dependency_status(qid, questions, trail=(), use_draft=True):
    q = questions[qid]
    if qid in trail:
        return []  # Jointly approved cycles were checked at the group transaction boundary.
    result = []
    reviews = q.get("dependency_reviews", [])
    owner = current(q)
    candidate = candidate_for_approval(qid, questions) if use_draft else None
    deps = candidate.get("dependencies", []) if candidate else requirements(q, draft=False)
    for dep in deps:
        upstream = questions.get(dep["question_id"])
        live = current(upstream) if upstream else None
        status = "reference" if not blocking(dep) else "ready"
        if blocking(dep):
            if not live:
                status = "waiting"
            elif live["number"] != dep["version"] or live["text_sha256"] != dep["text_sha256"]:
                accepted = (not use_draft or not state(q)["draft"]) and any(
                    review["owner_version"] == (owner or {}).get("number")
                    and review["bindings"].get(dep["question_id"]) == [live["number"], live["text_sha256"]]
                    for review in reviews
                )
                status = "ready" if accepted else "needs_review"
            if status == "ready" and any(
                x["status"] in {"waiting", "needs_review"}
                for x in dependency_status(dep["question_id"], questions, (*trail, qid), use_draft=False)
            ):
                status = "needs_review"
        result.append(
            {
                **dep,
                "title": upstream["title"] if upstream else dep["question_id"],
                "current_version": live["number"] if live else None,
                "status": status,
            }
        )
    return result


def readiness(qid, questions, use_draft=True):
    deps = dependency_status(qid, questions, use_draft=use_draft)
    status = (
        "waiting"
        if any(d["status"] == "waiting" for d in deps)
        else "needs_review"
        if any(d["status"] == "needs_review" for d in deps)
        else "ready"
        if state(questions[qid])["draft"]
        else "effective"
        if current(questions[qid])
        else "discuss"
    )
    return {"status": status, "dependencies": deps}


def review_dependencies(question, value, questions, actor, request_id):
    owner = current(question)
    if not owner or state(question)["draft"]:
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


def notify_dependency_changes(questions, previous_versions, writes, request_id):
    """Wake actual dependents without changing their working phase or formal version."""
    from .workflow import event

    changed = {
        qid for qid, q in questions.items() if state(q)["current_version"] != previous_versions.get(qid)
    }
    affected = []
    for qid, q in questions.items():
        targets = sorted({d["question_id"] for d in requirements(q) if d["question_id"] in changed})
        path = f"questions/{qid}.json"
        if targets and qid not in changed:
            event(
                q,
                request_id + ":dependencies:" + qid,
                "system",
                "dependencies_changed",
                {
                    up: [current(questions[up])["number"], current(questions[up])["text_sha256"]]
                    for up in targets
                },
            )
            if path not in writes:
                q["revision"] += 1
            writes[path] = q
            affected.append(qid)
    return affected


def check_approval(qid, questions, prospective=None):
    prospective = prospective or {}
    for dep in requirements(questions[qid]):
        if not blocking(dep):
            continue
        q = questions[dep["question_id"]]
        live = prospective.get(dep["question_id"]) or current(q)
        if not live:
            raise FreezeError("等待前序口径：" + q["title"])
        if live["number"] != dep["version"] or live["text_sha256"] != dep["text_sha256"]:
            raise FreezeError("前序口径已变化，请更新候选依据并重新审阅：" + q["title"])
        if dep["question_id"] not in prospective and readiness(
            dep["question_id"], questions, use_draft=False
        )["status"] in {
            "waiting",
            "needs_review",
        }:
            raise FreezeError("前序口径仍需复核：" + q["title"])


def group_view(group, questions):
    result = copy.deepcopy(group)
    if result.get("example"):
        result["example"].pop("html", None)
    relevant = set(group["member_ids"])
    todo = list(relevant)
    while todo:
        qid = todo.pop()
        for dep in requirements(questions[qid]):
            if dep["question_id"] not in relevant:
                relevant.add(dep["question_id"])
                todo.append(dep["question_id"])
    # Bind only this group's actual dependency closure; unrelated edits do not invalidate review.
    result["approval_token"] = request_fingerprint(
        "group-approval",
        {"group": group, "questions": {qid: questions[qid]["revision"] for qid in sorted(relevant)}},
    )
    result["readiness"] = {qid: readiness(qid, questions) for qid in group["member_ids"]}
    if "work" in group:
        from .workflow import projection

        result.update(projection(group, questions))
    return result


def snapshot_groups(store, questions):
    return [group_view(g, questions) for g in catalog(store)["groups"]]


def group_membership(store, qid):
    return next((g for g in catalog(store)["groups"] if qid in g["member_ids"]), None)


def clean_group(value, questions):
    if not isinstance(value, dict):
        raise FreezeError("Decision group must be an object")
    members = value.get("member_ids")
    if (
        not isinstance(members, list)
        or not 1 <= len(members) <= 50
        or any(not isinstance(q, str) or q not in questions for q in members)
        or len(set(members)) != len(members)
    ):
        raise FreezeError("Select 1–50 different existing questions")
    options = value.get("options", [])
    if not isinstance(options, list) or len(options) > 8:
        raise FreezeError("Provide at most eight complete options")
    clean = []
    for option in options:
        if not isinstance(option, dict):
            raise FreezeError("Each option must be an object")
        rules = option.get("rules", {})
        if not isinstance(rules, dict) or set(rules) != set(members):
            raise FreezeError("Each option must explain every member question")
        clean.append(
            {
                "label": require_text(option.get("label"), "option label", 200),
                "rules": {qid: require_text(text, "option rule", 5000) for qid, text in rules.items()},
                "consequences": require_text(option.get("consequences"), "option consequences", 5000),
                "tradeoffs": require_text(option.get("tradeoffs"), "option tradeoffs", 5000),
            }
        )
    return {
        "title": require_text(value.get("title"), "group title", 300),
        "purpose": require_text(value.get("purpose"), "group purpose", 5000),
        "member_ids": members,
        "options": clean,
    }


def change_group(store, group_id, operation, value, *, expected_revision, request_id, actor):
    if store.v5:
        if actor not in {"codex", "user", "external_ai"}:
            raise FreezeError("Unknown v5 actor")
        if actor == "external_ai" and operation != "comment":
            raise FreezeError("External AI may only comment on a decision group")
        if operation in {"create", "update"} and actor != "codex":
            raise FreezeError("Only the local agent may organize decision groups")
        if operation == "example":
            raise FreezeError("Use immutable images in definition wording instead of HTML examples")
    elif actor not in AI_ACTORS | {"user"}:
        raise FreezeError("Unknown actor")
    if operation in {"approve", "begin", "discard", "select_option"} and actor != "user":
        raise FreezeError("Only the user may choose, open revisions or confirm a decision group")
    require_text(request_id, "request_id", 100)
    fingerprint = request_fingerprint(operation, [group_id, value])
    with store.locked(create=True):
        data, questions = catalog(store), all_questions(store)
        previous_versions = {qid: state(q)["current_version"] for qid, q in questions.items()}
        receipt = data["requests"].get(request_id)
        if receipt:
            if receipt["fingerprint"] != fingerprint or receipt["actor"] != actor:
                raise FreezeError("request_id was used with different content")
            g = next(g for g in data["groups"] if g["id"] == receipt["group_id"])
            return {**group_view(g, questions), "replayed": True}
        group = next((g for g in data["groups"] if g["id"] == group_id), None)
        writes = {}
        if operation == "create":
            if group_id is not None or expected_revision != 0:
                raise FreezeError("New group requires null ID and revision zero")
            group = {
                "id": f"B-{max((int(g['id'][2:]) for g in data['groups']), default=0) + 1:06d}",
                "revision": 0,
                "messages": [],
                "history": [],
                "confirmations": [],
                "example": None,
                "created_by": actor,
                "created_at": now(),
                **clean_group(value, questions),
            }
            if store.v5:
                from .workflow import initial_work, initialize_progress

                group["work"] = initial_work()
                initialize_progress(group, question=False)
            data["groups"].append(group)
        elif not group:
            raise FreezeError("Decision group not found")
        elif expected_revision != group["revision"]:
            raise FreezeError("Decision group changed since read; reload before editing")
        elif operation == "update":
            cleaned = clean_group(value, questions)
            group["history"].append({"by": actor, "at": now(), **{k: group[k] for k in cleaned}})
            group.update(cleaned)
            group.pop("selected_option", None)
        elif operation == "comment":
            if isinstance(value, str):
                value = {"text": value}
            if not isinstance(value, dict) or value.get("question_id") not in [None, *group["member_ids"]]:
                raise FreezeError("Comment target must be a group member")
            group["messages"].append(
                {
                    "id": request_id,
                    "actor": actor,
                    "at": now(),
                    "question_id": value.get("question_id"),
                    "text": require_text(value.get("text"), "group comment"),
                    **({"label": "外部 AI · 未经本地核查"} if actor == "external_ai" else {}),
                }
            )
        elif operation == "select_option":
            if type(value) is not int or not 0 <= value < len(group["options"]):
                raise FreezeError("Unknown option")
            group["selected_option"] = value
            group["messages"].append(
                {
                    "id": request_id,
                    "actor": actor,
                    "at": now(),
                    "text": "倾向方案：" + group["options"][value]["label"] + "（尚未确认口径）",
                }
            )
        elif operation == "example" and actor in AI_ACTORS:
            if not isinstance(value, dict):
                raise FreezeError("Example must be an object")
            group["example"] = {
                "title": require_text(value.get("title"), "example title", 300),
                "summary": require_text(value.get("summary"), "example summary", 2000),
                "html": require_text(value.get("html"), "example HTML", MAX_HTML),
                "updated_at": now(),
                "updated_by": actor,
            }
        elif operation == "begin":
            for qid in group["member_ids"]:
                q = questions[qid]
                if state(q)["draft"] is None:
                    if store.v5:
                        from .workflow import apply_definition

                        apply_definition(q, "definition_begin", None, actor, questions)
                    else:
                        change_definition(q, "definition_begin", None, actor)
                    q["revision"] += 1
                    writes[f"questions/{qid}.json"] = q
        elif operation == "discard":
            if (
                not isinstance(value, dict)
                or value.get("token") != group_view(group, questions)["approval_token"]
            ):
                raise FreezeError("Decision group changed since read; reload before cancelling")
            edits = value.get("edits", {})
            if not isinstance(edits, dict) or any(qid not in group["member_ids"] for qid in edits):
                raise FreezeError("Local edits must belong to this group")
            if any(state(questions[qid])["draft"] is None for qid in edits):
                raise FreezeError("Candidate changed since read; reload before cancelling")
            for qid in group["member_ids"]:
                q = questions[qid]
                if state(q)["draft"] is not None:
                    if store.v5:
                        from .workflow import apply_definition

                        apply_definition(q, "definition_discard", edits.get(qid), actor, questions)
                    else:
                        change_definition(q, "definition_discard", edits.get(qid), actor)
                    q["revision"] += 1
                    writes[f"questions/{qid}.json"] = q
            if not writes:
                raise FreezeError("No candidate revision to cancel")
        elif operation == "approve":
            if value != group_view(group, questions)["approval_token"]:
                raise FreezeError(
                    "Decision group changed since read; review all wording and dependencies again"
                )
            proposed, reconfirmed = {}, []
            for qid in group["member_ids"]:
                q, d = questions[qid], state(questions[qid])
                if store.v5 and (d["draft"] or q.get("review_required")):
                    from .workstore import WorkStore

                    if q["work"]["phase"] != "human_review" or (d["draft"] and q.get("review_required")):
                        raise FreezeError("Each member requires a prepared evidence and review packet")
                    WorkStore(store).validate_review(q, writes)
                if d["draft"]:
                    d["draft"] = candidate_for_approval(qid, questions)
                    if not d["draft"]["text"].strip():
                        raise FreezeError("请先补齐组内候选：" + q["title"])
                    old = current(q)
                    if (
                        old is None
                        or old["text"] != d["draft"]["text"]
                        or old.get("dependencies", []) != d["draft"].get("dependencies", [])
                    ):
                        proposed[qid] = {
                            "number": len(d["versions"]) + 1,
                            "text_sha256": d["draft"]["text_sha256"],
                        }
                elif not current(q):
                    raise FreezeError("请先补齐组内候选：" + q["title"])
                elif store.v5 and q.get("review_required"):
                    reconfirmed.append(qid)
            # An unchanged clause also needs a new version if its bound group prerequisite changes.
            for _ in group["member_ids"]:
                for qid in group["member_ids"]:
                    draft = state(questions[qid])["draft"]
                    if (
                        qid not in proposed
                        and draft
                        and any(
                            blocking(dep) and dep["question_id"] in proposed
                            for dep in draft.get("dependencies", [])
                        )
                    ):
                        proposed[qid] = {
                            "number": len(state(questions[qid])["versions"]) + 1,
                            "text_sha256": draft["text_sha256"],
                        }
            if not proposed and not reconfirmed:
                raise FreezeError("本组没有发生变更的候选")
            for qid in group["member_ids"]:
                if qid not in proposed:
                    if readiness(qid, questions)["status"] in {"waiting", "needs_review"}:
                        raise FreezeError("组内已确认条目需要复核：" + questions[qid]["title"])
                    if any(
                        blocking(dep) and dep["question_id"] in proposed
                        for dep in requirements(questions[qid])
                    ):
                        raise FreezeError(
                            "本次会改变组内条目的依据，请先开启相关修订：" + questions[qid]["title"]
                        )
                    continue
                draft = state(questions[qid])["draft"]
                # Internal prerequisites bind to the same confirmed transaction's prospective versions.
                for dep in draft.get("dependencies", []):
                    if blocking(dep) and dep["question_id"] in proposed:
                        dep.update(
                            version=proposed[dep["question_id"]]["number"],
                            text_sha256=proposed[dep["question_id"]]["text_sha256"],
                        )
            for qid in proposed:
                check_approval(qid, questions, proposed)
            for qid in reconfirmed:
                check_approval(qid, questions, proposed)
            from .definitions import approval_token

            for qid in proposed:
                q = questions[qid]
                change_definition(q, "definition_approve", approval_token(state(q)["draft"]), actor)
                if store.v5:
                    q.pop("status", None)
                    from .workflow import automatic_phase

                    automatic_phase(q, "closed", "group_confirmed", request_id, actor)
                current(q)["decision_group"] = group["id"]
                q["revision"] += 1
                writes[f"questions/{qid}.json"] = q
            for qid in reconfirmed:
                from .workflow import reconfirm, review_token

                q = questions[qid]
                reconfirm(q, review_token(q), actor)
                q["revision"] += 1
                writes[f"questions/{qid}.json"] = q
            for qid in group["member_ids"]:
                if qid not in proposed and state(questions[qid])["draft"] is not None:
                    change_definition(questions[qid], "definition_discard", None, actor)
                    if store.v5:
                        questions[qid].pop("status", None)
                        from .workflow import automatic_phase

                        automatic_phase(questions[qid], "closed", "unchanged", request_id, actor)
                    questions[qid]["revision"] += 1
                    writes[f"questions/{qid}.json"] = questions[qid]
            group["confirmations"].append(
                {
                    "by": actor,
                    "at": now(),
                    "request_id": request_id,
                    **({"reconfirmed_ids": reconfirmed} if store.v5 else {}),
                    "versions": {
                        qid: [current(questions[qid])["number"], current(questions[qid])["text_sha256"]]
                        for qid in group["member_ids"]
                    },
                }
            )
        else:
            raise FreezeError("Operation is unavailable to this actor")
        if len(group["messages"]) > 2000:
            raise FreezeError("Group discussion is too large")
        if store.v5:
            from .workflow import event, validate_record

            if actor in {"user", "external_ai"} and operation in {
                "comment",
                "select_option",
                "begin",
                "discard",
            }:
                # Group feedback has exactly one owner; do not copy it into every F.
                reference = (
                    request_id if operation in {"comment", "select_option"} else {"operation": operation}
                )
                event(group, request_id, actor, operation, reference)
            if operation == "approve":
                from .workflow import automatic_phase

                automatic_phase(group, "closed", "confirmed", request_id, actor)
            validate_record(group)
        members = group["member_ids"]
        if any(set(members).intersection(g["member_ids"]) for g in data["groups"] if g is not group):
            raise FreezeError("A question already belongs to another decision group")
        group["revision"] += 1
        group.update(updated_at=now(), updated_by=actor)
        data["revision"] += 1
        data["requests"][request_id] = {"group_id": group["id"], "actor": actor, "fingerprint": fingerprint}
        manifest = store._manifest()
        manifest.update(schema_version=3 if store.v5 else 2, revision=manifest["revision"] + 1)
        writes.update({"decision-groups.json": data, "manifest.json": manifest})
        if store.v5:
            notify_dependency_changes(questions, previous_versions, writes, request_id)
        commit(store, writes)
        return group_view(group, questions)
