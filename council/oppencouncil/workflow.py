"""Version-five work records: bounded feedback, explicit stages and append-only evidence.

These are storage contracts, not a substitute for the agent's semantic assessment.
All mutations are planned in memory and saved through the existing project journal.
"""

from __future__ import annotations

import copy
import json
import re

from .definitions import approval_token, change_definition, digest, state
from .store import FreezeError, now, require_text

PHASES = {"triage", "evidence", "prepare_review", "human_review", "closed"}
CONCLUSIONS = {
    "not_applicable",
    "fact_lookup",
    "covered",
    "single_recommendation",
    "parallel_recommendations",
    "departure",
    "tradeoff",
    "needs_check",
}
ITEM_ID = re.compile(r"[FIB]-[0-9]{6}\Z")
EVIDENCE_PATH = re.compile(r"evidence/(sources/S|claims/E)-[0-9]{6}/r[0-9]{6}\.json\Z")
SUBMISSION_PATH = re.compile(r"evidence/submissions/X-[A-Za-z0-9_-]{8,80}\.json\Z")
SOURCE_TYPES = {
    "method_guideline",
    "reporting_guideline",
    "comparable_study",
    "method_paper",
    "project_experience",
    "project_fact",
    "engineering_constraint",
}
VERIFICATION = {
    "full_text_location",
    "abstract_only",
    "model_claim_only",
    "code_check",
    "data_check",
    "measurement",
}


def initial_work(phase="triage"):
    return {
        "revision_id": 1,
        "phase": phase,
        "conclusion_type": "needs_check",
        "trigger_refs": [],
        "affected_refs": [],
        "completion_conditions": [],
        "blockers": [],
        "closed_reason": None,
        "transitions": [],
    }


def event(record, event_id, actor, kind, reference, *, at=None):
    events = record.setdefault("feedback_events", [])
    if any(e["id"] == event_id for e in events):
        raise FreezeError("Duplicate feedback event")
    entry = {
        "id": event_id,
        "sequence": len(events) + 1,
        "actor": actor,
        "kind": kind,
        "reference": reference,
        "at": at or now(),
    }
    events.append(entry)
    return entry


def initialize_progress(record, *, legacy_status=None, question=True):
    """OPP-20 mechanical migration; never infer that an AI reply resolved an opinion."""
    record["feedback_events"] = []
    for message in record.get("messages", []):
        actor = (
            "user"
            if message.get("actor") == "user"
            else ("external_ai" if message.get("actor") in {"chatgpt", "web_ai", "external_ai"} else "codex")
        )
        if actor in {"user", "external_ai"}:
            event(
                record,
                "message:" + message["id"],
                actor,
                "comment",
                message["id"],
                at=message.get("at") or "unknown",
            )
    humans = [e for e in record["feedback_events"] if e["actor"] == "user"]
    messages = record.get("messages", [])
    last_is_human = bool(messages and messages[-1].get("actor") == "user")
    cursor = (
        humans[-2]["id"]
        if last_is_human and len(humans) > 1
        else (None if last_is_human else humans[-1]["id"] if humans else None)
    )
    d = record.get("definition", {})
    only_formal = bool(d.get("current_version") and not d.get("draft"))
    reconcile = (
        question and not only_formal and (bool(d.get("draft")) or legacy_status in {"discussing", "open"})
    )
    record["processing"] = {
        "human_cursor": cursor,
        "handled_external": [],
        "handled_changes": [],
        "bootstrap": "needs_reconciliation" if reconcile else "complete",
        "receipts": [],
    }
    record["pending_items"] = []


