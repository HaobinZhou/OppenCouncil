"""Independent stage trials; keep arm identity and expected artifacts with the evaluator."""

import argparse
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
from skill_candidate import STAGES

BASE = "a871bea87add686eece05ac6ac28c6e58c7ea869"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def skill(case, stage, arm):
    destination = case / "skill"
    if arm == "v4.3.1":
        destination.mkdir()
        names = subprocess.check_output(
            ["git", "ls-tree", "-r", "--name-only", BASE, "skills/stepwise-r-project"],
            cwd=ROOT,
            text=True,
        ).splitlines()
        for name in names:
            if name.endswith(".md") and "/tests/" not in name:
                target = destination / Path(name).relative_to("skills/stepwise-r-project")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(subprocess.check_output(["git", "show", BASE + ":" + name], cwd=ROOT))
    else:
        shutil.copytree(
            ROOT / "skills/oppencouncil", destination, ignore=shutil.ignore_patterns("__pycache__")
        )
        if arm == "candidate":
            path = destination / "references" / f"research-stage-{stage}.md"
            title, body = path.read_text().split("\n\n", 1)
            path.write_text(title + "\n\n" + STAGES[stage][1] + "\n\n" + body)


def cleaning(project):
    create(project, project_type="research")
    for name in ("Data/raw", "Data/derived", "Scripts", "Results", "Audit/checks"):
        (project / name).mkdir(parents=True, exist_ok=True)
    source = project / "Data/raw/records.csv"
    source.write_text("id,age\n p1 ,0\n p2 ,54\n p3 ,\n")
    producer = project / "Scripts/01_clean.py"
    producer.write_text(
        "import csv,json\nfrom pathlib import Path\n"
        "root=Path(__file__).resolve().parents[1]\n"
        "with (root/'Data/raw/records.csv').open() as f: rows=list(csv.DictReader(f))\n"
        "for row in rows: row['id']=row['id'].strip()\n"
        "with (root/'Results/cleaned.csv').open('w',newline='') as f:\n"
        " writer=csv.DictWriter(f,fieldnames=['id','age']);writer.writeheader();writer.writerows(rows)\n"
        "(root/'Results/quality.json').write_text(json.dumps({'n':len(rows),"
        "'missing_age':sum(not r['age'] for r in rows)}))\n"
    )
    (project / "Audit/checks/source.py").write_text(
        "import csv\nfrom pathlib import Path\n"
        "root=Path(__file__).resolve().parents[2]\n"
        "with (root/'Data/raw/records.csv').open() as f: rows=list(csv.DictReader(f))\n"
        "assert len(rows)==3 and rows[0]['age']=='0'\n"
    )
    subprocess.run([str(ROOT / "council/.venv/bin/python"), str(producer)], check=True)
    Outputs(project).register_data(
        {
            "path": "Data/raw/records.csv",
            "kind": "raw",
            "version": "fictional-v1",
            "source": "Fictional three-record fixture supplied for this task",
        }
    )
    (project / "README.md").write_text(
        "# Fictional data import\n\nProject type: research. Current stage: import and cleaning. "
        "Scripts/01_clean.py and Audit/checks/source.py have run successfully. The requested transformation "
        "is to trim surrounding whitespace from IDs while preserving all three records, their order, "
        "age 0 and the empty age as missing. No exclusion, imputation, cohort construction, descriptive "
        "analysis, article output or new scientific decision is requested in this stage. "
        "The three input records are fictional. Continue only this stage.\n"
    )
    return {
        "expected_rows": [["id", "age"], ["p1", "0"], ["p2", "54"], ["p3", ""]],
        "producer": "Scripts/01_clean.py",
        "source": "Data/raw/records.csv",
        "raw_sha256": digest(source),
    }


