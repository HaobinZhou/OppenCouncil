"""Current high-risk verification records and durable replacement of Audit runs.

Legacy module/function audits are read-only history. The helper records reported
verification; source/check hashes do not claim that executable checks were run.
"""

from __future__ import annotations

import json
import re
import stat
import tempfile
from pathlib import Path

from . import project_transaction as tx
from .outputs import fingerprint
from .project import json_bytes
from .project_registry import Registry, read_table, relative_path, stable_key, within
from .script_ops import inventory
from .store import FreezeError, FreezeStore, now, require_text

GENERAL_FIELDS = ("purpose_and_risk", "contract", "edge_cases_and_verification", "known_limits")
RESEARCH_FIELDS = ("summary", "checks", "verification", "limits")
RUN_MANIFEST = ".oppencouncil-run.json"
RESIDUE = re.compile(
    r"(?:\.steward-(?:promote|previous|rollback|recover-remove)-.+|"
    r"(?:staging|failed|incomplete|abandoned|candidate|partial)(?:[._-].*)?)",
    re.I,
)


def read_contract(registry, topic):
    entry = registry.metadata.get("contract_audits", {}).get(topic)
    if entry is None:
        return None
    path = relative_path(registry.root, entry["path"], required=True)
    raw = tx.read_bytes(path)
    if tx.digest(raw) != entry["sha256"]:
        raise FreezeError("Managed contract audit changed: " + entry["path"])
    # The JSON record is an explicit fenced block, not a permissive YAML parser.
    from .project import unique_object

    prefix = "<!-- oppencouncil:audit:start -->\n```json\n"
    suffix = "\n```\n<!-- oppencouncil:audit:end -->"
    text = raw.decode("utf-8")
    if text.count(prefix) != 1 or text.count(suffix) != 1:
        raise FreezeError("Malformed current audit record")
    result = json.loads(text.split(prefix, 1)[1].split(suffix, 1)[0], object_pairs_hook=unique_object)
    if result.get("topic") != topic or result.get("schema_version") != 1:
        raise FreezeError("Invalid current audit identity")
    return result


def contract(root, topic, *, source=None, risk_reason=None, payload=None, fault=None):
    with tx.project_lock(root):
        registry = Registry(root)
        root = registry.root
        topic = stable_key(topic, "Audit topic")
        old = read_contract(registry, topic)
        if payload is not None and (source is not None or risk_reason is not None):
            raise FreezeError("Complete an audit with --input only; create its source/risk binding first")
        if payload is None:
            if source is None or risk_reason is None:
                raise FreezeError("Audit creation requires source and risk reason")
            risk_reason = require_text(risk_reason, "risk reason", 5000)
            if old:
                if old["source"] != source or old["risk_reason"] != risk_reason:
                    raise FreezeError("Audit topic already has a different source or risk binding")
                return {
                    "changed_paths": [],
                    "path": registry.metadata["contract_audits"][topic]["path"],
                    "status": old["status"],
                }
            record = {
                "schema_version": 1,
                "topic": topic,
                "source": source,
                "risk_reason": risk_reason,
                "project_type": registry.project.project_type,
                "status": "draft",
                "content": {},
            }
        else:
            if old is None:
                raise FreezeError("Create the audit source/risk binding before completing it")
            fields = RESEARCH_FIELDS if registry.project.project_type == "research" else GENERAL_FIELDS
            if not isinstance(payload, dict) or set(payload) != set(fields):
                raise FreezeError("Audit completion requires exactly: " + ", ".join(fields))
            content = {}
            for field in fields:
                if field != "checks":
                    content[field] = require_text(payload[field], field, 30000)
            if "checks" in fields:
                checks = payload["checks"]
                if not isinstance(checks, list) or not checks or any(not isinstance(p, str) for p in checks):
                    raise FreezeError("Research audit checks must list existing executable check files")
                if len(set(checks)) != len(checks):
                    raise FreezeError("Audit checks must be unique")
                content["checks"] = checks
            record = {
                **old,
                "project_type": registry.project.project_type,
                "status": "complete",
                "content": content,
            }
        reads = {}
        source = record["source"]
        evidence = fingerprint(root, source)
        if not evidence["bytes"]:
            raise FreezeError("Audit source must not be empty")
        record["source_sha256"] = reads[source] = evidence["sha256"]
        record["check_sha256"] = {}
        for name in record["content"].get("checks", []):
            checked = fingerprint(root, name)
            if not checked["bytes"] or Path(name).suffix.lower() in {".md", ".txt", ".csv", ".json"}:
                raise FreezeError("Research audit requires executable checks, not explanatory documents")
            record["check_sha256"][name] = reads[name] = checked["sha256"]
        if old == record:
            return {
                "changed_paths": [],
                "path": registry.metadata["contract_audits"][topic]["path"],
                "status": record["status"],
            }
        record["reviewed_at"] = now() if record["status"] == "complete" else None
        name = (
            registry.metadata.get("contract_audits", {}).get(topic, {}).get("path")
            or registry.roles()["audit"] + "/Contracts/v5_" + topic + ".md"
        )
        if old is None and relative_path(root, name).exists():
            raise FreezeError("Audit destination is already occupied: " + name)
        raw = (
            "# High-risk verification: " + topic + "\n\n"
            "<!-- oppencouncil:audit:start -->\n```json\n"
            + json_bytes(record).decode().rstrip()
            + "\n```\n<!-- oppencouncil:audit:end -->\n"
        ).encode("utf-8")
        registry.metadata.setdefault("contract_audits", {})[topic] = {"path": name, "sha256": tx.digest(raw)}
        result = registry.commit(writes={name: raw}, reads=reads, fault=fault)
        return {**result, "path": name, "status": record["status"]}