def upgrade_question(old):
    """Pure transformation; migration owns application and rollback."""
    if old.get("schema_version") == 2:
        validate_record(old)
        return copy.deepcopy(old)
    q = copy.deepcopy(old)
    status = q.pop("status", "open")
    q["schema_version"] = 2
    legacy = {"status": status}
    answer = q.pop("user_answer", None)
    if answer:
        q.setdefault("messages", []).append(
            {
                "id": "migration:answer:" + q["id"],
                "actor": "user",
                "text": answer,
                "kind": "historical_answer",
                "at": None,
                "provenance": {"field": "user_answer", "time_unknown": True},
            }
        )
    for key in ("ai_position", "ai_position_by", "ai_position_at"):
        if key in q:
            legacy[key] = q.pop(key)
    position = legacy.get("ai_position")
    if position and not any(
        m.get("kind") == "proposal"
        and m.get("text") == position
        and m.get("actor") == legacy.get("ai_position_by")
        and legacy.get("ai_position_at") is not None
        and m.get("at") == legacy["ai_position_at"]
        for m in q.get("messages", [])
    ):
        q.setdefault("messages", []).append(
            {
                "id": "migration:position:" + q["id"],
                "actor": legacy.get("ai_position_by", "codex"),
                "text": position,
                "kind": "historical_proposal",
                "at": legacy.get("ai_position_at"),
                "provenance": {"field": "ai_position"},
            }
        )
    q["legacy"] = legacy
    q["historical"] = status == "historical"
    d = state(q)
    phase = "prepare_review" if d["draft"] else "closed" if d["current_version"] else "triage"
    if q["historical"] and not d["draft"]:
        phase = "closed"
    q["work"] = initial_work(phase)
    if phase == "closed":
        q["work"]["closed_reason"] = "legacy_effective" if d["current_version"] else "historical"
    q["evidence_refs"] = []
    q["verification_tests"] = []
    q["review_basis"] = None
    q["review_required"] = None
    q["problem_type"] = "unknown"
    # Imported fields are historical discussion, not newly arrived human feedback.
    # Initialize from the original discussion only, including its mechanical cursor.
    original = {"messages": copy.deepcopy(old.get("messages", [])), "definition": d}
    initialize_progress(original, legacy_status=status)
    for key in ("feedback_events", "processing", "pending_items"):
        q[key] = original[key]
    validate_record(q)
    return q


def validate_record(record):
    try:
        if not isinstance(record["id"], str) or not ITEM_ID.fullmatch(record["id"]):
            raise ValueError("item identity")
        if type(record["revision"]) is not int or record["revision"] < 0:
            raise ValueError("item revision")
        if not isinstance(record["title"], str) or not record["title"].strip():
            raise ValueError("item title")
        if record["work"]["phase"] not in PHASES or record["work"]["conclusion_type"] not in CONCLUSIONS:
            raise ValueError("work state")
        for key in ("trigger_refs", "affected_refs", "completion_conditions", "blockers", "transitions"):
            if not isinstance(record["work"][key], list):
                raise ValueError("work " + key)
        if type(record["work"]["revision_id"]) is not int or record["work"]["revision_id"] < 1:
            raise ValueError("work revision")
        messages = record.get("messages", [])
        message_ids = [m["id"] for m in messages]
        if len(set(message_ids)) != len(message_ids):
            raise ValueError("duplicate message identity")
        events = record["feedback_events"]
        ids = [e["id"] for e in events]
        if any(
            not isinstance(e["id"], str) or e["actor"] not in {"user", "codex", "external_ai", "system"}
            for e in events
        ):
            raise ValueError("event identity or actor")
        if len(set(ids)) != len(ids) or [e["sequence"] for e in events] != list(range(1, len(events) + 1)):
            raise ValueError("event ordering")
        cursor = record["processing"]["human_cursor"]
        if cursor is not None and not any(e["id"] == cursor and e["actor"] == "user" for e in events):
            raise ValueError("human cursor")
        pending = record["pending_items"]
        if len({p["id"] for p in pending}) != len(pending):
            raise ValueError("pending IDs")
        if record["processing"]["bootstrap"] not in {"complete", "needs_reconciliation"}:
            raise ValueError("bootstrap")
        for key, actor in (("handled_external", "external_ai"), ("handled_changes", "system")):
            handled = record["processing"].get(key, [])
            if not isinstance(handled, list) or not set(handled) <= {
                e["id"] for e in events if e["actor"] == actor
            }:
                raise ValueError(key)
    except (KeyError, TypeError, ValueError) as error:
        raise FreezeError(f"Invalid work record: {error}") from error


