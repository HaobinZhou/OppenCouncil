"""Read-only v3/v4 migration planning and exact-plan application.

No analysis, project configuration, data relocation or script renumbering occurs
here. Runtime capability discovery is supplied by the local command boundary.
"""

from __future__ import annotations

import copy
import json
import os
import re
import tempfile
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path

from . import decisions, memory
from . import project_transaction as tx
from . import workflow as wf
from .definitions import state, validate_definition
from .output_rules import IGNORED_AREAS, NUMBERED, artifact_error, known_area
from .project import MARKER, NAMESPACE, Project, baseline_bytes, json_bytes, metadata_block
from .project_registry import tables
from .script_ops import analysis_scripts
from .store import MAX_JSON, FreezeError, FreezeStore, file_lock, governance_registry, now

IGNORE = ("/.oppencouncil-migration/", "/.oppencouncil-project.lock", "/Releases/*.zip")
ATTENTION_LABELS = (
    "ID",
    "Title",
    "Blocking",
    "Observation",
    "Evidence",
    "Why It Matters",
    "Why No Action Was Taken",
    "Human Decision Needed",
)


def attention_entry(path, raw):
    text = raw.decode("utf-8")
    if text.startswith("---"):
        separators = list(re.finditer(r"^---\r?$", text, re.MULTILINE))[:2]
        if len(separators) != 2:
            raise FreezeError("Invalid Attention frontmatter")
        meta = {}
        for line in text[separators[0].end() : separators[1].start()].strip().splitlines():
            key, value = line.split(":", 1)
            if key in meta:
                raise FreezeError("Duplicate Attention metadata")
            meta[key] = json.loads(value)
        if tuple(meta) != ("id", "title", "blocking") or type(meta["blocking"]) is not bool:
            raise FreezeError("Invalid Attention metadata")
        sections, _ = memory.section_values(text[separators[1].end() :], ATTENTION_LABELS[3:])
        values = {"ID": meta["id"], "Title": meta["title"], "Blocking": meta["blocking"], **sections}
    else:
        values, _ = memory.section_values(text, ATTENTION_LABELS)
        if values["Blocking"] not in {"true", "false"}:
            raise FreezeError("Invalid Attention blocking value")
        values["Blocking"] = values["Blocking"] == "true"
    if not re.fullmatch(r"A-[0-9]{4,}", values["ID"]) or Path(path).stem != values["ID"]:
        raise FreezeError("Attention ID and path disagree")
    return values


@dataclass
class Plan:
    report: dict
    writes: dict

    def public(self):
        return copy.deepcopy(self.report)


