"""Inspect the independent table-feedback trial and replay only its project copy."""

import argparse
import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from oppencouncil.memory import Memory
from oppencouncil.project_checks import validate
from oppencouncil.store import FreezeStore
from oppencouncil.workstore import WorkStore


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect(manifest, replay):
    case = json.loads(manifest.read_text())
    root = Path(case["directory"])
    project = root / "project"
    before = case["files_before"]
    current = {p.relative_to(project).as_posix(): digest(p) for p in project.rglob("*") if p.is_file()}
    changed = sorted(k for k in set(before) | set(current) if before.get(k) != current.get(k))
    saved = WorkStore(FreezeStore(project)).read("F-000001")
    candidate = saved["candidate"]["text"]
    table = json.loads(re.search(r"```table\n(.*?)\n```", candidate, re.S)[1])
    assets = re.findall(r"Freeze/assets/[a-f0-9]{64}\.svg", candidate)
    traces = [json.loads(line) for line in (root / "trace.jsonl").read_text().splitlines()]
    reads = [e for e in traces if e["operation"] == "read"]
    instructions = [e for e in reads if e["path"].startswith("skills/")]
    calls = [e for e in traces if e["operation"] in ("execute", "council", "project")]
    checks = {
        "exact_human_table_preserved": table == case["expected_table"],
        "formal_version_preserved": saved["current"] == case["before"]["current"],
        "formal_results_preserved": current["Results/current-table.csv"]
        == before["Results/current-table.csv"],
        "original_formal_producer_preserved": current["Scripts/01_table.py"] == before["Scripts/01_table.py"],
        "old_assets_preserved": all(
            current.get(k) == v for k, v in before.items() if k.startswith("Freeze/assets/")
        ),
        "fresh_immutable_image": len(assets) == 1
        and assets[0] not in before
        and digest(project / assets[0]) == Path(assets[0]).stem,
        "candidate_image_matches_generated_preview": len(assets) == 1
        and (project / assets[0]).read_bytes()
        == (project / "Explore/table-preview/example.svg").read_bytes(),
        "human_review_without_approval": saved["work"]["phase"] == "human_review"
        and saved["candidate"].get("approval") is None,
        "feedback_handled": not saved["inputs"] and not saved["human_pending"],
        "no_premature_pending_wakeup": saved["ready_pending_ids"] == [],
        "no_memory": Memory(project).index() == [],
        "no_release": not (project / "Releases").exists() or not any((project / "Releases").iterdir()),
        "generated_preview_read_back": any(
            e["path"] == "project/Explore/table-preview/table.json" for e in reads
        ),
    }
    shutil.copytree(project, replay, ignore=shutil.ignore_patterns("__pycache__"))
    runs = []
    for name in ["Scripts/01_table.py", "Explore/table-preview/render.py"]:
        run = subprocess.run([sys.executable, name], cwd=replay, text=True, capture_output=True)
        runs.append({"script": name, "returncode": run.returncode, "stderr": run.stderr})
    expected_csv = [
        ["Characteristic", "Group B", "Group A"],
        ["Age, years", "60.0 (14.1)", "50.0 (14.1)"],
        ["Diabetes, n (%)", "2 (100.0%)", "1 (50.0%)"],
    ]
    with (replay / "Explore/table-preview/example.csv").open(newline="") as stream:
        checks["replayed_preview_values_and_order"] = list(csv.reader(stream)) == expected_csv
    checks["project_only_replay_succeeded"] = all(r["returncode"] == 0 for r in runs)
    checks["replayed_formal_v1_identical"] = (
        digest(replay / "Results/current-table.csv") == before["Results/current-table.csv"]
    )
    checks["replayed_preview_identical"] = all(
        digest(replay / "Explore/table-preview" / name) == digest(project / "Explore/table-preview" / name)
        for name in ["example.svg", "example.csv", "table.json"]
    )
    return {
        "scenario": "human_table_edit",
        "directory": str(root),
        "checks": checks,
        "rubric_deviation": (
            "The original formal producer was refactored into a shared CSV writer. "
            "The preregistered byte-preservation criterion fails; project-only replay "
            "separately checks unchanged formal v1 behavior. No blanket rubric pass is claimed."
        ),
        "validation": validate(project),
        "changed_project_files": changed,
        "instruction_reads": instructions,
        "metrics": {
            "skill_words": sum(e["whitespace_words"] for e in instructions),
            "cli_and_script_calls": len(calls),
            "nonzero_calls": sum(bool(e["returncode"]) for e in calls),
        },
        "nonzero_calls": [e for e in calls if e["returncode"]],
        "saved_item": saved,
        "replay": {"directory": str(replay), "runs": runs},
        "hashes": {
            "manifest": digest(manifest),
            "trace": digest(root / "trace.jsonl"),
            "entry": digest(root / "skills/oppencouncil/SKILL.md"),
            "outcome": digest(root / "outcome.md"),
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--replay-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = inspect(args.manifest, args.replay_directory)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ("checks", "metrics", "rubric_deviation")}, indent=2))
