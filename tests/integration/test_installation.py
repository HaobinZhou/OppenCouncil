"""Exercise installation boundaries with real directories, links and dry runs."""

import importlib.util
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.test_filesystem import sparse_truncate

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("product_install", ROOT / "scripts/install.py")
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


def test_existing_directory_blocks_all_link_changes(tmp_path):
    target = tmp_path / installer.SKILLS[1]
    target.mkdir()
    (target / "custom.md").write_text("Preserve local instructions")
    with pytest.raises(ValueError, match="Existing files"):
        installer.skill_plan(tmp_path, replace_links=True)
    assert not (tmp_path / installer.SKILLS[0]).exists()
    assert (target / "custom.md").read_text() == "Preserve local instructions"


def test_install_replace_and_repeat_preserve_old_source(tmp_path):
    destination = tmp_path / "installed"
    destination.mkdir()
    old = tmp_path / "old source"
    old.mkdir()
    (old / "SKILL.md").write_text("Preserved")
    try:
        (destination / installer.SKILLS[0]).symlink_to(old, target_is_directory=True)
    except OSError:
        pytest.skip("This host does not allow directory symlinks")
    with pytest.raises(ValueError, match="Existing link"):
        installer.skill_plan(destination)
    installer.install_links(installer.skill_plan(destination, replace_links=True))
    assert (old / "SKILL.md").read_text() == "Preserved"
    assert all(e["action"] == "unchanged" for e in installer.skill_plan(destination))
    for name in installer.SKILLS:
        assert (destination / name).resolve() == ROOT / "skills" / name


def test_windows_link_swap_rolls_back_without_touching_source(tmp_path, monkeypatch):
    destination = tmp_path / "installed"
    destination.mkdir()
    old = tmp_path / "old"
    old.mkdir()
    (old / "local.md").write_text("Keep me", encoding="utf-8")
    target = destination / installer.SKILLS[0]
    try:
        target.symlink_to(old, target_is_directory=True)
    except OSError:
        pytest.skip("This host does not allow directory symlinks")
    plan = installer.skill_plan(destination, replace_links=True)
    monkeypatch.setattr(installer, "IS_WINDOWS", True)
    rename = Path.rename

    def fail_install(path, to):
        if path.name.endswith(".install-link"):
            raise OSError("synthetic rename failure")
        return rename(path, to)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "rename", fail_install)
        with pytest.raises(OSError, match="synthetic"):
            installer.install_links(plan)
    assert target.is_symlink() and target.resolve() == old.resolve()
    assert (old / "local.md").read_text(encoding="utf-8") == "Keep me"
    assert not target.with_name(target.name + ".previous-link").exists()
    installer.install_links(plan)
    assert target.resolve() == ROOT / "skills" / installer.SKILLS[0]


def test_later_link_failure_rolls_back_the_whole_installation(tmp_path, monkeypatch):
    destination = tmp_path / "installed"
    destination.mkdir()
    for name in installer.SKILLS:
        old = tmp_path / "old" / name
        old.mkdir(parents=True)
        (old / "instructions.txt").write_text("Preserve old installation")
        (destination / name).symlink_to(old, target_is_directory=True)
    plan = installer.skill_plan(destination, replace_links=True)
    rename = Path.rename

    def fail_last(path, target):
        if path.name == installer.SKILLS[-1] + ".install-link":
            raise OSError("late swap failed")
        return rename(path, target)

    monkeypatch.setattr(Path, "rename", fail_last)
    with pytest.raises(OSError, match="late swap"):
        installer.install_links(plan)
    for name in installer.SKILLS:
        assert (destination / name).resolve() == tmp_path / "old" / name
        assert (destination / name / "instructions.txt").read_text() == "Preserve old installation"
    assert sorted(p.name for p in destination.iterdir()) == sorted(installer.SKILLS)


def test_install_rechecks_target_after_plan(tmp_path):
    destination = tmp_path / "installed"
    plan = installer.skill_plan(destination)
    target = destination / installer.SKILLS[-1]
    target.mkdir(parents=True)
    (target / "custom.md").write_text("New user content after check")
    with pytest.raises(ValueError, match="changed since preflight"):
        installer.install_links(plan)
    assert not (destination / installer.SKILLS[0]).exists()
    assert (target / "custom.md").read_text() == "New user content after check"


def test_install_rollback_preserves_a_concurrent_user_replacement(tmp_path, monkeypatch):
    destination = tmp_path / "installed"
    destination.mkdir()
    old = tmp_path / "old"
    old.mkdir()
    first = destination / installer.SKILLS[0]
    first.symlink_to(old, target_is_directory=True)
    plan = installer.skill_plan(destination, replace_links=True)
    rename = Path.rename

    def concurrent_change(path, target):
        if path.name == installer.SKILLS[-1] + ".install-link":
            first.unlink()
            first.write_text("Concurrent user content")
            raise OSError("late swap failed")
        return rename(path, target)

    monkeypatch.setattr(Path, "rename", concurrent_change)
    with pytest.raises(ValueError, match="preserved recovery links"):
        installer.install_links(plan)
    assert first.read_text() == "Concurrent user content"
    assert first.with_name(first.name + ".previous-link").resolve() == old
    assert not (destination / installer.SKILLS[1]).exists()


