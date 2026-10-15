"""One registry adapter for both project layouts and preserved legacy tables."""

from __future__ import annotations

import copy
import re
from pathlib import PurePosixPath

from . import project_transaction as tx
from .project import Project, replace_metadata
from .store import FreezeError

PREFIXES = ("oppencouncil", "stepwise-r-project", "oppen-project-steward")
OUTPUT_HEADERS = ("ID", "Path", "Kind", "Audience", "Producer")
ROLE_NAMES = {
    "r": "scripts",
    "scripts": "scripts",
    "source": "source",
    "data": "data",
    "results": "results",
    "deliverables": "deliverables",
    "audit": "audit",
    "explore": "explore",
    "releases": "releases",
}


def tables(text, prefix, block):
    start, end = f"<!-- {prefix}:{block}:start -->", f"<!-- {prefix}:{block}:end -->"
    if start not in text and end not in text:
        return []
    if text.count(start) != 1 or text.count(end) != 1 or text.index(start) > text.index(end):
        raise FreezeError("Malformed registry block: " + block)
    body = text.split(start, 1)[1].split(end, 1)[0]
    lines = [line.strip() for line in body.splitlines() if line.strip().startswith("|")]
    if not lines:
        return []
    if len(lines) < 2:
        raise FreezeError("Malformed registry table: " + block)
    headers = [s.strip() for s in lines[0].strip("|").split("|")]
    result = []
    for line in lines[2:]:
        cells = [s.strip().strip("`") for s in line.strip("|").split("|")]
        if len(cells) != len(headers):
            raise FreezeError("Malformed registry row: " + block)
        result.append(dict(zip(headers, ["" if s == "-" else s for s in cells], strict=True)))
    return result


def block_prefix(text, block):
    found = [p for p in PREFIXES if f"<!-- {p}:{block}:" in text]
    if len(found) > 1:
        raise FreezeError("Ambiguous registry block: " + block)
    return found[0] if found else "oppencouncil"


def read_table(text, block):
    return tables(text, block_prefix(text, block), block)


def write_table(text, block, headers, rows):
    prefix = block_prefix(text, block)
    # Parse first so a malformed existing table is never silently replaced.
    tables(text, prefix, block)
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        values = [str(row.get(key) or "-") for key in headers]
        if any("|" in v or "\n" in v or "\r" in v for v in values):
            raise FreezeError("Registry values must be single-line text without table separators")
        lines.append("| " + " | ".join(values) + " |")
    start, end = f"<!-- {prefix}:{block}:start -->", f"<!-- {prefix}:{block}:end -->"
    body = start + "\n" + "\n".join(lines) + "\n" + end
    if start in text:
        return text[: text.index(start)] + body + text[text.index(end) + len(end) :]
    return text.rstrip() + "\n\n" + body + "\n"


def relative_path(root, value, *, directory=False, required=False):
    if not isinstance(value, str) or not value or any(c in value for c in "\x00\n\r|:"):
        raise FreezeError("A plain project-relative path is required")
    path = tx.safe_destination(root, value + "/.path-check" if directory else value)
    path = path.parent if directory else path
    if required and not (path.is_dir() if directory else path.is_file()):
        raise FreezeError("Registered path does not exist: " + value)
    return path


def within(path, directory):
    p, d = PurePosixPath(path), PurePosixPath(directory)
    return p == d or d in p.parents


class Registry:
    def __init__(self, root, *, recover=True):
        self.project = Project(root, recover=recover)
        self.project.baseline_state()
        self.text = self.project.registry_bytes.decode("utf-8")
        self.metadata = copy.deepcopy(self.project.metadata)

    @property
    def root(self):
        return self.project.root

    def roles(self):
        result = {}
        for row in read_table(self.text, "roles"):
            role = ROLE_NAMES.get(row.get("Role", "").lower())
            if not role or role in result:
                raise FreezeError("Unknown or duplicate project role")
            value = row.get("Path") or row.get("Directory")
            relative_path(self.root, value, directory=True)
            result[role] = value
        defaults = {"audit": self.project.relative(self.project.control / "Audit")}
        if self.project.project_type == "research":
            defaults.update(
                scripts="Scripts", data="Data", results="Results", explore="Explore", releases="Releases"
            )
        return {**defaults, **result}

    def outputs(self):
        result = []
        details = self.metadata.get("output_details", {})
        if not isinstance(details, dict):
            raise FreezeError("Output details must be an object")
        for block in ("results", "deliverables"):
            for row in read_table(self.text, block):
                if set(row) != set(OUTPUT_HEADERS):
                    raise FreezeError("Invalid output registration columns")
                value = {key.lower(): row[key] for key in OUTPUT_HEADERS}
                if any(r["id"] == value["id"] for r in result):
                    raise FreezeError("Duplicate output ID")
                extra = details.get(value["id"], {})
                if set(extra) & set(value):
                    raise FreezeError("Output details cannot override registered fields")
                result.append({**value, **copy.deepcopy(extra), "registry_block": block})
        if set(details) - {r["id"] for r in result}:
            raise FreezeError("Output details reference unknown registrations")
        return result

    def legacy_output_ids(self):
        return set().union(
            *(
                self.metadata.get(key, {}).get("legacy_outputs_without_specification", [])
                for key in ("migration", "adoption")
            )
        )

    def set_output(self, value):
        records = self.outputs()
        old = next((r for r in records if r["id"] == value["id"]), None)
        block = (
            old["registry_block"]
            if old
            else ("results" if self.project.project_type == "research" else "deliverables")
        )
        rows = read_table(self.text, block)
        rows = [row for row in rows if row["ID"] != value["id"]]
        rows.append({key: value[key.lower()] for key in OUTPUT_HEADERS})
        self.text = write_table(self.text, block, OUTPUT_HEADERS, sorted(rows, key=lambda r: r["ID"]))
        self.metadata.setdefault("output_details", {})[value["id"]] = {
            key: copy.deepcopy(item)
            for key, item in value.items()
            if key not in {*[k.lower() for k in OUTPUT_HEADERS], "registry_block"}
        }

    def write(self):
        return {self.project.registry_name: replace_metadata(self.text, self.metadata).encode("utf-8")}

    def commit(self, *, writes=None, reads=None, verify=None, fault=None):
        return self.project.commit(
            {**(writes or {}), **self.write()},
            read_set={self.project.registry_name: tx.digest(self.project.registry_bytes), **(reads or {})},
            verify=verify,
            fault=fault,
        )


def stable_key(value, label="ID"):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{0,79}", value):
        raise FreezeError(label + " must be a stable lowercase key")
    return value
