"""Read saved stage trials and replay their producers in project-only copies."""

import argparse
import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

from oppencouncil.memory import Memory
from oppencouncil.project_checks import validate
from oppencouncil.store import FreezeStore
from oppencouncil.workstore import WorkStore
from stage_fixture import digest


def csv_rows(path):
    with path.open(newline="") as stream:
        return list(csv.reader(stream))


def inspect(manifest, replay_root):
    replay_root.mkdir(parents=True, exist_ok=False)
    rows = []
    for case in json.loads(manifest.read_text()):
        root = Path(case["directory"])
        project = root / "project"
        events = [json.loads(line) for line in (root / "trace.jsonl").read_text().splitlines()]
        reads = [e for e in events if e["operation"] == "read"]
        instructions = [e for e in reads if e["path"].startswith("skill/")]
        adapters = [e for e in reads if e["path"] == "interface.md"]
        calls = [e for e in events if e["operation"] in ("council", "project", "execute")]
        generated = [
            p
            for p in (project / "Data").rglob("*.csv")
            if p.relative_to(project).as_posix() != case["source"]
        ]
        matches = [p for p in generated if csv_rows(p) == case["expected_rows"]]
        outputs = sorted(
            p.relative_to(project).as_posix() for p in (project / "Results").rglob("*") if p.is_file()
        )
        checks = {
            "raw_preserved": digest(project / case["source"]) == case["raw_sha256"],
            "exact_cleaned_data_in_data": len(matches) == 1,
            "no_article_output_manufactured": outputs == [],
            "no_new_f": not list((project / "Freeze/questions").glob("*.json")),
            "no_memory": Memory(project).index() == [],
            "no_release": not (project / "Releases").exists() or not any((project / "Releases").iterdir()),
            "producer_fixed": digest(project / case["producer"]) != case["files_before"][case["producer"]],
            "data_read_back": any(
                e["path"] == "project/" + p.relative_to(project).as_posix() and e["sha256"] == digest(p)
                for p in matches
                for e in reads
            ),
        }
        if case["scenario"] != "cleaning":
            saved = WorkStore(FreezeStore(project)).read("F-000001")
            checks = {
                key: value
                for key, value in checks.items()
                if key
                not in {
                    "exact_cleaned_data_in_data",
                    "no_article_output_manufactured",
                    "no_new_f",
                    "data_read_back",
                }
            }
            checks.update(
                {
                    "exact_article_table": csv_rows(project / "Results/stage.csv") == case["expected_rows"],
                    "only_specified_outputs": outputs == sorted(case["outputs"]),
                    "formal_version_preserved": saved["current"] == case["before"]["current"],
                    "no_candidate": saved["candidate"] is None,
                    "no_new_f": sorted(p.name for p in (project / "Freeze/questions").glob("*.json"))
                    == ["F-000001.json"],
                    "outputs_read_back": all(
                        any(
                            e["path"] == "project/" + name and e["sha256"] == digest(project / name)
                            for e in reads
                        )
                        for name in case["outputs"]
                    ),
                }
            )
            if case["scenario"] == "reporting":
                markdown = (project / "Results/stage.md").read_text()
                table = [
                    [cell.strip() for cell in line.strip().strip("|").split("|")]
                    for line in markdown.splitlines()
                    if line.strip().startswith("|")
                ]
                table = [row for row in table if any(c.replace("-", "").replace(":", "") for c in row)]
                checks["markdown_matches_table"] = table == case["expected_rows"]
                checks["markdown_title_and_footnote"] = (
                    "Primary outcome" in markdown
                    and "Estimates are risk ratios; intervals are 95% CIs." in markdown
                )
        if case["arm"] != "v4.3.1":
            checks["only_current_stage_loaded"] = {
                e["path"] for e in reads if "research-stage-" in e["path"]
            } == {"skill/references/research-stage-" + case["scenario"] + ".md"}
        replay = replay_root / root.name
        shutil.copytree(project, replay, ignore=shutil.ignore_patterns("__pycache__"))
        for name in (
            [p.relative_to(project).as_posix() for p in generated]
            if case["scenario"] == "cleaning"
            else case["outputs"]
        ):
            (replay / name).unlink()
        run = subprocess.run([sys.executable, case["producer"]], cwd=replay, text=True, capture_output=True)
        checks["replay_from_raw_reproduces_data"] = (
            run.returncode == 0
            and len(matches) == 1
            and all(
                (replay / p.relative_to(project)).is_file()
                and digest(replay / p.relative_to(project)) == digest(p)
                for p in matches
            )
        )
        checks["replay_does_not_recreate_results"] = not any(
            p.is_file() for p in (replay / "Results").rglob("*")
        )
        if case["scenario"] != "cleaning":
            del checks["replay_from_raw_reproduces_data"]
            del checks["replay_does_not_recreate_results"]
            checks["project_only_replay_identical"] = run.returncode == 0 and all(
                (replay / name).is_file() and digest(replay / name) == digest(project / name)
                for name in case["outputs"]
            )
        rows.append(
            {
                "scenario": case["scenario"],
                "arm": case["arm"],
                "directory": str(root),
                "checks": checks,
                "outputs": outputs,
                "generated_data": [p.relative_to(project).as_posix() for p in generated],
                "validation": validate(project),
                "instruction_reads": instructions + adapters,
                "metrics": {
                    "skill_words": sum(e["whitespace_words"] for e in instructions),
                    "adapter_words": sum(e["whitespace_words"] for e in adapters),
                    "cli_and_script_calls": len(calls),
                    "nonzero_calls": sum(bool(e["returncode"]) for e in calls),
                },
                "nonzero_calls": [e for e in calls if e["returncode"]],
                "replay": {"directory": str(replay), "returncode": run.returncode, "stderr": run.stderr},
                "hashes": {
                    "manifest": digest(manifest),
                    "trace": digest(root / "trace.jsonl"),
                    "entry": digest(root / "skill/SKILL.md"),
                    "outcome": digest(root / "outcome.md"),
                },
            }
        )
    return {
        "measurement": "Actual reads/calls; whitespace words are not model tokens. "
        "Project-only replays are separate evaluator checks.",
        "runs": rows,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--replay-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = inspect(args.manifest, args.replay_directory)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps([{k: r[k] for k in ("arm", "checks", "metrics")} for r in result["runs"]], indent=2))
