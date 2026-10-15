"""Explicit experiment lifecycle with an archive summary that needs no archive reads."""

from __future__ import annotations

import copy
import json
import stat
from pathlib import Path

from . import project_transaction as tx
from .outputs import Outputs, fingerprint, members, producer_error
from .project import Project, json_bytes, unique_object
from .project_registry import Registry, relative_path, stable_key, within
from .script_ops import Plan, inventory
from .store import FreezeError, now, require_text

STATES = {"in_progress", "retained", "abandoned", "promoted"}


def summaries(registry):
    entries = registry.metadata.get("experiments", {})
    if not isinstance(entries, dict):
        raise FreezeError("Experiment index must be an object")
    for key, value in entries.items():
        if value.get("id") != key or value.get("status") not in STATES:
            raise FreezeError("Invalid experiment index entry")
    return entries


def index_text(entries):
    lines = [
        "# Experiments",
        "",
        "| ID | Path | Status | Question | Conclusion |",
        "| --- | --- | --- | --- | --- |",
    ]
    for entry in sorted(entries.values(), key=lambda item: item["id"]):
        cells = [entry.get(k, "") for k in ("id", "path", "status", "question", "conclusion")]
        lines.append("| " + " | ".join(str(c).replace("|", "\\|").replace("\n", " ") for c in cells) + " |")
    return ("\n".join(lines) + "\n").encode()


def index(root):
    return list(summaries(Registry(root)).values())