def unread(record):
    cursor = record["processing"]["human_cursor"]
    events = record["feedback_events"]
    sequence = next((e["sequence"] for e in events if e["id"] == cursor), 0)
    handled = set(record["processing"]["handled_external"])
    changes = set(record["processing"].get("handled_changes", []))
    return [
        e
        for e in events
        if (e["actor"] == "user" and e["sequence"] > sequence)
        or (e["actor"] == "external_ai" and e["id"] not in handled)
        or (e["actor"] == "system" and e["id"] not in changes)
    ]


def pending_ready(item, questions, record=None):
    if item.get("resolved"):
        return False
    condition = item["continue_when"]
    if condition["kind"] == "definition_confirmed":
        q = questions.get(condition.get("question_id"), {})
        version = q.get("definition", {}).get("current_version")
        return bool(version and version >= condition.get("min_version", 1))
    if condition["kind"] == "new_material":
        return any(
            e["sequence"] > condition["after_sequence"] and e["kind"] == "evidence"
            for e in (record or {}).get("feedback_events", [])
        )
    # Semantic conditions require an explicit local assessment, not an external claim.
    return condition["kind"] in {"local_assessment", "human_continue"} and bool(condition.get("satisfied"))


def waiting_for_human_continue(record):
    return any(
        not item.get("resolved") and item["continue_when"]["kind"] == "human_continue"
        for item in record["pending_items"]
    )


def projection(record, questions):
    w = record["work"]
    inputs = unread(record)
    waiting = [p for p in record["pending_items"] if pending_ready(p, questions, record)]
    bootstrap = record["processing"]["bootstrap"] == "needs_reconciliation"
    reason = w["conclusion_type"]
    category = (
        "excluded"
        if reason == "not_applicable"
        else "checking"
        if (reason == "needs_check" or w["phase"] in {"triage", "evidence"} or w["blockers"])
        else "quick_confirm"
        if reason == "single_recommendation"
        else "decision"
    )
    member_states = [questions[qid] for qid in record.get("member_ids", [])]
    human_pending = any(e["actor"] == "user" for e in inputs)
    return {
        "review_category": category,
        "human_pending": human_pending,
        "actionable": bool(inputs or waiting or bootstrap),
        "awaiting_human": (w["phase"] == "human_review" and category in {"decision", "quick_confirm"})
        or any(q["work"]["phase"] == "human_review" for q in member_states),
        "ready_pending_ids": [p["id"] for p in waiting],
        "bootstrap_required": bootstrap,
        "historical": bool(record.get("historical")),
    }


def transition(record, value, actor):
    if actor != "codex" or not isinstance(value, dict) or value.get("phase") not in PHASES:
        raise FreezeError("A local agent must specify a valid work phase")
    if value["phase"] in {"prepare_review", "human_review", "closed"} and waiting_for_human_continue(record):
        raise FreezeError("Research handoff is waiting for an explicit human instruction to continue")
    previous = record["work"]
    reason = require_text(value.get("reason"), "stage change reason", 5000)
    completion = value.get("completion_conditions")
    affected = value.get("affected_refs")
    if not isinstance(completion, list) or not completion or not isinstance(affected, list) or not affected:
        raise FreezeError("Stage changes require scope and completion conditions")
    conclusion = value.get("conclusion_type", previous["conclusion_type"])
    if conclusion not in CONCLUSIONS:
        raise FreezeError("Unknown conclusion type")
    if value["phase"] == "closed" and conclusion == "needs_check":
        raise FreezeError("Unresolved investigation must retain its checking phase")
    record["work"] = {
        **previous,
        "phase": value["phase"],
        "conclusion_type": conclusion,
        "trigger_refs": copy.deepcopy(value.get("trigger_refs", previous["trigger_refs"])),
        "affected_refs": copy.deepcopy(affected),
        "completion_conditions": copy.deepcopy(completion),
        "blockers": copy.deepcopy(value.get("blockers", [])),
        "closed_reason": reason if value["phase"] == "closed" else None,
    }
    record["work"]["transitions"].append(
        {
            "from": previous["phase"],
            "to": value["phase"],
            "reason": reason,
            "trigger_refs": copy.deepcopy(value.get("trigger_refs", [])),
            "affected_refs": copy.deepcopy(affected),
            "completion_conditions": copy.deepcopy(completion),
            "by": actor,
            "at": now(),
        }
    )
    if previous["phase"] == "closed" and value["phase"] != "closed":
        record["work"]["revision_id"] += 1


