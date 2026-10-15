#!/usr/bin/env python3
"""Use the same project helper from a source checkout or an installed Council package."""

import sys
from pathlib import Path

# A standalone skill uses the installed package. Python otherwise finds this
# same-named entry script first and tries to import it as the package.
if sys.path and Path(sys.path[0]).resolve() == Path(__file__).resolve().parent:
    sys.path.pop(0)

source = Path(__file__).resolve().parents[3] / "council"
if (source / "oppencouncil" / "governance.py").is_file():
    sys.path.insert(0, str(source))

try:
    from oppencouncil.helper_router import main
except ImportError as exc:
    raise SystemExit(
        "Install the matching OppenCouncil package before using the v5 helper: " + str(exc)
    ) from exc

if __name__ == "__main__":
    raise SystemExit(main(entry_path=Path(__file__)))