class Planner:
    def __init__(self, root):
        self.root = Path(root).expanduser().resolve(strict=True)
        if (self.root / tx.STAGING).exists():
            raise FreezeError("Recover the interrupted transaction before experiment check")
        self.registry = Registry(root, recover=False)
        if self.registry.project.project_type != "research":
            raise FreezeError("Experiment lifecycle applies to research projects")
        self.area = self.registry.roles()["explore"]
        relative_path(self.root, self.area, directory=True)
        self.reads = {self.registry.project.registry_name: tx.digest(self.registry.project.registry_bytes)}

    def read(self, name):
        raw = tx.read_bytes(tx.safe_destination(self.root, name))
        checksum = tx.digest(raw)
        if name in self.reads and self.reads[name] != checksum:
            raise FreezeError("Experiment input changed during check")
        self.reads[name] = checksum
        return raw

    def references(self, record):
        for key in ("scripts", "outputs"):
            values = record.get(key, [])
            if (
                not isinstance(values, list)
                or not all(isinstance(p, str) for p in values)
                or len(values) != len(set(values))
            ):
                raise FreezeError("Experiment references must be unique path arrays")
            for name in values:
                if not within(name, record["path"]) or name == record["path"]:
                    raise FreezeError("Experiment references must remain inside that experiment")
                self.reads[name] = fingerprint(self.root, name)["sha256"]

    def promotion(self, ids):
        if not isinstance(ids, list) or not ids or len(ids) != len(set(ids)):
            raise FreezeError("Promotion requires unique formal result IDs")
        outputs = Outputs(self.root)
        available = {item["id"]: item for item in outputs.registry.outputs()}
        for identifier in ids:
            if identifier not in available:
                raise FreezeError("Promoted result is not registered: " + str(identifier))
            value = available[identifier]
            if reason := producer_error(value["producer"], self.registry.roles()):
                raise FreezeError(reason)
            self.reads[value["producer"]] = fingerprint(self.root, value["producer"])["sha256"]
            paths = members(self.root, value["path"], value["kind"])
            if value["kind"] == "group":
                specs = value.get("member_specifications", {})
                if set(specs) != set(paths):
                    raise FreezeError("Every promoted group member needs a confirmed specification")
                for spec in specs.values():
                    outputs.specification(spec, self.reads)
            else:
                outputs.specification(value.get("specification"), self.reads)
            for path in paths:
                self.reads[path] = fingerprint(self.root, path)["sha256"]

    def plan(self, operation, payload, *, created_at=None):
        if not isinstance(payload, dict):
            raise FreezeError("Experiment input must be an object")
        fields = {
            "create": {"slug", "question"},
            "update": {"id", "question", "status", "scripts", "outputs", "conclusion"},
            "archive": {"id", "conclusion"},
            "promote": {"id", "result_ids", "conclusion"},
        }
        if operation not in fields or set(payload) - fields[operation]:
            raise FreezeError("Unknown experiment operation or fields")
        at = created_at or now()
        entries = copy.deepcopy(summaries(self.registry))
        writes, modes, create_dirs, remove_dirs, dir_modes = {}, {}, [], [], {}
        if operation == "create":
            slug = stable_key(payload.get("slug"), "Experiment slug")
            question = require_text(payload.get("question"), "experiment question", 5000)
            number = max([int(key.split("-")[1]) for key in entries] + [0]) + 1
            identifier = f"EXP-{number:06d}"
            directory = f"{self.area}/{number:03d}-{slug}"
            if relative_path(self.root, directory, directory=True).exists():
                raise FreezeError("Experiment directory already exists")
            record = {
                "schema_version": 1,
                "id": identifier,
                "path": directory,
                "question": question,
                "status": "in_progress",
                "scripts": [],
                "outputs": [],
                "result_ids": [],
                "conclusion": "",
                "created_at": at,
                "history": [],
            }
        else:
            identifier = payload.get("id")
            if identifier not in entries:
                raise FreezeError("Unknown experiment ID")
            summary = entries[identifier]
            if summary["status"] == "abandoned":
                raise FreezeError("Archived experiments are immutable historical records")
            directory = summary["path"]
            if not within(directory, self.area) or within(directory, self.area + "/_archive"):
                raise FreezeError("Active experiment path is outside the active area")
            record = json.loads(self.read(directory + "/experiment.json"), object_pairs_hook=unique_object)
            if (
                record["id"] != identifier
                or record["path"] != directory
                or record["status"] != summary["status"]
            ):
                raise FreezeError("Experiment record and index disagree")
        previous = copy.deepcopy(record)
        if operation == "update":
            if record["status"] == "promoted":
                raise FreezeError("Promoted experiments retain their formal links; start a new experiment")
            if payload.get("status", record["status"]) not in {"in_progress", "retained"}:
                raise FreezeError("Use explicit archive or promote for those transitions")
            record.update({k: copy.deepcopy(v) for k, v in payload.items() if k != "id"})
            require_text(record["question"], "experiment question", 5000)
            if not isinstance(record["conclusion"], str):
                raise FreezeError("Experiment conclusion must be text")
            self.references(record)
        elif operation in {"archive", "promote"}:
            record["conclusion"] = require_text(payload.get("conclusion"), "experiment conclusion", 10000)
            if operation == "promote":
                self.promotion(payload.get("result_ids"))
                record.update(status="promoted", result_ids=payload["result_ids"])
                self.references(record)
            else:
                self.references(record)
                destination = self.area + "/_archive/" + Path(directory).name
                if relative_path(self.root, destination, directory=True).exists():
                    raise FreezeError("Archive destination already exists")
                files, dirs = inventory(self.root, directory)
                for name in files:
                    source = tx.FileSource.checked(self.root / name)
                    self.reads[name] = source.sha256
                    target = destination + name[len(directory) :]
                    writes[name], writes[target] = None, source
                    modes[target] = stat.S_IMODE((self.root / name).stat().st_mode)
                create_dirs = [destination + p[len(directory) :] for p in dirs]
                remove_dirs = dirs
                dir_modes = {
                    destination + p[len(directory) :]: stat.S_IMODE((self.root / p).stat().st_mode)
                    for p in dirs
                }
                record.update(path=destination, status="abandoned")
                for key in ("scripts", "outputs"):
                    record[key] = [destination + p[len(directory) :] for p in record[key]]
        changed = operation == "create" or record != previous
        if changed:
            record["updated_at"] = at
            record["history"].append(
                {
                    "at": at,
                    "operation": operation,
                    "from": None if operation == "create" else previous["status"],
                    "to": record["status"],
                    "conclusion": record["conclusion"],
                }
            )
            writes[record["path"] + "/experiment.json"] = json_bytes(record)
            entries[identifier] = {
                k: copy.deepcopy(record[k])
                for k in ("id", "path", "status", "question", "conclusion", "result_ids")
            }
            self.registry.metadata["experiments"] = entries
            index_path = self.area + "/index.md"
            self.read(index_path)
            writes[index_path] = index_text(entries)
        operation_id = tx.digest(
            json_bytes({"operation": operation, "input": payload, "at": at, "reads": self.reads})
        )
        if changed:
            self.registry.metadata.setdefault("experiment_operations", []).append(
                {"id": operation_id, "operation": operation, "input": payload}
            )
            writes.update(self.registry.write())
            writes, expected, reads = self.registry.project.prepare_writes(writes)
            if any(p in self.reads and self.reads[p] != value for p, value in reads.items()):
                raise FreezeError("Managed state changed during experiment check")
            self.reads.update(reads)
        else:
            expected = {}
        report = {
            "schema_version": 1,
            "domain": "experiment",
            "root": str(self.root),
            "operation": operation,
            "input": payload,
            "created_at": at,
            "operation_id": operation_id,
            "experiment": entries.get(identifier),
            "read_set": self.reads,
            "write_set": {p: {"before": expected[p], "after": tx.digest(raw)} for p, raw in writes.items()},
            "modes": modes,
            "create_directories": create_dirs,
            "remove_directories": remove_dirs,
            "directory_modes": dir_modes,
        }
        report["plan_sha256"] = tx.digest(json_bytes(report))
        return Plan(report, writes)


