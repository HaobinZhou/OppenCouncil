"""Isolated human table-edit continuation using actual runtime Skill files."""

import argparse
import copy
import hashlib
import json
import shutil
import subprocess
import uuid
from pathlib import Path

from council_fixture import ROOT, TOOLS
from oppencouncil.bootstrap import create
from oppencouncil.outputs import Outputs
from oppencouncil.store import FreezeStore
from oppencouncil.workstore import WorkStore


def block(table, image):
    return (
        "Article table layout. The numbers below are simulated examples, not study results.\n\n"
        "```table\n"
        + json.dumps(table, ensure_ascii=False, indent=2)
        + "\n```\n\n"
        + f"![Simulated example]({image})\n"
    )


def prepare(destination):
    destination.mkdir(parents=True, exist_ok=False)
    case = destination / uuid.uuid4().hex[:12]
    project = case / "project"
    project.mkdir(parents=True)
    create(project, project_type="research")
    preview = project / "Explore/table-preview"
    preview.mkdir(parents=True)
    table = {
        "schema_version": 1,
        "id": "baseline",
        "title": "Baseline summary",
        "simulated": True,
        "columns": [{"id": "a", "label": "Group A"}, {"id": "b", "label": "Group B"}],
        "headers": [
            {"id": "ha", "label": "Group A", "column_id": "a"},
            {"id": "hb", "label": "Group B", "column_id": "b"},
        ],
        "rows": [
            {"id": "age", "label": "Age, years", "cells": {"a": "50.0 (14.1)", "b": "60.0 (14.1)"}},
            {"id": "bmi", "label": "BMI, kg/m²", "cells": {"a": "24.0 (2.0)", "b": "25.0 (3.0)"}},
            {"id": "diabetes", "label": "Diabetes, n (%)", "cells": {"a": "1 (50.0%)", "b": "2 (100.0%)"}},
        ],
        "footnotes": [{"id": "simulation", "text": "Simulated data for layout review only."}],
    }
    producer = (
        "import csv,html,json\nfrom pathlib import Path\n"
        "HERE=Path(__file__).resolve().parent\n"
        "TABLE=json.loads(" + repr(json.dumps(table, ensure_ascii=False)) + ")\n"
        "lines=[TABLE['title'], 'SIMULATED DATA', "
        "' | '.join(['Characteristic']+[c['label'] for c in TABLE['columns']])]\n"
        "lines += [' | '.join([r['label']]+[r['cells'].get(c['id'],'') "
        "for c in TABLE['columns']]) for r in TABLE['rows']]\n"
        "lines += [n['text'] for n in TABLE['footnotes']]\n"
        "body=''.join('<text x=\"20\" y=\"'+str(35+i*30)+'\">'+html.escape(line)+'</text>' "
        "for i,line in enumerate(lines))\n"
        "(HERE/'example.svg').write_text('<svg xmlns=\"http://www.w3.org/2000/svg\" "
        "width=\"760\" height=\"260\">'+body+'</svg>')\n"
        "(HERE/'table.json').write_text(json.dumps(TABLE,ensure_ascii=False,indent=2))\n"
        "with (HERE/'example.csv').open('w',newline='') as f:\n"
        " w=csv.writer(f);w.writerow(['Characteristic']+[c['label'] for c in TABLE['columns']])\n"
        " for r in TABLE['rows']:w.writerow([r['label']]+[r['cells'].get(c['id'],'') "
        "for c in TABLE['columns']])\n"
    )
    script = preview / "render.py"
    script.write_text(producer)
    subprocess.run([str(ROOT / "council/.venv/bin/python"), str(script)], check=True)
    work = WorkStore(FreezeStore(project))
    work.add(
        [{"title": "Article table", "why": "Existing human layout requirement"}],
        request_id="seed",
        actor="codex",
    )
    work.commit_work(
        {
            "read_set": {"F-000001": 1},
            "changes": [
                {
                    "id": "F-000001",
                    "problem_type": "project_fact",
                    "definition": {
                        "operation": "definition_draft",
                        "value": block(table, "Explore/table-preview/example.svg"),
                    },
                    "phase": {
                        "phase": "human_review",
                        "conclusion_type": "single_recommendation",
                        "reason": "Human fixture layout",
                        "trigger_refs": ["human-layout"],
                        "affected_refs": ["F-000001"],
                        "completion_conditions": ["Human confirmation"],
                    },
                }
            ],
        },
        request_id="draft",
    )
    token = work.read("F-000001")["candidate"]["approval_token"]
    work.commit_work(
        {
            "read_set": work.read("F-000001")["read_set"],
            "changes": [
                {"id": "F-000001", "definition": {"operation": "definition_approve", "value": token}}
            ],
        },
        request_id="approve",
        actor="user",
    )
    (project / "Data/derived").mkdir(parents=True, exist_ok=True)
    (project / "Data/derived/table-v1.json").write_text(json.dumps(table, ensure_ascii=False))
    (project / "Scripts/01_table.py").write_text(
        "import csv,json\nfrom pathlib import Path\nroot=Path(__file__).resolve().parents[1]\n"
        "t=json.loads((root/'Data/derived/table-v1.json').read_text())\n"
        "with (root/'Results/current-table.csv').open('w',newline='') as f:\n"
        " w=csv.writer(f);w.writerow(['Characteristic']+[c['label'] for c in t['columns']])\n"
        " for r in t['rows']:w.writerow([r['label']]+[r['cells'][c['id']] for c in t['columns']])\n"
    )
    (project / "Audit/checks").mkdir(parents=True, exist_ok=True)
    (project / "Audit/checks/table_v1.py").write_text(
        "import csv\nfrom pathlib import Path\nr=Path(__file__).resolve().parents[2]\n"
        "rows=list(csv.reader((r/'Results/current-table.csv').open()))\n"
        "assert rows[0]==['Characteristic','Group A','Group B'] and len(rows)==4\n"
    )
    shutil.copy2(preview / "example.csv", project / "Results/current-table.csv")
    work.commit_work(
        {
            "read_set": work.read("F-000001")["read_set"],
            "changes": [
                {
                    "id": "F-000001",
                    "problem_type": "output_specification",
                    "verification_tests": [
                        {
                            "path": "Audit/checks/table_v1.py",
                            "scope": "v1 table layout",
                            "definition_version": 1,
                        }
                    ],
                }
            ],
        },
        request_id="seed-kind",
    )
    current = work.read("F-000001")["current"]
    Outputs(project).register(
        {
            "id": "current-table",
            "path": "Results/current-table.csv",
            "kind": "table",
            "audience": "publication",
            "producer": "Scripts/01_table.py",
            "specification": {"question_id": "F-000001", "version": 1, "text_sha256": current["text_sha256"]},
        }
    )
    updated = copy.deepcopy(table)
    updated["title"] = "Baseline characteristics by treatment"
    updated["columns"].reverse()
    updated["headers"].reverse()
    updated["rows"] = [r for r in updated["rows"] if r["id"] != "bmi"]
    updated["footnotes"].append({"id": "format", "text": "Age is mean (SD); diabetes is n (%)."})
    work.commit_work(
        {
            "read_set": work.read("F-000001")["read_set"],
            "changes": [
                {
                    "id": "F-000001",
                    "definition": {
                        "operation": "definition_draft",
                        "value": block(updated, "Explore/table-preview/example.svg"),
                    },
                }
            ],
        },
        request_id="human-table-edit",
        actor="user",
    )
    (project / "README.md").write_text(
        "# Synthetic reporting project\n\nCurrent research stage: report assembly. All values are fictional. "
        "F-000001 has a confirmed v1 and a pending candidate edited by the human in the table editor. "
        "Explore/table-preview/render.py generates the SVG, CSV and structured JSON example. "
        "Results/current-table.csv is the existing output for v1. No other analysis is in scope.\n"
    )
    for skill in ("oppencouncil", "oppen-project-steward", "stepwise-r-project"):
        shutil.copytree(
            ROOT / "skills" / skill,
            case / "skills" / skill,
            ignore=shutil.ignore_patterns("__pycache__", "tests"),
        )
    wrapper = TOOLS.replace(
        'elif command in {"council","project"}:',
        """elif command=="execute":
    path=local(args[0]);path.relative_to(BASE/"project")
    run=subprocess.run([CONFIG["python"],str(path)],cwd=BASE/"project",text=True,capture_output=True)
    log({"operation":"execute","path":args[0],"returncode":run.returncode,"stdout":run.stdout,"stderr":run.stderr})
    print(run.stdout,end="");print(run.stderr,file=sys.stderr,end="");sys.exit(run.returncode)
elif command in {"council","project"}:""",
    )
    (case / "tools.py").write_text(wrapper)
    (case / "runtime.json").write_text(
        json.dumps(
            {
                "python": str(ROOT / "council/.venv/bin/python"),
                "helper": str(case / "skills/oppencouncil/scripts/oppencouncil.py"),
            }
        )
    )
    (case / "request.md").write_text(
        "我已经在候选表格里改了标题、删掉 BMI 行，把 B 组放到了 A 组前面，还补了格式脚注。"
        "继续处理这次修改，把制表代码和模拟示例同步好，留给我审阅。\n\n"
        "Use the supplied Skill and synthetic project only. No network, live service, external messages, "
        "human-confirmation calls or other cases. Write only inside this case. "
        "Use `python3 tools.py read PATH...`, "
        "`list [DIRECTORY]`, `write PATH` (UTF-8 stdin), `council COMMAND PROJECT [OPTIONS]`, "
        "`project COMMAND PROJECT [OPTIONS]`, or `execute PROJECT_SCRIPT_PATH` for all operations. "
        "Do not inspect or change tools.py, runtime.json or trace.jsonl. Start by reading "
        "skills/oppencouncil/SKILL.md and project/README.md. Finish with outcome.md.\n"
    )
    def digest(p):
        return hashlib.sha256(p.read_bytes()).hexdigest()
    manifest = {
        "directory": str(case),
        "scenario": "human_table_edit",
        "before": work.read("F-000001"),
        "expected_table": updated,
        "files_before": {
            p.relative_to(project).as_posix(): digest(p) for p in project.rglob("*") if p.is_file()
        },
    }
    (destination / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    return str(case)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    print(prepare(parser.parse_args().destination))
