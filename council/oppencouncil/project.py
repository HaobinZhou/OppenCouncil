"""The common v5 project anchor, declared type and managed-file baseline.

Layout selects paths only. Project type selects governance behavior. Existing
Steward baseline files keep their schema and generation semantics.
"""

from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath

from . import project_transaction as tx
from .store import FreezeError, governance_registry, now

MARKER = "<!-- oppencouncil:v5 -->"
META_START = "<!-- oppencouncil:metadata:start -->"
META_END = "<!-- oppencouncil:metadata:end -->"
NAMESPACE = ".oppen-project-steward"


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise FreezeError("Duplicate JSON key: " + key)
        value[key] = item
    return value


def metadata_block(value):
    return META_START + "\n```json\n" + json_bytes(value).decode() + "```\n" + META_END


def read_metadata(text):
    text = text.replace("\r\n", "\n")
    if text.count(META_START) != 1 or text.count(META_END) != 1:
        raise FreezeError("v5 requires exactly one project metadata block")
    block = text.split(META_START, 1)[1].split(META_END, 1)[0].strip()
    if not block.startswith("```json\n") or not block.endswith("\n```"):
        raise FreezeError("Malformed project metadata block")
    try:
        value = json.loads(block[8:-4], object_pairs_hook=unique_object)
    except (ValueError, TypeError) as exc:
        raise FreezeError("Invalid project metadata JSON") from exc
    if not isinstance(value, dict) or value.get("governance_version") != 5:
        raise FreezeError("Unsupported governance metadata")
    if value.get("project_type") not in {"research", "general"}:
        raise FreezeError("Project type must be research or general")
    if not isinstance(value.get("type_history", []), list):
        raise FreezeError("Project type history must be an array")
    return value


def replace_metadata(text, value):
    read_metadata(text)
    start = text.index(META_START)
    end = text.index(META_END, start) + len(META_END)
    return text[:start] + metadata_block(value) + text[end:]


