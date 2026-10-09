"""Exercise both bundled updaters against real, isolated Git repositories."""

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2] / "skills"
SKILLS = ("oppen-project-steward", "stepwise-r-project")


def git(root, *args):
    env = os.environ.copy()
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
               GIT_AUTHOR_NAME="Test", GIT_AUTHOR_EMAIL="test@example.invalid",
               GIT_COMMITTER_NAME="Test", GIT_COMMITTER_EMAIL="test@example.invalid")
    return subprocess.check_output(["git", "-C", str(root), *args], env=env,
                                   stderr=subprocess.PIPE).decode().strip()


def write(root, path, content):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def commit(root, message="change"):
    git(root, "add", "-A")
    git(root, "commit", "-qm", message)
    return git(root, "rev-parse", "HEAD")


def snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob("*") if p.is_file() and ".git" not in p.relative_to(root).parts}


@pytest.fixture(params=SKILLS)
def setup(tmp_path, request, monkeypatch):
    # Isolate the updater's subprocesses from user Git configuration too.
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    script = ROOT / request.param / "scripts/update_skill.py"
    spec = importlib.util.spec_from_file_location(request.param + "_update", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = tmp_path / "source with spaces"
    source.mkdir()
    git(source, "init", "-b", "release")
    for skill in SKILLS:
        write(source, f"skills/{skill}/SKILL.md", f"---\nname: {skill}\ndescription: Fixture\n---\nOld instructions\n")
        write(source, f"skills/{skill}/scripts/{skill.replace('-', '_')}.py", "print('old')\n")
    write(source, "notes.txt", "original notes\n")
    write(source, ".gitignore", "cache/\n")
    before = commit(source, "initial")
    clone = tmp_path / "installed checkout"
    git(tmp_path, "clone", str(source), str(clone))
    monkeypatch.setattr(module, "SOURCE_URL", str(source))
    return module, source, clone, clone / "skills" / request.param, before


def publish(source):
    write(source, "skills/oppen-project-steward/SKILL.md",
          "---\nname: oppen-project-steward\ndescription: Fixture\n---\nNew instructions\n")
    write(source, "skills/stepwise-r-project/scripts/stepwise_r_project.py", "print('new')\n")
    return commit(source, "upstream update")


def test_bundles_stay_self_contained_and_identical():
    assert (ROOT / SKILLS[0] / "scripts/update_skill.py").read_bytes() == (
        ROOT / SKILLS[1] / "scripts/update_skill.py").read_bytes()


def test_check_then_apply_and_repeat(setup):
    module, source, clone, skill, before = setup
    expected = publish(source)
    original = snapshot(clone)
    checked = module.update(skill)
    assert checked["status"] == "UPDATE_AVAILABLE"
    assert checked["upstream_branch"] == "refs/heads/release"
    assert checked["upstream"] == expected
    assert snapshot(clone) == original
    assert git(clone, "rev-parse", "HEAD") == before
    applied = module.update(skill, apply=True)
    assert applied["status"] == "UPDATED"
    assert applied["after"] == expected == git(clone, "rev-parse", "HEAD")
    assert snapshot(clone) == snapshot(source)
    assert module.update(skill, apply=True)["status"] == "UP_TO_DATE"


def test_no_update_preserves_local_edits(setup):
    module, _, clone, skill, before = setup
    write(clone, "skills/oppen-project-steward/SKILL.md", "local instructions\n")
    original = snapshot(clone)
    report = module.update(skill, apply=True)
    assert report["status"] == "UP_TO_DATE"
    assert report["local_changes"] == ["skills/oppen-project-steward/SKILL.md"]
    assert snapshot(clone) == original
    assert git(clone, "rev-parse", "HEAD") == before


@pytest.mark.parametrize("kind", ["unstaged", "staged", "untracked", "ignored", "directory"])
def test_overlap_blocks_without_mutating_installation(setup, kind):
    module, source, clone, skill, before = setup
    if kind in ("unstaged", "staged"):
        path = "skills/oppen-project-steward/SKILL.md"
        publish(source)
    else:
        path = "cache/payload.txt" if kind == "ignored" else "incoming"
        write(source, path, "upstream\n")
        git(source, "add", "-f", path)
        commit(source)
    local = path + "/child.txt" if kind == "directory" else path
    write(clone, local, "user work\n")
    if kind == "staged":
        git(clone, "add", path)
    original = snapshot(clone)
    index = git(clone, "diff", "--cached", "--binary")
    report = module.update(skill, apply=True)
    assert report["status"] == "UPDATE_BLOCKED"
    assert report["reason"] == "LOCAL_CHANGES_CONFLICT"
    assert snapshot(clone) == original
    assert git(clone, "diff", "--cached", "--binary") == index
    assert git(clone, "rev-parse", "HEAD") == before


def test_unrelated_staged_unstaged_untracked_and_ignored_work_survives(setup):
    module, source, clone, skill, _ = setup
    publish(source)
    write(clone, "notes.txt", "staged user work\n")
    git(clone, "add", "notes.txt")
    write(clone, "notes.txt", "unstaged user work\n")
    write(clone, "user/untracked.txt", "untracked user work\n")
    write(clone, "cache/ignored.txt", "ignored user work\n")
    original = snapshot(clone)
    index = git(clone, "diff", "--cached", "--binary")
    assert module.update(skill, apply=True)["status"] == "UPDATED"
    assert git(clone, "diff", "--cached", "--binary") == index
    for path in ("notes.txt", "user/untracked.txt", "cache/ignored.txt"):
        assert (clone / path).read_bytes() == original[path]


@pytest.mark.parametrize("diverged", [False, True])
def test_local_commits_are_never_rewritten(setup, diverged):
    module, source, clone, skill, _ = setup
    write(clone, "notes.txt", "local commit\n")
    local_head = commit(clone)
    if diverged:
        publish(source)
    original = snapshot(clone)
    result = module.update(skill, apply=True)
    assert result["status"] == ("UPDATE_BLOCKED" if diverged else "LOCAL_AHEAD")
    assert git(clone, "rev-parse", "HEAD") == local_head
    assert snapshot(clone) == original


def test_symlink_resolves_installation_independent_of_working_project(setup, tmp_path, monkeypatch):
    module, source, clone, skill, _ = setup
    link = tmp_path / "skills" / skill.name
    link.parent.mkdir()
    try:
        link.symlink_to(skill, target_is_directory=True)
    except OSError:
        pytest.skip("Creating directory symlinks is unavailable")
    project = tmp_path / "scientific project"
    project.mkdir()
    write(project, "Data/patients.txt", "untouched project data\n")
    original = snapshot(project)
    monkeypatch.chdir(project)
    publish(source)
    assert module.update(link, apply=True)["repository"] == str(clone.resolve())
    assert snapshot(project) == original


@pytest.mark.parametrize("problem", ["copied", "wrong-source", "detached", "in-progress", "offline", "invalid-python"])
def test_blockers_are_not_reported_as_up_to_date(setup, problem, tmp_path, capsys):
    module, source, clone, skill, before = setup
    if problem == "copied":
        copy = tmp_path / "copy" / skill.name
        shutil.copytree(skill, copy)
        skill = copy
    elif problem == "wrong-source":
        git(clone, "remote", "set-url", "origin", "https://github.com/example/unrelated.git")
    elif problem == "detached":
        git(clone, "checkout", "--detach")
    elif problem == "in-progress":
        (clone / ".git/MERGE_HEAD").write_text(before + "\n")
    elif problem == "offline":
        source.rename(source.with_name("unavailable"))
    elif problem == "invalid-python":
        write(source, "skills/stepwise-r-project/scripts/stepwise_r_project.py", "def broken(\n")
        commit(source)
    original = snapshot(clone)
    assert module.main(["--skill-dir", str(skill), "--apply"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "UPDATE_BLOCKED"
    assert report["reason"]
    assert snapshot(clone) == original
    assert git(clone, "rev-parse", "HEAD") == before


def test_cli_defaults_to_its_skill_not_cwd(setup, tmp_path):
    module, source, clone, skill, _ = setup
    script = skill / "scripts/update_skill.py"
    shutil.copyfile(Path(module.__file__), script)
    # Use Git's URL rewriting for an offline CLI integration, without a source override flag.
    official = "https://github.com/HaobinZhou/OppenCouncil.git"
    git(clone, "remote", "set-url", "origin", official)
    git(clone, "config", f"url.{source}.insteadOf", official)
    # remote get-url expands insteadOf, so prove source via a second literal URL form.
    git(clone, "remote", "add", "identity", "git@github.com:HaobinZhou/OppenCouncil.git")
    result = subprocess.run([sys.executable, str(script), "--check"], cwd=tmp_path,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["repository"] == str(clone.resolve())