def test_installed_aliases_run_the_shared_helper_without_migrating_old_sources(tmp_path):
    destination = tmp_path / "installed"
    result = subprocess.run([sys.executable, str(ROOT / "scripts/install.py"), "--skills-only",
                             "--skill-dir", str(destination)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr + result.stdout
    project = tmp_path / "analysis"
    entry = destination / "oppencouncil/scripts/oppencouncil.py"
    result = subprocess.run([sys.executable, str(entry), "init", str(project), "--project-type", "research"],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    for name in installer.SKILLS:
        entry = destination / name / "scripts" / (name.replace("-", "_") + ".py")
        result = subprocess.run([sys.executable, str(entry), "project-type", str(project)],
                                capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["project_type"] == "research"


def test_standalone_shared_entry_uses_package_without_safe_path_flag(tmp_path):
    import shutil

    # Unlike checkout symlinks, a standalone skill has no adjacent council/.
    entry = tmp_path / "standalone/skills/oppencouncil/scripts/oppencouncil.py"
    entry.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / "skills/oppencouncil/scripts/oppencouncil.py", entry)
    env = dict(os.environ, PYTHONPATH=str(ROOT / "council"))
    env.pop("PYTHONSAFEPATH", None)
    project = tmp_path / "standalone-project"
    for arguments in (
        ["init", str(project), "--project-type", "general"],
        ["memory", "index", str(project)],
    ):
        run = subprocess.run([sys.executable, str(entry), *arguments], env=env,
                             capture_output=True, text=True)
        assert run.returncode == 0, run.stdout + run.stderr
    assert json.loads(run.stdout) == []


def test_large_fixture_is_really_sparse_on_each_platform(tmp_path):
    path = tmp_path / "huge.bin"
    try:
        with path.open("w+b") as handle:
            sparse_truncate(handle, 5 * 1024**4)
        info = path.stat()
        assert info.st_size == 5 * 1024**4
        if os.name == "nt":
            assert info.st_file_attributes & stat.FILE_ATTRIBUTE_SPARSE_FILE
        else:
            assert info.st_blocks * 512 < 1024 * 1024
    finally:
        # pytest retains tmp_path after success and failure. Do not leave a
        # multi-terabyte sparse file for later copy/export tools to materialize.
        path.unlink(missing_ok=True)


@pytest.mark.parametrize("skill", installer.SKILLS)
def test_chinese_cli_paths_use_utf8_even_in_legacy_pipes(tmp_path, skill):
    project = tmp_path / "中文项目"
    script = ROOT / "skills" / skill / "scripts" / (skill.replace("-", "_") + ".py")
    env = {**os.environ, "PYTHONIOENCODING": "cp1252", "PYTHONUTF8": "0"}
    extra = ["--project-type", "general"] if skill == "oppencouncil" else []
    initialized = subprocess.run([sys.executable, str(script), "init", str(project), *extra],
                                 env=env, capture_output=True)
    assert initialized.returncode == 0, initialized.stderr.decode("utf-8")
    assert "中文项目" in initialized.stdout.decode("utf-8")
    registered = subprocess.run([sys.executable, "-m", "oppencouncil", "--directory",
                                 str(tmp_path / "站点"), "register", str(project)], env=env,
                                capture_output=True)
    assert registered.returncode == 0, registered.stderr.decode("utf-8")
    assert json.loads(registered.stdout.decode("utf-8"))["name"] == "中文项目"


@pytest.mark.parametrize("options,components", [
    ([], ["council"]), (["--with-mcp"], ["council", "mcp"]), (["--skills-only"], []),
])
def test_dry_run_has_no_filesystem_side_effects(tmp_path, options, components):
    destination = tmp_path / "skills"
    run = subprocess.run([sys.executable, str(ROOT / "scripts/install.py"), "--check",
                          "--skill-dir", str(destination), *options],
                         capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 0, run.stdout + run.stderr
    report = json.loads(run.stdout)
    assert report["components"] == components
    assert not destination.exists()


def test_memory_contract_matches_approved_baseline():
    # Hash the actual approved skill section, not the design document or a copy.
    import hashlib
    import re

    baseline = json.loads((Path(__file__).with_name("governance-baseline.json")).read_text(
        encoding="utf-8"))["memory_contract"]
    entry = (ROOT / baseline["path"]).read_text(encoding="utf-8")
    sections = re.findall(r"^## Decision Memory\n.*?(?=^## |\Z)", entry, re.M | re.S)
    assert len(sections) == 1
    assert hashlib.sha256(sections[0].encode("utf-8")).hexdigest() == baseline["sha256"]


def test_legacy_memory_implementations_match_imported_baseline():
    # OPP-20 narrows the lock to Memory functions and their schemas. The hashes
    # were extracted from the unchanged 4.3.1 source, not blessed from new code.
    # Shared infrastructure and other governance operations use behavior tests.
    import ast
    import hashlib

    baselines = json.loads((Path(__file__).with_name("governance-baseline.json")).read_text(
        encoding="utf-8"))["legacy_helpers"]

    def structure(node):
        if isinstance(node, ast.AST):
            return {"type": type(node).__name__, **{
                key: structure(value) for key, value in ast.iter_fields(node)
                if value is not None and value != []
            }}
        if isinstance(node, list):
            return [structure(item) for item in node]
        if isinstance(node, (bytes, complex)) or node is Ellipsis:
            return {"literal": repr(node)}
        return node

    for baseline in baselines.values():
        tree = ast.parse((ROOT / baseline["path"]).read_text(encoding="utf-8"))
        nodes = {}
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                nodes[node.name] = node
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                for name in ast.walk(node):
                    if isinstance(name, ast.Name) and isinstance(name.ctx, ast.Store):
                        nodes[name.id] = node
        selected = {name: structure(nodes[name]) for name in baseline["memory_nodes"]}
        semantic_source = json.dumps(selected, sort_keys=True, ensure_ascii=True)
        assert hashlib.sha256(semantic_source.encode()).hexdigest() == baseline["memory_ast_sha256"]
