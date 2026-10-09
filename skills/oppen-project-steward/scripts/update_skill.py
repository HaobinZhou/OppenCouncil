#!/usr/bin/env python3
"""Check/update a Git-backed OppenCouncil installation using only Git and Python.

Bundled identically in both skills so either skill can be installed on its own.
The integration tests enforce parity. Project governance helpers are not invoked.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


SOURCE_URL = "https://github.com/HaobinZhou/OppenCouncil.git"
SKILLS = ("oppen-project-steward", "stepwise-r-project")


class UpdateError(RuntimeError):
    """An update cannot safely proceed; no destructive recovery is attempted."""


def git(root: Path, *args: str, allowed: tuple[int, ...] = (0,)) -> str:
    """Run bounded, noninteractive Git commands without shell interpolation."""
    env = os.environ.copy()
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR"):
        env.pop(key, None)
    env["GIT_TERMINAL_PROMPT"] = "0"
    # Hooks and automatic maintenance may write outside the update's file set.
    with tempfile.TemporaryDirectory(prefix="academic-skill-hooks-") as hooks:
        result = subprocess.run(
            ["git", "-C", str(root), "-c", f"core.hooksPath={hooks}",
             "-c", "maintenance.auto=false", "-c", "gc.auto=0", *args],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, timeout=120,
        )
    if result.returncode not in allowed:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise UpdateError(detail or f"Git {args[0]} failed ({result.returncode})")
    return result.stdout.decode("utf-8", "surrogateescape")


def source_matches(url: str) -> bool:
    """Accept the documented GitHub source over HTTPS or SSH, not arbitrary forks."""
    return url.rstrip("/").removesuffix(".git") in {
        SOURCE_URL.rstrip("/").removesuffix(".git"),
        "git@github.com:HaobinZhou/OppenCouncil",
        "ssh://git@github.com/HaobinZhou/OppenCouncil",
    }


def installation(skill_dir: Path) -> tuple[Path, Path]:
    """Resolve symlinks and prove that the target belongs to the source checkout."""
    skill_dir = skill_dir.expanduser().resolve(strict=True)
    if skill_dir.name not in SKILLS or not (skill_dir / "SKILL.md").is_file():
        raise UpdateError("Target must be an installed oppen-project-steward or stepwise-r-project skill")
    try:
        root = Path(git(skill_dir, "rev-parse", "--show-toplevel").strip()).resolve()
    except UpdateError as exc:
        raise UpdateError("UNSUPPORTED_INSTALL: automatic updates require the documented Git clone/symlink installation; preserve this copied installation") from exc
    if skill_dir != root / "skills" / skill_dir.name:
        raise UpdateError("UNSUPPORTED_INSTALL: skill must be in the product repository skills/ directory; see docs/migration.md")
    remotes = git(root, "remote").splitlines()
    if not any(source_matches(git(root, "remote", "get-url", name).strip()) for name in remotes):
        raise UpdateError("SOURCE_MISMATCH: no remote identifies HaobinZhou/OppenCouncil")
    return root, skill_dir


def dirty_paths(root: Path) -> list[str]:
    """Include staged, unstaged, untracked and ignored paths; disable rename records."""
    status = git(root, "status", "--porcelain=v1", "-z", "--no-renames",
                 "--untracked-files=all", "--ignored=matching")
    return sorted({record[3:].rstrip("/") for record in status.split("\0") if record})


def overlaps(path: str, other: str) -> bool:
    """Protect both a file and directory/file replacements at that path."""
    return path == other or path.startswith(other + "/") or other.startswith(path + "/")


def validate_candidate(root: Path, commit: str) -> None:
    """Check skill identities and Python syntax without executing downloaded code."""
    for name in SKILLS:
        skill = git(root, "show", f"{commit}:skills/{name}/SKILL.md")
        frontmatter = skill.split("---", 2)
        if (not skill.startswith("---\n") or len(frontmatter) < 3
                or not re.search(rf"^name: {re.escape(name)}$", frontmatter[1], re.M)):
            raise UpdateError(f"INVALID_CANDIDATE: missing skill identity for {name}")
        helper = name.replace("-", "_")
        ast.parse(git(root, "show", f"{commit}:skills/{name}/scripts/{helper}.py"))
    changed_python = git(root, "ls-tree", "-r", "--name-only", "-z", commit, "--", "skills", "council", "mcp", "scripts")
    for path in changed_python.split("\0"):
        if path.endswith(".py"):
            ast.parse(git(root, "show", f"{commit}:{path}"), filename=path)


def update(skill_dir: Path, *, apply: bool = False) -> dict:
    """Fetch the default branch, then fast-forward only if the write set is safe."""
    root, skill_dir = installation(skill_dir)
    for marker in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply", "sequencer"):
        if (root / git(root, "rev-parse", "--git-path", marker).strip()).exists():
            raise UpdateError(f"GIT_OPERATION_IN_PROGRESS: {marker}")
    branch = git(root, "symbolic-ref", "--quiet", "--short", "HEAD", allowed=(0, 1)).strip()
    if not branch:
        raise UpdateError("DETACHED_HEAD: select the intended local branch before updating")
    before = git(root, "rev-parse", "HEAD").strip()
    remote = git(root, "ls-remote", "--symref", SOURCE_URL, "HEAD")
    branch_match = re.search(r"^ref: (refs/heads/[^\s]+)\s+HEAD$", remote, re.M)
    sha_match = re.search(r"^([0-9a-f]{40,64})\s+HEAD$", remote, re.M)
    if not branch_match or not sha_match:
        raise UpdateError("SOURCE_UNAVAILABLE: cannot resolve GitHub's default branch and commit")
    target = sha_match[1]
    result = {
        "status": "UP_TO_DATE", "source": SOURCE_URL, "repository": str(root),
        "skill": skill_dir.name, "branch": branch, "upstream_branch": branch_match[1],
        "before": before, "upstream": target, "after": before,
        "scope": "shared OppenCouncil product checkout (all upstream changed paths)",
        "runtime_action": "After UPDATED, rerun scripts/install.py with the previously selected components; restart services separately.",
        "changed_paths": [], "local_changes": dirty_paths(root),
    }
    if before == target:
        return result
    # Fetch objects only; keep local branches and the worktree unchanged during checks.
    git(root, "fetch", "--no-tags", "--no-recurse-submodules", SOURCE_URL, target)
    base = git(root, "merge-base", before, target, allowed=(0, 1)).strip()
    if base == target:
        result["status"] = "LOCAL_AHEAD"
        return result
    if base != before:
        result.update(status="UPDATE_BLOCKED", reason="DIVERGED_HISTORY")
        return result
    changed = git(root, "diff", "--name-only", "--no-renames", "-z", before, target, "--").split("\0")
    result["changed_paths"] = sorted(path for path in changed if path)
    conflicts = [path for path in result["local_changes"]
                 if any(overlaps(path, other) for other in result["changed_paths"])]
    if conflicts:
        result.update(status="UPDATE_BLOCKED", reason="LOCAL_CHANGES_CONFLICT", conflicts=conflicts)
        return result
    validate_candidate(root, target)
    result["status"] = "UPDATE_AVAILABLE"
    if not apply:
        return result
    # Recheck the preflight immediately before mutation. Git protects the index too.
    if (git(root, "rev-parse", "HEAD").strip() != before
            or git(root, "symbolic-ref", "--quiet", "--short", "HEAD", allowed=(0, 1)).strip() != branch
            or dirty_paths(root) != result["local_changes"]):
        raise UpdateError("LOCAL_STATE_CHANGED: rerun the update check")
    git(root, "-c", "submodule.recurse=false", "merge", "--ff-only", "--no-edit",
        "--no-autostash", "--no-overwrite-ignore", target)
    result["after"] = git(root, "rev-parse", "HEAD").strip()
    if result["after"] != target:
        raise UpdateError("VERIFY_FAILED: installed HEAD does not match the checked upstream commit")
    result["status"] = "UPDATED"
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="Check only; fetch Git metadata without changing installed files")
    mode.add_argument("--apply", action="store_true", help="Check and install an available fast-forward update")
    parser.add_argument("--skill-dir", type=Path, default=Path(__file__).resolve().parents[1],
                        help="Installed skill directory; defaults to this script's skill, never the working project")
    args = parser.parse_args(argv)
    try:
        result = update(args.skill_dir, apply=args.apply)
    except (UpdateError, OSError, subprocess.TimeoutExpired, SyntaxError) as exc:
        print(json.dumps({"status": "UPDATE_BLOCKED", "reason": str(exc)}, ensure_ascii=True))
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 1 if result["status"] == "UPDATE_BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
