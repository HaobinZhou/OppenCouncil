#!/usr/bin/env python3
"""Install OppenCouncil and its compatibility skill names, with optional MCP."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ("oppencouncil", "oppen-project-steward", "stepwise-r-project")
IS_WINDOWS = os.name == "nt"


def python_in(component: str) -> Path:
    return ROOT / component / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def skill_plan(destination: Path, replace_links: bool = False) -> list[dict]:
    """Preflight all destinations before installing or replacing any links."""
    result = []
    for name in SKILLS:
        source = ROOT / "skills" / name
        if not (source / "SKILL.md").is_file():
            raise ValueError(f"Incomplete skill bundle: {source}")
        target = destination / name
        action = "link"
        if target.is_symlink():
            if target.resolve() == source.resolve():
                action = "unchanged"
            elif replace_links:
                action = "replace-link"
            else:
                raise ValueError(f"Existing link at {target}; review it and use --replace-existing-links")
        elif target.exists():
            raise ValueError(f"Existing files at {target}; preserve and reconcile this installation manually")
        result.append({"source": str(source), "target": str(target), "action": action,
                       "previous": str(target.readlink()) if target.is_symlink() else None})
    return result


def install_links(plan: list[dict]) -> None:
    """Prepare every link, then publish the set with rollback on a failed swap."""
    prepared, moved, published = [], [], []

    def unchanged(entry, target):
        observed = str(target.readlink()) if target.is_symlink() else None
        return observed == entry["previous"] and (observed is not None or not target.exists())

    try:
        for entry in plan:
            target = Path(entry["target"])
            if not unchanged(entry, target):
                raise ValueError(f"Installation target changed since preflight: {target}")
            if entry["action"] == "unchanged":
                continue
            source = Path(entry["source"])
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(target.name + ".install-link")
            previous = target.with_name(target.name + ".previous-link")
            if any(p.exists() or p.is_symlink() for p in (temporary, previous)):
                raise ValueError(f"Unresolved installer link at {target}")
            temporary.symlink_to(source, target_is_directory=True)
            prepared.append((entry, target, temporary, previous))
        for entry, target, temporary, previous in prepared:
            if not unchanged(entry, target):
                raise ValueError(f"Installation target changed since preflight: {target}")
            if entry["previous"] is not None:
                # Also works on Windows, where replacing a directory link fails.
                target.rename(previous)
                moved.append((target, previous))
            # Windows readlink may return a native \\?\ prefix. Keep the actual
            # link text we published so rollback recognizes our own link.
            link_text = temporary.readlink()
            temporary.rename(target)
            published.append((target, link_text))
    except (OSError, ValueError) as error:
        conflicts = []
        for target, source in reversed(published):
            if target.is_symlink() and target.readlink() == source:
                target.unlink()
            else:
                conflicts.append(str(target))
        for target, previous in reversed(moved):
            if not target.exists() and not target.is_symlink():
                previous.rename(target)
            else:
                conflicts.append(str(target))
        if conflicts:
            raise ValueError("Installation changed during rollback; preserved recovery links: "
                             + ", ".join(sorted(set(conflicts)))) from error
        raise
    finally:
        for _, _, temporary, _ in prepared:
            if temporary.is_symlink():
                temporary.unlink()
    # A cleanup failure leaves all installed links pointing to the same new bundle.
    for _, previous in moved:
        previous.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--with-mcp", action="store_true", help="Also install the optional MCP runtime")
    parser.add_argument("--skills-only", action="store_true", help="Install skill links without runtimes")
    parser.add_argument("--no-skills", action="store_true", help="Install runtimes without skill links")
    parser.add_argument("--skill-dir", type=Path, default=Path.home() / ".codex/skills")
    parser.add_argument("--replace-existing-links", action="store_true", help="Replace reviewed symlinks")
    parser.add_argument("--dev", action="store_true", help="Include tools needed by scripts/verify.py")
    parser.add_argument("--python", help="Python interpreter/version for uv (MCP requires 3.12+)")
    parser.add_argument("--check", action="store_true", help="Preview without writes or fetching")
    args = parser.parse_args(argv)
    if args.skills_only and (args.with_mcp or args.no_skills):
        parser.error("--skills-only cannot be combined with --with-mcp or --no-skills")
    try:
        plan = [] if args.no_skills else skill_plan(
            args.skill_dir.expanduser().absolute(), args.replace_existing_links
        )
        components = [] if args.skills_only else ["council"] + (["mcp"] if args.with_mcp else [])
        uv = shutil.which("uv")
        if components and not uv and not args.check:
            raise ValueError("Install uv first: https://docs.astral.sh/uv/getting-started/installation/")
        commands = [
            [uv or "uv", "sync", "--project", str(ROOT / component), "--locked",
             "--dev" if args.dev else "--no-dev"] + (["--python", args.python] if args.python else [])
            for component in components
        ]
        if not args.check:
            for command in commands:
                subprocess.run(command, cwd=ROOT, check=True)
            install_links(plan)
        print(json.dumps({"status": "PLAN" if args.check else "INSTALLED", "repository": str(ROOT),
                          "components": components, "skills": plan, "commands": commands}, indent=2))
        return 0
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(json.dumps({"status": "INSTALL_BLOCKED", "reason": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
