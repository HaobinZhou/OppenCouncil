"""Explicit, exact-plan script renumbering and analysis-directory relocation."""

from __future__ import annotations

import copy
import json
import os
import posixpath
import re
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from . import project_transaction as tx
from .decisions import JOURNAL
from .output_rules import IGNORED_AREAS, NUMBERED, SCRIPT_SUFFIXES
from .project import Project, json_bytes, unique_object
from .project_registry import Registry, read_table, relative_path, within, write_table
from .store import FreezeError, FreezeStore, now

SHARED = {"functions", "config", "configuration", "shared"}
LANGUAGES = SCRIPT_SUFFIXES | {".js", ".ts", ".ps1", ".bat", ".cmd", ".rmd", ".qmd", ".c", ".cpp", ".pl"}


def inventory(root, directory):
    base = relative_path(root, directory, directory=True, required=True)
    files, directories = [], [directory]
    for current, children, names in os.walk(base, followlinks=False):
        for name in children + names:
            path = Path(current) / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                raise FreezeError("Script operations cannot move linked paths: " + relative)
            if path.is_dir():
                directories.append(relative)
            else:
                relative_path(root, relative, required=True)
                files.append(relative)
    return sorted(files), sorted(directories)


def analysis_scripts(files, area):
    return [
        name
        for name in files
        if not set(PurePosixPath(name).relative_to(area).parts[:-1]) & SHARED
        and (NUMBERED.fullmatch(PurePosixPath(name).name) or PurePosixPath(name).suffix.lower() in LANGUAGES)
    ]


def rewrite_text(text, name, destination, mapping, root, directory_move=None):
    """Replace literal path references once; never cascade across a numbering permutation."""
    pairs = {}
    directory_keys = set()
    for old, new in mapping.items():
        pairs[old] = new
        pairs[str(root / old)] = str(root / new)
        before = posixpath.relpath(old, str(PurePosixPath(name).parent))
        after = posixpath.relpath(new, str(PurePosixPath(destination).parent))
        if before != after:
            pairs[before] = after
    if directory_move:
        old, new = directory_move
        pairs[old] = new
        pairs[str(root / old)] = str(root / new)
        directory_keys.update((old, str(root / old)))
    pairs = {a: b for a, b in pairs.items() if a != b}
    if not pairs:
        return text
    # Forward and Windows separators are recognized in literal code/config paths.
    for old, new in list(pairs.items()):
        pairs[old.replace("/", "\\")] = new.replace("/", "\\")
        pairs[old.replace("/", "\\\\")] = new.replace("/", "\\\\")
        if old in directory_keys:
            directory_keys.update((old.replace("/", "\\"), old.replace("/", "\\\\")))
    patterns = []
    for path in sorted(pairs, key=len, reverse=True):
        escaped = re.escape(path)
        if path in directory_keys:
            patterns += [r"(?<=[\"'])" + escaped + r"(?=[\"'])", r"(?<![\w.\-])" + escaped + r"(?=[/\\])"]
        else:
            patterns.append(r"(?<![\w.\-])" + escaped + r"(?![\w.\-])")
    pattern = "|".join(patterns)
    return re.sub(pattern, lambda match: pairs[match[0]], text)


def rewrite_paths(value, mapping, directory_move):
    """Update structured current path fields, not descriptions or historical prose."""

    def path(name):
        if not isinstance(name, str):
            return name
        if name in mapping:
            return mapping[name]
        if directory_move and within(name, directory_move[0]):
            return directory_move[1] + name[len(directory_move[0]) :]
        return name

    result = copy.deepcopy(value)
    for key in ("producer", "verification", "path", "source_path"):
        if key in result:
            result[key] = path(result[key])
    if isinstance(result.get("generation"), dict):
        result["generation"] = rewrite_paths(result["generation"], mapping, directory_move)
    if isinstance(result.get("inputs"), dict):
        # Input hashes refer to the generation which produced the artifact; moving a
        # path does not claim that changed producer code was rerun.
        result["inputs"] = {path(key): item for key, item in result["inputs"].items()}
    return result


