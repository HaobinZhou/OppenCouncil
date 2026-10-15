"""Select the project generation before parsing or mutating through a helper.

The legacy engines are preserved maintenance code, never the v5 write path.
Project layout and the invoked alias do not override an existing project's type.
"""

from __future__ import annotations

import re
import runpy
import sys
from pathlib import Path

from . import project_transaction as tx
from .store import FreezeError

ALIASES = {"stepwise-r-project": "research", "oppen-project-steward": "general"}
NESTED = {"memory", "review", "attention", "audit", "scripts", "explore", "release", "data"}
SWITCHES = {"--check", "--apply", "--replace", "--bootstrap", "--actionable", "--help", "-h"}
V5_ONLY = {"upgrade-v5", "project-type", "scripts", "explore", "release", "data"}
LEGACY_ONLY = {"upgrade-v4", "upgrade-layout", "managed-state", "migrate", "function-audit"}


def target_argument(argv):
    """Locate the positional target without interpreting a payload or executing a parser."""
    positionals, skip = [], False
    for arg in argv:
        if skip:
            skip = False
        elif arg.startswith("-"):
            skip = arg not in SWITCHES and "=" not in arg
        else:
            positionals.append(arg)
    index = 2 if positionals and positionals[0] in NESTED else 1
    return Path(positionals[index]).expanduser() if len(positionals) > index else None


def generation(root, *, recover=True):
    if root is None or not root.exists():
        return None, None
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise FreezeError("Project target must be a directory")
    # A crash can leave the new marker with old files (or the reverse). Recover
    # before dispatch so no generation is selected from half-applied state.
    if (root / tx.STAGING).exists() or (root / tx.STAGING).is_symlink():
        if not recover:
            raise FreezeError(
                "RECOVERY_REQUIRED: run validate to recover the interrupted operation before --check"
            )
        tx.recover(root)
    found = []
    for name in ("project.md", ".oppen-project-steward/registry.md"):
        raw = tx.read_bytes(tx.safe_destination(root, name))
        if raw is None:
            continue
        text = raw.decode("utf-8")
        markers = re.findall(
            r"<!-- (oppencouncil|stepwise-r-project|oppen-project-steward):v([2-5]) -->", text
        )
        if any(skill == "oppencouncil" and version == "5" for skill, version in markers):
            found.append(("oppencouncil", 5))
        elif markers:
            if len(set(markers)) != 1:
                raise FreezeError("Ambiguous project generation; inspect the existing registry")
            found.append((markers[0][0], int(markers[0][1])))
    if len(found) > 1:
        raise FreezeError("Multiple project anchors; resolve ownership before helper operations")
    return found[0] if found else (None, None)


def legacy_main(skill, argv, entry_path):
    filename = "legacy_" + skill.replace("-", "_") + ".py"
    roots = [Path(entry_path).resolve().parents[2]] if entry_path else []
    roots.append(Path(__file__).resolve().parents[2] / "skills")
    path = next(
        (p / skill / "scripts" / filename for p in roots if (p / skill / "scripts" / filename).is_file()),
        None,
    )
    if path is None:
        raise FreezeError("Install the complete matching skill bundle to operate this legacy project")
    previous = sys.argv
    try:
        sys.argv = [str(path), *argv]
        try:
            runpy.run_path(str(path), run_name="__main__")
        except SystemExit as result:
            return result.code if isinstance(result.code, int) else 1 if result.code else 0
        return 0
    finally:
        sys.argv = previous


def main(argv=None, *, alias="oppencouncil", entry_path=None):
    from .governance import main as shared_main

    argv = list(sys.argv[1:] if argv is None else argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    try:
        command = argv[0] if argv else None
        target = target_argument(argv)
        skill, version = generation(target, recover="--check" not in argv)
        if version is not None and version < 5 and command != "upgrade-v5":
            if command in V5_ONLY:
                raise FreezeError("Project requires explicit upgrade-v5 before v5 helper operations")
            return legacy_main(skill, argv, entry_path)
        if version == 5 and command in LEGACY_ONLY:
            raise FreezeError(
                "This maintenance command is retired for v5. Use the shared helper; "
                "legacy function/module audit records remain read-only."
            )
        if version is None and command in LEGACY_ONLY:
            if alias not in ALIASES:
                raise FreezeError("Select the original legacy helper for legacy maintenance")
            return legacy_main(alias, argv, entry_path)
        if command in {"init", "adopt"}:
            current = None
            if version == 5:
                from .project import Project

                current = Project(target)
                if not any(a == "--layout" or a.startswith("--layout=") for a in argv):
                    argv += ["--layout", "namespace" if current.namespaced else "root"]
            if not any(a == "--project-type" or a.startswith("--project-type=") for a in argv):
                if current:
                    argv += ["--project-type", current.project_type]
                elif alias in ALIASES:
                    argv += ["--project-type", ALIASES[alias]]
        if command == "audit-recover":
            argv = ["audit", "recover", *argv[1:]]
        if command == "module-audit":
            argv = [
                "--topic"
                if a == "--module"
                else a.replace("--module=", "--topic=", 1)
                if a.startswith("--module=")
                else a
                for a in argv
            ]
            if sum(a == "--source" or a.startswith("--source=") for a in argv) > 1:
                raise FreezeError(
                    "A v5 high-risk check binds one source; list dependent checks in its completion payload"
                )
        return shared_main(argv)
    except (FreezeError, OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
