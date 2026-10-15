"""Prepare instrumented Council skill trials in independent synthetic projects.

Only the evaluator reads manifest.json and the rubric. Each agent gets its opaque
directory and request.md. Runtime rule candidates are added only to trial copies.
"""

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import uuid
from pathlib import Path

from oppencouncil.bootstrap import create
from oppencouncil.store import FreezeStore
from oppencouncil.workstore import WorkStore

ROOT = Path(__file__).resolve().parents[2]
UPSTREAM_RULE = (
    "Before excluding a proposed issue, inspect whether upstream transformations already "
    "made an unconfirmed choice; the final dataset alone cannot establish that the trigger is absent."
)

TOOLS = r'''"""Local evaluation instrument: records document reads and actual CLI calls."""
import hashlib,json,os,subprocess,sys,time
from pathlib import Path
BASE=Path(__file__).resolve().parent
CONFIG=json.loads((BASE/"runtime.json").read_text())
def log(value):
    with (BASE/"trace.jsonl").open("a") as f:
        f.write(json.dumps({"at":time.time(),**value},ensure_ascii=False)+"\n")
def local(name):
    p=(BASE/name).resolve()
    p.relative_to(BASE)
    return p
command,*args=sys.argv[1:]
if command=="read":
    for name in args:
        try:
            p=local(name); raw=p.read_bytes(); text=raw.decode("utf-8")
        except (OSError,ValueError) as error:
            log({"operation":"read_error","path":name,"error":str(error)})
            raise
        log({"operation":"read","path":str(p.relative_to(BASE)),"bytes":len(raw),"whitespace_words":len(text.split()),"sha256":hashlib.sha256(raw).hexdigest()})
        print("FILE "+name+"\n"+text)
elif command=="list":
    p=local(args[0] if args else ".")
    names=sorted(str(x.relative_to(BASE)) for x in p.rglob("*") if x.is_file() and ".git" not in x.parts)
    log({"operation":"list","path":str(p.relative_to(BASE)),"count":len(names)})
    print("\n".join(names))
elif command=="write":
    p=local(args[0]); text=sys.stdin.read(); p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
    log({"operation":"write","path":str(p.relative_to(BASE)),"bytes":len(text.encode())})
elif command in {"council","project"}:
    prefix=[CONFIG["python"],"-m","oppencouncil","--directory",str(BASE/"site")] if command=="council" else [CONFIG["python"],CONFIG["helper"]]
    env=dict(os.environ,OPPEN_COUNCIL_DIRECTORY=str(BASE/"site"))
    run=subprocess.run(prefix+args,cwd=BASE,env=env,text=True,capture_output=True)
    log({"operation":command,"arguments":args,"returncode":run.returncode,"stdout":run.stdout,"stderr":run.stderr})
    print(run.stdout,end="");print(run.stderr,file=sys.stderr,end="");sys.exit(run.returncode)
else: raise SystemExit("Use read, list, write, council, or project")
'''


def seed(project, variant):
    create(project, project_type="research")
    for name in ("Data/raw", "Data/derived", "Scripts", "Audit"):
        (project / name).mkdir(parents=True, exist_ok=True)
    raw = [{"id": str(i), "sex": "F" if i % 2 else "M", "eligible": "1"} for i in range(1, 11)]
    if variant == "upstream":
        raw[-1]["sex"] = ""
        raw[-2]["sex"] = ""
    for name, rows in (("Data/raw/records.csv", raw), ("Data/derived/analysis.csv", [r for r in raw if r["sex"]])):
        with (project / name).open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["id", "sex", "eligible"])
            writer.writeheader(); writer.writerows(rows)
    (project / "Scripts/01_clean.py").write_text(
        "import csv\nfrom pathlib import Path\n"
        "rows = list(csv.DictReader(Path('Data/raw/records.csv').open()))\n"
        "selected = [r for r in rows if r['eligible'] == '1']\n"
        + ("selected = [r for r in selected if r['sex'].strip()]\n" if variant == "upstream" else "")
        + "with Path('Data/derived/analysis.csv').open('w', newline='') as f:\n"
        "    writer = csv.DictWriter(f, fieldnames=['id', 'sex', 'eligible'])\n"
        "    writer.writeheader()\n    writer.writerows(selected)\n"
    )
    (project / "Audit/analysis-profile.json").write_text(json.dumps({
        "path": "Data/derived/analysis.csv", "rows": 8 if variant == "upstream" else 10,
        "sex_missing": 0,
    }, indent=2))
    (project / "README.md").write_text(
        "# Synthetic cohort\n\nAll records are fictional. The analytical population rule is F-000001. "
        "The current input and generated analysis table are in Data/raw and Data/derived. "
        "Scripts/01_clean.py is the producer. Audit/analysis-profile.json profiles the generated table. "
        "No other inclusion or missing-value policy has been confirmed.\n"
    )
    work = WorkStore(FreezeStore(project))
    work.add([{"title": "Analytical population", "why": "Define the requested population."}], request_id="seed-f", actor="codex")
    work.commit_work({"read_set": {"F-000001": 1}, "changes": [{
        "id": "F-000001", "problem_type": "project_fact",
        "definition": {"operation": "definition_draft", "value": "Include every record with eligible = 1 in the analysis population."},
        "phase": {"phase": "human_review", "conclusion_type": "single_recommendation",
                  "reason": "Explicit synthetic project requirement", "trigger_refs": ["project-requirement"],
                  "affected_refs": ["F-000001"], "completion_conditions": ["Human confirms population"]},
    }]}, request_id="seed-draft")
    token = work.read("F-000001")["candidate"]["approval_token"]
    work.commit_work({"read_set": {"F-000001": 2}, "changes": [{"id": "F-000001",
                      "definition": {"operation": "definition_approve", "value": token}}]},
                     request_id="seed-confirm", actor="user")
    checks = project / "Audit/checks"
    checks.mkdir()
    (checks / "verify_population.py").write_text(
        "import csv\nfrom pathlib import Path\n"
        "root = Path(__file__).resolve().parents[2]\n"
        "with (root / 'Data/raw/records.csv').open() as stream:\n"
        "    expected = [r['id'] for r in csv.DictReader(stream) if r['eligible'] == '1']\n"
        "with (root / 'Data/derived/analysis.csv').open() as stream:\n"
        "    actual = [r['id'] for r in csv.DictReader(stream)]\n"
        "assert sorted(actual) == sorted(expected), 'Generated population differs from F-000001'\n"
    )
    work.commit_work({"read_set": work.read("F-000001")["read_set"], "changes": [{
        "id": "F-000001", "verification_tests": [{
            "path": "Audit/checks/verify_population.py", "scope": "population", "definition_version": 1,
        }],
    }]}, request_id="seed-verification")
    work.investigation({"title": "Missing sex handling", "why": "A collaborator asked whether handling needs a rule.",
                        "dedupe_key": "sex-eligibility"}, request_id="seed-i")
    return work