def stage_path(registry, stage):
    stable_key(stage, "Audit stage")
    if stage.endswith(".") or stage.split(".")[0] in {
        "aux",
        "con",
        "nul",
        "prn",
        *[f"com{i}" for i in range(1, 10)],
        *[f"lpt{i}" for i in range(1, 10)],
    }:
        raise FreezeError("Audit stage must be a portable path key")
    relative_path(registry.root, registry.roles()["audit"] + "/Runs/" + stage, directory=True)
    return registry.roles()["audit"] + "/Runs/" + stage


def run_files(root, current):
    if not relative_path(root, current, directory=True).exists():
        return [], []
    return inventory(root, current)


def verify_run(registry, stage):
    current = stage_path(registry, stage) + "/current"
    entry = registry.metadata.get("audit_runs", {}).get(stage)
    if not entry:
        return {"stage": stage, "registered": False}
    name = current + "/" + RUN_MANIFEST
    raw = tx.read_bytes(relative_path(registry.root, name, required=True))
    if entry["path"] != name or tx.digest(raw) != entry["sha256"]:
        raise FreezeError("Audit run manifest changed: " + name)
    from .project import unique_object

    manifest = json.loads(raw, object_pairs_hook=unique_object)
    if manifest.get("schema_version") != 1 or manifest.get("stage") != stage:
        raise FreezeError("Invalid Audit run manifest")
    files, directories = run_files(registry.root, current)
    expected_files = {current + "/" + p for p in manifest["files"]} | {name}
    expected_dirs = {current, *[current + "/" + p for p in manifest["directories"]]}
    if set(files) != expected_files or set(directories) != expected_dirs:
        raise FreezeError("Audit run inventory changed: " + current)
    for path, expected in manifest["files"].items():
        if fingerprint(registry.root, current + "/" + path) != expected:
            raise FreezeError("Audit run file changed: " + path)
    return {"stage": stage, "registered": True, "files": len(manifest["files"])}