class Planner:
    def __init__(self, root):
        self.root = Path(root).expanduser().resolve(strict=True)
        self.reads = {}

    def read(self, name, *, json_record=False):
        raw = tx.read_bytes(tx.safe_destination(self.root, name))
        self.reads[name] = tx.digest(raw)
        if raw is not None and json_record and len(raw) > MAX_JSON:
            raise FreezeError("Legacy record exceeds the supported JSON limit: " + name)
        return json.loads(raw) if raw is not None and json_record else raw

    def inventory(self, area, *, report_links=None):
        path = tx.safe_destination(self.root, area + "/.path-check").parent
        if not path.exists():
            return []
        names = []
        for item in path.rglob("*"):
            if item.is_symlink():
                name = item.relative_to(self.root).as_posix()
                if report_links is None:
                    raise FreezeError("Migration input cannot contain links: " + name)
                report_links.append(name)
                continue
            if item.is_file() and item.name != ".DS_Store":
                names.append(item.relative_to(self.root).as_posix())
        return sorted(names)

    def plan(self, capabilities, *, project_type=None, created_at=None):
        created_at = created_at or now()
        self.type_override = project_type
        if (self.root / tx.STAGING).exists() or (self.root / tx.STAGING).is_symlink():
            raise FreezeError("Interrupted project transaction requires recovery before migration check")
        anchor, skill = governance_registry(self.root)
        name = anchor.relative_to(self.root).as_posix()
        raw = self.read(name)
        text = raw.decode("utf-8")
        blockers = []
        for component, value in capabilities.items():
            if value.get("required", True) and 5 not in value.get("governance_versions", []):
                blockers.append(component + " must support governance v5 before project migration")
            if value.get("error") and value.get("required", True):
                blockers.append(component + ": " + value["error"])
        if not {"council", "skill"} <= capabilities.keys():
            blockers.append("Council and skill capability checks are required")
        if skill == "oppencouncil":
            project = Project(self.root, recover=False)
            project.baseline_state()
            if project_type and project_type != project.project_type:
                blockers.append("An upgraded project changes type through project-type, not migration")
            return self.finish(
                {}, capabilities, created_at, project.project_type, blockers, [], {"already_v5": True}
            )
        kind = project_type or ("research" if skill == "stepwise-r-project" else "general")
        if kind not in {"research", "general"}:
            raise FreezeError("Project type must be research or general")
        prefix = NAMESPACE + "/" if skill == "oppen-project-steward" else ""
        memory_files = self.inventory(prefix + "Memory")
        entries = []
        for path in memory_files:
            entry_raw = self.read(path)
            if "/entries/" in path:
                entries.append(memory.parse(path, entry_raw))
        memory.validate_relationships(entries)
        # Preserve the complete existing Steward control baseline before any overlay.
        baseline_name = prefix + (".managed-state.json" if prefix else ".oppencouncil-state.json")
        old_baseline = self.read(baseline_name, json_record=True)
        managed_names = [
            name,
            *memory_files,
            *self.inventory(prefix + "Attention"),
            *self.inventory(prefix + "Audit/Contracts"),
        ]
        control_hashes = {p[len(prefix) :]: tx.digest(self.read(p)) for p in sorted(set(managed_names))}
        if prefix:
            if old_baseline is None:
                blockers.append("MANAGED_BASELINE_MISSING: bootstrap the existing Steward baseline first")
            else:
                expected = {e["path"]: e["sha256"] for e in old_baseline.get("files", [])}
                if old_baseline.get("schema_version") != 1 or expected != control_hashes:
                    blockers.append(
                        "MANAGED_STATE_CONFLICT: reconcile the existing Steward control files first"
                    )
        freeze_journal = self.read("Freeze/.decision-transaction.json")
        if freeze_journal is not None:
            blockers.append("A pending Freeze journal must be recovered with the current governor first")
        store = FreezeStore(self.root, recover_project=False)
        manifest = self.read("Freeze/manifest.json", json_record=True) or store._manifest()
        if manifest.get("schema_version") not in {1, 2}:
            raise FreezeError("Legacy manifest schema is not v3/v4 compatible")
        ids = manifest.get("question_ids", [])
        if not isinstance(ids, list) or len(set(ids)) != len(ids):
            raise FreezeError("Invalid legacy question index")
        question_files = self.inventory("Freeze/questions")
        if set(question_files) != {f"Freeze/questions/{qid}.json" for qid in ids}:
            blockers.append("Freeze question files and manifest disagree; reconcile before migration")
        questions, writes = {}, {}
        for qid in ids:
            path = f"Freeze/questions/{qid}.json"
            old = self.read(path, json_record=True)
            if old is None or old.get("id") != qid:
                raise FreezeError("Missing or mismatched question: " + qid)
            validate_definition(old)
            current = wf.upgrade_question(old)
            questions[qid] = current
        canonical = tables(text, skill, "canonical")
        for row in canonical:
            path = row.get("Canonical path", "")
            if re.fullmatch(r"Freeze/questions/F-[0-9]{6}\.json", path):
                qid = Path(path).stem
                if qid not in questions:
                    raise FreezeError("Registered Council owner is not in the manifest")
                verification = row.get("Contract test") or row.get("Verification")
                if verification:
                    questions[qid]["verification_tests"].append(
                        {
                            "path": verification,
                            "scope": row.get("Topic", ""),
                            "definition_version": state(questions[qid])["current_version"],
                        }
                    )
        for qid, value in questions.items():
            writes[f"Freeze/questions/{qid}.json"] = json_bytes(value)
        groups = self.read("Freeze/decision-groups.json", json_record=True)
        if groups:
            decisions.validate_catalog(groups)
            for group in groups["groups"]:
                if any(qid not in questions for qid in group["member_ids"]):
                    raise FreezeError("Group references an unknown question")
                members = [questions[qid] for qid in group["member_ids"]]
                phase = "prepare_review" if any(state(q)["draft"] for q in members) else "triage"
                if members and all(state(q)["current_version"] and not state(q)["draft"] for q in members):
                    phase = "closed"
                group["work"] = wf.initial_work(phase)
                group["work"]["closed_reason"] = "legacy_effective" if phase == "closed" else None
                wf.initialize_progress(group, question=False)
                if any(q["processing"]["bootstrap"] == "needs_reconciliation" for q in members):
                    group["processing"]["bootstrap"] = "needs_reconciliation"
                group["evidence_refs"] = []
                wf.validate_record(group)
            writes["Freeze/decision-groups.json"] = json_bytes(groups)
        attention = []
        for path in self.inventory(prefix + "Attention/entries"):
            original = self.read(path)
            fields = attention_entry(path, original)
            iid = f"I-{len(attention) + 1:06d}"
            entry = {
                "schema_version": 1,
                "id": iid,
                "revision": 1,
                "title": fields["Title"],
                "created_at": created_at,
                "created_by": "migration",
                "why": fields["Why It Matters"],
                "dedupe_key": "legacy-attention:" + fields["ID"],
                "question_ids": [],
                "messages": [],
                "evidence_refs": [],
                "work": wf.initial_work(),
                "legacy_attention": {
                    "id": fields["ID"],
                    "path": path,
                    "sha256": tx.digest(original),
                    "fields": fields,
                    "text": original.decode("utf-8"),
                },
            }
            entry["work"]["trigger_refs"] = [path]
            entry["work"]["blockers"] = [fields["Human Decision Needed"]] if fields["Blocking"] else []
            wf.initialize_progress(entry, question=False)
            entry["processing"]["bootstrap"] = "needs_reconciliation"
            wf.validate_record(entry)
            writes[f"Freeze/investigations/{iid}.json"] = json_bytes(entry)
            attention.append({"old_id": fields["ID"], "id": iid, "source": path})
        if self.inventory("Freeze/investigations") or self.inventory("Freeze/evidence"):
            blockers.append("Legacy project already contains v5 work paths; inspect before migration")
        output_rows = tables(text, skill, "results" if not prefix else "deliverables")
        warnings = (
            [
                {"kind": "legacy_output_without_specification", "id": row["ID"], "path": row["Path"]}
                for row in output_rows
            ]
            if kind == "research"
            else []
        )
        roles = tables(text, skill, "roles")
        role_paths = [row.get("Path") or row.get("Directory") for row in roles]
        role_paths = list(filter(None, role_paths))
        for row in canonical:
            path = row.get("Canonical path", "")
            if path and not path.startswith("Freeze/questions/"):
                warnings.append({"kind": "legacy_definition_requires_classification", "registration": row})
        script_roles = [
            r.get("Path") or r.get("Directory") for r in roles if r.get("Role") in {"R", "Scripts"}
        ]
        for directory in filter(None, script_roles):
            for path in analysis_scripts(self.inventory(directory), directory):
                self.read(path)
                if not NUMBERED.fullmatch(Path(path).name):
                    warnings.append({"kind": "unnumbered_script", "path": path})
        if kind == "research":
            results_paths = [
                row.get("Path") or row.get("Directory")
                for row in roles
                if row.get("Role", "").lower() in {"results", "deliverables"}
            ] or ["Results"]
            for directory in filter(None, results_paths):
                for path in self.inventory(directory):
                    relative = Path(path).relative_to(directory).as_posix()
                    registered = next(
                        (
                            row
                            for row in output_rows
                            if row["Path"] == path
                            or (row.get("Kind") == "group" and Path(row["Path"]) in Path(path).parents)
                        ),
                        None,
                    )
                    reason = artifact_error(relative, registered.get("Kind") if registered else None)
                    if reason or not registered:
                        warnings.append(
                            {
                                "kind": "legacy_output_needs_review",
                                "path": path,
                                "reason": reason or "unregistered output",
                            }
                        )
            data_paths = [
                row.get("Path") or row.get("Directory")
                for row in roles
                if row.get("Role", "").lower() == "data"
            ] or ["Data"]
            for directory in filter(None, data_paths):
                links = []
                # Legacy Data may contain linked historical snapshots. Report
                # them without following, copying, hashing or modifying targets.
                for path in self.inventory(directory, report_links=links):
                    if Path(path).relative_to(directory).parts[0] not in {"raw", "derived"}:
                        warnings.append({"kind": "data_origin_requires_classification", "path": path})
                warnings.extend(
                    {"kind": "legacy_data_link_requires_review", "path": path} for path in sorted(links)
                )
            for path in self.inventory("Releases"):
                warnings.append({"kind": "legacy_release_requires_manifest", "path": path})
            explore = self.root / "Explore"
            if explore.exists():
                # Report experiment owners without reading archived experiment contents.
                for item in sorted(explore.iterdir()):
                    if item.name not in {"_archive", ".DS_Store"}:
                        warnings.append(
                            {
                                "kind": "legacy_experiment_requires_status",
                                "path": item.relative_to(self.root).as_posix(),
                            }
                        )
            for directory, directories, names in os.walk(self.root, followlinks=False):
                directories[:] = sorted(d for d in directories if d not in IGNORED_AREAS)
                # Recognized areas are already owned; do not traverse raw data or archives here.
                directories[:] = [
                    d
                    for d in directories
                    if not known_area((Path(directory) / d).relative_to(self.root).as_posix(), role_paths)
                ]
                for filename in sorted(names):
                    path = (Path(directory) / filename).relative_to(self.root).as_posix()
                    if not known_area(path, role_paths):
                        warnings.append({"kind": "unassigned_project_file", "path": path})
        manifest.update(
            schema_version=3,
            investigation_ids=[i["id"] for i in attention],
            evidence_paths=[],
            submission_paths=[],
            submission_reviews={},
        )
        writes["Freeze/manifest.json"] = json_bytes(manifest)
        version_match = re.search(r"<!-- " + re.escape(skill) + r":v([34]) -->", text)
        operation_id = tx.digest(
            json_bytes(
                {
                    "root": str(self.root),
                    "created_at": created_at,
                    "registry_sha256": tx.digest(raw),
                    "project_type": kind,
                }
            )
        )
        metadata = {
            "governance_version": 5,
            "project_type": kind,
            "type_history": [
                {
                    "from": None,
                    "to": kind,
                    "at": created_at,
                    "by": "migration",
                    "reason": "Explicit migration selection" if project_type else "Legacy governor default",
                }
            ],
            "migration": {
                "operation_id": operation_id,
                "from_skill": skill,
                "from_version": int(version_match.group(1)),
                "at": created_at,
                "attention": attention,
                "legacy_outputs_without_specification": [row["ID"] for row in output_rows]
                if kind == "research"
                else [],
                "legacy_unnumbered_scripts": [
                    item["path"] for item in warnings if item["kind"] == "unnumbered_script"
                ],
            },
        }
        upgraded = text[: version_match.start()] + MARKER + text[version_match.end() :]
        upgraded += "\n" + metadata_block(metadata) + "\n"
        writes[name] = upgraded.encode("utf-8")
        ignore_raw = self.read(".gitignore")
        ignore = ignore_raw.decode("utf-8") if ignore_raw else ""
        missing = [line for line in IGNORE if line not in ignore.splitlines()]
        if missing:
            writes[".gitignore"] = (ignore.rstrip("\n") + "\n" + "\n".join(missing) + "\n").encode("utf-8")
        control_hashes[name[len(prefix) :]] = tx.digest(writes[name])
        generation = old_baseline.get("generation", 0) + 1 if old_baseline else 1
        writes[baseline_name] = baseline_bytes(generation, control_hashes)
        summary = {
            "operation_id": operation_id,
            "questions": len(questions),
            "groups": len(groups["groups"]) if groups else 0,
            "memory_entries": len(entries),
            "attention_to_investigations": attention,
            "registered_outputs_preserved": len(output_rows),
            "canonical_rows_preserved": len(canonical),
        }
        return self.finish(writes, capabilities, created_at, kind, blockers, warnings, summary)

    def finish(self, writes, capabilities, created_at, kind, blockers, warnings, summary):
        for path, raw in writes.items():
            if path.endswith(".json") and path.startswith("Freeze/") and len(raw) > MAX_JSON:
                blockers.append("Converted record exceeds the per-record limit: " + path)
            if path not in self.reads:
                self.read(path)
        report = {
            "schema_version": 1,
            "root": str(self.root),
            "created_at": created_at,
            "project_type": kind,
            "type_override": self.type_override,
            "capabilities": copy.deepcopy(capabilities),
            "read_set": self.reads,
            "writes": [
                {"path": path, "before": self.reads[path], "after": tx.digest(raw), "bytes": len(raw)}
                for path, raw in sorted(writes.items())
            ],
            "blockers": blockers,
            "warnings": warnings,
            "summary": summary,
        }
        report["plan_sha256"] = tx.digest(json_bytes(report))
        return Plan(report, writes)


