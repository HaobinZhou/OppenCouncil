"""One project-owned source for per-question formal definitions and their versions."""

from __future__ import annotations

import copy
import hashlib
import json

from .store import FreezeError, now, require_text


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def approval_token(draft: dict) -> str:
    if not draft.get("dependencies"):
        return draft["text_sha256"]
    return digest(json.dumps([draft["text"], draft["dependencies"]], ensure_ascii=False, sort_keys=True))


def state(question: dict) -> dict:
    return question.setdefault("definition", {"draft": None, "versions": [], "current_version": None})


def change_definition(question: dict, operation: str, value: object, actor: str) -> None:
    definition = state(question)
    draft = definition["draft"]
    current = definition["current_version"]
    if operation == "definition_begin":
        if actor != "user":
            raise FreezeError("Only the user can explicitly open the next definition version")
        if draft is not None:
            raise FreezeError("A candidate definition already exists")
        text = definition["versions"][-1]["text"] if current else ""
        definition["draft"] = {
            "text": text,
            "text_sha256": digest(text),
            "base_version": current,
            "updated_by": actor,
            "updated_at": now(),
            "approval": None,
            "edits": [],
            "dependencies": copy.deepcopy(definition["versions"][-1].get("dependencies", []))
            if current
            else [],
        }
    elif operation == "definition_draft":
        dependencies = (
            value.get("dependencies", [])
            if isinstance(value, dict)
            else (draft.get("dependencies", []) if draft else [])
        )
        text = require_text(value.get("text") if isinstance(value, dict) else value, "definition text", 20000)
        if draft is None and current is not None:
            raise FreezeError("Open a revision explicitly before editing an effective definition")
        if draft is not None and draft["text"] == text and draft.get("dependencies", []) == dependencies:
            return
        if draft is None:
            draft = {"base_version": current, "edits": []}
            definition["draft"] = draft
        draft.setdefault("edits", []).append({"text": text, "by": actor, "at": now()})
        draft.update(
            text=text,
            text_sha256=digest(text),
            updated_by=actor,
            updated_at=now(),
            approval=None,
            dependencies=copy.deepcopy(dependencies),
        )
    elif operation == "definition_approve":
        if actor != "user":
            raise FreezeError("Only the user can confirm candidate wording")
        if not draft or not draft["text"].strip():
            raise FreezeError("Save the complete candidate wording before confirming it")
        if value != approval_token(draft):
            raise FreezeError("Candidate wording changed since read; review it again")
        if (
            current
            and draft["text"] == definition["versions"][-1]["text"]
            and draft.get("dependencies", []) == definition["versions"][-1].get("dependencies", [])
        ):
            raise FreezeError("Candidate wording is unchanged; edit it or withdraw the candidate")
        number = len(definition["versions"]) + 1
        version = {
            "number": number,
            "text": draft["text"],
            "text_sha256": digest(draft["text"]),
            "approval": {"by": "user", "at": now(), "text_sha256": draft["text_sha256"]},
            "published_at": now(),
            "published_by": "user",
            "supersedes": current,
            "source": f"Freeze/questions/{question['id']}.json#/definition/versions/{number - 1}",
            "edits": copy.deepcopy(draft.get("edits", [])),
            "dependencies": copy.deepcopy(draft.get("dependencies", [])),
            "content_sha256": approval_token(draft),
        }
        definition["versions"].append(version)
        definition["current_version"] = number
        definition["draft"] = None
        question["canonical_ref"] = f"Freeze/questions/{question['id']}.json#/definition"
        question["status"] = "frozen"
        return
    elif operation == "definition_discard":
        if actor != "user" or draft is None:
            raise FreezeError("Only the user can withdraw an existing candidate")
        withdrawn = {**draft, "withdrawn_at": now()}
        # Retain unfinished browser edits without promoting them into formal wording.
        if value is not None:
            if (
                not isinstance(value, dict)
                or not isinstance(value.get("text"), str)
                or len(value["text"]) > 20000
            ):
                raise FreezeError("Invalid local candidate edit")
            withdrawn["local_edit"] = {
                "text": value["text"],
                "request_id": require_text(value.get("request_id"), "local edit request_id", 100),
                "by": actor,
            }
        definition.setdefault("withdrawn_drafts", []).append(withdrawn)
        definition["draft"] = None
        question["status"] = "frozen" if current else "discussing"
        return
    else:
        raise FreezeError("Unknown definition operation")
    # Discussion/working state and the effective version are deliberately independent.
    question["status"] = "discussing"


def validate_definition(question: dict) -> None:
    """Every reader rejects invalid current pointers or altered formal version text."""
    if "definition" not in question:
        return  # Pre-versioning records remain readable without promotion.
    try:
        definition = question["definition"]
        versions, current = definition["versions"], definition["current_version"]
        if not isinstance(versions, list) or current != (len(versions) or None):
            raise ValueError("invalid current pointer")
        if current is not None and type(current) is not int:
            raise ValueError("invalid version number")
        for number, version in enumerate(versions, 1):
            source = f"Freeze/questions/{question['id']}.json#/definition/versions/{number - 1}"
            text = version["text"]
            approval = version["approval"]
            if (
                type(version["number"]) is not int
                or version["number"] != number
                or not isinstance(text, str)
                or not text.strip()
                or digest(text) != version["text_sha256"]
                or approval["by"] != "user"
                or not approval["at"]
                or approval["text_sha256"] != version["text_sha256"]
                or ("content_sha256" in version and version["content_sha256"] != approval_token(version))
                or version["source"] != source
                or version["supersedes"] != (number - 1 if number > 1 else None)
            ):
                raise ValueError("invalid formal version or confirmation")
        draft = definition["draft"]
        if draft is not None and (
            draft["base_version"] != current or digest(draft["text"]) != draft["text_sha256"]
        ):
            raise ValueError("invalid candidate base or text")
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        raise FreezeError(f"Invalid definition record: {exc}") from exc


def read_definition(store, question_id: str, number: int | None = None) -> dict:
    """Read the exact effective or historical text used by web, MCP and project code."""
    question = store.read_question(question_id)
    definition = state(question)
    number = definition["current_version"] if number is None else number
    if type(number) is not int or number < 1:
        raise FreezeError("This question has no effective definition")
    version = next((v for v in definition["versions"] if v["number"] == number), None)
    if version is None:
        raise FreezeError("Definition version not found")
    if digest(version["text"]) != version["text_sha256"]:
        raise FreezeError("Formal definition text changed outside version management")
    return {
        **version,
        "question_id": question_id,
        "title": question["title"],
        "effective": number == definition["current_version"],
        "readiness": question.get("readiness", {}),
    }


def render_definition(version: dict) -> str:
    """A derived Markdown view; the authoritative text remains in the question JSON."""
    return (
        f"# {version['title']}\n\n"
        f"口径编号：{version['question_id']} · v{version['number']}\n\n"
        f"来源：{version['source']}\n\n" + version["text"] + "\n"
    )