def article_stage(project, stage):
    create(project, project_type="research")
    for name in ("Data/raw", "Scripts", "Results", "Audit/checks"):
        (project / name).mkdir(parents=True, exist_ok=True)
    if stage == "cohort":
        data = [{"step": "screened", "n": 120}, {"step": "excluded", "n": 20}, {"step": "included", "n": 100}]
        expected = [
            ["Cohort step", "Participants"],
            ["Screened", "120"],
            ["Excluded: eligibility", "20"],
            ["Included", "100"],
        ]
        specification = (
            "The current cohort-flow table has exactly columns Cohort step, Participants. "
            "Its rows are Screened, Excluded: eligibility, Included, in that order. "
            "They use screened, excluded, included counts respectively from Data/raw/stage.json. "
            "Use integer counts. There are no additional rows or columns."
        )
    else:
        data = (
            [
                {"analysis": "exclude_early", "rr": 0.9, "lo": 0.7, "hi": 1.2},
                {"analysis": "late_entry", "rr": 0.85, "lo": 0.65, "hi": 1.15},
            ]
            if stage == "sensitivity"
            else [{"analysis": "A_vs_B", "rr": 0.8, "lo": 0.6, "hi": 1.1}]
        )
        expected = (
            [
                ["Analysis", "Risk ratio (95% CI)"],
                ["Exclude first-year events", "0.90 (0.70–1.20)"],
                ["Later entry cohort", "0.85 (0.65–1.15)"],
            ]
            if stage == "sensitivity"
            else [["Contrast", "Risk ratio (95% CI)"], ["Treatment A vs B", "0.80 (0.60–1.10)"]]
        )
        specification = (
            "Use the supplied risk ratios and 95% interval bounds in Data/raw/stage.json; "
            "these are already on the ratio scale. "
            "Do not fit a model, exponentiate them, or invert the contrast. "
            "The exact first column labels, row order and table headings are "
            + json.dumps([expected[0], *[[r[0]] for r in expected[1:]]], ensure_ascii=False)
            + ". Match input rows by analysis ID: "
            + json.dumps({r["analysis"]: out[0] for r, out in zip(data, expected[1:], strict=True)})
            + ". Display rr (lo–hi) with two decimal places in the second column, using an en dash. "
            "Do not add p values, sample size or other rows or columns."
        )
    outputs = ["Results/stage.csv"]
    if stage == "reporting":
        outputs.append("Results/stage.md")
        specification += (
            " Both Results/stage.csv and Results/stage.md show exactly this same table. "
            "The Markdown title is Primary outcome. Its footnote is: "
            "Estimates are risk ratios; intervals are 95% CIs."
        )
    source = project / "Data/raw/stage.json"
    source.write_text(json.dumps(data))
    producer = project / ("Scripts/01_" + stage + ".py")
    code = (
        "import csv,json\nfrom pathlib import Path\n"
        "root=Path(__file__).resolve().parents[1]\n"
        "rows=json.loads((root/'Data/raw/stage.json').read_text())\n"
        "with (root/'Results/stage.csv').open('w',newline='') as f:\n"
        " writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)\n"
    )
    if stage == "reporting":
        code += (
            "(root/'Results/stage.md').write_text('# Working results\\n\\n"
            "| Contrast | Estimate |\\n| --- | --- |\\n| Treatment B vs A | 1.80 |\\n')\n"
        )
    producer.write_text(code)
    check = project / "Audit/checks/source.py"
    check.write_text(
        "import json\nfrom pathlib import Path\n"
        "root=Path(__file__).resolve().parents[2]\n"
        "rows=json.loads((root/'Data/raw/stage.json').read_text())\n"
        f"assert len(rows)=={len(data)}\n"
    )
    subprocess.run([str(ROOT / "council/.venv/bin/python"), str(producer)], check=True)
    work = WorkStore(FreezeStore(project))
    work.add(
        [{"title": "Confirmed stage output", "why": "Human article format requirement"}],
        request_id="seed-f",
        actor="codex",
    )
    work.commit_work(
        {
            "read_set": {"F-000001": 1},
            "changes": [
                {
                    "id": "F-000001",
                    "problem_type": "project_fact",
                    "definition": {"operation": "definition_draft", "value": specification},
                    "phase": {
                        "phase": "human_review",
                        "conclusion_type": "single_recommendation",
                        "reason": "Human fixture requirement",
                        "trigger_refs": ["fixture-requirement"],
                        "affected_refs": ["F-000001"],
                        "completion_conditions": ["Human confirmation"],
                    },
                }
            ],
        },
        request_id="seed-draft",
    )
    saved = work.read("F-000001")
    work.commit_work(
        {
            "read_set": saved["read_set"],
            "changes": [
                {
                    "id": "F-000001",
                    "definition": {
                        "operation": "definition_approve",
                        "value": saved["candidate"]["approval_token"],
                    },
                }
            ],
        },
        request_id="seed-confirm",
        actor="user",
    )
    work.commit_work(
        {
            "read_set": work.read("F-000001")["read_set"],
            "changes": [
                {
                    "id": "F-000001",
                    "problem_type": "output_specification",
                    "verification_tests": [
                        {"path": "Audit/checks/source.py", "scope": "supplied input", "definition_version": 1}
                    ],
                }
            ],
        },
        request_id="seed-kind",
    )
    current = work.read("F-000001")["current"]
    store = Outputs(project)
    store.register_data(
        {
            "path": "Data/raw/stage.json",
            "kind": "raw",
            "version": "fixture-v1",
            "source": "Fictional stage summary supplied for this task",
        }
    )
    for n, name in enumerate(outputs):
        Outputs(project).register(
            {
                "id": "stage-" + str(n),
                "path": name,
                "kind": "cohort-flow" if stage == "cohort" else "table",
                "audience": "publication",
                "producer": producer.relative_to(project).as_posix(),
                "specification": {
                    "question_id": "F-000001",
                    "version": 1,
                    "text_sha256": current["text_sha256"],
                },
            }
        )
    (project / "README.md").write_text(
        "# Fictional research stage\n\nDeclared type: research. Current stage: " + stage + ". "
        "All source numbers are fictional, supplied immutable summaries for this task. "
        "The numbered script has run successfully. Audit/checks/source.py checks its input. "
        "F-000001 is the human-confirmed output specification. Finish only this stage's current outputs; "
        "no additional model, cohort change, data collection or scientific decision is requested.\n"
    )
    return {
        "expected_rows": expected,
        "outputs": outputs,
        "before": work.read("F-000001"),
        "producer": producer.relative_to(project).as_posix(),
        "source": "Data/raw/stage.json",
        "raw_sha256": digest(source),
    }


