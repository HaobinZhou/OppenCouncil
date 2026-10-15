"""One Memory implementation, with lossless readers for both legacy formats."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from . import project_transaction as tx
from .project import Project
from .store import FreezeError, require_text

ID = re.compile(r"M-(?:[0-9]{4}|[1-9][0-9]{4,})\Z")
TOPIC = re.compile(r"[a-z0-9][a-z0-9._-]{0,79}\Z")
FORMAT = "<!-- oppencouncil:memory:v5 -->"
META = (
    "id",
    "status",
    "title",
    "related_topics",
    "supersedes",
    "invalidates",
    "superseded_by",
    "invalidated_by",
)
LABELS = (
    "ID",
    "Status",
    "Title",
    "Related Topics",
    "Supersedes",
    "Invalidates",
    "Superseded By",
    "Invalidated By",
)
SECTIONS = ("Before", "Trigger", "Decision", "Why", "Rejected or Prior Approach", "Consequence")
FIELDS = ("before", "trigger", "decision", "why", "rejected_or_prior_approach", "consequence")
LEGACY_SECTIONS = (*SECTIONS[:3], "Scientific or Technical Rationale", "Basis", *SECTIONS[4:])
ARRAYS = META[3:]


def string_list(value, pattern, label):
    if not isinstance(value, list) or any(not isinstance(v, str) or not pattern.fullmatch(v) for v in value):
        raise FreezeError(label + " must be an array of valid IDs")
    if len(set(value)) != len(value):
        raise FreezeError(label + " contains duplicate IDs")
    return list(value)


def payload_text(value, label):
    text = require_text(value, label)
    if re.search(r"^#{1,6}\s+", text, re.MULTILINE):
        raise FreezeError(label + " cannot contain Markdown headings")
    return text


def normalize(payload, project_type):
    if not isinstance(payload, dict):
        raise FreezeError("Memory payload must be an object")
    required = {"title", *FIELDS} - {"why"}
    allowed = required | {"why", "scientific_or_technical_rationale", "basis", *ARRAYS[:3]}
    if required - payload.keys() or payload.keys() - allowed:
        raise FreezeError("Invalid Memory payload fields; IDs, status and reverse links are helper-managed")
    why = payload.get("why", payload.get("scientific_or_technical_rationale"))
    if "why" in payload and "scientific_or_technical_rationale" in payload:
        if payload["why"] != payload["scientific_or_technical_rationale"]:
            raise FreezeError("Conflicting rationale aliases")
    value = {key: payload_text(payload[key], key) for key in required}
    value["why"] = payload_text(why, "why")
    if "\n" in value["title"] or "\r" in value["title"]:
        raise FreezeError("Memory title must be one line")
    if project_type not in {"research", "general"}:
        raise FreezeError("A declared project type is required")
    if project_type == "research" or "basis" in payload:
        value["basis"] = payload_text(payload.get("basis"), "basis")
    for key in ARRAYS[:3]:
        value[key] = string_list(payload.get(key, []), TOPIC if key == "related_topics" else ID, key)
    if set(value["supersedes"]) & set(value["invalidates"]):
        raise FreezeError("The same ID cannot appear in supersedes and invalidates")
    return value


def section_values(text, names):
    matches = list(re.finditer(r"^## ([^\r\n]+)\r?$", text, re.MULTILINE))
    if tuple(m.group(1) for m in matches) != tuple(names):
        raise FreezeError("Memory has an invalid fixed section sequence")
    values, spans = {}, {}
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        raw = text[match.end() : end]
        value = raw.strip()
        if not value:
            raise FreezeError("Memory sections must not be empty")
        values[match.group(1)] = value
        start = match.end() + len(raw) - len(raw.lstrip())
        spans[match.group(1)] = (start, start + len(value))
    return values, spans


@dataclass
class Entry:
    path: str
    raw: bytes
    format: str
    metadata: dict
    values: dict
    spans: dict

    def view(self):
        return {**self.metadata, **self.values, "source_format": self.format, "source_path": self.path}

    def relationship(self, status, reverse, new_id):
        """Replace only two scalar spans; all unrelated bytes, including CRLF, survive."""
        text = self.raw.decode("utf-8")
        changes = {"status": status, reverse: [new_id]}
        replacements = []
        for key, value in changes.items():
            rendered = value if self.format == "stepwise" and isinstance(value, str) else json.dumps(value)
            start, end = self.spans[key]
            replacements.append((start, end, rendered))
        for start, end, value in sorted(replacements, reverse=True):
            text = text[:start] + value + text[end:]
        return text.encode("utf-8")


def parse(path, raw):
    try:
        text = raw.decode("utf-8")
        if text.startswith("---\n") or text.startswith("---\r\n"):
            end = re.search(r"^---\r?$", text[4:], re.MULTILINE)
            if end is None:
                raise FreezeError("Unclosed Memory frontmatter")
            # Find delimiters independently of LF/CRLF prefix length.
            separators = list(re.finditer(r"^---\r?$", text, re.MULTILINE))[:2]
            if len(separators) != 2:
                raise FreezeError("Unclosed Memory frontmatter")
            front = text[separators[0].end() : separators[1].start()]
            metadata, spans = {}, {}
            offset = separators[0].end()
            for match in re.finditer(r"^([a-z_]+):[ \t]*(.*?)\r?$", front, re.MULTILINE):
                key = match.group(1)
                if key in metadata:
                    raise FreezeError("Duplicate Memory metadata field")
                metadata[key] = json.loads(match.group(2))
                spans[key] = (offset + match.start(2), offset + match.end(2))
            if tuple(metadata) != META or len(front.strip().splitlines()) != len(META):
                raise FreezeError("Invalid Memory frontmatter schema")
            body = text[separators[1].end() :].lstrip("\r\n")
            format_name = (
                "v5" if body.startswith(FORMAT + "\n") or body.startswith(FORMAT + "\r\n") else "steward"
            )
            if format_name == "v5":
                body = body[len(FORMAT) :].lstrip("\r\n")
            heading = f"# Decision Memory {metadata['id']}: {metadata['title']}"
            if body.splitlines()[0] != heading:
                raise FreezeError("Invalid Memory heading")
            has_basis = bool(re.search(r"^## Basis\r?$", body, re.MULTILINE))
            names = (*SECTIONS[:4], "Basis", *SECTIONS[4:]) if has_basis and format_name == "v5" else SECTIONS
            sections, _ = section_values(body, names)
            values = {key: sections[label] for key, label in zip(FIELDS, SECTIONS, strict=True)}
            if has_basis:
                values["basis"] = sections["Basis"]
        else:
            sections, all_spans = section_values(text, (*LABELS, *LEGACY_SECTIONS))
            first_heading = text.find("## ID")
            if text[:first_heading].strip() or len(re.findall(r"^#{1,6}\s+", text, re.MULTILINE)) != len(
                sections
            ):
                raise FreezeError("Invalid legacy Stepwise fixed fields")
            metadata = {key: sections[label] for key, label in zip(META, LABELS, strict=True)}
            for key in ARRAYS:
                metadata[key] = json.loads(metadata[key])
            spans = {key: all_spans[label] for key, label in zip(META, LABELS, strict=True)}
            values = {
                key: sections[label]
                for key, label in zip(FIELDS, (*SECTIONS[:3], LEGACY_SECTIONS[3], *SECTIONS[4:]), strict=True)
            }
            values["basis"] = sections["Basis"]
            format_name = "stepwise"
        identifier = metadata["id"]
        if not isinstance(identifier, str) or not ID.fullmatch(identifier) or int(identifier[2:]) == 0:
            raise FreezeError("Invalid Memory ID")
        if path.split("/")[-1] != identifier + ".md":
            raise FreezeError("Memory filename and ID disagree")
        if metadata["status"] not in {"active", "superseded", "invalidated"}:
            raise FreezeError("Invalid Memory status")
        if not isinstance(metadata["title"], str) or not metadata["title"].strip():
            raise FreezeError("Memory title must be nonempty text")
        for key in ARRAYS:
            string_list(metadata[key], TOPIC if key == "related_topics" else ID, key)
        # Historical writers had no length cap; Steward also allowed headings
        # other than its level-two section delimiters. Do not reject valid history
        # because the new-entry payload is intentionally narrower.
        if format_name == "v5":
            for key, value in values.items():
                payload_text(value, key)
        return Entry(path, raw, format_name, metadata, values, spans)
    except (UnicodeError, ValueError, KeyError, IndexError, TypeError) as exc:
        raise FreezeError("Invalid Memory record " + path + ": " + str(exc)) from exc


def render(identifier, payload):
    meta = {"id": identifier, "status": "active", "title": payload["title"]}
    for key in ARRAYS:
        meta[key] = payload.get(key, [])
    lines = [
        "---",
        *(f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in meta.items()),
        "---",
        "",
        FORMAT,
        "",
    ]
    lines += [f"# Decision Memory {identifier}: {payload['title']}", ""]
    for key, label in zip(FIELDS, SECTIONS, strict=True):
        lines += [f"## {label}", "", payload[key], ""]
        if key == "why" and "basis" in payload:
            lines += ["## Basis", "", payload["basis"], ""]
    return "\n".join(lines).encode("utf-8")


def validate_relationships(entries):
    by_id = {entry.metadata["id"]: entry for entry in entries}
    if len(by_id) != len(entries):
        raise FreezeError("Duplicate Memory IDs")
    for identifier, entry in by_id.items():
        meta = entry.metadata
        if set(meta["supersedes"]) & set(meta["invalidates"]):
            raise FreezeError("Memory relationship arrays overlap")
        for forward, reverse, status in (
            ("supersedes", "superseded_by", "superseded"),
            ("invalidates", "invalidated_by", "invalidated"),
        ):
            for target in meta[forward]:
                if target not in by_id or int(target[2:]) >= int(identifier[2:]):
                    raise FreezeError("Memory relationship must target an earlier existing ID")
                prior = by_id[target].metadata
                if prior["status"] != status or prior[reverse] != [identifier]:
                    raise FreezeError("Memory relationship status or reverse link disagrees")
            for source in meta[reverse]:
                if source not in by_id or identifier not in by_id[source].metadata[forward]:
                    raise FreezeError("Memory reverse link has no matching relationship")
        expected = (
            "superseded" if meta["superseded_by"] else "invalidated" if meta["invalidated_by"] else "active"
        )
        if meta["status"] != expected or (meta["superseded_by"] and meta["invalidated_by"]):
            raise FreezeError("Memory status does not match reverse links")
    return by_id


class Memory:
    def __init__(self, root):
        self.project = Project(root)

    def entries(self):
        directory = self.project.memory
        tx.safe_destination(self.project.root, self.project.relative(directory / "entries/.path-check"))
        if not directory.exists():
            return []
        if {p.name for p in directory.iterdir()} - {"entries", "index.md", ".DS_Store"}:
            raise FreezeError("Memory must use its fixed entries/index topology")
        entries = []
        for path in sorted((directory / "entries").iterdir()):
            if path.name == ".DS_Store":
                continue
            name = self.project.relative(path)
            raw = tx.read_bytes(tx.safe_destination(self.project.root, name))
            entries.append(parse(name, raw))
        validate_relationships(entries)
        return entries

    def index(self):
        self.project.baseline_state()
        return [
            {key: entry.view()[key] for key in ("id", "status", "title", "related_topics", "source_path")}
            for entry in self.entries()
        ]

    def read(self, identifier):
        self.project.baseline_state()
        for entry in self.entries():
            if entry.metadata["id"] == identifier:
                return entry.view()
        raise FreezeError("Memory ID does not exist")

    def add(self, payload, *, fault=None):
        value = normalize(payload, self.project.project_type)
        self.project.baseline_state()
        unknown = set(value["related_topics"]) - self.project.canonical_topics()
        if unknown:
            raise FreezeError("Memory references unregistered related topics: " + ", ".join(sorted(unknown)))
        entries = self.entries()
        by_id = {entry.metadata["id"]: entry for entry in entries}
        for target in (*value["supersedes"], *value["invalidates"]):
            if target not in by_id or by_id[target].metadata["status"] != "active":
                raise FreezeError("Memory relationship targets must exist and be active: " + target)
        index_path = self.project.memory / "index.md"
        index_raw = tx.read_bytes(index_path)
        high_water = max((int(i[2:]) for i in by_id), default=0)
        if index_raw:
            marks = re.findall(
                rb"<!-- (?:oppen-project-steward|oppencouncil):memory-high-water:([0-9]+) -->", index_raw
            )
            if len(marks) > 1:
                raise FreezeError("Ambiguous Memory high-water marker")
            if marks:
                high_water = max(high_water, int(marks[0]))
        identifier = f"M-{high_water + 1:04d}"
        path = self.project.relative(self.project.memory / "entries" / (identifier + ".md"))
        writes = {path: render(identifier, value)}
        for forward, status, reverse in (
            ("supersedes", "superseded", "superseded_by"),
            ("invalidates", "invalidated", "invalidated_by"),
        ):
            for target in value[forward]:
                entry = by_id[target]
                writes[entry.path] = entry.relationship(status, reverse, identifier)
        final_entries = [parse(e.path, writes.get(e.path, e.raw)) for e in entries] + [
            parse(path, writes[path])
        ]
        validate_relationships(final_entries)
        lines = [
            "# Decision Memory",
            "",
            f"<!-- oppencouncil:memory-high-water:{high_water + 1:04d} -->",
            "",
            "| ID | Title | Status | Related topics | Path |",
            "| --- | --- | --- | --- | --- |",
        ]
        for entry in sorted(final_entries, key=lambda e: int(e.metadata["id"][2:])):
            meta = entry.metadata
            title = meta["title"].replace("|", "&#124;")
            lines.append(
                f"| {meta['id']} | {title} | {meta['status']} | {', '.join(meta['related_topics'])} "
                f"| entries/{meta['id']}.md |"
            )
        writes[self.project.relative(index_path)] = ("\n".join(lines) + "\n").encode("utf-8")
        reads = {entry.path: tx.digest(entry.raw) for entry in entries}
        reads[self.project.relative(index_path)] = tx.digest(index_raw)
        reads[self.project.registry_name] = tx.digest(self.project.registry_bytes)

        def verify():
            # Reuse the already-open project: calling the constructor would recover
            # this still-uncommitted transaction while its lock is held.
            validate_relationships(self.entries())

        result = self.project.commit(writes, read_set=reads, verify=verify, fault=fault)
        return {**result, "id": identifier, "path": path}