def promote(root, stage, staging, *, fault=None):
    root = Path(root).expanduser().resolve(strict=True)
    staging = Path(staging).expanduser().absolute()
    if (
        staging.is_symlink()
        or staging.resolve().is_relative_to(root)
        or root.is_relative_to(staging.resolve())
    ):
        raise FreezeError("Audit staging must be a separate external directory")
    staging = staging.resolve(strict=True)
    if not staging.is_dir():
        raise FreezeError("Audit staging must be a directory")
    with tx.project_lock(root):
        registry = Registry(root)
        area = stage_path(registry, stage)
        directory = relative_path(root, area, directory=True)
        if directory.exists() and {p.name for p in directory.iterdir()} - {"current", ".DS_Store"}:
            raise FreezeError("Audit stage has legacy residue; recover it before promotion")
        current = area + "/current"
        # inventory rejects links and non-regular files.
        files, dirs = inventory(staging.parent, staging.name)
        if len({p.casefold() for p in files + dirs}) != len(files + dirs):
            raise FreezeError("Audit staging has paths that collide on supported filesystems")
        paths = {p: Path(p).relative_to(staging.name).as_posix() for p in files}
        if not paths or RUN_MANIFEST in paths.values():
            raise FreezeError("Audit staging must contain evidence and no helper-owned run manifest")
        sources = {name: tx.FileSource.checked(staging.parent / p) for p, name in paths.items()}
        manifest = {
            "schema_version": 1,
            "stage": stage,
            "files": {p: {"sha256": s.sha256, "bytes": s.size} for p, s in sorted(sources.items())},
            "directories": sorted(
                Path(p).relative_to(staging.name).as_posix() for p in dirs if p != staging.name
            ),
        }
        old_files, old_dirs = run_files(root, current)
        new_dirs = {current, *[current + "/" + p for p in manifest["directories"]]}
        writes = {p: None for p in old_files}
        writes.update({current + "/" + p: value for p, value in sources.items()})
        manifest_name = current + "/" + RUN_MANIFEST
        manifest_raw = json_bytes(manifest)
        writes[manifest_name] = manifest_raw
        existing = registry.metadata.get("audit_runs", {}).get(stage)
        if existing and existing == {"path": manifest_name, "sha256": tx.digest(manifest_raw)}:
            verify_run(registry, stage)
            return {"changed_paths": [], "stage": stage}
        registry.metadata.setdefault("audit_runs", {})[stage] = {
            "path": manifest_name,
            "sha256": tx.digest(manifest_raw),
        }
        writes.update(registry.write())
        writes, expected, reads = registry.project.prepare_writes(writes)
        modes = {
            current + "/" + name: stat.S_IMODE(source.path.stat().st_mode) for name, source in sources.items()
        }

        def verify():
            observed = Registry(root, recover=False)
            verify_run(observed, stage)
            if run_files(root, current)[0] != sorted(
                p for p in writes if p.startswith(current + "/") and writes[p] is not None
            ):
                raise FreezeError("Audit run inventory changed during promotion")
            # Reject newly added/removed source files too; copied hashes alone cannot see them.
            if inventory(staging.parent, staging.name) != (files, dirs):
                raise FreezeError("Audit staging inventory changed during promotion")
            for source in sources.values():
                if tx.file_digest(source.path) != source.sha256:
                    raise FreezeError("Audit staging changed during promotion")

        result = tx.apply(
            root,
            writes,
            expected=expected,
            read_set=reads,
            modes=modes,
            create_directories=sorted(new_dirs - set(old_dirs)),
            remove_directories=sorted(set(old_dirs) - new_dirs),
            verify=verify,
            fault=fault,
        )
        return {**result, "stage": stage, "current": current}