@dataclass
class Plan:
    report: dict
    writes: dict

    def public(self):
        return copy.deepcopy(self.report)


class Planner:
    def __init__(self, root):
        self.root = Path(root).expanduser().resolve(strict=True)
        if (self.root / tx.STAGING).exists() or (self.root / tx.STAGING).is_symlink():
            raise FreezeError("Recover the interrupted transaction before checking script changes")
        if (self.root / "Freeze" / JOURNAL).exists():
            raise FreezeError("Recover the pending Council transaction before checking script changes")
        self.registry = Registry(self.root, recover=False)
        if self.registry.project.project_type != "research":
            raise FreezeError("Analysis script numbering applies to research projects")
        self.reads = {}

    def read(self, name):
        raw = tx.read_bytes(tx.safe_destination(self.root, name))
        checksum = tx.digest(raw)
        if name in self.reads and self.reads[name] != checksum:
            raise FreezeError("Project input changed while planning: " + name)
        self.reads[name] = checksum
        return raw

    def reference_files(self, area):
        roles = self.registry.roles()
        excluded = {v for k, v in roles.items() if k not in {"scripts", "source", "explore"}}
        excluded |= {"Freeze", "Memory", "Attention", "Audit", "Releases", ".oppen-project-steward"}
        excluded.add(roles.get("explore", "Explore") + "/_archive")
        result = []
        for current, directories, names in os.walk(self.root, followlinks=False):
            directories[:] = [
                d
                for d in sorted(directories)
                if d not in IGNORED_AREAS
                and not (Path(current) / d).is_symlink()
                and (Path(current) / d).relative_to(self.root).as_posix() not in excluded
            ]
            for child in sorted(names):
                path = Path(current) / child
                name = path.relative_to(self.root).as_posix()
                if path.is_symlink() or name == self.registry.project.registry_name or child.startswith("."):
                    continue
                # Avoid scanning data/binary artifacts outside their expected roles.
                if (
                    path.suffix.lower()
                    in LANGUAGES | {".md", ".toml", ".json", ".yml", ".yaml", ".ini", ".cfg"}
                    or child == "Makefile"
                ):
                    result.append(name)
        return sorted(result)

    def plan(self, operation, payload, *, created_at=None):
        if not isinstance(payload, dict):
            raise FreezeError("Script operation input must be an object")
        area = self.registry.roles().get("scripts")
        if not area:
            raise FreezeError("Project has no scripts role")
        files, directories = inventory(self.root, area)
        candidates = analysis_scripts(files, area)
        directory_move, remove_dirs, create_dirs, directory_modes = None, [], [], {}
        if operation == "renumber":
            if set(payload) - {"order", "start", "step"}:
                raise FreezeError("Unknown renumber fields")
            order = payload.get("order")
            if (
                not isinstance(order, list)
                or not all(isinstance(p, str) for p in order)
                or len(set(order)) != len(order)
            ):
                raise FreezeError("Provide a unique ordered list of analysis script paths")
            # Explicit order can name an additional language; shared files remain exempt.
            if not set(candidates) <= set(order) or not set(order) <= set(files):
                raise FreezeError("Order must contain all analysis scripts, and only existing script files")
            if any(set(PurePosixPath(p).relative_to(area).parts[:-1]) & SHARED for p in order):
                raise FreezeError("Shared function/configuration files must not be numbered")
            start, step = payload.get("start", 1), payload.get("step", 1)
            if (
                type(start) is not int
                or type(step) is not int
                or start < 0
                or step < 1
                or start + (len(order) - 1) * step > 99
            ):
                raise FreezeError("Script numbers must fit two digits with a positive interval")
            mapping = {}
            for index, name in enumerate(order):
                path = PurePosixPath(name)
                stem = re.sub(r"^[0-9]{2}[_-]", "", path.name)
                new = str(path.with_name(f"{start + index * step:02d}_" + stem))
                if not NUMBERED.fullmatch(PurePosixPath(new).name):
                    raise FreezeError("Numbered analysis scripts require a filename extension")
                if name != new:
                    mapping[name] = new
        elif operation == "rename-directory":
            if set(payload) != {"to"}:
                raise FreezeError("Directory rename requires only the new 'to' path")
            destination = payload["to"]
            target = relative_path(self.root, destination, directory=True)
            if destination == area:
                mapping = {}
            else:
                if target.exists() or within(destination, area) or within(area, destination):
                    raise FreezeError(
                        "New scripts directory must be absent and separate from the current area"
                    )
                if any(
                    within(destination, p) or within(p, destination)
                    for k, p in self.registry.roles().items()
                    if k != "scripts"
                ):
                    raise FreezeError("New scripts directory overlaps another project role")
                directory_move = area, destination
                mapping = {name: destination + name[len(area) :] for name in files}
                remove_dirs = directories
                create_dirs = [destination + name[len(area) :] for name in directories]
                directory_modes = {
                    destination + name[len(area) :]: stat.S_IMODE((self.root / name).stat().st_mode)
                    for name in directories
                }
        else:
            raise FreezeError("Unknown script operation")
        destinations = list(mapping.values())
        if len({p.casefold() for p in destinations}) != len(destinations):
            raise FreezeError("Script destinations must be unique across supported filesystems")
        remaining = {p.casefold() for p in files if p not in mapping}
        if remaining & {p.casefold() for p in destinations}:
            raise FreezeError("Script destination conflicts with an existing file, ignoring case")
        for name in destinations:
            if name not in mapping and self.read(name) is not None:
                raise FreezeError("Script destination is already occupied: " + name)
        created_at = created_at or now()
        writes, modes = {}, {}
        source_bytes = {name: self.read(name) for name in files}
        for name in mapping:
            writes[name] = None
        for name, destination in mapping.items():
            writes[destination] = source_bytes[name]
            modes[destination] = stat.S_IMODE((self.root / name).stat().st_mode)
        for name in self.reference_files(area):
            raw = self.read(name)
            try:
                text = raw.decode("utf-8")
            except UnicodeError:
                continue
            destination = mapping.get(name, name)
            revised = rewrite_text(text, name, destination, mapping, self.root, directory_move)
            if revised != text:
                writes[destination] = revised.encode("utf-8")
        # Registry tables keep their existing shape and legacy prefix.
        for block, fields in {
            "canonical": {"Canonical path", "Verification", "Contract test"},
            "results": {"Path", "Producer"},
            "deliverables": {"Path", "Producer"},
        }.items():
            rows = read_table(self.registry.text, block)
            changed = False
            for row in rows:
                for key in fields & row.keys():
                    original = row[key]
                    row[key] = rewrite_paths({"path": original}, mapping, directory_move)["path"]
                    changed |= row[key] != original
            if changed:
                self.registry.text = write_table(self.registry.text, block, tuple(rows[0]), rows)
        if directory_move:
            rows = read_table(self.registry.text, "roles")
            found = False
            for row in rows:
                if row["Role"].lower() in {"r", "scripts"}:
                    row["Path" if "Path" in row else "Directory"] = directory_move[1]
                    found = True
            if not found:
                headers = tuple(rows[0]) if rows else ("Role", "Path")
                row = {h: "" for h in headers}
                row.update(Role="Scripts")
                row["Path" if "Path" in headers else "Directory"] = directory_move[1]
                rows.append(row)
            self.registry.text = write_table(self.registry.text, "roles", tuple(rows[0]), rows)
        for key in ("output_details", "data"):
            if key in self.registry.metadata:
                self.registry.metadata[key] = {
                    k: rewrite_paths(v, mapping, directory_move)
                    for k, v in self.registry.metadata[key].items()
                }
        for key in ("adoption", "migration"):
            legacy = self.registry.metadata.get(key, {})
            if "legacy_unnumbered_scripts" in legacy:
                legacy["legacy_unnumbered_scripts"] = [
                    revised
                    for name in legacy["legacy_unnumbered_scripts"]
                    if not NUMBERED.fullmatch(PurePosixPath(revised := mapping.get(name, name)).name)
                ]
        # Only live verification paths change. Formal text, versions, evidence,
        # discussion, Memory and old audit records retain their original bytes/content.
        manifest_path = "Freeze/manifest.json"
        manifest_raw = self.read(manifest_path)
        if manifest_raw:
            manifest = json.loads(manifest_raw, object_pairs_hook=unique_object)
            changed_questions = False
            for qid in manifest["question_ids"]:
                name = f"Freeze/questions/{qid}.json"
                question = json.loads(self.read(name), object_pairs_hook=unique_object)
                old = question.get("verification_tests", [])
                updated = [rewrite_paths(item, mapping, directory_move) for item in old]
                if old != updated:
                    question["verification_tests"] = updated
                    question["revision"] += 1
                    writes[name] = json_bytes(question)
                    changed_questions = True
            if changed_questions:
                manifest["revision"] += 1
                writes[manifest_path] = json_bytes(manifest)
        registry_path = self.registry.project.registry_name
        if self.read(registry_path) != self.registry.project.registry_bytes:
            raise FreezeError("Project registry changed while planning")
        operation_id = tx.digest(
            json_bytes({"operation": operation, "input": payload, "at": created_at, "reads": self.reads})
        )
        if mapping or directory_move:
            self.registry.metadata.setdefault("script_operations", []).append(
                {
                    "id": operation_id,
                    "operation": operation,
                    "input": payload,
                    "at": created_at,
                    "by": "codex",
                    "paths": mapping,
                    "directory": directory_move,
                }
            )
            writes.update(self.registry.write())
            writes, expected, managed_reads = self.registry.project.prepare_writes(writes)
            if any(name in self.reads and self.reads[name] != value for name, value in managed_reads.items()):
                raise FreezeError("Managed project inputs changed while planning")
            self.reads.update(managed_reads)
        else:
            writes, expected = {}, {}
        report = {
            "schema_version": 1,
            "root": str(self.root),
            "operation": operation,
            "input": payload,
            "created_at": created_at,
            "operation_id": operation_id,
            "mapping": mapping,
            "read_set": self.reads,
            "write_set": {p: {"before": expected[p], "after": tx.digest(raw)} for p, raw in writes.items()},
            "modes": modes,
            "directory_modes": directory_modes,
            "create_directories": create_dirs,
            "remove_directories": remove_dirs,
            "reference_files_changed": [
                p for p, raw in writes.items() if raw is not None and p not in destinations
            ],
            "review_note": "Literal references are updated; inspect dynamic path construction before apply.",
        }
        report["plan_sha256"] = tx.digest(json_bytes(report))
        return Plan(report, writes)


