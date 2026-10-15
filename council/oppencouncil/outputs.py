"""Shared output/data registrations; research specifications stay in Council."""

from __future__ import annotations

import copy
import hashlib
import os
from pathlib import PurePosixPath

from .output_rules import NUMBERED, RESULT_KINDS, artifact_error
from .project_registry import Registry, relative_path, stable_key, within
from .store import FreezeError, FreezeStore, ordinary_file_info, require_text


def fingerprint(root, name):
    path = relative_path(root, name, required=True)
    info = ordinary_file_info(path, path.stat().st_size)
    if info is None:
        raise FreezeError("Project file disappeared: " + name)
    checksum = hashlib.sha256()
    with path.open("rb") as handle:
        opened = os.fstat(handle.fileno())
        if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
            raise FreezeError("Project file changed while opening: " + name)
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            checksum.update(chunk)
        after = os.fstat(handle.fileno())
    final = ordinary_file_info(path, max(info.st_size, after.st_size))

    def identity(value):
        return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns

    if final is None or identity(info) != identity(after) or identity(info) != identity(final):
        raise FreezeError("Project file changed while reading: " + name)
    return {"sha256": checksum.hexdigest(), "bytes": info.st_size}


def members(root, name, kind):
    path = relative_path(root, name, directory=kind == "group", required=True)
    if kind != "group":
        return [name]
    result = []
    for directory, dirs, files in os.walk(path, followlinks=False):
        for child in dirs + files:
            if (path.__class__(directory) / child).is_symlink():
                raise FreezeError("Output groups must not contain links")
        for child in files:
            result.append((path.__class__(directory) / child).relative_to(root).as_posix())
    if not result:
        raise FreezeError("Output group must contain at least one artifact")
    return sorted(result)


def producer_error(path, roles):
    scripts = roles.get("scripts")
    if not scripts or not within(path, scripts) or path == scripts:
        return "Research producer must belong to the registered scripts area"
    relative = PurePosixPath(path).relative_to(scripts)
    if "functions" in relative.parts[:-1] or not NUMBERED.fullmatch(relative.name):
        return "Research producer must be a numbered analysis script, in any language"
    return None


