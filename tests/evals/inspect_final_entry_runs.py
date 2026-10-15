"""Read back final-entry integration trials without changing the original cases."""

import argparse
import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

from final_entry_fixture import digest
from inspect_output_runs import EXPECTED
from oppencouncil.memory import Memory
from oppencouncil.project_checks import validate
from oppencouncil.store import FreezeStore
from oppencouncil.workstore import WorkStore


def inspect(manifest, replay_root):
    replay_root.mkdir(parents=True, exist_ok=False)
    results = []
    for case in json.loads(manifest.read_text()):
        root = Path(case["directory"])
        project = root / "project"
        events = [json.loads(line) for line in (root / "trace.jsonl").read_text().splitlines()]
        reads = [e for e in events if e["operation"] == "read"]
        instructions = [e for e in reads if e["path"].startswith("skills/")]
        calls = [e for e in events if e["operation"] in ("project", "council", "execute")]
        current_files = {str(p.relative_to(project)): digest(p) for p in project.rglob("*") if p.is_file()}
        changed = sorted(
            k
            for k in set(current_files) | set(case["files_before"])
            if current_files.get(k) != case["files_before"].get(k)
        )
        checks = {
            "shared_entry_loaded": any(e["path"] == "skills/oppencouncil/SKILL.md" for e in reads),
            "no_memory": Memory(project).index() == [],
        }
        stages = [e["path"] for e in reads if "/research-stage-" in e["path"]]
        saved = None
        replay = None
        if case["scenario"] == "general_alias":
            checks["legacy_alias_loaded"] = any(e["path"] == case["entry"] for e in reads)
            checks["no_research_stage_loaded"] = not stages
            checks["no_f_created"] = not list((project / "Freeze/questions").glob("*.json"))
            copy = replay_root / root.name
            shutil.copytree(project, copy, ignore=shutil.ignore_patterns("__pycache__"))
            code = (
                "import runpy; f=runpy.run_path('Source/report.py')['export_rows']; "
                "rows=[{'id':'a','amount':0},{'id':'b','amount':None},"
                "{'id':'c','amount':-2},{'id':'d','amount':7.5}]; "
                "assert f(rows)==[rows[0],rows[2],rows[3]]; assert f([])==[]; assert len(rows)==4"
            )
            run = subprocess.run([sys.executable, "-c", code], cwd=copy, capture_output=True, text=True)
            checks["independent_contract_check"] = run.returncode == 0
            replay = {"directory": str(copy), "returncode": run.returncode, "stderr": run.stderr}
        else:
            work = WorkStore(FreezeStore(project))
            saved = work.read("F-000001")
            checks["formal_version_preserved"] = saved["current"] == case["before"]["current"]
            checks["no_new_f"] = [q["id"] for q in work.store.snapshot()["questions"]] == ["F-000001"]
            checks["no_candidate"] = saved["candidate"] is None
            if case["scenario"] == "descriptive":
                with (project / "Results/baseline.csv").open(newline="") as stream:
                    checks["exact_article_table"] = list(csv.reader(stream)) == EXPECTED
                checks["raw_input_preserved"] = "Data/raw/baseline.csv" not in changed
                checks["output_read_back"] = any(e["path"] == "project/Results/baseline.csv" for e in reads)
                checks["only_current_stage"] = set(stages) == {
                    "skills/oppencouncil/references/research-stage-descriptive.md"
                }
                copy = replay_root / root.name
                shutil.copytree(project, copy, ignore=shutil.ignore_patterns("__pycache__"))
                run = subprocess.run(
                    [sys.executable, "Scripts/01_descriptive.py"], cwd=copy, capture_output=True, text=True
                )
                checks["project_only_replay_matches"] = run.returncode == 0 and digest(
                    copy / "Results/baseline.csv"
                ) == digest(project / "Results/baseline.csv")
                replay = {"directory": str(copy), "returncode": run.returncode, "stderr": run.stderr}
            else:
                checks["no_analysis_execution"] = not any(e["operation"] == "execute" for e in calls)
                checks["human_feedback_handled"] = (
                    not saved["human_pending"] and not saved["actionable"] and not saved["inputs"]
                )
                checks["unrelated_investigation_preserved"] = (
                    "Freeze/investigations/I-000001.json" not in changed
                )
                checks["analysis_files_preserved"] = not any(
                    k.startswith(("Data/", "Scripts/", "Results/")) for k in changed
                )
                checks["no_research_stage_loaded"] = not stages
        results.append(
            {
                "scenario": case["scenario"],
                "directory": str(root),
                "checks": checks,
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
                "replay": replay,
                "hashes": {
                    "manifest": digest(manifest),
                    "trace": digest(root / "trace.jsonl"),
                    "entry": digest(root / "skills/oppencouncil/SKILL.md"),
                    "outcome": digest(root / "outcome.md"),
                },
            }
        )
    return {
        "measurement": (
            "Actual reads and calls; whitespace words are not model tokens. "
            "Replays are evaluator checks in project-only copies."
        ),
        "runs": results,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--replay-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = inspect(args.manifest, args.replay_directory)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps([{k: r[k] for k in ("scenario", "checks", "metrics")} for r in result["runs"]], indent=2)
    )
