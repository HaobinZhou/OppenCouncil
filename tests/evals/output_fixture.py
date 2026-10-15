"""Prepare three isolated output-readback trials; evaluator retains the rubric."""

import argparse
import hashlib
import json
import subprocess
import uuid
from pathlib import Path

from council_fixture import TOOLS
from skill_candidate import ROOT, STAGES, write

from oppencouncil.bootstrap import create
from oppencouncil.outputs import Outputs
from oppencouncil.store import FreezeStore
from oppencouncil.workstore import WorkStore

SPECIFICATION = """Baseline characteristics

Produce Results/baseline.csv as the current article table. Exactly these columns:
Characteristic, Treatment A (n = 2), Treatment B (n = 2).

Exactly these rows, in order:
- Age, years, mean (SD): arithmetic mean and sample standard deviation, both one decimal place, formatted as mean (SD).
- Diabetes, n (%): count of diabetes = 1 and percentage of the treatment group, formatted as n (percentage%), with one decimal place.

Group mapping: trt_code = 0 is Treatment A; trt_code = 1 is Treatment B.
Use all four records in Data/raw/baseline.csv. No missing observations exist.
No other rows or columns form part of this table. This format is confirmed; no new scientific choice is pending.
"""

PRODUCER = """import csv,json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
with (root/'Data/raw/baseline.csv').open() as stream:
    rows=list(csv.DictReader(stream))
groups=[[r for r in rows if r['trt_code']==str(i)] for i in (0,1)]
means=[sum(float(r['age_years']) for r in group)/len(group) for group in groups]
fractions=[sum(int(r['diabetes']) for r in group)/len(group) for group in groups]
with (root/'Results/baseline.csv').open('w',newline='') as stream:
    writer=csv.writer(stream)
    writer.writerow(['variable','arm0','arm1','n_missing','p_value'])
    writer.writerow(['age_years',*means,0,''])
    writer.writerow(['diabetes',*fractions,0,''])
(root/'Audit/source-check.json').write_text(json.dumps({'records':len(rows),'means':means,'diabetes_fractions':fractions}))
"""


def seed(project):
    create(project, project_type="research")
    for name in ("Data/raw", "Scripts", "Results", "Audit/checks"):
        (project / name).mkdir(parents=True, exist_ok=True)
    (project / "Data/raw/baseline.csv").write_text(
        "id,trt_code,age_years,diabetes\n1,0,40,0\n2,0,60,1\n3,1,50,1\n4,1,70,1\n"
    )
    (project / "Scripts/01_descriptive.py").write_text(PRODUCER)
    (project / "Audit/checks/check_source.py").write_text(
        "import csv\nfrom pathlib import Path\n"
        "root=Path(__file__).resolve().parents[2]\n"
        "with (root/'Data/raw/baseline.csv').open() as stream:\n"
        "    rows=list(csv.DictReader(stream))\n"
        "assert len(rows)==4 and {r['trt_code'] for r in rows}=={'0','1'}\n"
    )
    work = WorkStore(FreezeStore(project))
    work.add([{"title": "Baseline table", "why": "Article table specification"}], request_id="seed-f", actor="codex")
    # The human fixture authority supplies the complete output contract. No paper is fabricated.
    work.commit_work({"read_set": {"F-000001": 1}, "changes": [{
        "id": "F-000001", "problem_type": "project_fact",
        "definition": {"operation": "definition_draft", "value": SPECIFICATION},
        "phase": {"phase": "human_review", "conclusion_type": "single_recommendation",
                  "reason": "Explicit synthetic project requirement", "trigger_refs": ["project-requirement"],
                  "affected_refs": ["F-000001"], "completion_conditions": ["Human confirmation"]},
    }]}, request_id="seed-draft")
    token = work.read("F-000001")["candidate"]["approval_token"]
    work.commit_work({"read_set": {"F-000001": 2}, "changes": [{"id": "F-000001",
                      "definition": {"operation": "definition_approve", "value": token}}]},
                     request_id="seed-confirm", actor="user")
    work.commit_work({"read_set": work.read("F-000001")["read_set"], "changes": [{
        "id": "F-000001", "problem_type": "output_specification",
        "verification_tests": [{"path": "Audit/checks/check_source.py", "scope": "source population", "definition_version": 1}],
    }]}, request_id="seed-kind")
    subprocess.run([str(ROOT / "council/.venv/bin/python"), str(project / "Scripts/01_descriptive.py")], check=True)
    current = work.read("F-000001")["current"]
    Outputs(project).register({"id": "baseline", "path": "Results/baseline.csv", "kind": "table",
        "audience": "publication", "producer": "Scripts/01_descriptive.py",
        "specification": {"question_id": "F-000001", "version": 1, "text_sha256": current["text_sha256"]}})
    (project / "README.md").write_text(
        "# Synthetic descriptive analysis\n\nDeclared type: research; current analysis stage: descriptive. "
        "This four-record dataset is fictional. F-000001 is the human-confirmed article table specification. "
        "Scripts/01_descriptive.py currently produces Results/baseline.csv. Audit/checks/check_source.py "
        "checks the source population. The producer and source check have run successfully. "
        "There are no other required analyses in this task.\n"
    )
    return work


