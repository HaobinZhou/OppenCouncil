"""Create a v5 anchor or adopt an ordinary project without moving its files."""

from __future__ import annotations

import copy
import re
from pathlib import Path, PurePosixPath

from . import project_transaction as tx
from .output_rules import artifact_error
from .outputs import fingerprint, members
from .project import MARKER, NAMESPACE, Project, baseline_bytes, metadata_block
from .project_registry import OUTPUT_HEADERS, ROLE_NAMES, relative_path, stable_key, within, write_table
from .store import FreezeError, now

CANONICAL_HEADERS = ("Topic", "Canonical path", "Section", "Status", "Verification")
ADOPTION_FIELDS = {"role_mappings", "initial_canonical_registrations", "initial_deliverable_registrations"}
NEW_PROJECT_FILES = {".git", ".gitignore", ".gitattributes", ".DS_Store", tx.LOCK}


def inspect(root):
    """Read-only preflight, including an interrupted transaction without recovering it."""
    root = Path(root).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise FreezeError("Project root must be a directory")
    if (root / tx.STAGING).exists() or (root / tx.STAGING).is_symlink():
        return {"state": "RECOVERY_REQUIRED", "project": str(root)}
    anchors = []
    for name in ("project.md", NAMESPACE + "/registry.md"):
        raw = tx.read_bytes(tx.safe_destination(root, name))
        if raw and re.search(
            rb"<!-- (?:oppencouncil|stepwise-r-project|oppen-project-steward):v[0-9]+ -->", raw
        ):
            anchors.append(name)
    if anchors:
        try:
            project = Project(root, recover=False)
            project.baseline_state()
        except FreezeError as error:
            return {"state": "EXISTING_GOVERNANCE", "project": str(root), "reason": str(error)}
        return {
            "state": "MANAGED_READY",
            "project": str(root),
            "project_type": project.project_type,
            "layout": "namespace" if project.namespaced else "root",
        }
    if (root / NAMESPACE).exists() or (root / NAMESPACE).is_symlink():
        return {
            "state": "ADOPTION_BLOCKED",
            "project": str(root),
            "reason": "Existing governance namespace needs inspection; never overwrite it",
        }
    return {
        "state": "ADOPTION_REQUIRED",
        "project": str(root),
        "entries": sorted(p.name for p in root.iterdir() if p.name not in {".DS_Store", tx.LOCK}),
    }


def canonical_rows(root, values, reads):
    if not isinstance(values, list):
        raise FreezeError("Initial canonical registrations must be an array")
    rows, topics, owners = [], set(), set()
    fields = {"topic", "path", "section", "status", "verification"}
    for value in values:
        if not isinstance(value, dict) or set(value) != fields:
            raise FreezeError("Invalid initial canonical registration fields")
        topic = stable_key(value["topic"], "Canonical topic")
        path, section = value["path"], value["section"] or ""
        relative_path(root, path, required=True)
        if not isinstance(section, str):
            raise FreezeError("Canonical section must be text or null")
        if section:
            content = tx.read_bytes(root / path).decode("utf-8")
            if len(re.findall(r"^#{1,6}\s+" + re.escape(section) + r"\s*$", content, re.M)) != 1:
                raise FreezeError("Canonical section must occur exactly once: " + section)
        if value["status"] not in {"draft", "partially-frozen", "frozen"}:
            raise FreezeError("Invalid canonical status")
        if topic in topics or (path, section) in owners:
            raise FreezeError("Canonical topics and owners must be unique")
        topics.add(topic)
        owners.add((path, section))
        for name in (path, value["verification"]):
            result = fingerprint(root, name)
            if not result["bytes"]:
                raise FreezeError("Canonical owner and verification must not be empty")
            reads[name] = result["sha256"]
        rows.append(
            dict(
                zip(
                    CANONICAL_HEADERS,
                    (topic, path, section, value["status"], value["verification"]),
                    strict=True,
                )
            )
        )
    return sorted(rows, key=lambda row: row["Topic"])


