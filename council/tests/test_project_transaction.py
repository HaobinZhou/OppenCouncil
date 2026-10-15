"""Crash a real process and recover only the declared project migration write set."""

import hashlib
import json
import os
import stat
import subprocess
import sys
from types import SimpleNamespace

import pytest

from oppencouncil import project_transaction as tx
from oppencouncil.store import FreezeError


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "项目"
    root.mkdir()
    (root / "project.md").write_bytes(b"Original registry\n")
    (root / "obsolete-index.md").write_bytes(b"Original index\n")
    (root / "Data").mkdir()
    (root / "Data/input.bin").write_bytes(b"Untouched source data")
    os.chmod(root / "project.md", 0o644)
    return root


def plan(project):
    writes = {"project.md": b"New registry\n", "Freeze/nested/item.json": b"{}\n", "obsolete-index.md": None}
    return writes, {name: tx.digest(tx.read_bytes(project / name)) for name in writes}


def crash_process(project, phase):
    script = """
import os, sys
from pathlib import Path
from oppencouncil import project_transaction as tx
root=Path(sys.argv[1])
writes={"project.md": b"New registry\\n", "Freeze/nested/item.json": b"{}\\n", "obsolete-index.md": None}
expected={name:tx.digest(tx.read_bytes(root/name)) for name in writes}
def crash(phase,path):
    if phase == sys.argv[2]:
        os._exit(73)
tx.apply(root,writes,expected=expected,fault=crash)
"""
    run = subprocess.run([sys.executable, "-c", script, str(project), phase], capture_output=True, text=True)
    assert run.returncode == 73, run.stderr
    assert (project / tx.STAGING).is_dir()


def assert_original(project):
    assert (project / "project.md").read_bytes() == b"Original registry\n"
    assert (project / "obsolete-index.md").read_bytes() == b"Original index\n"
    assert not (project / "Freeze").exists()
    assert (project / "Data/input.bin").read_bytes() == b"Untouched source data"
    if os.name != "nt":
        assert stat.S_IMODE((project / "project.md").stat().st_mode) == 0o644


@pytest.mark.parametrize("phase", ["prepared", "written", "verified"])
def test_interrupted_process_is_rolled_back_on_recovery(project, phase):
    crash_process(project, phase)
    result = tx.recover(project)
    assert result == {"recovered": True, "action": "rollback"}
    assert_original(project)
    assert not (project / tx.STAGING).exists()
    assert tx.recover(project) == {"recovered": False}


def test_committed_crash_only_cleans_recovery_area(project):
    crash_process(project, "committed")
    assert tx.recover(project)["action"] == "cleanup_committed"
    assert (project / "project.md").read_bytes() == b"New registry\n"
    assert (project / "Freeze/nested/item.json").read_bytes() == b"{}\n"
    assert not (project / "obsolete-index.md").exists()
    assert (project / "Data/input.bin").read_bytes() == b"Untouched source data"


def test_input_change_during_write_rolls_back_only_managed_files(project):
    writes, expected = plan(project)
    source = project / "Data/input.bin"
    reads = {"Data/input.bin": tx.digest(source.read_bytes())}

    def change_input(phase, path):
        if phase == "written":
            source.write_bytes(b"New independent input")

    with pytest.raises(FreezeError, match="input changed during apply"):
        tx.apply(project, writes, expected=expected, read_set=reads, fault=change_input)
    assert (project / "project.md").read_bytes() == b"Original registry\n"
    assert not (project / "Freeze").exists()
    assert source.read_bytes() == b"New independent input"


def test_conflicting_explicit_directory_is_rejected_before_staging(project):
    with pytest.raises(FreezeError, match="both a file and a directory"):
        tx.apply(project, {"same": b"file"}, expected={"same": None}, create_directories=["same"])
    assert not (project / tx.STAGING).exists()