def check(root, operation, payload):
    return Planner(root).plan(operation, payload)


def apply(root, saved, *, fault=None):
    root = Path(root).expanduser().resolve(strict=True)
    if not isinstance(saved, dict) or saved.get("root") != str(root) or saved.get("domain") != "experiment":
        raise FreezeError("Experiment plan belongs to another project")
    if tx.digest(json_bytes({k: v for k, v in saved.items() if k != "plan_sha256"})) != saved.get(
        "plan_sha256"
    ):
        raise FreezeError("Experiment plan checksum mismatch")
    with tx.project_lock(root):
        tx.recover_locked(root)
        project = Project(root, recover=False)
        project.baseline_state()
        for entry in project.metadata.get("experiment_operations", []):
            if entry["id"] == saved["operation_id"]:
                if entry["operation"] != saved["operation"] or entry["input"] != saved["input"]:
                    raise FreezeError("Completed experiment operation does not match this plan")
                return {"changed_paths": [], "replayed": True}
        planned = Planner(root).plan(saved["operation"], saved["input"], created_at=saved["created_at"])
        if planned.report != saved:
            raise FreezeError("Experiment inputs or plan changed; run --check again")
        if not planned.writes:
            return {"changed_paths": []}
        return tx.apply(
            root,
            planned.writes,
            expected={p: v["before"] for p, v in saved["write_set"].items()},
            read_set=saved["read_set"],
            modes=saved["modes"],
            create_directories=saved["create_directories"],
            remove_directories=saved["remove_directories"],
            directory_modes=saved["directory_modes"],
            verify=lambda: Project(root, recover=False).baseline_state(),
            fault=fault,
        )


def validate(root):
    registry = Registry(root)
    entries, errors, warnings = summaries(registry), [], []
    area = registry.roles().get("explore")
    if not area:
        return {"errors": [], "warnings": []}
    for entry in entries.values():
        try:
            relative_path(registry.root, entry["path"], directory=True, required=True)
            if entry["status"] != "abandoned":
                raw = tx.read_bytes(
                    relative_path(registry.root, entry["path"] + "/experiment.json", required=True)
                )
                record = json.loads(raw, object_pairs_hook=unique_object)
                if any(record[k] != v for k, v in entry.items()):
                    raise FreezeError("Experiment index and record disagree")
                Planner(root).references(record)
        except (FreezeError, OSError, ValueError, KeyError, TypeError) as error:
            errors.append({"path": entry["path"], "reason": str(error)})
    if entries and tx.read_bytes(registry.root / area / "index.md") != index_text(entries):
        errors.append({"path": area + "/index.md", "reason": "Experiment summary index is stale"})
    directory = registry.root / area
    if directory.exists():
        known = {entry["path"] for entry in entries.values()}
        for item in directory.iterdir():
            if (
                item.name not in {"_archive", "index.md", ".DS_Store"}
                and item.relative_to(registry.root).as_posix() not in known
            ):
                warnings.append(
                    {
                        "path": item.relative_to(registry.root).as_posix(),
                        "reason": "Legacy experiment needs lifecycle registration",
                    }
                )
    return {"errors": errors, "warnings": warnings}
