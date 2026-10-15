"""Prepare isolated integration tasks using the actual final shared Skill files."""

import argparse
import hashlib
import json
import shutil
import uuid
from pathlib import Path

from council_fixture import ROOT, TOOLS
from council_fixture import seed as seed_council
from oppencouncil.bootstrap import create
from output_fixture import seed as seed_output


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(destination):
    destination.mkdir(parents=True, exist_ok=False)
    manifest = []
    for scenario in ("general_alias", "descriptive", "resume"):
        case = destination / uuid.uuid4().hex[:12]
        case.mkdir()
        project = case / "project"
        before = None
        if scenario == "general_alias":
            project.mkdir()
            (project / "Source").mkdir()
            (project / "Source/report.py").write_text(
                "def export_rows(rows):\n"
                "    return [{'id': r['id'], 'amount': r['amount']} for r in rows if r['amount']]\n"
            )
            (project / "README.md").write_text(
                "# Ordinary software project\n\nThe export API accepts rows with id and amount. "
                "Its existing contract preserves input order and both positive and negative numeric amounts; "
                "zero is a valid amount. None means absent and is omitted. Field names are id and amount. "
                "Source/report.py implements this API. This is an ordinary software project, "
                "with no scientific analysis or pending product decision.\n"
            )
            create(
                project,
                project_type="general",
                layout="namespace",
                adoption=True,
                payload={
                    "role_mappings": {"source": "Source"},
                    "initial_canonical_registrations": [],
                    "initial_deliverable_registrations": [],
                },
            )
            entry = "skills/oppen-project-steward/SKILL.md"
            helper = "skills/oppen-project-steward/scripts/oppen_project_steward.py"
            task = "导出函数漏掉了金额为 0 的记录。按现有接口约定修复并验证，完成这项小修复。"
        elif scenario == "descriptive":
            work = seed_output(project)
            before = work.read("F-000001")
            entry = "skills/oppencouncil/SKILL.md"
            helper = "skills/oppencouncil/scripts/oppencouncil.py"
            task = (
                "继续完成这一轮描述性分析并验收。现有脚本已经跑通，请把当前产出整理到可以用于文章的状态。"
                "保持已确认的研究范围和表格规格；不做额外分析。"
            )
        else:
            work = seed_council(project, "absent")
            work.commit_work(
                {
                    "read_set": work.read("F-000001")["read_set"],
                    "changes": [
                        {
                            "id": "F-000001",
                            "comments": [
                                "The study team confirmed a baseline-eligible target population. "
                                "The synthetic eligible flag is measured at baseline, "
                                "before outcome follow-up. "
                                "Restricting to eligible = 1 implements that population; it is not a "
                                "later-outcome or missing-sex exclusion. The decision and project rationale "
                                "are already confirmed; no new literature claim is involved."
                            ],
                        }
                    ],
                },
                request_id="recorded-rationale",
            )
            work.commit_work(
                {
                    "read_set": work.read("F-000001")["read_set"],
                    "changes": [
                        {
                            "id": "F-000001",
                            "comments": ["为什么使用 eligible = 1 的人群？这是随访结局之后才筛的吗？"],
                        }
                    ],
                },
                request_id="human-followup",
                actor="user",
            )
            before = work.read("F-000001")
            entry = "skills/stepwise-r-project/SKILL.md"
            helper = "skills/stepwise-r-project/scripts/stepwise_r_project.py"
            task = "接续 F-000001 的新留言，把解释保存在原事项中。这次只解释已有口径。"
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
            json.dumps({"python": str(ROOT / "council/.venv/bin/python"), "helper": str(case / helper)})
        )
        request = task + (
            "\n\nUse the supplied Skill and this synthetic project. "
            "No network, live service, external messages, "
            "human-confirmation calls or other case access. Write only inside this case. "
            "For auditable operations, use `python3 tools.py read PATH...`, `list [DIRECTORY]`, "
            "`write PATH` (UTF-8 stdin), `council COMMAND PROJECT [OPTIONS]`, "
            "`project COMMAND PROJECT [OPTIONS]`, or `execute PROJECT_SCRIPT_PATH` (Python). "
            "Use these wrappers for all reads, writes and CLI/script execution. "
            "Do not inspect or change tools.py, runtime.json or trace.jsonl. "
            f"Start by reading {entry} and project/README.md. "
            "Finish by writing outcome.md with results and checks.\n"
        )
        (case / "request.md").write_text(request)
        manifest.append(
            {
                "scenario": scenario,
                "directory": str(case),
                "entry": entry,
                "request_sha256": digest(case / "request.md"),
                "before": before,
                "files_before": {
                    str(p.relative_to(project)): digest(p) for p in project.rglob("*") if p.is_file()
                },
            }
        )
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return [{"scenario": c["scenario"], "directory": c["directory"]} for c in manifest]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    print(json.dumps(prepare(parser.parse_args().destination), indent=2))