def automatic_phase(record, phase, reason, trigger, actor):
    """Record mechanical changes caused by a saved edit or human confirmation."""
    if waiting_for_human_continue(record):
        phase = "evidence"
    work = record["work"]
    previous = work["phase"]
    if previous == phase:
        return
    conditions = ["Review the saved candidate"] if phase == "prepare_review" else [reason]
    work["transitions"].append(
        {
            "from": previous,
            "to": phase,
            "reason": reason,
            "trigger_refs": [trigger],
            "affected_refs": [record["id"]],
            "completion_conditions": conditions,
            "by": actor,
            "at": now(),
        }
    )
    work.update(
        phase=phase, completion_conditions=conditions, closed_reason=reason if phase == "closed" else None
    )
    if previous == "closed" and phase != "closed":
        work["revision_id"] += 1


def save_progress(record, payload, request_id):
    """Advance only through feedback explicitly accounted for by this transaction."""
    if not isinstance(payload, dict):
        raise FreezeError("Processing requires a progress object")
    target = payload.get("human_cursor", record["processing"]["human_cursor"])
    events = record["feedback_events"]
    old = record["processing"]["human_cursor"]
    old_seq = next((e["sequence"] for e in events if e["id"] == old), 0)
    target_event = next((e for e in events if e["id"] == target and e["actor"] == "user"), None)
    if target is not None and target_event is None:
        raise FreezeError("Cursor must refer to an observed human event")
    target_seq = target_event["sequence"] if target_event else 0
    if target_seq < old_seq:
        raise FreezeError("Feedback cursor cannot move backwards")
    dispositions = payload.get("dispositions", [])
    if not isinstance(dispositions, list):
        raise FreezeError("Feedback dispositions must be a list")
    covered = {d.get("event_id") for d in dispositions if isinstance(d, dict)}
    if len(covered) != len(dispositions):
        raise FreezeError("Each disposition must identify one distinct feedback event")
    needed = {e["id"] for e in events if e["actor"] == "user" and old_seq < e["sequence"] <= target_seq}
    if not needed <= covered:
        raise FreezeError("Every crossed human feedback needs a reply or pending item")
    messages = {
        m["id"]
        for m in record.get("messages", [])
        if m.get("actor") == "codex" and m.get("request_id") == request_id
    }
    pending = {
        p["id"]
        for p in record["pending_items"]
        if p.get("updated_in") == request_id and not p.get("resolved")
    }
    for d in dispositions:
        if d.get("event_id") not in {e["id"] for e in events}:
            raise FreezeError("Unknown disposition feedback")
        if d.get("reply_id") not in messages and d.get("pending_id") not in pending:
            raise FreezeError("Disposition must reference a reply or pending item saved in this transaction")
        if d.get("pending_id") in pending:
            item = next(p for p in record["pending_items"] if p["id"] == d["pending_id"])
            refs = item.setdefault("input_refs", [])
            if d["event_id"] not in refs:
                refs.append(d["event_id"])
    external = payload.get("handled_external", [])
    external_ids = {e["id"] for e in events if e["actor"] == "external_ai"}
    if not isinstance(external, list) or not set(external) <= external_ids or not set(external) <= covered:
        raise FreezeError("External input needs a saved assessment")
    record["processing"]["human_cursor"] = target
    record["processing"]["handled_external"] = sorted(
        set(record["processing"]["handled_external"]) | set(external)
    )
    changes = payload.get("handled_changes", [])
    change_ids = {e["id"] for e in events if e["actor"] == "system"}
    if not isinstance(changes, list) or not set(changes) <= change_ids or not set(changes) <= covered:
        raise FreezeError("Changed evidence or dependencies need a saved assessment")
    record["processing"]["handled_changes"] = sorted(
        set(record["processing"].get("handled_changes", [])) | set(changes)
    )
    if payload.get("bootstrap_complete"):
        require_text(payload.get("bootstrap_reason"), "legacy reconciliation result", 5000)
        record["processing"]["bootstrap"] = "complete"
    record["processing"]["receipts"].append(
        {
            "request_id": request_id,
            "at": now(),
            "human_cursor": target,
            "dispositions": copy.deepcopy(dispositions),
            "bootstrap_reason": payload.get("bootstrap_reason"),
        }
    )


