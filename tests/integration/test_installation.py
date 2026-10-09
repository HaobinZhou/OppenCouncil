"""Exercise installation boundaries with real directories, links and dry runs."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

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


@pytest.mark.parametrize("options,components", [
    ([], ["council"]), (["--with-mcp"], ["council", "mcp"]), (["--skills-only"], []),
])
def test_dry_run_has_no_filesystem_side_effects(tmp_path, options, components):
    destination = tmp_path / "skills"
    run = subprocess.run([sys.executable, str(ROOT / "scripts/install.py"), "--check",
                          "--skill-dir", str(destination), *options], capture_output=True, text=True)
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
        tree.body = [node for node in tree.body
                     if not isinstance(node, ast.FunctionDef) or node.name != "list_pending_decisions"]
        semantic_source = json.dumps(structure(tree), sort_keys=True, ensure_ascii=True)
        assert hashlib.sha256(semantic_source.encode()).hexdigest() == baseline["preserved_helper_ast_sha256"]