def check(root, capabilities, *, project_type=None):
    return Planner(root).plan(capabilities, project_type=project_type)


@contextmanager
def legacy_locks(root):
    """Wait for in-flight legacy helper writes before acquiring the new project lock."""
    identity = os.path.normcase(os.path.normpath(str(Path(root).resolve())))
    key = tx.digest(identity.encode("utf-8"))
    with ExitStack() as stack:
        for name in ("stepwise-r-project-locks", "oppen-project-steward-locks"):
            directory = Path(tempfile.gettempdir()) / name
            directory.mkdir(exist_ok=True)
            if directory.is_symlink():
                raise FreezeError("Legacy helper lock directory must not be linked")
            stack.enter_context(file_lock(directory / (key + ".lock")))
        yield


def apply(root, saved_plan, capabilities, *, fault=None):
    with legacy_locks(root), tx.project_lock(root):
        return apply_locked(root, saved_plan, capabilities, fault=fault)


def apply_locked(root, saved_plan, capabilities, *, fault=None):
    if not isinstance(saved_plan, dict) or saved_plan.get("root") != str(Path(root).expanduser().resolve()):
        raise FreezeError("Migration plan belongs to a different project")
    unsigned = {k: v for k, v in saved_plan.items() if k != "plan_sha256"}
    if tx.digest(json_bytes(unsigned)) != saved_plan.get("plan_sha256"):
        raise FreezeError("Migration plan checksum does not match its contents")
    # Explicitly recover first; a plan remains usable only if its original state was restored.
    tx.recover(root)
    if governance_registry(Path(root))[1] == "oppencouncil":
        current = Project(root, recover=False)
        operation_id = current.metadata.get("migration", {}).get("operation_id")
        if operation_id and operation_id == saved_plan.get("summary", {}).get("operation_id"):
            current.baseline_state()
            return {"changed_paths": [], "already_v5": True, "replayed": True}
    planned = Planner(root).plan(
        capabilities, project_type=saved_plan.get("type_override"), created_at=saved_plan["created_at"]
    )
    # Preserve the human-selected/default provenance used during the original check.
    if planned.report != saved_plan:
        raise FreezeError("Migration inputs, capabilities or plan changed; run --check again")
    if saved_plan["blockers"]:
        raise FreezeError("Migration is blocked: " + "; ".join(saved_plan["blockers"]))
    if not planned.writes:
        return {"changed_paths": [], "already_v5": True}

    def verify():
        project = Project(root, recover=False)
        project.baseline_state()
        store = FreezeStore(root, recover_project=False)
        snapshot = store.snapshot()
        if snapshot.get("governance_version") != 5:
            raise FreezeError("Migrated project did not validate as v5")
        service = object.__new__(memory.Memory)
        service.project = project
        memory.validate_relationships(service.entries())

    return tx.apply(
        root,
        planned.writes,
        expected={path: saved_plan["read_set"][path] for path in planned.writes},
        read_set=saved_plan["read_set"],
        verify=verify,
        fault=fault,
    )
