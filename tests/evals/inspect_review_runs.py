"""Collect bounded review-trial evidence; semantic grading is a separate readback."""

import argparse
import json
from pathlib import Path

from oppencouncil.memory import Memory
from oppencouncil.project_checks import validate
from oppencouncil.store import FreezeStore
from oppencouncil.workstore import WorkStore
from stage_fixture import digest


def inspect(manifest):
    results = []
    for case in json.loads(manifest.read_text()):
        root = Path(case["directory"])
        project = root / "project"
        events = [json.loads(line) for line in (root / "trace.jsonl").read_text().splitlines()]
        reads = [e for e in events if e["operation"] == "read"]
        instructions = [e for e in reads if e["path"].startswith("skill/")]
        calls = [e for e in events if e["operation"] in {"council", "project", "execute"}]
        actual = {
            p.relative_to(project).as_posix(): digest(p)
            for p in project.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts
        }
        before = case["files_before"]
        changed = sorted(p for p in set(before) | set(actual) if before.get(p) != actual.get(p))
        work = WorkStore(FreezeStore(project))
        snapshot = work.store.snapshot()
        ids = [q["id"] for q in snapshot["questions"]]
        ids.extend(p.stem for p in (project / "Freeze/investigations").glob("I-*.json"))
        checks = {
            "actual_entry_unchanged": digest(root / "skill/SKILL.md") == case["entry_sha256"],
            "entry_loaded": any(e["path"] == "skill/SKILL.md" for e in reads),
            "no_memory": Memory(project).index() == [],
            "no_release": not any(p.startswith("Releases/") for p in changed),
            "no_archived_content_read": not any("Explore/_archive/" in e["path"] for e in reads),
            "archived_content_unchanged": not any(p.startswith("Explore/_archive/") for p in changed),
        }
        if case["scenario"] == "preview":
            checks["no_formal_results"] = not any(p.is_file() for p in (project / "Results").rglob("*"))
        if case["scenario"] == "continuation":
            checks["unrelated_f_unchanged"] = "Freeze/questions/F-000003.json" not in changed
            checks["no_analysis_or_data_change"] = not any(
                p.startswith(("Scripts/", "Data/", "Results/")) for p in changed
            )
            checks["no_new_f"] = sorted(q["id"] for q in snapshot["questions"]) == [
                "F-000001",
                "F-000002",
                "F-000003",
            ]
        results.append(
            {
                "scenario": case["scenario"],
                "directory": str(root),
                "checks": checks,
                "validation": validate(project),
                "changed_project_files": changed,
                "instruction_reads": instructions,
                "source_reads": [e for e in reads if e["path"].startswith("project/")],
                "metrics": {
                    "skill_words": sum(e["whitespace_words"] for e in instructions),
                    "adapter_words": sum(e["whitespace_words"] for e in reads if e["path"] == "interface.md"),
                    "cli_and_script_calls": len(calls),
                    "nonzero_calls": sum(bool(e["returncode"]) for e in calls),
                },
                "nonzero_calls": [e for e in calls if e["returncode"]],
                "saved_items": [work.read(identifier) for identifier in ids],
                "snapshot": snapshot,
                "hashes": {
                    "manifest": digest(manifest),
                    "trace": digest(root / "trace.jsonl"),
                    "outcome": digest(root / "outcome.md"),
                },
            }
        )
    return {
        "measurement": "Actual file reads/calls; whitespace words are not model tokens. "
        "Mechanical checks alone do not establish semantic success.",
        "runs": results,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = inspect(args.manifest)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps([{k: r[k] for k in ("scenario", "checks", "metrics")} for r in result["runs"]], indent=2)
    )
