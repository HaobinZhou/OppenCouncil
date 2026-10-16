"""Local execution of explicit human instructions, using the ordinary Council mutations.

The local agent is responsible for faithfully carrying the actual human instruction.
This receipt records provenance; it does not authenticate a natural-language instruction.
External MCP clients and ordinary AI writes do not enter this interface.
"""

from __future__ import annotations

import copy
import re

from .store import FreezeError, now, request_fingerprint, require_text

QUESTION_OPERATIONS = {
    "comment", "definition_draft", "definition_approve", "definition_reconfirm",
    "definition_begin", "definition_discard", "answer", "discuss", "resolve",
}
GROUP_OPERATIONS = {"comment", "select_option", "begin", "discard", "approve"}


def normalize_authorization(value, actor):
    if value is None:
        return None
    if actor != "user" or not isinstance(value, dict):
        raise FreezeError("Conversation authorization requires a human action")
    if set(value) - {"source", "instruction", "thread_id", "message_id"}:
        raise FreezeError("Unknown conversation authorization fields")
    if value.get("source") != "conversation":
        raise FreezeError("Authorization must identify the human conversation")
    result = {
        "source": "conversation",
        "instruction": require_text(value.get("instruction"), "actual human instruction", 20000),
    }
    for key in ("thread_id", "message_id"):
        if key in value:
            result[key] = require_text(value[key], key, 300)
    return result


def record_action(record, authorization, operation, value, revision, request_id, *,
                  approved=False, reconfirmed=False, group_id=None):
    """Include the receipt in the same atomic write as its result, never a later repair."""
    if authorization is None:
        return
    origin = {**copy.deepcopy(authorization), "authorized_by": "user", "executed_by": "codex"}
    receipt = {
        **origin, "request_id": request_id, "at": now(), "target_id": record["id"],
        "operation": operation, "expected_revision": revision,
        "value_sha256": request_fingerprint(operation, value),
    }
    if group_id:
        receipt["group_id"] = group_id
    definition = record.get("definition", {})
    if approved or reconfirmed:
        receipt["version"] = definition["current_version"]
        version = definition["versions"][-1]
        receipt["text_sha256"] = version["text_sha256"]
        target = version["approval"] if approved else version["reconfirmations"][-1]
        target["authorization"] = copy.deepcopy(origin)
    record.setdefault("human_actions", []).append(receipt)
    for message in record.get("messages", []):
        if message.get("id") == request_id or message.get("request_id") == request_id:
            message["authorization"] = copy.deepcopy(origin)
    for confirmation in record.get("confirmations", []):
        if confirmation.get("request_id") == request_id:
            confirmation["authorization"] = copy.deepcopy(origin)


def execute(store, payload):
    """One authorized item action; group confirmation retains its atomic member transaction."""
    if not isinstance(payload, dict) or set(payload) - {
        "request_id", "id", "operation", "value", "expected_revision", "authorization",
    }:
        raise FreezeError("Invalid human-action payload")
    authorization = normalize_authorization(payload.get("authorization"), "user")
    if authorization is None:
        raise FreezeError("An explicit human conversation instruction is required")
    identifier = payload.get("id")
    if not isinstance(identifier, str) or not re.fullmatch(r"[FBI]-[0-9]{6}", identifier):
        raise FreezeError("Human action requires an existing F, B or I ID")
    revision = payload.get("expected_revision")
    if type(revision) is not int or revision < 1:
        raise FreezeError("Human action requires the revision shown during review")
    operation = payload.get("operation")
    allowed = GROUP_OPERATIONS if identifier.startswith("B-") else (
        {"comment"} if identifier.startswith("I-") else QUESTION_OPERATIONS
    )
    if not isinstance(operation, str) or operation not in allowed:
        raise FreezeError("Human action must use an existing webpage operation")
    request_id = require_text(payload.get("request_id"), "request_id", 100)
    arguments = dict(expected_revision=revision, request_id=request_id,
                     actor="user", authorization=authorization)
    if identifier.startswith("B-"):
        result = store.change_group(identifier, operation, payload.get("value"), **arguments)
    elif identifier.startswith("I-"):
        from .workstore import WorkStore

        work = WorkStore(store)
        result = work.commit_work(
            {"read_set": {identifier: revision},
             "changes": [{"id": identifier, "comments": [payload.get("value")]}]},
            request_id=request_id, actor="user", authorization=authorization,
        )
        result = {**result, "item": work.read(identifier)}
    else:
        result = store.change(identifier, operation, payload.get("value"), **arguments)
    return {"channel": "conversation", "executed_by": "codex", "result": result}