def update_pending(record, values, request_id, questions):
    if not isinstance(values, list):
        raise FreezeError("Pending updates must be a list")
    seen = set()
    for value in values:
        if not isinstance(value, dict):
            raise FreezeError("Pending item must be an object")
        identifier = require_text(value.get("id"), "pending ID", 100)
        if identifier in seen:
            raise FreezeError("Combine each pending item's updates into one entry")
        seen.add(identifier)
        old = next((p for p in record["pending_items"] if p["id"] == identifier), None)
        condition = value.get("continue_when", (old or {}).get("continue_when"))
        if not isinstance(condition, dict) or condition.get("kind") not in {
            "definition_confirmed",
            "local_assessment",
            "new_material",
            "human_continue",
        }:
            raise FreezeError("Pending item requires an explicit continuation condition")
        condition = copy.deepcopy(condition)
        if (old or {}).get("continue_when", {}).get("kind") == "human_continue" and condition[
            "kind"
        ] != "human_continue":
            raise FreezeError("A human continuation wait cannot be replaced with an automatic condition")
        if condition["kind"] == "human_continue":
            if type(condition.get("satisfied")) is not bool:
                raise FreezeError("Human continuation requires an explicit satisfied boolean")
            if condition["satisfied"]:
                if not old or old["continue_when"]["kind"] != "human_continue":
                    raise FreezeError("Save the handoff before recording the human instruction to continue")
                require_text(condition.get("instruction"), "human continuation instruction", 5000)
                if condition.get("source") not in {"conversation", "council"}:
                    raise FreezeError("Human continuation source must be conversation or council")
            if value.get("resolved", (old or {}).get("resolved", False)) and not condition["satisfied"]:
                raise FreezeError("Resolve the handoff only after an explicit human instruction to continue")
        if condition["kind"] == "definition_confirmed":
            question_id = condition.get("question_id")
            if not isinstance(question_id, str) or question_id not in questions:
                raise FreezeError("Invalid pending prerequisite")
            if "min_version" in condition and (
                type(condition["min_version"]) is not int or condition["min_version"] < 1
            ):
                raise FreezeError("Pending prerequisite requires a positive min_version")
        if condition["kind"] == "new_material" and (
            type(condition.get("after_sequence")) is not int
            or not 0 <= condition["after_sequence"] <= len(record["feedback_events"])
        ):
            raise FreezeError("New-material condition requires the observed event boundary")
        if condition["kind"] == "local_assessment" and condition.get("satisfied"):
            require_text(condition.get("assessment"), "local condition assessment", 5000)
        item = {
            **(old or {}),
            **copy.deepcopy(value),
            "continue_when": copy.deepcopy(condition),
            "updated_at": now(),
            "updated_in": request_id,
        }
        require_text(item.get("question"), "unresolved question", 5000)
        require_text(item.get("reason"), "pending reason", 5000)
        if old:
            record["pending_items"][record["pending_items"].index(old)] = item
        else:
            record["pending_items"].append(item)


