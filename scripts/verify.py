#!/usr/bin/env python3
"""Run the product's functional acceptance suites using its locked environments."""

import argparse
import subprocess
from pathlib import Path

from install import ROOT, python_in


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", action="store_true", help="Verify Council and skills without optional MCP")
    args = parser.parse_args()
    council = str(python_in("council"))
    commands = [
        (ROOT / "council", [council, "-m", "ruff", "check", "."]),
        (ROOT, [council, "-m", "ruff", "check", "scripts", "tests/integration/test_installation.py"]),
        (ROOT / "council", [council, "-m", "pytest", "-q"]),
        (ROOT, [council, "-m", "pytest", "-q", "skills", "tests/integration", "--import-mode=importlib"]),
        (
            ROOT,
            ["node", "--test", "council/tests/test_workbench.cjs", "council/tests/test_decision_groups.cjs",
             "council/tests/test_login.cjs"],
        ),
    ]
    if not args.core:
        mcp = str(python_in("mcp"))
        commands += [
            (ROOT / "mcp", [mcp, "-m", "ruff", "check", "."]),
            (ROOT / "mcp", [mcp, "-m", "pytest", "-q"]),
        ]
    for directory, command in commands:
        print(f"Verifying {Path(directory).relative_to(ROOT)}: {' '.join(command)}", flush=True)
        subprocess.run(command, cwd=directory, check=True)
    print("Product acceptance passed" + (" (core components)" if args.core else " (including MCP)"))


if __name__ == "__main__":
    main()