class Project:
    def __init__(self, root, *, recover=True):
        self.root = Path(root).expanduser().resolve(strict=True)
        if recover:
            tx.recover(self.root)
        self.registry, self.skill = governance_registry(self.root)
        if self.skill != "oppencouncil":
            raise FreezeError("Project requires explicit upgrade-v5 before v5 helper operations")
        self.registry_name = self.registry.relative_to(self.root).as_posix()
        self.registry_bytes = tx.read_bytes(self.registry)
        self.metadata = read_metadata(self.registry_bytes.decode("utf-8"))
        self.project_type = self.metadata["project_type"]
        self.namespaced = self.registry_name.startswith(NAMESPACE + "/")
        self.control = self.root / NAMESPACE if self.namespaced else self.root
        self.memory = self.control / "Memory"
        self.baseline = self.control / (
            ".managed-state.json" if self.namespaced else ".oppencouncil-state.json"
        )

    def relative(self, path):
        return path.relative_to(self.root).as_posix()

    def canonical_topics(self):
        text = self.registry_bytes.decode("utf-8")
        blocks = re.findall(
            r"<!-- (?:stepwise-r-project|oppen-project-steward|oppencouncil):canonical:start -->"
            r"(.*?)<!-- (?:stepwise-r-project|oppen-project-steward|oppencouncil):canonical:end -->",
            text,
            re.DOTALL,
        )
        if not blocks:
            return set()
        if len(blocks) != 1:
            raise FreezeError("Ambiguous canonical registry")
        rows = [line.strip() for line in blocks[0].splitlines() if line.strip().startswith("|")]
        return {line.strip("|").split("|", 1)[0].strip().strip("`") for line in rows[2:]}

    def managed(self, name):
        path = PurePosixPath(name)
        registry = "registry.md" if self.namespaced else "project.md"
        if name == registry:
            return True
        if len(path.parts) > 1 and path.parts[0] in {"Memory", "Attention"}:
            return True
        return path.parts[:2] == ("Audit", "Contracts") and len(path.parts) > 2

    def snapshot(self):
        files = {self.registry}
        for area in ("Memory", "Attention", "Audit/Contracts"):
            scope = self.control / area
            # safe_destination rejects a final directory, so check its parents using a leaf.
            tx.safe_destination(self.root, self.relative(scope / ".path-check"))
            if scope.exists():
                for path in scope.rglob("*"):
                    if path.is_symlink():
                        raise FreezeError("Managed control plane cannot contain symbolic links")
                    if path.is_file() and path.name != ".DS_Store":
                        files.add(path)
        return {
            path.relative_to(self.control).as_posix(): tx.digest(tx.read_bytes(path))
            for path in sorted(files)
        }

    def baseline_state(self):
        raw = tx.read_bytes(self.baseline)
        if raw is None:
            raise FreezeError("MANAGED_BASELINE_MISSING: " + self.relative(self.baseline))
        try:
            value = json.loads(raw, object_pairs_hook=unique_object)
            if set(value) != {"schema_version", "generation", "files"} or value["schema_version"] != 1:
                raise ValueError("schema")
            if type(value["generation"]) is not int or value["generation"] < 1:
                raise ValueError("generation")
            files = {}
            for entry in value["files"]:
                name, checksum = entry["path"], entry["sha256"]
                if set(entry) != {"path", "sha256"} or name in files or not self.managed(name):
                    raise ValueError("file entry")
                tx.safe_destination(self.root, self.relative(self.control / name))
                if not re.fullmatch(r"[a-f0-9]{64}", checksum):
                    raise ValueError("checksum")
                files[name] = checksum
            if list(files) != sorted(files):
                raise ValueError("file order")
        except (ValueError, TypeError, KeyError) as exc:
            raise FreezeError("Invalid managed-state baseline") from exc
        observed = self.snapshot()
        changed = [
            name for name in sorted(files.keys() | observed.keys()) if files.get(name) != observed.get(name)
        ]
        if changed:
            raise FreezeError("MANAGED_STATE_CONFLICT: " + ", ".join(changed))
        return value, files, raw

    def prepare_writes(self, writes):
        """Return exact writes plus updated baseline and every managed read dependency."""
        state, files, baseline_raw = self.baseline_state()
        reads = {self.relative(self.control / name): checksum for name, checksum in files.items()}
        reads[self.relative(self.baseline)] = tx.digest(baseline_raw)
        result = dict(writes)
        for name, raw in writes.items():
            path = tx.safe_destination(self.root, name)
            try:
                local = path.relative_to(self.control).as_posix()
            except ValueError:
                continue
            if self.managed(local):
                if raw is None:
                    files.pop(local, None)
                else:
                    files[local] = tx.digest(raw)
        result[self.relative(self.baseline)] = baseline_bytes(state["generation"] + 1, files)
        expected = {name: tx.file_digest(tx.safe_destination(self.root, name)) for name in result}
        return result, expected, reads

    def commit(self, writes, *, read_set=None, verify=None, fault=None):
        writes, expected, reads = self.prepare_writes(writes)
        for name, checksum in (read_set or {}).items():
            if name in reads and reads[name] != checksum:
                raise FreezeError("Project input changed while preparing: " + name)
            reads[name] = checksum

        def verify_all():
            Project(self.root, recover=False).baseline_state()
            if verify:
                verify()

        return tx.apply(self.root, writes, expected=expected, read_set=reads, verify=verify_all, fault=fault)

    def change_type(self, project_type, reason):
        if project_type not in {"research", "general"}:
            raise FreezeError("Project type must be research or general")
        if not isinstance(reason, str) or not reason.strip():
            raise FreezeError("An explicit type-change reason is required")
        if project_type == self.project_type:
            return {"changed_paths": [], "project_type": project_type}
        value = dict(self.metadata)
        value["project_type"] = project_type
        value["type_history"] = [
            *value.get("type_history", []),
            {
                "from": self.project_type,
                "to": project_type,
                "reason": reason.strip(),
                "at": now(),
                "by": "codex",
            },
        ]
        content = replace_metadata(self.registry_bytes.decode("utf-8"), value).encode("utf-8")
        return self.commit(
            {self.registry_name: content}, read_set={self.registry_name: tx.digest(self.registry_bytes)}
        )


def baseline_bytes(generation, files):
    return json_bytes(
        {
            "schema_version": 1,
            "generation": generation,
            "files": [{"path": name, "sha256": value} for name, value in sorted(files.items())],
        }
    )