def prepare(root, project_type, layout, payload, *, adoption):
    if project_type not in {"research", "general"} or layout not in {"root", "namespace"}:
        raise FreezeError("Explicit project type and root/namespace layout are required")
    if not isinstance(payload, dict) or set(payload) != ADOPTION_FIELDS:
        raise FreezeError("Adoption payload requires role_mappings and both initial registration arrays")
    roles = {}
    if not isinstance(payload["role_mappings"], dict):
        raise FreezeError("Role mappings must be an object")
    for raw_role, name in payload["role_mappings"].items():
        role = ROLE_NAMES.get(raw_role.lower()) if isinstance(raw_role, str) else None
        if not role or role in roles:
            raise FreezeError("Unknown or duplicate role mapping")
        relative_path(root, name, directory=True, required=adoption)
        if within(name, NAMESPACE) or name in {"Freeze", "Memory", "Attention"}:
            raise FreezeError("Roles must not take over the governance control plane")
        if any(within(name, p) or within(p, name) for p in roles.values()):
            raise FreezeError("Project role areas must not overlap")
        roles[role] = name
    control = NAMESPACE + "/" if layout == "namespace" else ""
    registry_name = control + ("registry.md" if control else "project.md")
    if tx.read_bytes(tx.safe_destination(root, registry_name)) is not None:
        raise FreezeError("Registry destination is already user-owned: " + registry_name)
    if not adoption and project_type == "research":
        roles = {
            "scripts": "Scripts",
            "data": "Data",
            "results": "Results",
            "explore": "Explore",
            "releases": "Releases",
            **roles,
        }
    reads = {}
    canonical = canonical_rows(root, payload["initial_canonical_registrations"], reads)
    values = payload["initial_deliverable_registrations"]
    if not isinstance(values, list):
        raise FreezeError("Initial output registrations must be an array")
    outputs, ids, paths = [], set(), []
    area = roles.get("results" if project_type == "research" else "deliverables")
    for value in values:
        if not isinstance(value, dict) or set(value) != {key.lower() for key in OUTPUT_HEADERS}:
            raise FreezeError("Invalid initial output registration fields")
        for field in ("id", "kind", "audience"):
            stable_key(value[field], field)
        name = value["path"]
        relative_path(root, name, directory=value["kind"] == "group", required=True)
        if not area or name == area or not within(name, area):
            raise FreezeError("Initial output requires an explicit matching role")
        if value["id"] in ids or any(within(name, p) or within(p, name) for p in paths):
            raise FreezeError("Initial output IDs and ownership must not overlap")
        for member in members(root, name, value["kind"]):
            if reason := artifact_error(
                PurePosixPath(member).relative_to(area), value["kind"], research=project_type == "research"
            ):
                raise FreezeError(member + ": " + reason)
            reads[member] = fingerprint(root, member)["sha256"]
        reads[value["producer"]] = fingerprint(root, value["producer"])["sha256"]
        ids.add(value["id"])
        paths.append(name)
        outputs.append({key: value[key.lower()] for key in OUTPUT_HEADERS})
    metadata = {
        "governance_version": 5,
        "project_type": project_type,
        "type_history": [],
        "adoption" if adoption else "initialization": {
            "at": now(),
            "by": "codex",
            "legacy_outputs_without_specification": sorted(ids) if project_type == "research" else [],
        },
    }
    if adoption and project_type == "research" and roles.get("scripts"):
        from .output_rules import NUMBERED
        from .script_ops import analysis_scripts, inventory

        script_files, _ = inventory(root, roles["scripts"])
        metadata["adoption"]["legacy_unnumbered_scripts"] = [
            path
            for path in analysis_scripts(script_files, roles["scripts"])
            if not NUMBERED.fullmatch(PurePosixPath(path).name)
        ]
    text = MARKER + "\n# Project registry\n\n" + metadata_block(metadata) + "\n"
    text = write_table(
        text, "roles", ("Role", "Path"), [{"Role": k.title(), "Path": v} for k, v in sorted(roles.items())]
    )
    text = write_table(text, "canonical", CANONICAL_HEADERS, canonical)
    text = write_table(
        text,
        "results" if project_type == "research" else "deliverables",
        OUTPUT_HEADERS,
        sorted(outputs, key=lambda row: row["ID"]),
    )
    raw = text.encode("utf-8")
    writes = {
        registry_name: raw,
        control + (".managed-state.json" if control else ".oppencouncil-state.json"): baseline_bytes(
            1, {"registry.md" if control else "project.md": tx.digest(raw)}
        ),
    }
    directories = [] if adoption else sorted(set(roles.values()) | {control + "Audit"})
    if not adoption and project_type == "research":
        directories += [roles["scripts"] + "/functions", roles["data"] + "/raw", roles["data"] + "/derived"]
    return writes, reads, directories


def create(root, *, project_type, layout=None, payload=None, adoption=False, fault=None):
    root = Path(root).expanduser().absolute()
    if not root.exists():
        if adoption:
            raise FreezeError("Adoption requires an existing project")
        root.mkdir(parents=True)
    layout = layout or ("root" if project_type == "research" else "namespace")
    payload = (
        copy.deepcopy(payload)
        if payload is not None
        else {
            "role_mappings": {},
            "initial_canonical_registrations": [],
            "initial_deliverable_registrations": [],
        }
    )
    with tx.project_lock(root) as root:
        tx.recover_locked(root)
        state = inspect(root)
        if state["state"] == "MANAGED_READY":
            if state["project_type"] != project_type or state["layout"] != layout:
                raise FreezeError(
                    "Use explicit project-type or migration operations to change existing governance"
                )
            if any(payload.values()):
                raise FreezeError("Project is already managed; use registration commands for further changes")
            return {**state, "changed_paths": []}
        if state["state"] != "ADOPTION_REQUIRED":
            raise FreezeError(
                state["state"] + ": " + state.get("reason", "Use upgrade-v5 for existing governance")
            )
        if not adoption and set(state["entries"]) - NEW_PROJECT_FILES:
            raise FreezeError("Existing project requires adopt; init only creates genuinely new projects")
        writes, reads, directories = prepare(root, project_type, layout, payload, adoption=adoption)
        expected = {name: None for name in writes}
        result = tx.apply(
            root,
            writes,
            expected=expected,
            read_set=reads,
            create_directories=directories,
            verify=lambda: Project(root, recover=False).baseline_state(),
            fault=fault,
        )
        return {
            **result,
            "state": "MANAGED_READY",
            "project": str(root),
            "project_type": project_type,
            "layout": layout,
        }
