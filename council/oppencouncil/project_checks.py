"""Shared mechanical project checks and bounded discovery, independent of layout."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path, PurePosixPath

from .memory import Memory
from .output_rules import IGNORED_AREAS, NUMBERED, known_area
from .outputs import Outputs, fingerprint, producer_error
from .project_registry import Registry, read_table, relative_path, stable_key, within
from .script_ops import analysis_scripts, inventory
from .store import FreezeError, FreezeStore
from .workstore import WorkStore


def index(root):
    registry = Registry(root)
    work = {"items": [], "total": 0, "next_offset": None, "inbox": [], "inbox_total": 0}
    if (registry.root / "Freeze").exists():
        work = WorkStore(FreezeStore(registry.root)).index(limit=200)
    return {
        "project": str(registry.root),
        "project_type": registry.project.project_type,
        "roles": registry.roles(),
        "canonical": read_table(registry.text, "canonical"),
        "outputs": registry.outputs(),
        "memory": Memory(root).index(),
        "work": work,
        "data": [
            {"path": path, "kind": value["kind"], "version": value["version"]}
            for path, value in sorted(registry.metadata.get("data", {}).items())
        ],
        "experiments": list(registry.metadata.get("experiments", {}).values()),
        "releases": registry.metadata.get("releases", []),
    }


class Checks:
    def __init__(self, root):
        self.registry = Registry(root)
        self.root = self.registry.root
        self.roles = self.registry.roles()
        self.research = self.registry.project.project_type == "research"
        self.errors, self.warnings, self.unknown = [], [], []
        self.owners = set()

    def error(self, path, reason):
        self.errors.append({"path": path, "reason": reason})

    def warning(self, path, reason):
        self.warnings.append({"path": path, "reason": reason})

    def canonical(self):
        topics, owners = set(), set()
        for row in read_table(self.registry.text, "canonical"):
            name = row.get("Canonical path")
            try:
                topic = stable_key(row.get("Topic"), "Canonical topic")
                path = relative_path(self.root, name, required=True)
                section = row.get("Section", "")
                council_owner = bool(re.fullmatch(r"Freeze/questions/F-[0-9]{6}\.json", name))
                # Preserved legacy topics can share one F. They are aliases of
                # the same formal source, not competing definition owners.
                if topic in topics or ((name, section) in owners and not council_owner):
                    raise FreezeError("Duplicate canonical topic or owner")
                topics.add(topic)
                owners.add((name, section))
                self.owners.add(name)
                verification = row.get("Verification") or row.get("Contract test")
                if not fingerprint(self.root, verification)["bytes"]:
                    raise FreezeError("Canonical verification must not be empty")
                self.owners.add(verification)
                if council_owner:
                    if section != "definition":
                        raise FreezeError("Council ownership must reference the definition scope")
                    question = FreezeStore(self.root).read_question(PurePosixPath(name).stem)
                    if row.get("Status") == "frozen" and not question["definition"]["current_version"]:
                        raise FreezeError("Frozen registration has no confirmed Council definition")
                elif section:
                    text = path.read_text(encoding="utf-8")
                    if len(re.findall(r"^#{1,6}\s+" + re.escape(section) + r"\s*$", text, re.M)) != 1:
                        raise FreezeError("Registered section must occur exactly once")
            except (FreezeError, OSError, ValueError, TypeError) as error:
                self.error(name, str(error))

    def council(self):
        if not (self.root / "Freeze").exists():
            return
        store = FreezeStore(self.root)
        store.snapshot()
        with store.locked():
            service = WorkStore(store)
            questions, groups, investigations = service.records()
            for path in store._manifest().get("evidence_paths", []):
                service.read_json(path)
            for question in questions.values():
                tests = question.get("verification_tests", [])
                if question["definition"]["current_version"] and not tests:
                    self.error(question["id"], "Confirmed definition requires a registered verification test")
                for item in tests:
                    path = item.get("path")
                    try:
                        if not fingerprint(self.root, path)["bytes"]:
                            raise FreezeError("Verification test must not be empty")
                        self.owners.add(path)
                    except (FreezeError, OSError, TypeError) as error:
                        self.error(question["id"], str(error))
            for record in [*questions.values(), *investigations.values()]:
                for blocker in record["work"]["blockers"]:
                    self.error(record["id"], "Unresolved work blocker: " + str(blocker))

    def scripts(self):
        if not self.research:
            return
        area = self.roles["scripts"]
        if not (self.root / area).exists():
            self.warning(area, "Analysis script area has not been created")
            return
        files, _ = inventory(self.root, area)
        candidates = analysis_scripts(files, area)
        legacy = set().union(
            *(
                self.registry.metadata.get(k, {}).get("legacy_unnumbered_scripts", [])
                for k in ("adoption", "migration")
            )
        )
        for name in candidates:
            filename = PurePosixPath(name).name
            if not NUMBERED.fullmatch(filename):
                message = "Analysis script needs a two-digit execution prefix"
                (self.warning if name in legacy else self.error)(name, message)
        # Shared functions are also part of the formal execution chain.
        explore = self.roles.get("explore", "Explore")
        pattern = re.compile(r"(?<![\w.-])" + re.escape(explore) + r"(?:[/\\]|[\"'])")
        for name in files:
            try:
                text = (self.root / name).read_text(encoding="utf-8")
            except UnicodeError:
                continue
            if pattern.search(text):
                self.error(name, "Formal scripts/functions reference Explore or its archive")

    def data(self):
        records = self.registry.metadata.get("data", {})
        if not isinstance(records, dict):
            raise FreezeError("Data registrations must be an object")
        area = self.roles.get("data")
        for name, value in records.items():
            try:
                if not area or name == area or not within(name, area) or value["path"] != name:
                    raise FreezeError("Data registration is outside its area or has a mismatched path")
                if value["kind"] not in {"raw", "derived"} or not value.get("version"):
                    raise FreezeError("Data requires classification and version")
                for kind in ("raw", "derived"):
                    if within(name, area + "/" + kind) and value["kind"] != kind:
                        raise FreezeError("Data classification conflicts with its directory")
                observed = fingerprint(self.root, name)
                if observed != {k: value[k] for k in ("sha256", "bytes")}:
                    raise FreezeError("Data changed since provenance registration")
                if value["kind"] == "raw":
                    if not value.get("source") or value.get("producer"):
                        raise FreezeError("Raw input needs its external source and no project producer")
                else:
                    relative_path(self.root, value["producer"], required=True)
                    if self.research and (reason := producer_error(value["producer"], self.roles)):
                        raise FreezeError(reason)
            except (FreezeError, OSError, KeyError, TypeError, ValueError) as error:
                self.error(name, str(error))
        if area and (self.root / area).exists():
            for current, dirs, files in os.walk(self.root / area, followlinks=False):
                dirs[:] = [d for d in dirs if d not in IGNORED_AREAS]
                for filename in files:
                    name = (Path(current) / filename).relative_to(self.root).as_posix()
                    if name not in records and filename != ".DS_Store":
                        self.warning(name, "Data origin/version requires classification before a release")

    def audit(self):
        from . import audits

        self.errors += audits.validate(self.root)["errors"]
        area = self.roles.get("audit")
        if not area or not (self.root / area).exists():
            return
        runs = self.root / area / "Runs"
        if runs.exists():
            for stage in runs.iterdir():
                if stage.name == ".DS_Store":
                    continue
                relative_path(
                    self.root, stage.relative_to(self.root).as_posix(), directory=True, required=True
                )
                if {p.name for p in stage.iterdir()} - {"current", ".DS_Store"}:
                    self.error(
                        stage.relative_to(self.root).as_posix(),
                        "Audit stage may contain only its current run",
                    )
        # v4 module/function audits are immutable historical evidence. New v5 audits
        # declare their schema explicitly and bind current source checksums.
        for name in ("Contracts", "Functions"):
            directory = self.root / area / name
            if not directory.exists():
                continue
            for path in directory.rglob("*"):
                if not path.is_file() or path.name == ".DS_Store":
                    continue
                relative = path.relative_to(self.root).as_posix()
                raw = fingerprint(self.root, relative)
                if not raw["bytes"]:
                    self.error(relative, "Audit record is empty")
                text = path.read_text(encoding="utf-8")
                if "oppencouncil_contract:" in text:
                    match = re.search(r"^source: (.+)$", text, re.M)
                    checksum = re.search(r"^source_sha256: (.+)$", text, re.M)
                    if not match or not checksum:
                        self.error(relative, "Current audit lacks source/hash metadata")
                    elif fingerprint(self.root, json.loads(match[1]))["sha256"] != json.loads(checksum[1]):
                        self.error(relative, "Current contract audit is stale for its source")

    def areas(self):
        if not self.research:
            return
        for current, dirs, files in os.walk(self.root, followlinks=False):
            dirs[:] = [
                d
                for d in dirs
                if d not in IGNORED_AREAS
                and not known_area((Path(current) / d).relative_to(self.root).as_posix(), self.roles.values())
            ]
            for filename in files:
                name = (Path(current) / filename).relative_to(self.root).as_posix()
                if name not in self.owners and not known_area(name, self.roles.values()):
                    self.unknown.append(name)
                    self.warning(name, "File is outside known project areas; classify its owner")

    def lifecycle(self):
        from . import explore, releases

        for service in (explore, releases):
            result = service.validate(self.root)
            self.errors += result["errors"]
            self.warnings += result["warnings"]

    def run(self):
        for name in ("canonical", "council", "scripts", "data", "audit", "areas", "lifecycle"):
            try:
                getattr(self, name)()
            except (FreezeError, OSError, ValueError, TypeError, KeyError) as error:
                self.error(name, str(error))
        try:
            Memory(self.root).index()
        except (FreezeError, OSError, ValueError, TypeError) as error:
            self.error("Memory", str(error))
        try:
            output = Outputs(self.root).check()
            self.errors += output["errors"]
            self.warnings += output["warnings"]
        except (FreezeError, OSError, ValueError, TypeError) as error:
            self.error("outputs", str(error))
        return {
            "state": "DAMAGED" if self.errors else "MANAGED_READY",
            "project": str(self.root),
            "project_type": self.registry.project.project_type,
            "errors": self.errors,
            "warnings": self.warnings,
            "unassigned_files": sorted(self.unknown),
        }


def validate(root):
    try:
        return Checks(root).run()
    except (FreezeError, OSError, ValueError, TypeError, KeyError) as error:
        return {"state": "DAMAGED", "errors": [{"path": "project", "reason": str(error)}], "warnings": []}