def prepare(destination, stage, arms=None):
    destination.mkdir(parents=True, exist_ok=False)
    rows = []
    for arm in arms or ("candidate", "without-stage-rule", "v4.3.1"):
        case = destination / uuid.uuid4().hex[:12]
        project = case / "project"
        project.mkdir(parents=True)
        expected = cleaning(project) if stage == "cleaning" else article_stage(project, stage)
        skill(case, stage, arm)
        (case / "interface.md").write_bytes(
            (ROOT / "skills/oppencouncil/references/project-operations.md").read_bytes()
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
                    "helper": str(ROOT / "skills/oppencouncil/scripts/oppencouncil.py"),
                }
            )
        )
        request = (
            "继续完成当前阶段并验收。现有脚本已经跑通；保持项目说明中的处理范围和已确认规格，不扩展分析。\n\n"
            "Use the supplied skill/SKILL.md for this synthetic v5 project. "
            "interface.md adapts installed v5 CLI mechanics when the supplied skill describes older tools. "
            "No network, live service, external messages, "
            "human-confirmation calls, or other case access. Write only inside this case. "
            "Use `python3 tools.py read PATH...`, `list [DIRECTORY]`, `write PATH` (UTF-8 stdin), "
            "`council COMMAND PROJECT [OPTIONS]`, `project COMMAND PROJECT [OPTIONS]`, "
            "or `execute PROJECT_SCRIPT_PATH` for all reads, writes and execution. "
            "For example, `project index project` and `project data register project --input payload.json`; "
            "nested subcommands precede the target. "
            "Do not inspect or change tools.py, runtime.json or trace.jsonl. "
            "Start by reading skill/SKILL.md and project/README.md. Finish with outcome.md.\n"
        )
        (case / "request.md").write_text(request)
        rows.append(
            {
                "arm": arm,
                "scenario": stage,
                "directory": str(case),
                **expected,
                "rule": STAGES[stage][1],
                "request_sha256": hashlib.sha256(request.encode()).hexdigest(),
                "files_before": {
                    p.relative_to(project).as_posix(): digest(p) for p in project.rglob("*") if p.is_file()
                },
            }
        )
    (destination / "manifest.json").write_text(json.dumps(rows, indent=2) + "\n")
    return [{"arm": row["arm"], "directory": row["directory"]} for row in rows]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument(
        "--stage", choices=["cleaning", "cohort", "primary", "sensitivity", "reporting"], required=True
    )
    parser.add_argument("--arm", action="append", choices=["candidate", "without-stage-rule", "v4.3.1"])
    args = parser.parse_args()
    print(json.dumps(prepare(args.destination, args.stage, args.arm), indent=2))
