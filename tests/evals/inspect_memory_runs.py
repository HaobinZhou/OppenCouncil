"""Read independent run artifacts. Structural checks are not semantic evaluation.

The final evaluator must also inspect each entry and outcome against the rubric.
This command never edits a project or changes an expected result.
"""

import argparse
import hashlib
import json
from pathlib import Path

from oppencouncil.memory import Memory
from oppencouncil.project import Project


def inspect(manifest_path):
    results = []
    for case in json.loads(manifest_path.read_text()):
        directory = Path(case["directory"])
        project = directory / "project"
        service = Memory(project)
        current = {entry["id"]: service.read(entry["id"]) for entry in service.index()}
        prior = case["before"]
        new = {k: v for k, v in current.items() if k not in prior}
        no_entry = case["case"] in {
            "memory_routine_fix_is_explained_by_git", "memory_task_completion_never_triggers",
            "memory_council_rationale_is_not_duplicated",
        }
        checks = {"expected_new_entry_count": len(new) == (0 if no_entry else 1)}
        if case["project_type"] == "research":
            checks["research_basis_present"] = all(bool(e.get("basis")) for e in new.values())
        for identifier, old in prior.items():
            record = current.get(identifier, {})
            mutable = {"status", "superseded_by", "invalidated_by"}
            checks["prior_content_preserved"] = all(record.get(k) == v for k, v in old.items() if k not in mutable)
            relation = "invalidates" if case["case"].endswith("uses_invalidates") else "supersedes"
            status, reverse = ("invalidated", "invalidated_by") if relation == "invalidates" else ("superseded", "superseded_by")
            checks["prior_status_and_reverse"] = record.get("status") == status and record.get(reverse) == list(new)
            checks["new_relationship"] = len(new) == 1 and next(iter(new.values())).get(relation) == [identifier]
            other = "supersedes" if relation == "invalidates" else "invalidates"
            checks["disjoint_relationships"] = all(not entry.get(other) for entry in new.values())
        if case.get("council_before"):
            checks["council_preserved"] = all(
                hashlib.sha256((project / name).read_bytes()).hexdigest() == digest
                for name, digest in case["council_before"].items()
            )
        try:
            Project(project).baseline_state()
            checks["managed_baseline"] = True
        except Exception as exc:
            checks["managed_baseline"] = str(exc)
        outcome = directory / "outcome.md"
        checks["outcome_saved"] = outcome.is_file()
        results.append({
            "case": case["case"], "directory": str(directory),
            "skill_sha256": case["skill_sha256"], "helper_sha256": case.get("helper_sha256"),
            "checks": checks, "entries": current,
            "outcome": outcome.read_text() if outcome.is_file() else None,
            "outcome_sha256": hashlib.sha256(outcome.read_bytes()).hexdigest() if outcome.is_file() else None,
        })
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    text = json.dumps(inspect(args.manifest), indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
