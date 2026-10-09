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


def test_large_fixture_is_really_sparse_on_each_platform(tmp_path):
    path = tmp_path / "huge.bin"
    with path.open("w+b") as handle:
        sparse_truncate(handle, 5 * 1024**4)
    info = path.stat()
    assert info.st_size == 5 * 1024**4
    if os.name == "nt":
        assert info.st_file_attributes & stat.FILE_ATTRIBUTE_SPARSE_FILE
    else:
        assert info.st_blocks * 512 < 1024 * 1024


@pytest.mark.parametrize("skill", installer.SKILLS)
def test_chinese_cli_paths_use_utf8_even_in_legacy_pipes(tmp_path, skill):
    project = tmp_path / "中文项目"
    script = ROOT / "skills" / skill / "scripts" / (skill.replace("-", "_") + ".py")
    env = {**os.environ, "PYTHONIOENCODING": "cp1252", "PYTHONUTF8": "0"}
    initialized = subprocess.run([sys.executable, str(script), "init", str(project)],
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


def test_memory_contract_and_implementation_match_imported_baseline():
    # Source fingerprints retain the import check without publishing old Git history
    # or any private project Memory records. Other tests exercise Memory behavior.
    import ast
    import hashlib
    import re

    baselines = json.loads((Path(__file__).with_name("governance-baseline.json")).read_text(encoding="utf-8"))

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

    for skill, baseline in baselines.items():
        entry = (ROOT / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
        pattern = r"^## Decision Memory\n.*?(?=^## |\Z)"
        section = re.search(pattern, entry, re.M | re.S).group()
        assert hashlib.sha256(section.encode()).hexdigest() == baseline["memory_contract_sha256"]
        script = "scripts/" + skill.replace("-", "_") + ".py"
        tree = ast.parse((ROOT / "skills" / skill / script).read_text(encoding="utf-8"))
        # The only added CLI adapter configures UTF-8 streams before existing work.
        # Keep comparing every governance operation, including all Memory code.
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == "main":
                first = node.body[0]
                assert isinstance(first, ast.Expr) and isinstance(first.value, ast.Call)
                assert isinstance(first.value.func, ast.Name)
                assert first.value.func.id == "configure_cli_output"
                node.body.pop(0)
        tree.body = [node for node in tree.body
                     if not isinstance(node, ast.FunctionDef)
                     or node.name not in {"list_pending_decisions", "configure_cli_output"}]
        semantic_source = json.dumps(structure(tree), sort_keys=True, ensure_ascii=True)
        assert hashlib.sha256(semantic_source.encode()).hexdigest() == baseline["preserved_helper_ast_sha256"]