def recover(root, stage, *, fault=None):
    """Preserve recognized legacy failed staging externally before transactional removal."""
    with tx.project_lock(root):
        registry = Registry(root)  # First recovers any interrupted v5 operation.
        root = registry.root
        area = stage_path(registry, stage)
        directory = relative_path(root, area, directory=True)
        if not directory.exists():
            return {"changed_paths": [], "stage": stage, "recovered": False}
        verify_run(registry, stage)
        sources = sorted(p for p in directory.iterdir() if p.name not in {"current", ".DS_Store"})
        if not sources:
            verify_run(registry, stage)
            return {"changed_paths": [], "stage": stage, "recovered": False}
        protected = [v for k, v in registry.roles().items() if k != "audit"]
        for row in read_table(registry.text, "canonical"):
            protected += [row["Canonical path"], row.get("Verification") or row.get("Contract test")]
        for row in registry.outputs():
            protected += [row["path"], row["producer"]]
        for topic in registry.metadata.get("contract_audits", {}):
            record = read_contract(registry, topic)
            protected += [record["source"], *record["check_sha256"]]
        if (root / "Freeze").exists():
            store = FreezeStore(root)
            with store.locked():
                for qid in store._manifest()["question_ids"]:
                    protected += [t["path"] for t in store._question(qid).get("verification_tests", [])]
        files, directories = [], []
        for path in sources:
            name = path.relative_to(root).as_posix()
            if path.is_symlink() or not RESIDUE.fullmatch(path.name):
                raise FreezeError("AUDIT_RECOVERY_REVIEW_REQUIRED: unclassified residue " + name)
            if any(p and (within(p, name) or within(name, p)) for p in protected):
                raise FreezeError("AUDIT_RECOVERY_REVIEW_REQUIRED: residue contains a registered owner/input")
            if path.is_dir():
                found, dirs = inventory(root, name)
                files += found
                directories += dirs
            else:
                relative_path(root, name, required=True)
                files.append(name)
        copies = {name: tx.FileSource.checked(root / name) for name in sorted(files)}
        destination = Path(tempfile.mkdtemp(prefix="oppencouncil-audit-recovery-"))
        if destination.is_relative_to(root):
            destination.rmdir()
            raise FreezeError("Audit recovery requires an external temporary directory")
        # Source state is preserved even if copying or the following transaction fails.
        for name in directories:
            (destination / Path(name).relative_to(area)).mkdir(parents=True, exist_ok=True)
        for name, source in copies.items():
            target = destination / Path(name).relative_to(area)
            target.parent.mkdir(parents=True, exist_ok=True)
            tx.atomic_write(target, source)
            tx.restore_mode(target, stat.S_IMODE(source.path.stat().st_mode))
        manifest = {
            "schema_version": 1,
            "project": str(root),
            "stage": stage,
            "created_at": now(),
            "recovery_path": str(destination),
            "directories": sorted(directories),
            "files": {p: {"sha256": s.sha256, "bytes": s.size} for p, s in copies.items()},
        }
        tx.atomic_write(destination / "recovery.json", json_bytes(manifest))
        for name in [destination, *[p for p in destination.rglob("*") if p.is_dir()]]:
            tx.sync_directory(name)
        tx.sync_directory(destination.parent)

        def verify_copy():
            for name, source in copies.items():
                target = destination / Path(name).relative_to(area)
                if tx.file_digest(target) != source.sha256 or target.stat().st_size != source.size:
                    raise FreezeError("External recovery read-back failed; original staging retained")

        verify_copy()
        registry.metadata.setdefault("audit_recoveries", []).append(manifest)
        writes = {**{name: None for name in files}, **registry.write()}
        writes, expected, reads = registry.project.prepare_writes(writes)
        reads.update({name: value.sha256 for name, value in copies.items()})

        def verify():
            Registry(root, recover=False)
            verify_copy()
            if {p.name for p in directory.iterdir()} - {"current", ".DS_Store"}:
                raise FreezeError("Audit residue changed during recovery")

        result = tx.apply(
            root,
            writes,
            expected=expected,
            read_set=reads,
            remove_directories=directories,
            verify=verify,
            fault=fault,
        )
        return {**result, "stage": stage, "recovered": True, "recovery_path": str(destination)}


def validate(root):
    registry = Registry(root)
    errors = []
    for topic in registry.metadata.get("contract_audits", {}):
        try:
            record = read_contract(registry, topic)
            if record["status"] != "complete":
                raise FreezeError("High-risk verification is incomplete")
            if fingerprint(registry.root, record["source"])["sha256"] != record["source_sha256"]:
                raise FreezeError("Current contract audit is stale for its source")
            for name, checksum in record["check_sha256"].items():
                if fingerprint(registry.root, name)["sha256"] != checksum:
                    raise FreezeError("Current contract audit is stale for its check: " + name)
        except (FreezeError, OSError, ValueError, KeyError, TypeError) as error:
            errors.append({"path": topic, "reason": str(error)})
    for stage in registry.metadata.get("audit_runs", {}):
        try:
            verify_run(registry, stage)
        except (FreezeError, OSError, ValueError, KeyError, TypeError) as error:
            errors.append({"path": stage, "reason": str(error)})
    return {"errors": errors}
