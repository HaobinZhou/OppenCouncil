#!/usr/bin/env python3
"""Install both skills and Council, optionally adding the MCP component."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ("oppen-project-steward", "stepwise-r-project")


def python_in(component: str) -> Path:
    return ROOT / component / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def skill_plan(destination: Path, replace_links: bool = False) -> list[dict]:
    """Preflight all destinations before installing or replacing any links."""
    result = []
    for name in SKILLS:
        source = ROOT / "skills" / name
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
        result.append({"source": str(source), "target": str(target), "action": action})
    return result


def install_links(plan: list[dict]) -> None:
    """Create sibling links before atomic replacement; never remove source directories."""
    for entry in plan:
        if entry["action"] == "unchanged":
            continue
        source, target = Path(entry["source"]), Path(entry["target"])
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".install-link")
        if temporary.exists() or temporary.is_symlink():
            raise ValueError(f"Unresolved installer link at {temporary}")
        try:
            temporary.symlink_to(source, target_is_directory=True)
            temporary.replace(target)
        finally:
            if temporary.is_symlink():
                temporary.unlink()


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
