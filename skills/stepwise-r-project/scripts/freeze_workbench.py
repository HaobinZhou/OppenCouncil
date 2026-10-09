"""Compatibility CLI delegating Freeze review to installed OppenCouncil."""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path


def council_command() -> list[str]:
    configured = os.environ.get("OPPEN_COUNCIL_PYTHON")
    if configured:
        return [configured, "-m", "oppencouncil"]
    checkout = Path(__file__).resolve().parents[3] / "council"
    python = checkout / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if python.is_file():
        return [str(python), "-m", "oppencouncil"]
    executable = shutil.which("oppencouncil")
    if executable:
        return [executable]
    if importlib.util.find_spec("oppencouncil") is not None:
        return [sys.executable, "-m", "oppencouncil"]
    raise RuntimeError("Install OppenCouncil, or set OPPEN_COUNCIL_PYTHON to its Python interpreter")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    prefix = []
    if "--directory" in args:
        index = args.index("--directory")
        if index + 1 >= len(args):
            print("OppenCouncil: --directory requires a path", file=sys.stderr)
            return 2
        prefix = args[index:index + 2]
        del args[index:index + 2]
    if args and args[0] == "start" and len(args) > 1 and not args[1].startswith("-"):
        args[0] = "open"
    elif args and args[0] == "stop" and len(args) > 1 and not args[1].startswith("-"):
        args[0] = "disable"
    try:
        return subprocess.call(council_command() + prefix + args)
    except (OSError, RuntimeError) as error:
        print(f"OppenCouncil: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
