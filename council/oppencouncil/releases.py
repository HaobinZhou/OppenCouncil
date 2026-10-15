"""Human-requested local ZIP snapshots with complete classified data and read-back checks."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path

from . import project_transaction as tx
from .assets import read_asset
from .outputs import fingerprint, members
from .project import Project, json_bytes, unique_object
from .project_registry import Registry, relative_path, within
from .script_ops import inventory
from .store import FreezeError, now, require_text

PURPOSES = {"submission", "revision", "preprint", "presentation", "collaborator", "other"}


def registered(registry):
    values = registry.metadata.get("releases", [])
    if not isinstance(values, list) or len({v["path"] for v in values}) != len(values):
        raise FreezeError("Invalid release registrations")
    return values


def ledger_bytes(values):
    return json_bytes({"schema_version": 1, "releases": values})


def git_state(root):
    def run(*args):
        result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
        if result.returncode:
            raise FreezeError("A release requires a readable Git commit for code provenance")
        return result.stdout.strip()

    return {
        "commit": run("rev-parse", "HEAD"),
        "dirty": bool(run("status", "--porcelain", "--untracked-files=normal")),
    }


def check(root, payload, *, created_at=None):
    from .project_checks import validate as validate_project

    root = Path(root).expanduser().resolve(strict=True)
    if (root / tx.STAGING).exists():
        raise FreezeError("Recover the interrupted transaction before release check")
    registry = Registry(root, recover=False)
    if registry.project.project_type != "research":
        raise FreezeError("Research release snapshots require a research project")
    allowed = {"purpose", "label", "human_request", "environment", "environment_files", "article_numbers"}
    if not isinstance(payload, dict) or set(payload) - allowed:
        raise FreezeError("Invalid release fields")
    request = require_text(payload.get("human_request"), "explicit human snapshot request", 5000)
    purpose = payload.get("purpose")
    if not isinstance(purpose, str) or purpose not in PURPOSES:
        raise FreezeError("Choose a supported release purpose")
    label = require_text(payload.get("label"), "release label", 500)
    environment = payload.get("environment")
    if (
        not isinstance(environment, dict)
        or not isinstance(environment.get("languages"), dict)
        or not environment["languages"]
        or not isinstance(environment.get("packages"), dict)
    ):
        raise FreezeError("Record actual language and package versions for the release")
    for category in ("languages", "packages"):
        for name, version in environment[category].items():
            require_text(name, "environment component", 200)
            require_text(version, "environment version", 2000)
    result = validate_project(root)
    if result["errors"]:
        raise FreezeError(
            "Resolve project validation errors before release: "
            + json.dumps(result["errors"], ensure_ascii=False)
        )
    roles = registry.roles()
    at = created_at or now()
    releases = registered(registry)
    name = f"{roles['releases']}/{at[:10]}-{purpose}-{len(releases) + 1:03d}.zip"
    if relative_path(root, name).exists():
        raise FreezeError("Release destination already exists; never overwrite a snapshot")
    reads = {registry.project.registry_name: tx.digest(registry.project.registry_bytes), name: None}
    ledger = roles["releases"] + "/index.json"
    prior_ledger = tx.read_bytes(tx.safe_destination(root, ledger))
    if prior_ledger is not None and not releases:
        raise FreezeError("Existing release index is user-owned; inspect it before creating a new ledger")
    reads[ledger] = tx.digest(prior_ledger)
    ignored = subprocess.run(
        ["git", "-C", str(root), "check-ignore", "--no-index", "-q", "--", ledger], capture_output=True
    )
    if ignored.returncode == 0:
        raise FreezeError("Release index must be eligible for Git; existing ignore rules hide " + ledger)
    if ignored.returncode not in {0, 1}:
        raise FreezeError("Cannot verify Git visibility of the release checksum index")
    packaged = {}

    def include(path, kind):
        observed = fingerprint(root, path)
        if path in reads and reads[path] != observed["sha256"]:
            raise FreezeError("Release input changed while checking: " + path)
        reads[path] = observed["sha256"]
        packaged[path] = {"path": path, "kind": kind, **observed}

    data = registry.metadata.get("data", {})
    data_files, _ = inventory(root, roles["data"])
    data_files = [p for p in data_files if Path(p).name != ".DS_Store"]
    if set(data_files) != set(data):
        raise FreezeError(
            "Classify every Data file before release; no generated data may be silently omitted"
        )
    raw_inputs = []
    for path, entry in sorted(data.items()):
        observed = fingerprint(root, path)
        if observed != {key: entry[key] for key in ("sha256", "bytes")}:
            raise FreezeError("Data changed since registration: " + path)
        reads[path] = observed["sha256"]
        if entry["kind"] == "derived":
            include(path, "derived_data")
        else:
            raw_inputs.append(copy.deepcopy(entry))
    script_files, _ = inventory(root, roles["scripts"])
    for path in script_files:
        if Path(path).name != ".DS_Store" and "__pycache__" not in Path(path).parts:
            include(path, "code")
    outputs = registry.outputs()
    if not outputs:
        raise FreezeError("A formal release requires registered current results")
    article_numbers = payload.get("article_numbers", {})
    if not isinstance(article_numbers, dict) or set(article_numbers) - {v["id"] for v in outputs}:
        raise FreezeError("Article numbers must reference existing result IDs")
    questions = set()
    for value in outputs:
        for path in members(root, value["path"], value["kind"]):
            include(path, "result")
        refs = list(value.get("member_specifications", {}).values())
        if value.get("specification"):
            refs.append(value["specification"])
        questions.update(ref["question_id"] for ref in refs)
        value["legacy_without_specification"] = not bool(refs)
        value.pop("registry_block", None)
        if value["id"] in article_numbers:
            value["article_number"] = require_text(article_numbers[value["id"]], "article number", 100)
    # Preserve complete F records and immutable example assets. The manifest pins
    # the output versions; formal and historical records retain their original form.
    seen = set()
    while questions - seen:
        qid = sorted(questions - seen)[0]
        path = f"Freeze/questions/{qid}.json"
        include(path, "specification")
        raw = tx.read_bytes(root / path)
        if tx.digest(raw) != reads[path]:
            raise FreezeError("Specification changed while preparing release")
        question = json.loads(raw, object_pairs_hook=unique_object)
        for version in question["definition"]["versions"]:
            for dependency in version.get("dependencies", []):
                if dependency.get("question_id"):
                    questions.add(dependency["question_id"])
        for asset in set(re.findall(r"Freeze/assets/([0-9a-f]{64}\.(?:png|svg))", raw.decode("utf-8"))):
            read_asset(root, asset)
            include("Freeze/assets/" + asset, "example_asset")
        seen.add(qid)
    environment_files = payload.get("environment_files", [])
    if not isinstance(environment_files, list) or not all(isinstance(p, str) for p in environment_files):
        raise FreezeError("Environment files must be project-relative paths")
    for path in environment_files:
        relative_path(root, path, required=True)
        if within(path, roles["data"]) or within(path, roles["explore"]) or within(path, roles["releases"]):
            raise FreezeError("Environment records must not copy raw inputs, experiments or old snapshots")
        include(path, "environment")
    manifest = {
        "schema_version": 1,
        "generated_at": at,
        "purpose": purpose,
        "label": label,
        "human_request": request,
        "git": git_state(root),
        "roles": roles,
        "environment": environment,
        "outputs": outputs,
        "raw_inputs": raw_inputs,
        "derived_data": [copy.deepcopy(v) for v in data.values() if v["kind"] == "derived"],
        "files": [packaged[p] for p in sorted(packaged)],
    }
    if len(json_bytes(manifest)) > tx.MAX_CONTROL:
        raise FreezeError("Release manifest exceeds the supported control-record limit")
    ignore = tx.read_bytes(tx.safe_destination(root, ".gitignore"))
    reads[".gitignore"] = tx.digest(ignore)
    ignored_pattern = "/" + re.sub(r"([\\*?\[\] ])", r"\\\1", roles["releases"]) + "/*.zip"
    ignore_text = (ignore or b"").decode("utf-8")
    if ignored_pattern not in ignore_text.splitlines():
        ignore_text = ignore_text.rstrip() + "\n" + ignored_pattern + "\n"
    report = {
        "schema_version": 1,
        "domain": "release",
        "root": str(root),
        "operation": "create",
        "input": payload,
        "created_at": at,
        "path": name,
        "manifest": manifest,
        "manifest_sha256": tx.digest(json_bytes(manifest)),
        "read_set": reads,
        "write_paths": [
            name,
            ledger,
            registry.project.registry_name,
            registry.project.relative(registry.project.baseline),
            ".gitignore",
        ],
        "gitignore": ignore_text,
        "uncompressed_bytes": sum(v["bytes"] for v in packaged.values()),
        "raw_input_bytes_excluded": sum(v["bytes"] for v in raw_inputs),
    }
    report["plan_sha256"] = tx.digest(json_bytes(report))
    return report


def write_zip(root, path, manifest):
    with zipfile.ZipFile(path, "x", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
        for record in manifest["files"]:
            source = root / record["path"]
            if tx.file_digest(source) != record["sha256"]:
                raise FreezeError("Release input changed before packaging: " + record["path"])
            info = zipfile.ZipInfo(record["path"], date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (source.stat().st_mode & 0xFFFF) << 16
            checksum, size = hashlib.sha256(), 0
            with source.open("rb") as input_file, archive.open(info, "w", force_zip64=True) as output:
                for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
                    output.write(chunk)
                    checksum.update(chunk)
                    size += len(chunk)
            if checksum.hexdigest() != record["sha256"] or size != record["bytes"]:
                raise FreezeError("Release input changed during packaging")
        archive.writestr("manifest.json", json_bytes(manifest))


def inspect_zip(path, *, checksum, manifest_checksum):
    if tx.file_digest(path) != checksum:
        raise FreezeError("Release archive is missing or changed")
    with zipfile.ZipFile(path, "r") as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise FreezeError("Release archive has duplicate members")
        if archive.getinfo("manifest.json").file_size > tx.MAX_CONTROL:
            raise FreezeError("Release manifest is too large")
        raw = archive.read("manifest.json")
        if tx.digest(raw) != manifest_checksum:
            raise FreezeError("Release manifest checksum mismatch")
        manifest = json.loads(raw, object_pairs_hook=unique_object)
        if set(names) != {"manifest.json", *(item["path"] for item in manifest["files"])}:
            raise FreezeError("Release archive membership disagrees with its manifest")
        for item in manifest["files"]:
            checksum, size = hashlib.sha256(), 0
            with archive.open(item["path"]) as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    checksum.update(chunk)
                    size += len(chunk)
            if checksum.hexdigest() != item["sha256"] or size != item["bytes"]:
                raise FreezeError("Release member checksum mismatch: " + item["path"])
    return manifest


def apply(root, saved, *, fault=None):
    root = Path(root).expanduser().resolve(strict=True)
    if not isinstance(saved, dict) or saved.get("root") != str(root) or saved.get("domain") != "release":
        raise FreezeError("Release plan belongs to another project")
    if tx.digest(json_bytes({k: v for k, v in saved.items() if k != "plan_sha256"})) != saved.get(
        "plan_sha256"
    ):
        raise FreezeError("Release plan checksum mismatch")
    with tx.project_lock(root):
        tx.recover_locked(root)
        registry = Registry(root, recover=False)
        for entry in registered(registry):
            if entry.get("plan_sha256") == saved["plan_sha256"]:
                inspect_zip(
                    root / entry["path"], checksum=entry["sha256"], manifest_checksum=entry["manifest_sha256"]
                )
                return {"changed_paths": [], "replayed": True, "release": entry}
        if check(root, saved["input"], created_at=saved["created_at"]) != saved:
            raise FreezeError("Release inputs or plan changed; run --check again")
        with tempfile.TemporaryDirectory(prefix="oppencouncil-release-") as temporary:
            archive = Path(temporary) / "snapshot.zip"
            write_zip(root, archive, saved["manifest"])
            source = tx.FileSource.checked(archive)
            inspect_zip(archive, checksum=source.sha256, manifest_checksum=saved["manifest_sha256"])
            entry = {
                "path": saved["path"],
                "sha256": source.sha256,
                "bytes": source.size,
                "manifest_sha256": saved["manifest_sha256"],
                "plan_sha256": saved["plan_sha256"],
                "created_at": saved["created_at"],
                "purpose": saved["input"]["purpose"],
                "label": saved["input"]["label"],
            }
            registry.metadata.setdefault("releases", []).append(entry)
            writes = {
                **registry.write(),
                saved["path"]: source,
                ".gitignore": saved["gitignore"].encode("utf-8"),
                registry.roles()["releases"] + "/index.json": ledger_bytes(registry.metadata["releases"]),
            }
            writes, expected, reads = registry.project.prepare_writes(writes)
            for name, checksum in saved["read_set"].items():
                if name in reads and reads[name] != checksum:
                    raise FreezeError("Project changed while building release")
                reads[name] = checksum

            def verify():
                Project(root, recover=False).baseline_state()
                inspect_zip(
                    root / entry["path"], checksum=source.sha256, manifest_checksum=entry["manifest_sha256"]
                )

            result = tx.apply(
                root,
                writes,
                expected=expected,
                read_set=reads,
                modes={entry["path"]: 0o400},
                verify=verify,
                fault=fault,
            )
            return {**result, "release": entry}


def validate(root):
    registry = Registry(root)
    errors, warnings = [], []
    releases = registered(registry)
    area = registry.roles().get("releases")
    if area and releases:
        ledger = area + "/index.json"
        if tx.read_bytes(relative_path(registry.root, ledger)) != ledger_bytes(releases):
            errors.append({"path": ledger, "reason": "Release checksum index is missing or changed"})
    for entry in releases:
        try:
            if not area or not within(entry["path"], area):
                raise FreezeError("Release is outside the registered area")
            path = relative_path(registry.root, entry["path"], required=True)
            if path.stat().st_size != entry["bytes"]:
                raise FreezeError("Release archive size changed")
            inspect_zip(path, checksum=entry["sha256"], manifest_checksum=entry["manifest_sha256"])
        except (FreezeError, OSError, KeyError, ValueError, zipfile.BadZipFile) as error:
            errors.append({"path": entry.get("path"), "reason": str(error)})
    if area and (registry.root / area).exists():
        known = {entry["path"] for entry in releases}
        for path in (registry.root / area).iterdir():
            if (
                path.name not in {".DS_Store", "index.json"}
                and path.relative_to(registry.root).as_posix() not in known
            ):
                warnings.append(
                    {
                        "path": path.relative_to(registry.root).as_posix(),
                        "reason": "Legacy release lacks a registered manifest/checksum",
                    }
                )
    return {"errors": errors, "warnings": warnings}