def check(root, operation, payload):
    return Planner(root).plan(operation, payload)


def apply(root, saved, *, fault=None):
    root = Path(root).expanduser().resolve(strict=True)
    if not isinstance(saved, dict) or saved.get("root") != str(root):
        raise FreezeError("Script plan belongs to a different project")
    if tx.digest(json_bytes({k: v for k, v in saved.items() if k != "plan_sha256"})) != saved.get(
        "plan_sha256"
    ):
        raise FreezeError("Script plan checksum does not match its contents")
    with tx.project_lock(root):
        tx.recover_locked(root)
        project = Project(root, recover=False)
        project.baseline_state()
        for record in project.metadata.get("script_operations", []):
            if record["id"] == saved["operation_id"]:
                if record["operation"] != saved["operation"] or record["input"] != saved["input"]:
                    raise FreezeError("Script plan identity does not match the completed operation")
                return {"changed_paths": [], "replayed": True}
        planned = Planner(root).plan(saved["operation"], saved["input"], created_at=saved["created_at"])
        if planned.report != saved:
            raise FreezeError("Script plan or project inputs changed; run --check again")
        if not planned.writes:
            return {"changed_paths": []}

        def verify():
            Project(root, recover=False).baseline_state()
            if (root / "Freeze/manifest.json").exists():
                FreezeStore(root, recover_project=False).snapshot()

        return tx.apply(
            root,
            planned.writes,
            expected={p: item["before"] for p, item in saved["write_set"].items()},
            read_set=saved["read_set"],
            modes=saved["modes"],
            directory_modes=saved["directory_modes"],
            create_directories=saved["create_directories"],
            remove_directories=saved["remove_directories"],
            verify=verify,
            fault=fault,
        )