def bind_pending_versions(record, questions, request_id):
    # Bind once, after all candidate edits in the transaction. The order of
    # changes must not make an old formal version satisfy a new candidate wait.
    for item in record["pending_items"]:
        condition = item["continue_when"]
        if (
            item.get("updated_in") == request_id
            and condition["kind"] == "definition_confirmed"
            and "min_version" not in condition
        ):
            definition = state(questions[condition["question_id"]])
            current = definition["current_version"] or 0
            condition["min_version"] = max(1, current + (definition["draft"] is not None))


def review_token(record):
    d = state(record)
    current = d["versions"][-1] if d["current_version"] else None
    return digest(
        json.dumps(
            [
                record["id"],
                (current or {}).get("number"),
                (current or {}).get("text_sha256"),
                record.get("review_basis"),
                record.get("review_required"),
            ],
            sort_keys=True,
            ensure_ascii=False,
        )
    )


def reconfirm(record, value, actor):
    if actor != "user":
        raise FreezeError("Only the user can reconfirm an effective definition")
    d = state(record)
    if not d["current_version"] or d["draft"]:
        raise FreezeError("Reconfirmation requires the current version without a wording candidate")
    if not record.get("review_required") or not record.get("review_basis"):
        raise FreezeError("No prepared evidence reassessment to reconfirm")
    if record["work"]["phase"] != "human_review":
        raise FreezeError("Reconfirmation requires a prepared human review")
    if value != review_token(record):
        raise FreezeError("Evidence changed since read; review again")
    version = d["versions"][-1]
    version.setdefault("reconfirmations", []).append(
        {
            "by": "user",
            "at": now(),
            "evidence_basis": copy.deepcopy(record["review_basis"]),
            "token": value,
            "reason": record["review_required"]["reason"],
        }
    )
    record["review_required"] = None
    automatic_phase(record, "closed", "reconfirmed", value, actor)


def apply_definition(record, operation, value, actor, questions):
    from .assets import freeze_images, validate_tables
    from .decisions import bind_dependencies, candidate_for_approval, check_approval

    if actor == "codex" and operation == "definition_draft" and waiting_for_human_continue(record):
        raise FreezeError("Research handoff is waiting for an explicit human instruction to continue")
    if operation == "definition_draft":
        value = copy.deepcopy(value) if isinstance(value, dict) else {"text": value}
        validate_tables(value.get("text", ""))
        if "dependencies" in value:
            value["dependencies"] = bind_dependencies(value["dependencies"], questions, record["id"])
        # Asset snapshots are prepared by the storage service, which supplies a project.
        project = record.pop("_asset_project", None)
        if project:
            value["text"] = freeze_images(project, value["text"])
    if operation == "definition_approve":
        candidate = candidate_for_approval(record["id"], questions)
        if not candidate or value != approval_token(candidate):
            raise FreezeError("Candidate or evidence changed since read; review again")
        if record["work"]["phase"] != "human_review":
            raise FreezeError("Complete the review packet before human confirmation")
        if record.get("review_required"):
            raise FreezeError("Evidence needs reassessment before confirmation")
        state(record)["draft"] = candidate
        check_approval(record["id"], questions)
    change_definition(record, operation, value, actor)
    if operation in {"definition_draft", "definition_begin"} and state(record)["draft"]:
        state(record)["draft"]["review_basis"] = copy.deepcopy(record.get("review_basis"))
        phase = "evidence" if waiting_for_human_continue(record) else "prepare_review"
        automatic_phase(record, phase, "Candidate wording saved", operation, actor)
    if operation == "definition_discard":
        automatic_phase(
            record,
            "closed" if state(record)["current_version"] else "triage",
            "candidate_withdrawn",
            operation,
            actor,
        )
    if operation == "definition_approve":
        automatic_phase(record, "closed", "confirmed", operation, actor)
    record.pop("status", None)