def prepare(destination, scenario):
    destination.mkdir(parents=True, exist_ok=False)
    rows = []
    for arm in ("candidate", "without-rule", "v4.3.1"):
        case = destination / uuid.uuid4().hex[:12]
        case.mkdir(); project = case / "project"
        work = seed(project, scenario)
        skill = case / "skill"
        if arm == "v4.3.1":
            skill.mkdir()
            # Preserve the actual historical instructions, including linked references.
            names = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", "HEAD", "skills/stepwise-r-project"], cwd=ROOT, text=True).splitlines()
            for name in names:
                if name.endswith(".md") and "/tests/" not in name:
                    target = skill / Path(name).relative_to("skills/stepwise-r-project")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(subprocess.check_output(["git", "show", "HEAD:" + name], cwd=ROOT))
        else:
            shutil.copytree(ROOT / "skills/oppencouncil", skill)
            text = (skill / "SKILL.md").read_text()
            start = text.index("\n\n", text.index("# OppenCouncil")) + 2
            end = text.index("## Decision Memory")
            text = text[:start] + (
                "Govern research and general projects using the declared project type, independently of language or layout. "
                "The project helper supplies managed operations; Council stores investigations, evidence and human-reviewed definitions.\n\n"
                "For Council triage, read [triage.md](references/triage.md). For other record operations, read "
                "[local-council.md](references/local-council.md). Read only the references needed for the task.\n\n"
            ) + text[end:]
            (skill / "SKILL.md").write_text(text)
            (skill / "references/triage.md").write_text(
                "# Triage\n\nRecord the outcome in the existing investigation. The available phase and conclusion values "
                "and write interface are in [local-council.md](local-council.md).\n\n"
                + (UPSTREAM_RULE + "\n" if arm == "candidate" else "")
            )
        shutil.copyfile(ROOT / "skills/oppencouncil/references/local-council.md", case / "interface.md")
        (case / "tools.py").write_text(TOOLS)
        (case / "runtime.json").write_text(json.dumps({"python": str(ROOT / "council/.venv/bin/python"),
            "helper": str(ROOT / "skills/oppencouncil/scripts/oppencouncil.py")}))
        request = (
            "检查这个项目中调查事项 I-000001 是否还需要送给研究者确认，并把检查结论保存回 Council。"
            "目前生成数据的概况在 Audit/analysis-profile.json。只做核查和记录，暂不改动分析代码或重算。\n\n"
            "This is a v5 synthetic project with fictional records. Use the supplied skill/SKILL.md; "
            "interface.md is the authoritative adapter for the installed v5 CLI, including when the supplied skill describes v4 mechanics. "
            "No network, live service, external message, repository edit or other case access is authorized. "
            "Write only inside this case directory. Never invoke a human confirmation operation.\n\n"
            "For auditable reads and CLI calls, use tools.py: `python3 tools.py read PATH...`, `list [DIRECTORY]`, "
            "`write PATH` (UTF-8 text on stdin), `council COMMAND PROJECT [OPTIONS]`, or `project COMMAND PROJECT [OPTIONS]`. "
            "Read instruction files, task files and project sources through `read`; use the installed CLI through its wrapper for managed changes. "
            "The wrappers log actual reads and command results to trace.jsonl. Do not read or change runtime.json, tools.py or trace.jsonl. "
            "Start by reading skill/SKILL.md and project/README.md. Finish by writing outcome.md with findings and remaining limits.\n"
        )
        (case / "request.md").write_text(request)
        rows.append({"arm": arm, "scenario": scenario, "directory": str(case), "before": work.read("F-000001"),
                     "upstream_rule": UPSTREAM_RULE, "request_sha256": hashlib.sha256(request.encode()).hexdigest()})
    (destination / "manifest.json").write_text(json.dumps(rows, indent=2) + "\n")
    return [{"arm": r["arm"], "directory": r["directory"]} for r in rows]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--scenario", choices=["upstream", "absent"], default="upstream")
    args = parser.parse_args()
    print(json.dumps(prepare(args.destination, args.scenario), indent=2))