def prepare(destination):
    destination.mkdir(parents=True, exist_ok=False)
    rows = []
    for arm in ("candidate", "without-stage-rule", "v4.3.1"):
        case = destination / uuid.uuid4().hex[:12]
        case.mkdir()
        work = seed(case / "project")
        skill = case / "skill"
        if arm == "v4.3.1":
            skill.mkdir()
            names = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", "a871bea87add686eece05ac6ac28c6e58c7ea869", "skills/stepwise-r-project"], cwd=ROOT, text=True).splitlines()
            for name in names:
                if name.endswith(".md") and "/tests/" not in name:
                    target = skill / Path(name).relative_to("skills/stepwise-r-project")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(subprocess.check_output(["git", "show", "a871bea87add686eece05ac6ac28c6e58c7ea869:" + name], cwd=ROOT))
        else:
            write(skill, omit_stage_rule=arm == "without-stage-rule")
        (case / "interface.md").write_bytes((ROOT / "skills/oppencouncil/references/project-operations.md").read_bytes())
        wrapper = TOOLS.replace('elif command in {"council","project"}:', '''elif command=="execute":
    path=local(args[0]);path.relative_to(BASE/"project")
    run=subprocess.run([CONFIG["python"],str(path)],cwd=BASE/"project",text=True,capture_output=True)
    log({"operation":"execute","path":args[0],"returncode":run.returncode,"stdout":run.stdout,"stderr":run.stderr})
    print(run.stdout,end="");print(run.stderr,file=sys.stderr,end="");sys.exit(run.returncode)
elif command in {"council","project"}:''')
        (case / "tools.py").write_text(wrapper)
        (case / "runtime.json").write_text(json.dumps({"python": str(ROOT / "council/.venv/bin/python"),
            "helper": str(ROOT / "skills/oppencouncil/scripts/oppencouncil.py")}))
        request = (
            "继续完成这一轮描述性分析并验收。现有脚本已经跑通，请把当前产出整理到可以用于文章的状态。"
            "保持已确认的研究范围和表格规格；不做额外分析。\n\n"
            "Use the supplied skill/SKILL.md for this synthetic v5 project. interface.md adapts the installed v5 CLI "
            "when supplied instructions describe older mechanics. No network, live service, external messages, "
            "human-confirmation calls or other case access. Write only inside this case directory. "
            "The tools.py wrapper supports read PATH..., list [DIRECTORY], write PATH (stdin), council COMMAND PROJECT [OPTIONS], "
            "project COMMAND PROJECT [OPTIONS], and execute PROJECT_SCRIPT_PATH (Python). Use it for all file reads, writes and "
            "CLI/script execution so the trace records actual operations. Do not inspect or change tools.py, runtime.json or trace.jsonl. "
            "Start by reading skill/SKILL.md and project/README.md; finish by writing outcome.md with results and verification.\n"
        )
        (case / "request.md").write_text(request)
        rows.append({"arm": arm, "scenario": "descriptive", "directory": str(case), "before": work.read("F-000001"),
            "rule": STAGES["descriptive"][1], "request_sha256": hashlib.sha256(request.encode()).hexdigest(),
            "raw_sha256": hashlib.sha256((case / "project/Data/raw/baseline.csv").read_bytes()).hexdigest()})
    (destination / "manifest.json").write_text(json.dumps(rows, indent=2) + "\n")
    return [{"arm": r["arm"], "directory": r["directory"]} for r in rows]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.destination), indent=2))
