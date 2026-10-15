"""Persistent, same-filesystem rollback for explicit project migrations and managed edits.

Unlike Freeze's committed forward journal, this transaction restores preimages until
the completion marker is durable. Only declared files are staged, never whole projects.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tempfile
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .store import FreezeError, file_lock, ordinary_file

STAGING = ".oppencouncil-migration"
LOCK = ".oppencouncil-project.lock"
MAX_CONTROL = 16 * 1024 * 1024
_held_locks = threading.local()


@dataclass(frozen=True)
class FileSource:
    """A checked external/staged file streamed into a new transaction destination."""

    path: Path
    sha256: str
    size: int

    @classmethod
    def checked(cls, path):
        path = Path(path)
        checksum = file_digest(path)
        if checksum is None:
            raise FreezeError("Transaction source file does not exist")
        return cls(path, checksum, path.stat().st_size)


def atomic_write(path, data):
    """Same durability as Freeze, without its per-record JSON size limit."""
    file_digest(path)
    descriptor, temporary = tempfile.mkstemp(prefix=".oppencouncil-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as output:
            if isinstance(data, FileSource):
                checksum, size = hashlib.sha256(), 0
                if file_digest(data.path) != data.sha256:
                    raise FreezeError("Transaction source file changed before copy")
                with data.path.open("rb") as source:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        output.write(chunk)
                        checksum.update(chunk)
                        size += len(chunk)
                if checksum.hexdigest() != data.sha256 or size != data.size:
                    raise FreezeError("Transaction source file changed during copy")
            else:
                output.write(data)
            output.flush()
            os.fsync(output.fileno())
        if os.name == "nt" and path.exists():
            os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
        os.replace(temporary, path)
        sync_directory(path.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def digest(data):
    if isinstance(data, FileSource):
        return data.sha256
    return hashlib.sha256(data).hexdigest() if data is not None else None


def sync_directory(path):
    if os.name != "nt":
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def restore_mode(path, mode):
    # Windows _commit requires a writable handle, even when only persisting
    # attributes. Open before restoring the read-only bit, which does not
    # revoke access from an already open handle.
    if os.name == "nt":
        os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
        descriptor = os.open(path, os.O_RDWR | os.O_BINARY)
    else:
        descriptor = os.open(path, os.O_RDONLY)
    try:
        os.chmod(path, mode)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def remove_file(path):
    if os.name == "nt":
        os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
    path.unlink()


def safe_destination(root, name):
    if not isinstance(name, str) or "\\" in name:
        raise FreezeError("Invalid managed path")
    path = PurePosixPath(name)
    if path.is_absolute() or not path.parts or any(p in {".", ".."} for p in name.split("/")):
        raise FreezeError("Managed path must be relative to this project")
    if path.parts[0] in {".git", STAGING, LOCK}:
        raise FreezeError("Reserved managed path")
    current = root
    for index, part in enumerate(path.parts):
        current /= part
        if current.is_symlink():
            raise FreezeError("Managed paths must not traverse links")
        if current.exists():
            mode = current.stat().st_mode
            if index < len(path.parts) - 1 and not stat.S_ISDIR(mode):
                raise FreezeError("Managed parent must be a directory")
            if index == len(path.parts) - 1 and not stat.S_ISREG(mode):
                raise FreezeError("Managed target must be an ordinary file")
    return current


def read_bytes(path):
    if path.is_symlink():
        raise FreezeError("Managed file must not be linked")
    try:
        info = path.stat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise FreezeError("Managed target must be an ordinary file")
    # The write set controls scope; project migration is not subject to the Freeze JSON cap.
    return path.read_bytes()


def file_digest(path):
    """Hash read dependencies in bounded memory, including large project data."""
    if path.is_symlink():
        raise FreezeError("Project input must not be linked")
    try:
        before = path.stat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise FreezeError("Project input must be an ordinary file")

    def identity(info, *, cross_api=False):
        value = info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_nlink
        # Windows CPython can expose creation time through stat and change time
        # through fstat. Compare ctime only within the same API there; retain
        # both before/after checks so in-place changes during hashing still fail.
        return value if os.name == "nt" and cross_api else (*value, info.st_ctime_ns)

    checksum = hashlib.sha256()
    with path.open("rb") as handle:
        opened = os.fstat(handle.fileno())
        if identity(opened, cross_api=True) != identity(before, cross_api=True):
            raise FreezeError("Project input changed while opening")
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            checksum.update(chunk)
        after = os.fstat(handle.fileno())
    if path.is_symlink() or identity(after) != identity(opened) or identity(path.stat()) != identity(before):
        raise FreezeError("Project input changed while reading")
    return checksum.hexdigest()


def save_control(stage, value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    if len(raw) > MAX_CONTROL:
        raise FreezeError("Migration write set is too large")
    atomic_write(stage / "transaction.json", raw)


def clean_stage(root, stage):
    if stage.is_symlink() or not stage.is_dir():
        raise FreezeError("Unsafe migration recovery area")
    if any((stage / area).is_symlink() for area in ("before", "after")):
        raise FreezeError("Migration preimage directories must not be linked")
    # Contents are owned exclusively by this transaction; never follow child links.
    # Windows may report a directory as nonempty while a successfully deleted
    # child is still pending removal by an external handle. Retry only these
    # transient native errors, with a bounded wait; keep other failures visible.
    for attempt in range(6):
        try:
            shutil.rmtree(stage)
            break
        except OSError as exc:
            if os.name != "nt" or getattr(exc, "winerror", None) not in {32, 145} or attempt == 5:
                raise
            time.sleep(0.02 * 2**attempt)
    sync_directory(root)


def recover_locked(root):
    """Caller holds the stable project lock. Validate every preimage before rollback."""
    stage = root / STAGING
    if not stage.exists() and not stage.is_symlink():
        return {"recovered": False}
    if stage.is_symlink() or not stage.is_dir():
        raise FreezeError("Unsafe migration recovery area")
    if any((stage / area).is_symlink() for area in ("before", "after")):
        raise FreezeError("Migration preimage directories must not be linked")
    raw = ordinary_file(stage / "transaction.json", MAX_CONTROL)
    if raw is None:
        # No control file means preparation never reached a target write.
        if any(p.name not in {"before", "after"} for p in stage.iterdir()):
            raise FreezeError("Unrecognized migration residue; inspect before recovery")
        clean_stage(root, stage)
        return {"recovered": True, "action": "discard_unprepared"}
    try:
        control = json.loads(raw)
        if control["schema_version"] != 1 or control["root"] != str(root):
            raise ValueError("transaction identity")
        phase = control["phase"]
        if phase not in {"preparing", "prepared", "applying", "committed"}:
            raise ValueError("transaction phase")
        entries = control["entries"]
        if not isinstance(entries, list) or len({e["path"] for e in entries}) != len(entries):
            raise ValueError("transaction entries")
        prepared = []
        for number, entry in enumerate(entries):
            target = safe_destination(root, entry["path"])
            original = None
            if phase != "preparing" and entry["before"] is not None:
                original = FileSource.checked(stage / "before" / str(number))
                if digest(original) != entry["before"] or original.size != entry["size_before"]:
                    raise ValueError("preimage checksum")
            if phase in {"prepared", "applying"}:
                current = file_digest(target)
                if current not in {entry["before"], entry["after"]}:
                    raise FreezeError("Migration recovery conflicts with later edits: " + entry["path"])
            prepared.append((target, entry, original))
        directories = []
        for name in control.get("created_directories", []):
            # Use a synthetic ordinary child to validate every directory segment.
            directory = safe_destination(root, name + "/.path-check").parent
            directories.append(directory)
        removed_directories = []
        for item in control.get("removed_directories", []):
            directory = safe_destination(root, item["path"] + "/.path-check").parent
            if type(item["mode"]) is not int or not 0 <= item["mode"] <= 0o777:
                raise ValueError("directory mode")
            removed_directories.append((directory, item["mode"]))
    except (KeyError, TypeError, ValueError) as error:
        raise FreezeError(f"Invalid migration recovery record: {error}") from error
    if phase in {"prepared", "applying"}:
        for directory, mode in sorted(removed_directories, key=lambda item: len(item[0].parts)):
            directory.mkdir(mode=mode, exist_ok=True)
            os.chmod(directory, mode)
            sync_directory(directory.parent)
        for target, entry, original in reversed(prepared):
            if entry["before"] is None:
                if target.exists():
                    remove_file(target)
                    sync_directory(target.parent)
            else:
                if file_digest(target) != entry["before"]:
                    atomic_write(target, original)
                restore_mode(target, entry["mode"])
        for directory in sorted(directories, key=lambda p: len(p.parts), reverse=True):
            try:
                directory.rmdir()
                sync_directory(directory.parent)
            except FileNotFoundError:
                pass
            except OSError as error:
                raise FreezeError(
                    "Recovery directory contains unexpected files: " + str(directory)
                ) from error
    clean_stage(root, stage)
    return {"recovered": True, "action": "cleanup_committed" if phase == "committed" else "rollback"}


@contextmanager
def project_lock(project):
    root = Path(project).resolve(strict=True)
    if not root.is_dir():
        raise FreezeError("Project root must be a directory")
    held = getattr(_held_locks, "roots", set())
    if root in held:
        yield root
        return
    lock = root / LOCK
    if lock.is_symlink():
        raise FreezeError("Project lock must not be linked")
    with file_lock(lock):
        _held_locks.roots = held | {root}
        try:
            yield root
        finally:
            _held_locks.roots = held


def recover(project):
    with project_lock(project) as root:
        return recover_locked(root)


def apply(
    project,
    writes,
    *,
    expected,
    read_set=None,
    create_directories=(),
    remove_directories=(),
    modes=None,
    directory_modes=None,
    verify=None,
    fault=None,
):
    """Apply an exact, previously checked byte write set and roll back exceptions.

    `fault` is an optional test hook. A process exit deliberately bypasses exception
    rollback so a fresh process can exercise persistent recovery.
    """
    if not isinstance(writes, dict) or not writes or set(writes) != set(expected):
        raise FreezeError("A complete checked write set is required")
    modes = modes or {}
    directory_modes = directory_modes or {}
    if set(modes) - set(writes) or any(
        type(mode) is not int or not 0 <= mode <= 0o777 for mode in modes.values()
    ):
        raise FreezeError("Invalid replacement file modes")
    if set(directory_modes) - set(create_directories) or any(
        type(mode) is not int or not 0 <= mode <= 0o777 for mode in directory_modes.values()
    ):
        raise FreezeError("Invalid replacement directory modes")
    with project_lock(project) as root:
        recover_locked(root)
        for name, checksum in (read_set or {}).items():
            if file_digest(safe_destination(root, name)) != checksum:
                raise FreezeError("Project input changed since check: " + name)
        entries, targets, directories = [], {}, set()
        removals = []
        for name in remove_directories:
            directory = safe_destination(root, name + "/.path-check").parent
            if not directory.is_dir():
                raise FreezeError("Directory to remove must exist: " + name)
            removals.append({"path": name, "mode": stat.S_IMODE(directory.stat().st_mode)})
        for name in create_directories:
            parent = safe_destination(root, name + "/.path-check").parent
            while parent != root and not parent.exists():
                directories.add(parent.relative_to(root).as_posix())
                parent = parent.parent
        for name, replacement in writes.items():
            if replacement is not None and not isinstance(replacement, (bytes, FileSource)):
                raise FreezeError("Managed writes require bytes, a checked file source or deletion")
            target = safe_destination(root, name)
            original = FileSource.checked(target) if target.exists() else None
            if digest(original) != expected[name]:
                raise FreezeError("Project changed since check: " + name)
            targets[name] = (target, original, replacement)
            entries.append(
                {
                    "path": name,
                    "before": digest(original),
                    "after": digest(replacement),
                    "size_before": original.size if original is not None else 0,
                    "mode": stat.S_IMODE(target.stat().st_mode) if original is not None else 0o600,
                    "after_mode": modes.get(
                        name, stat.S_IMODE(target.stat().st_mode) if original is not None else 0o600
                    ),
                }
            )
            parent = target.parent
            while parent != root and not parent.exists():
                directories.add(parent.relative_to(root).as_posix())
                parent = parent.parent
        if set(writes) & directories:
            raise FreezeError("A transaction path cannot be both a file and a directory")
        if directories & set(remove_directories):
            raise FreezeError("A directory cannot be created and removed in one transaction")
        stage = root / STAGING
        stage.mkdir(mode=0o700)
        sync_directory(root)
        control = {
            "schema_version": 1,
            "root": str(root),
            "phase": "preparing",
            "entries": entries,
            "created_directories": sorted(directories),
            "removed_directories": removals,
        }
        save_control(stage, control)
        try:
            for area in ("before", "after"):
                (stage / area).mkdir(mode=0o700)
            sync_directory(stage)
            for number, (_, original, replacement) in enumerate(targets.values()):
                if original is not None:
                    atomic_write(stage / "before" / str(number), original)
                if replacement is not None:
                    atomic_write(stage / "after" / str(number), replacement)
            control["phase"] = "prepared"
            save_control(stage, control)
            if fault:
                fault("prepared", None)
            control["phase"] = "applying"
            save_control(stage, control)
            for name in sorted(directories, key=lambda p: len(PurePosixPath(p).parts)):
                directory = root / name
                directory.mkdir(mode=0o700)
                if name in directory_modes:
                    os.chmod(directory, directory_modes[name])
                sync_directory(directory.parent)
            if fault:
                fault("directories", None)
            for number, (target, _, replacement) in enumerate(targets.values()):
                if replacement is None:
                    if target.exists():
                        remove_file(target)
                        sync_directory(target.parent)
                else:
                    source = (
                        FileSource(stage / "after" / str(number), replacement.sha256, replacement.size)
                        if isinstance(replacement, FileSource)
                        else replacement
                    )
                    atomic_write(target, source)
                    restore_mode(target, entries[number]["after_mode"])
                if fault:
                    fault("written", entries[number]["path"])
            for item in sorted(
                removals, key=lambda item: len(PurePosixPath(item["path"]).parts), reverse=True
            ):
                directory = root / item["path"]
                directory.rmdir()
                sync_directory(directory.parent)
            if fault:
                fault("removed_directories", None)
            for entry in entries:
                if file_digest(root / entry["path"]) != entry["after"]:
                    raise FreezeError("Migration output checksum mismatch")
            for name, checksum in (read_set or {}).items():
                if name not in writes and file_digest(safe_destination(root, name)) != checksum:
                    raise FreezeError("Project input changed during apply: " + name)
            if verify:
                verify()
            if fault:
                fault("verified", None)
            control["phase"] = "committed"
            save_control(stage, control)
            if fault:
                fault("committed", None)
        except Exception:
            recover_locked(root)
            raise
        clean_stage(root, stage)
        return {"changed_paths": list(writes), "recovered": False}
