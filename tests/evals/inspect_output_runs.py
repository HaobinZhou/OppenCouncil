"""Read back independent output trials and optionally replay copies of each case.

Keep original traces and projects unchanged. Replays are evaluator verification,
not additional independent Agent passes or part of the measured Agent trace.
"""

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from oppencouncil.memory import Memory
from oppencouncil.project_checks import validate
from oppencouncil.project_registry import Registry
from oppencouncil.store import FreezeStore
from oppencouncil.workstore import WorkStore

EXPECTED = [
    ["Characteristic", "Treatment A (n = 2)", "Treatment B (n = 2)"],
    ["Age, years, mean (SD)", "50.0 (14.1)", "60.0 (14.1)"],
    ["Diabetes, n (%)", "1 (50.0%)", "2 (100.0%)"],
]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect(manifest, replay_root=None):
    if replay_root:
        replay_root.mkdir(parents=True, exist_ok=False)
    results = []
    for case in json.loads(manifest.read_text()):
        root = Path(case["directory"])
        project = root / "project"
        trace_path = root / "trace.jsonl"
        events = [json.loads(line) for line in trace_path.read_text().splitlines()]
        reads = [e for e in events if e["operation"] == "read"]
        instructions = [e for e in reads if e["path"].startswith("skill/")]
        adapters = [e for e in reads if e["path"] == "interface.md"]
        calls = [e for e in events if e["operation"] in {"project", "council", "execute"}]
        output = project / "Results/baseline.csv"
        with output.open(newline="") as stream:
            rows = list(csv.reader(stream))
        current = WorkStore(FreezeStore(project)).read("F-000001")
        outputs = Registry(project).outputs()
        checks = {
            "exact_article_table": rows == EXPECTED,
            "raw_input_preserved": digest(project / "Data/raw/baseline.csv") == case["raw_sha256"],
            "formal_version_preserved": current["current"] == case["before"]["current"],
            "no_candidate": current["candidate"] is None,
            "no_new_f": [q["id"] for q in FreezeStore(project).snapshot()["questions"]] == ["F-000001"],
            "no_new_memory": Memory(project).index() == [],
            "only_requested_result": sorted(p.relative_to(project).as_posix() for p in (project / "Results").rglob("*") if p.is_file()) == ["Results/baseline.csv"],
            "output_read_back": any(e["path"] == "project/Results/baseline.csv" and e["sha256"] == digest(output) for e in reads),
        }
        if case["arm"] != "v4.3.1":
            stage_paths = {e["path"] for e in reads if "research-stage-" in e["path"]}
            checks["only_current_stage_loaded"] = stage_paths == {"skill/references/research-stage-descriptive.md"}
        replay = None
        if replay_root:
            destination = replay_root / root.name
            shutil.copytree(root, destination, ignore=shutil.ignore_patterns("trace.jsonl", "__pycache__"))
            run = subprocess.run([sys.executable, "tools.py", "execute", "project/Scripts/01_descriptive.py"],
                                 cwd=destination, text=True, capture_output=True, timeout=60)
            replay = {"directory": str(destination), "returncode": run.returncode,
                      "stdout": run.stdout, "stderr": run.stderr,
                      "output_sha256": digest(destination / "project/Results/baseline.csv")}
            checks["producer_replay_matches"] = run.returncode == 0 and replay["output_sha256"] == digest(output)
        results.append({
            "arm": case["arm"], "scenario": case["scenario"], "directory": str(root),
            "manifest_sha256": digest(manifest), "trace_sha256": digest(trace_path),
            "skill_sha256": digest(root / "skill/SKILL.md"), "outcome_sha256": digest(root / "outcome.md"),
            "output_sha256": digest(output), "producer_sha256": digest(project / "Scripts/01_descriptive.py"),
            "checks": checks, "output_registration": outputs, "validation": validate(project),
            "metrics": {"skill_words": sum(e["whitespace_words"] for e in instructions),
                        "adapter_words": sum(e["whitespace_words"] for e in adapters),
                        "instruction_bytes": sum(e["bytes"] for e in instructions + adapters),
                        "cli_and_script_calls": len(calls),
                        "nonzero_calls": sum(bool(e["returncode"]) for e in calls)},
            "instruction_reads": instructions + adapters,
            "nonzero_calls": [{k: e[k] for k in e if k != "at"} for e in calls if e["returncode"]],
            "replay": replay,
        })
    return {"measurement": "Actual wrapper reads and calls; whitespace words are not model tokens. Replay copies are evaluator verification, outside the independent traces.", "runs": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--replay-directory", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rendered = json.dumps(inspect(args.manifest, args.replay_directory), indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