def test_large_read_dependency_is_never_loaded_as_one_blob(project, monkeypatch):
    source = project / "Data/input.bin"
    with source.open("wb") as handle:
        for _ in range(17):
            handle.write(b"x" * 1024 * 1024)
    reads = {"Data/input.bin": tx.file_digest(source)}
    old_reader = tx.read_bytes

    def bounded_reader(path):
        assert path != source, "Read dependencies must be streamed, not staged as full file blobs"
        return old_reader(path)

    monkeypatch.setattr(tx, "read_bytes", bounded_reader)
    writes, expected = plan(project)
    tx.apply(project, writes, expected=expected, read_set=reads)
    assert tx.file_digest(source) == reads["Data/input.bin"]


def test_validation_failure_rolls_back_without_waiting_for_another_command(project):
    writes, expected = plan(project)

    def fail():
        raise ValueError("candidate validation failed")

    with pytest.raises(ValueError, match="validation failed"):
        tx.apply(project, writes, expected=expected, verify=fail)
    assert_original(project)
    assert not (project / tx.STAGING).exists()


def test_stale_check_does_not_start_migration(project):
    writes, expected = plan(project)
    (project / "project.md").write_bytes(b"Concurrent edit")
    with pytest.raises(FreezeError, match="changed since check"):
        tx.apply(project, writes, expected=expected)
    assert (project / "project.md").read_bytes() == b"Concurrent edit"
    assert not (project / tx.STAGING).exists()


def test_recovery_reports_later_edits_and_keeps_preimages(project):
    crash_process(project, "verified")
    (project / "project.md").write_bytes(b"Later user work")
    with pytest.raises(FreezeError, match="conflicts with later edits"):
        tx.recover(project)
    assert (project / "project.md").read_bytes() == b"Later user work"
    assert (project / "Freeze/nested/item.json").read_bytes() == b"{}\n"
    assert (project / tx.STAGING / "before/0").read_bytes() == b"Original registry\n"


def test_corrupt_preimage_blocks_every_restore(project):
    crash_process(project, "verified")
    (project / tx.STAGING / "before/2").write_bytes(b"Damaged")
    with pytest.raises(FreezeError, match="preimage checksum"):
        tx.recover(project)
    assert (project / "project.md").read_bytes() == b"New registry\n"
    assert not (project / "obsolete-index.md").exists()


def test_migration_larger_than_freeze_journal_limit_is_supported(project):
    data = b"x" * (17 * 1024 * 1024)
    writes = {"large-record.json": data}
    tx.apply(project, writes, expected={"large-record.json": None})
    assert (project / "large-record.json").read_bytes() == data
    assert not (project / tx.STAGING).exists()
    # Existing large files must also support replacement and rollback.
    tx.apply(project, writes, expected={"large-record.json": tx.digest(data)})
    with pytest.raises(ValueError, match="rollback large"):
        tx.apply(
            project,
            {"large-record.json": b"short"},
            expected={"large-record.json": tx.digest(data)},
            verify=lambda: (_ for _ in ()).throw(ValueError("rollback large")),
        )
    assert (project / "large-record.json").read_bytes() == data


def test_read_dependency_change_blocks_write(project):
    writes, expected = plan(project)
    reads = {"Data/input.bin": tx.digest((project / "Data/input.bin").read_bytes())}
    (project / "Data/input.bin").write_bytes(b"Changed after planning")
    with pytest.raises(FreezeError, match="input changed since check"):
        tx.apply(project, writes, expected=expected, read_set=reads)
    assert (project / "project.md").read_bytes() == b"Original registry\n"


def test_link_or_path_escape_never_stages_external_files(project, tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"Private outside file")
    for name in ("../outside.txt", "/absolute", ".git/config", "Data/../project.md"):
        with pytest.raises(FreezeError):
            tx.apply(project, {name: b"bad"}, expected={name: None})
    try:
        (project / "linked").symlink_to(outside)
    except OSError:
        pytest.skip("Symlinks unavailable")
    with pytest.raises(FreezeError, match="links"):
        tx.apply(project, {"linked": b"bad"}, expected={"linked": tx.digest(outside.read_bytes())})
    assert outside.read_bytes() == b"Private outside file"