class Outputs:
    def __init__(self, root):
        self.registry = Registry(root)
        self.roles = self.registry.roles()
        self.root = self.registry.root
        self.research = self.registry.project.project_type == "research"

    def specification(self, value, reads):
        if not isinstance(value, dict) or set(value) != {"question_id", "version", "text_sha256"}:
            raise FreezeError("Each research artifact requires its exact confirmed specification")
        store = FreezeStore(self.root)
        with store.locked():
            question = store._question(value["question_id"])
            definition = question["definition"]
            current = next(
                (v for v in definition["versions"] if v["number"] == definition["current_version"]), None
            )
            if question.get("problem_type") != "output_specification" or current is None:
                raise FreezeError("Output specification must be a human-confirmed output F")
            if (
                type(value["version"]) is not int
                or value["version"] != current["number"]
                or value["text_sha256"] != current["text_sha256"]
            ):
                raise FreezeError("Output specification changed; use the current confirmed version")
            path = f"Freeze/questions/{question['id']}.json"
            reads[path] = fingerprint(self.root, path)["sha256"]
            return copy.deepcopy(value)

    def register(self, payload, *, replace=False, fault=None):
        if not isinstance(payload, dict):
            raise FreezeError("Output payload must be an object")
        required = {"id", "path", "kind", "audience", "producer"}
        allowed = required | {"specification", "member_specifications", "generation", "structure_changed"}
        if not required <= set(payload) or set(payload) - allowed:
            raise FreezeError("Output payload has missing or unknown fields")
        value = copy.deepcopy(payload)
        relative_path(self.root, value["path"], directory=value["kind"] == "group", required=True)
        stable_key(value["id"], "Output ID")
        for field in ("kind", "audience"):
            require_text(value[field], field, 200)
        if self.research and (
            value["kind"] not in {*RESULT_KINDS, "group"}
            or value["audience"] not in {"publication", "formal-review"}
        ):
            raise FreezeError("Research outputs must be publication/formal-review tables, figures or reports")
        area = self.roles.get("results" if self.research else "deliverables")
        if not area or value["path"] == area or not within(value["path"], area):
            raise FreezeError("Output must belong to its registered Results/Deliverables area")
        existing = self.registry.outputs()
        previous = next((r for r in existing if r["id"] == value["id"]), None)
        if previous and previous["path"] != value["path"] and not replace:
            raise FreezeError("Output ID already owns a different path; explicit replacement required")
        for other in existing:
            if other["id"] != value["id"] and (
                within(other["path"], value["path"]) or within(value["path"], other["path"])
            ):
                raise FreezeError("Output ownership overlaps another registration")
        paths = members(self.root, value["path"], value["kind"])
        reads = {}
        for name in paths:
            if reason := artifact_error(
                PurePosixPath(name).relative_to(area), value["kind"], research=self.research
            ):
                raise FreezeError(name + ": " + reason)
            reads[name] = fingerprint(self.root, name)["sha256"]
        relative_path(self.root, value["producer"], required=True)
        reads[value["producer"]] = fingerprint(self.root, value["producer"])["sha256"]
        legacy = previous and value["id"] in self.registry.legacy_output_ids()
        unspecified_legacy = (
            legacy and not value.get("specification") and not value.get("member_specifications")
        )
        if unspecified_legacy:
            if value.pop("structure_changed", False):
                raise FreezeError("Legacy output structure changes require a confirmed specification")
            if any(value[k] != previous[k] for k in required):
                raise FreezeError(
                    "Legacy outputs may regenerate unchanged; registration changes require a specification"
                )
        elif self.research:
            if reason := producer_error(value["producer"], self.roles):
                raise FreezeError(reason)
            value.pop("structure_changed", None)
            if value["kind"] == "group":
                specs = value.get("member_specifications")
                if not isinstance(specs, dict) or set(specs) != set(paths) or value.get("specification"):
                    raise FreezeError("Every output group member requires its own specification")
                for name, spec in specs.items():
                    specs[name] = self.specification(spec, reads)
            else:
                if value.get("member_specifications"):
                    raise FreezeError("Only groups use member specifications")
                value["specification"] = self.specification(value.get("specification"), reads)
        else:
            value.pop("structure_changed", None)
        generation = value.get("generation")
        if generation is not None:
            if not isinstance(generation, dict) or set(generation) - {
                "inputs",
                "environment",
                "seed",
                "verification",
            }:
                raise FreezeError("Invalid generation provenance")
            if not isinstance(generation.get("inputs", {}), dict):
                raise FreezeError("Generation inputs must map paths to SHA-256 checksums")
            for name, checksum in generation.get("inputs", {}).items():
                if fingerprint(self.root, name)["sha256"] != checksum:
                    raise FreezeError("Generation input changed: " + name)
                reads[name] = checksum
            if generation.get("verification"):
                path = generation["verification"]
                reads[path] = fingerprint(self.root, path)["sha256"]
        if previous and {k: v for k, v in previous.items() if k != "registry_block"} == value:
            return {
                "changed_paths": [],
                "output": value,
                "legacy_without_specification": bool(unspecified_legacy),
            }
        self.registry.set_output(value)

        def verify_members():
            if members(self.root, value["path"], value["kind"]) != paths:
                raise FreezeError("Output membership changed during registration")

        result = self.registry.commit(reads=reads, verify=verify_members, fault=fault)
        return {**result, "output": value, "legacy_without_specification": bool(unspecified_legacy)}

    def register_data(self, payload):
        if not isinstance(payload, dict) or set(payload) - {"path", "kind", "source", "version", "producer"}:
            raise FreezeError("Invalid data registration fields")
        name, kind = payload.get("path"), payload.get("kind")
        relative_path(self.root, name, required=True)
        if kind not in {"raw", "derived"}:
            raise FreezeError("Data kind must be raw or derived")
        data = self.roles.get("data")
        if not data or not within(name, data) or name == data:
            raise FreezeError("Data must be inside the registered Data area")
        if (
            within(name, data + "/raw")
            and kind != "raw"
            or within(name, data + "/derived")
            and kind != "derived"
        ):
            raise FreezeError("Data classification conflicts with its directory")
        value = copy.deepcopy(payload)
        value.update(fingerprint(self.root, name))
        reads = {name: value["sha256"]}
        require_text(value.get("version"), "data version", 500)
        if kind == "raw":
            require_text(value.get("source"), "raw input source", 5000)
            if value.get("producer"):
                raise FreezeError("Raw inputs are not produced by this project")
        else:
            producer = value.get("producer")
            relative_path(self.root, producer, required=True)
            if self.research and (reason := producer_error(producer, self.roles)):
                raise FreezeError(reason)
            reads[producer] = fingerprint(self.root, producer)["sha256"]
        records = self.registry.metadata.setdefault("data", {})
        if records.get(name) == value:
            return {"changed_paths": [], "data": value}
        records[name] = value
        return {**self.registry.commit(reads=reads), "data": value}

    def check(self):
        errors, warnings = [], []
        registered = set()
        legacy = self.registry.legacy_output_ids()
        area = self.roles.get("results" if self.research else "deliverables")
        for value in self.registry.outputs():
            try:
                if not area or value["path"] == area or not within(value["path"], area):
                    raise FreezeError("Output is outside its registered area")
                paths = members(self.root, value["path"], value["kind"])
                registered.update(paths)
                for name in paths:
                    if reason := artifact_error(
                        PurePosixPath(name).relative_to(area), value["kind"], research=self.research
                    ):
                        errors.append({"path": name, "reason": reason})
                relative_path(self.root, value["producer"], required=True)
                unspecified = not value.get("specification") and not value.get("member_specifications")
                if self.research and value["id"] in legacy and unspecified:
                    warnings.append(
                        {
                            "id": value["id"],
                            "reason": "Legacy output without specification; unchanged regeneration allowed",
                        }
                    )
                elif self.research:
                    if reason := producer_error(value["producer"], self.roles):
                        raise FreezeError(reason)
                    specs = value.get("member_specifications")
                    if value["kind"] == "group":
                        if not isinstance(specs, dict) or set(specs) != set(paths):
                            raise FreezeError(
                                "Output group membership changed without specification registration"
                            )
                        for spec in specs.values():
                            self.specification(spec, {})
                    else:
                        self.specification(value.get("specification"), {})
            except (FreezeError, OSError, ValueError, TypeError) as error:
                errors.append({"id": value["id"], "reason": str(error)})
        area = self.roles.get("results" if self.research else "deliverables")
        if area and (self.root / area).exists():
            for directory, dirs, files in os.walk(self.root / area, followlinks=False):
                for child in dirs + files:
                    path = self.root.__class__(directory) / child
                    name = path.relative_to(self.root).as_posix()
                    if path.is_symlink():
                        errors.append({"path": name, "reason": "Linked output is unsupported"})
                    elif path.is_file() and name not in registered and child != ".DS_Store":
                        errors.append({"path": name, "reason": "Unregistered output"})
        return {"errors": errors, "warnings": warnings}
