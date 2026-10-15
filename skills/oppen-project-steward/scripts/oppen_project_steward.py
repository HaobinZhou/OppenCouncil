#!/usr/bin/env python3
"""Compatibility command name; project generation selects the implementation."""

import sys
from pathlib import Path

_entry = Path(__file__).resolve()
_legacy = _entry.with_name("legacy_" + _entry.name)

if __name__ != "__main__":
    # Retain the importable v4 maintenance API and its original module globals.
    exec(compile(_legacy.read_bytes(), str(_legacy), "exec"), globals())
else:
    _source = _entry.parents[3] / "council"
    if (_source / "oppencouncil/helper_router.py").is_file():
        sys.path.insert(0, str(_source))
    try:
        from oppencouncil.helper_router import main
    except ImportError as error:
        raise SystemExit("Install the matching OppenCouncil package before using this helper: " + str(error)) from error
    raise SystemExit(main(alias=_entry.parents[1].name, entry_path=_entry))
