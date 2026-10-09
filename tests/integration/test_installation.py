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
    # No dependency on the user's old checkout or private project Memory records.
    import ast
    import re

    baselines = {"oppen-project-steward": "b4ba3fd6a978fdb76abda64940f5262cf3ae1de6",
                 "stepwise-r-project": "7862191808b4149bd0b8d8ed039d70a3308d18c7"}
    for skill, revision in baselines.items():
        def original(path, revision=revision):
            return subprocess.check_output(["git", "show", f"{revision}:{path}"], cwd=ROOT).decode()

        entry = (ROOT / "skills" / skill / "SKILL.md").read_text()
        pattern = r"^## Decision Memory\n.*?(?=^## |\Z)"
        assert re.search(pattern, entry, re.M | re.S).group() == re.search(
            pattern, original("SKILL.md"), re.M | re.S).group()
        script = "scripts/" + skill.replace("-", "_") + ".py"
        # Only the pending-decision view changes for dependency readiness. All Memory
        # implementation and every other governance operation remain identical.
        def preserved(source):
            tree = ast.parse(source)
            tree.body = [node for node in tree.body
                         if not isinstance(node, ast.FunctionDef) or node.name != "list_pending_decisions"]
            return ast.dump(tree)
        assert preserved(original(script)) == preserved((ROOT / "skills" / skill / script).read_text())