def test_recovery_rejects_a_control_record_copied_from_another_root(project):
    crash_process(project, "prepared")
    control = project / tx.STAGING / "transaction.json"
    value = json.loads(control.read_bytes())
    value["root"] = str(project.parent)
    control.write_text(json.dumps(value))
    with pytest.raises(FreezeError, match="transaction identity"):
        tx.recover(project)
    assert_original(project)


def test_linked_preimages_are_rejected_before_any_restore(project):
    crash_process(project, "verified")
    stage = project / tx.STAGING
    (stage / "before").rename(stage / "original-preimages")
    try:
        (stage / "before").symlink_to(stage / "original-preimages", target_is_directory=True)
    except OSError:
        pytest.skip("Symlinks unavailable")
    with pytest.raises(FreezeError, match="must not be linked"):
        tx.recover(project)
    assert (project / "project.md").read_bytes() == b"New registry\n"


def test_digest_accepts_repeated_atomic_replacement(tmp_path):
    path = tmp_path / "transaction.json"
    for value in (b'{"state":"prepared"}', b'{"state":"complete"}'):
        tx.atomic_write(path, value)
        assert tx.file_digest(path) == hashlib.sha256(value).hexdigest()


def test_restore_mode_preserves_contents_and_read_only_state(tmp_path):
    path = tmp_path / "release.zip"
    path.write_bytes(b"immutable release")
    try:
        for mode in (0o444, 0o444, 0o600):
            tx.restore_mode(path, mode)
            assert path.read_bytes() == b"immutable release"
            assert bool(path.stat().st_mode & stat.S_IWRITE) == bool(mode & stat.S_IWRITE)
    finally:
        os.chmod(path, stat.S_IREAD | stat.S_IWRITE)


@pytest.mark.parametrize("persistent", [False, True])
def test_windows_pending_delete_cleanup_is_bounded(tmp_path, monkeypatch, persistent):
    stage = tmp_path / tx.STAGING
    stage.mkdir()
    (stage / "transaction.json").write_bytes(b"committed state")
    real_remove = tx.shutil.rmtree
    attempts = []

    def remove(path):
        attempts.append(path)
        if persistent or len(attempts) == 1:
            error = OSError("Windows directory still has a pending deletion")
            error.winerror = 145
            raise error
        real_remove(path)

    with monkeypatch.context() as patch:
        patch.setattr(tx.os, "name", "nt")
        patch.setattr(tx.shutil, "rmtree", remove)
        patch.setattr(tx.time, "sleep", lambda _: None)
        if persistent:
            with pytest.raises(OSError, match="pending deletion"):
                tx.clean_stage(tmp_path, stage)
            assert len(attempts) == 6 and stage.exists()
        else:
            tx.clean_stage(tmp_path, stage)
            assert len(attempts) == 2 and not stage.exists()


@pytest.mark.parametrize("changed_field", [None, "st_ctime_ns", "st_nlink"])
def test_windows_stat_clocks_differ_but_handle_changes_still_fail(tmp_path, monkeypatch, changed_field):
    path = tmp_path / "input.bin"
    path.write_bytes(b"stable contents")
    real_fstat = os.fstat
    calls = 0

    def handle_stat(fd):
        nonlocal calls
        info = real_fstat(fd)
        values = {
            key: getattr(info, key)
            for key in ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns", "st_nlink")
        }
        # Model the observed native Windows creation/change-time distinction.
        values["st_ctime_ns"] += 1000
        calls += 1
        if calls == 2 and changed_field:
            values[changed_field] += 1
        return SimpleNamespace(**values)

    with monkeypatch.context() as patch:
        patch.setattr(tx.os, "name", "nt")
        patch.setattr(tx.os, "fstat", handle_stat)
        if changed_field:
            with pytest.raises(FreezeError, match="changed while reading"):
                tx.file_digest(path)
        else:
            assert tx.file_digest(path) == hashlib.sha256(b"stable contents").hexdigest()
