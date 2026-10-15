"""Measure independent Council runs; semantic judgments remain with the evaluator.

Reads the instrumented traces and actual saved records, never changes the cases.
Word counts are whitespace counts, not model tokens. Preserve repeated reads.
"""

import argparse
import hashlib
import json
from pathlib import Path

from oppencouncil.store import FreezeStore
from oppencouncil.workstore import WorkStore


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect(manifests):
    results = []
    for manifest in manifests:
        for case in json.loads(manifest.read_text()):
            root = Path(case["directory"])
            trace = [json.loads(line) for line in (root / "trace.jsonl").read_text().splitlines()]
            reads = [event for event in trace if event["operation"] == "read"]
            calls = [event for event in trace if event["operation"] in {"council", "project"}]
            instructions = [event for event in reads if event["path"].startswith("skill/")]
            adapters = [event for event in reads if event["path"] == "interface.md"]
            store = FreezeStore(root / "project")
            work = WorkStore(store)
            investigation = next(i for i in store.snapshot()["investigations"] if i["id"] == "I-000001")
            current = work.read("F-000001")
            protected = {
                event["path"]: event["sha256"] for event in reads
                if event["path"].startswith(("project/Data/", "project/Scripts/"))
            }
            checks = {
                "formal_version_preserved": current["current"] == case["before"]["current"],
                "no_new_candidate": current["candidate"] is None,
                "no_new_f": [q["id"] for q in store.snapshot()["questions"]] == ["F-000001"],
                "read_code_and_data_preserved": all(digest(root / p) == h for p, h in protected.items()),
                "upstream_inputs_and_producer_read": all(p in protected for p in (
                    "project/Data/raw/records.csv", "project/Data/derived/analysis.csv", "project/Scripts/01_clean.py",
                )),
                "saved_discussion": bool(investigation["messages"]),
                "not_awaiting_human": not work.read("I-000001")["awaiting_human"],
                "outcome_saved": (root / "outcome.md").is_file(),
            }
            phase, conclusion = investigation["work"]["phase"], investigation["work"]["conclusion_type"]
            checks["triage_state"] = (
                (phase, conclusion) == ("closed", "not_applicable") if case["scenario"] == "absent"
                else conclusion in {"needs_check", "covered"}
            )
            results.append({
                "scenario": case["scenario"], "arm": case["arm"], "directory": str(root),
                "manifest_sha256": digest(manifest), "trace_sha256": digest(root / "trace.jsonl"),
                "outcome_sha256": digest(root / "outcome.md"), "checks": checks,
                "phase": phase, "conclusion": conclusion,
                "metrics": {
                    "skill_words": sum(e["whitespace_words"] for e in instructions),
                    "adapter_words": sum(e["whitespace_words"] for e in adapters),
                    "instruction_bytes": sum(e["bytes"] for e in instructions + adapters),
                    "all_read_words": sum(e["whitespace_words"] for e in reads),
                    "cli_calls": len(calls), "failed_cli_calls": sum(e["returncode"] != 0 for e in calls),
                },
                "instruction_reads": instructions + adapters,
                "failed_cli": [{k: e[k] for k in ("operation", "arguments", "returncode", "stdout", "stderr")}
                               for e in calls if e["returncode"]],
                "read_errors": [e for e in trace if e["operation"] == "read_error"],
                "discussion_sha256": hashlib.sha256(json.dumps(investigation["messages"], sort_keys=True).encode()).hexdigest(),
                "pending_ids": [p["id"] for p in investigation["pending_items"] if not p.get("resolved")],
            })
    return {"measurement": "Actual wrapper reads and calls; whitespace words are not token usage. Structural checks are not semantic grading.", "runs": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifests", nargs="+", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rendered = json.dumps(inspect(args.manifests), indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
