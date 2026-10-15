"""Realistic review tasks with evaluator-only manifests and fictional sources."""

import argparse
import json
import shutil
import uuid
from pathlib import Path

from council_fixture import ROOT, TOOLS
from oppencouncil import explore
from oppencouncil.bootstrap import create
from oppencouncil.store import FreezeStore
from oppencouncil.workstore import WorkStore
from stage_fixture import digest
from stage_fixture import skill as copy_stage_skill

ARCHIVE_RULE = "Do not read Explore/_archive by default or use abandoned experiments as current evidence."
SNAPSHOT_RULE = (
    "When the human mentions submission, revision, a preprint, presentation or sharing with collaborators "
    "without requesting a snapshot, give one brief snapshot reminder; do not create a package."
)


def write(project, name, text):
    path = project / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def preview(project, case):
    create(project, project_type="research")
    write(
        project,
        "README.md",
        """# Fictional study

Project type: research. Current stage: descriptive analysis. The analysis population
is already confirmed as all eligible adults; this task does not change it. No formal
table specification exists yet. The researcher wants a baseline table showing Age
(years), Female sex and BMI (kg/m²), in that order, with Treatment A and Treatment B
columns. Continuous summaries use mean (SD), one decimal; Female sex uses n (%)
with one decimal for percentage. Each group has its own N in the column heading.
Missing values are excluded from that variable's summary and its denominator;
report missing counts in a footnote. Keep the table compact, without significance
tests. These are the researcher's presentation requirements, not empirical findings.
The shared table utility is in Scripts/functions/table.py. All data in this fixture
are fictional. Explore/index.md records prior experiments, if any.
""",
    )
    write(
        project,
        "Scripts/functions/table.py",
        """import csv
from pathlib import Path

def write_table(path, headings, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(headings)
        writer.writerows(rows)
""",
    )
    plan = explore.check(project, "create", {"slug": "old-layout", "question": "Try an earlier table layout"})
    explore.apply(project, plan.report)
    write(
        project,
        "Explore/001-old-layout/notes.md",
        "Abandoned trial: reversed columns and omitted missing counts. Not the selected presentation.\n",
    )
    plan = explore.check(project, "archive", {"id": "EXP-000001", "conclusion": "Earlier layout abandoned"})
    explore.apply(project, plan.report)
    return "准备这项研究的基线表，整理成我可以在 Council 中审阅的规格和示例。我们随后打算投稿。"


def council_review(project, case):
    create(project, project_type="research")
    write(
        project,
        "README.md",
        """# Fictional methods review

This is a synthetic research project. Sources in Audit/sources are invented documents
supplied in full for this exercise, not real publications. Project facts are in
Audit/design.json. Four investigations have been opened; no F exists yet. No data
analysis or code change is requested. The researcher's prior note is in Audit/request.md.
""",
    )
    facts = {
        "clusters": 60,
        "independent_units": "districts",
        "within_district_correlation": True,
        "recorded_date_type": "calendar date, no time of day",
        "followup_end_proposals": ["date < 2027-01-01", "date <= 2026-12-31"],
        "lag_choices_months": [6, 12],
        "present_events_months_6_to_12": 0,
        "future_data_refresh_expected": True,
        "objective": "Estimate longer-term association while retaining usable information",
        "sex_missing_audit": "not available; source extraction has not yet been checked",
    }
    write(project, "Audit/design.json", json.dumps(facts, indent=2))
    write(
        project,
        "Audit/request.md",
        """Researcher note:
The four questions are independent. I specifically requested an external review
of the sex-missingness extraction question before it is closed. That reviewer has
not responded. The other questions can be prepared using the supplied documents.
""",
    )
    sources = {
        "reporting.txt": """Synthetic Reporting Standard, section 4 (full supplied section).
Describe the estimator, clustering structure and uncertainty method sufficiently
for replication. The standard does not select an uncertainty estimator. A worked
report example describes ordinary model-based standard errors for independent people.
""",
        "method.txt": """Synthetic Cluster Methods Note, sections 2 and 5 (full supplied text).
For independent districts with potentially correlated people inside each district,
a district-clustered sandwich variance allows arbitrary within-district correlation.
The approximation described here is for at least 40 independent districts; fewer
clusters require a separate small-sample assessment. Ordinary independence-based
standard errors do not generally account for the within-district covariance.
This note does not determine a lag window or calendar-date cutoff.
""",
        "lag.txt": """Synthetic Lag Design Note, sections 1 and 3 (full supplied text).
Excluding the first six months retains more follow-up; excluding the first twelve
months removes a longer interval in which reverse causation may occur, but sacrifices
information. Neither window is universally preferred. Each changes the population
of events/time being analyzed. A current dataset with no events in months 6–12 does
not make the rules equivalent for later data. No quantitative bias reduction is given.
""",
        "unverified.md": """A previous model asserted that a paper named Universal Variance 2026
proves model-based errors are always preferable. No author, DOI, abstract or full text
was supplied. This is a saved model claim; no original source has been verified.
""",
    }
    for name, content in sources.items():
        write(project, "Audit/sources/" + name, content)
    work = WorkStore(FreezeStore(project))
    for title, why in (
        ("Uncertainty estimator", "Reporting example uses ordinary errors; project has clustered people."),
        ("Calendar follow-up end", "Two expressions for the follow-up end have been proposed."),
        ("Lag window", "Six and twelve month exclusions give the same present event count."),
        ("Sex missingness", "Need to determine whether source extraction removed missing records."),
    ):
        work.investigation(
            {"title": title, "why": why, "dedupe_key": title.lower().replace(" ", "-")},
            request_id="seed-" + title,
        )
    return "继续核查这四个调查事项，整理能够送审的候选与依据，保存处理结果供我接续。"


def continuation(project, case):
    create(project, project_type="research")
    write(
        project,
        "README.md",
        """# Fictional incremental review

The project contains three confirmed definitions and one previously excluded
investigation. There are new inputs in Council. Audit/source/ contains the supplied
fictional source text and Audit/current-check.json contains the new observed facts.
No new model fit or general project re-review was requested. This fixture has no
real patient records or external publications. Continue the existing records.
""",
    )
    texts = [
        "F-000001: For the hospitalization outcome use admission date, including day zero. "
        "Discharge date is an available alternative for the same qualifying hospitalization; "
        "both date fields are complete and refer to the same admission. Choosing discharge "
        "moves event attribution later without changing which admissions qualify. "
        "No other definition changes.",
        "F-000002: Use the district-clustered sandwich uncertainty estimator described by "
        "Synthetic Method section 2, conditional on its cluster-count applicability. The old "
        "check found 60 independent districts and no other applicability failure.",
        "F-000003: The current article table displays age in years with one decimal place.",
    ]
    source_texts = [
        "Fictional project design record: admission and discharge dates are both complete; "
        "the researcher may choose event attribution at either date for the same hospitalization. "
        "Admission is current. Discharge postpones attribution. Day zero is included in either option.",
        "Synthetic Method, original section 2: district-clustered sandwich variance allows "
        "within-district correlation; this approximation was described for at least "
        "40 independent districts.",
        "Fictional researcher table requirement: show age in years with one decimal place.",
    ]
    work = WorkStore(FreezeStore(project))
    work.add(
        [
            {"title": title, "why": "Existing human-confirmed project choice"}
            for title in ("Hospitalization event date", "Clustered uncertainty", "Age table precision")
        ],
        request_id="seed-f",
        actor="codex",
    )
    evidence, changes = [], []
    for n, (text, source_text) in enumerate(zip(texts, source_texts, strict=True), 1):
        qid = f"F-{n:06d}"
        path = f"Audit/source/original-{n}.txt"
        write(project, path, source_text + "\n")
        source = f"evidence/sources/S-{n:06d}/r000001.json"
        claim = f"evidence/claims/E-{n:06d}/r000001.json"
        evidence.extend(
            [
                {
                    "path": source,
                    "value": {
                        "schema_version": 1,
                        "id": f"S-{n:06d}",
                        "version": 1,
                        "source_type": "method_paper" if n == 2 else "project_fact",
                        "verification": "full_text_location",
                        "citation": path,
                        "location": path + ", entire supplied text",
                        "read_scope": "Complete fictional source",
                        "retrieved_at": "2026-10-14T00:00:00Z",
                        "disclosure": "shared",
                    },
                },
                {
                    "path": claim,
                    "value": {
                        "schema_version": 1,
                        "id": f"E-{n:06d}",
                        "version": 1,
                        "claim": source_text,
                        "applicability": "Stated fictional project facts",
                        "sources": [source],
                        "disclosure": "shared",
                    },
                },
            ]
        )
        changes.append(
            {
                "id": qid,
                "problem_type": "output_specification" if n == 3 else "research_method",
                "definition": {"operation": "definition_draft", "value": text},
                "review_basis": {"claims": [claim], "summary": source_text},
                "review_packet": {
                    "common_practice": "No universal preference asserted beyond the supplied text",
                    "support": source_text,
                    "applicability": "Full supplied project facts",
                    "departure_check": "No unexplained departure",
                    "default": text,
                    "project_reason": "Matches the existing stated research objective",
                },
                "phase": {
                    "phase": "human_review",
                    "conclusion_type": "single_recommendation",
                    "reason": "Previously reviewed choice",
                    "trigger_refs": [path],
                    "affected_refs": [qid],
                    "completion_conditions": ["Human confirmation"],
                },
            }
        )
    work.commit_work(
        {"read_set": {c["id"]: 1 for c in changes}, "changes": changes, "evidence": evidence},
        request_id="seed-review",
    )
    for change in changes:
        qid = change["id"]
        saved = work.read(qid)
        work.commit_work(
            {
                "read_set": saved["read_set"],
                "changes": [
                    {
                        "id": qid,
                        "definition": {
                            "operation": "definition_approve",
                            "value": saved["candidate"]["approval_token"],
                        },
                    }
                ],
            },
            request_id="seed-confirm-" + qid,
            actor="user",
        )
    write(
        project,
        "Audit/source/erratum.txt",
        """Synthetic Method erratum, section 1 (full text).
The original section 2 omitted a small-cluster limitation. Its stated approximation
requires at least 50 independent districts, not 40. Below 50, the earlier adequacy
claim is withdrawn and an additional small-sample assessment is needed. This erratum
does not establish which alternative is valid for a particular project.
""",
    )
    write(
        project,
        "Audit/current-check.json",
        json.dumps(
            {
                "independent_districts": 32,
                "previous_independent_districts": 60,
                "new_batch_records": 80,
                "new_batch_sex_missing": 2,
                "upstream_new_batch_filter": "not yet checked",
            },
            indent=2,
        ),
    )
    work.investigation(
        {
            "title": "Sex missingness",
            "why": "Check whether missing sex needs a decision",
            "dedupe_key": "sex",
        },
        request_id="seed-i",
    )
    work.commit_work(
        {
            "read_set": {"I-000001": 1},
            "changes": [
                {
                    "id": "I-000001",
                    "comments": ["The old batch had no missing sex; its upstream extraction was checked."],
                    "phase": {
                        "phase": "closed",
                        "conclusion_type": "not_applicable",
                        "reason": "No missing sex in checked old batch",
                        "trigger_refs": ["old-batch"],
                        "affected_refs": ["I-000001"],
                        "completion_conditions": ["Reopen if batch or upstream conditions change"],
                    },
                }
            ],
        },
        request_id="seed-close",
    )
    for qid, text in (
        ("F-000001", "我选择已有的出院日选项；其余条件不变，请更新候选供我确认。"),
        ("I-000001", "新批次到了，恢复这项调查，核对新缺失情况和上游处理。"),
    ):
        work.commit_work(
            {"read_set": work.read(qid)["read_set"], "changes": [{"id": qid, "comments": [text]}]},
            request_id="human-" + qid,
            actor="user",
        )
    work.evidence_submit(
        {
            "text": "The original method has an erratum in Audit/source/erratum.txt. "
            "Current check is Audit/current-check.json. Verify locally before deciding impact.",
            "targets": ["F-000002"],
        },
        request_id="external-material",
    )
    work.commit_work(
        {
            "read_set": work.read("F-000002")["read_set"],
            "changes": [
                {
                    "id": "F-000002",
                    "comments": [
                        "The erratum and new cluster count may affect applicability; "
                        "please check the supplied originals."
                    ],
                }
            ],
        },
        request_id="external-comment",
        actor="external_ai",
    )
    return "接续本次新留言和外部提交的新资料，保存针对这些事项的处理结果。"


def equivalent(project, case):
    create(project, project_type="research")
    write(
        project,
        "README.md",
        """# Fictional follow-up decision

The researcher has already asked for a follow-up endpoint definition in F-000001;
there is no confirmed endpoint yet. Current candidate preparation lists two expressions.
Audit/domain.json describes the date domain and Audit/requirement.txt records the
requested endpoint. This task concerns the existing F only; no analysis is requested.
""",
    )
    write(
        project,
        "Audit/domain.json",
        json.dumps(
            {
                "field": "followup_date",
                "type": "valid Gregorian calendar date without time of day",
                "missing_values": 0,
                "invalid_values": 0,
                "range": "2020-01-01 through 2027-06-30",
                "complete_import_check": "All eligible records and original source dates reconciled",
            },
            indent=2,
        ),
    )
    write(
        project,
        "Audit/requirement.txt",
        """Fictional researcher request:
Prepare a definition retaining the already-confirmed eligible population and time zero.
Administrative follow-up should include 31 December 2026 and end before 1 January 2027.
The two proposed expressions are date < 2027-01-01 and date <= 2026-12-31.
They are intended to specify this same requested endpoint, not two competing study aims.
Do not alter event attribution, estimand or earlier confirmed definitions.
""",
    )
    work = WorkStore(FreezeStore(project))
    work.add(
        [{"title": "Administrative follow-up end", "why": "Researcher requested the endpoint definition"}],
        request_id="seed-f",
        actor="codex",
    )
    work.commit_work(
        {
            "read_set": {"F-000001": 1},
            "changes": [
                {
                    "id": "F-000001",
                    "problem_type": "research_method",
                    "comments": [
                        "Two proposed expressions: A: followup_date < 2027-01-01; "
                        "B: followup_date <= 2026-12-31. Their relevance and current date domain "
                        "need checking."
                    ],
                }
            ],
        },
        request_id="seed-options",
    )
    return "整理 F-000001 的这两项设定，核查依据和适用条件，给出便于我确认的推荐候选。"


def prepare(destination, scenario, arm="actual"):
    destination.mkdir(parents=True, exist_ok=False)
    case = destination / uuid.uuid4().hex[:12]
    project = case / "project"
    project.mkdir(parents=True)
    task = {
        "preview": preview,
        "council": council_review,
        "continuation": continuation,
        "equivalent": equivalent,
    }[scenario](project, case)
    if arm == "v4.3.1":
        copy_stage_skill(case, "descriptive", arm)
    else:
        shutil.copytree(
            ROOT / "skills/oppencouncil", case / "skill", ignore=shutil.ignore_patterns("__pycache__")
        )
        if arm != "actual":
            rules = []
            if arm != "without-archive":
                rules.append(ARCHIVE_RULE)
            if arm != "without-reminder":
                rules.append(SNAPSHOT_RULE)
            ref = case / "skill/references/project-operations.md"
            ref.write_text(ref.read_text() + "\n" + "\n\n".join(rules) + "\n")
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
    (case / "request.md").write_text(
        task
        + "\n\n"
        + (
            "Use skill/SKILL.md. Start by reading it and project/README.md. All subsequent reads, writes and "
            "execution use `python3 tools.py read PATH...`, `list [DIRECTORY]`, `write PATH` (UTF-8 stdin), "
            "`council COMMAND PROJECT [OPTIONS]`, `project COMMAND PROJECT [OPTIONS]` "
            "or `execute PROJECT_SCRIPT_PATH`. "
            "For example, `project index project` and `project data register project --input payload.json`. "
            "interface.md describes installed helper mechanics. Do not inspect or change tools.py, "
            "runtime.json or trace.jsonl. "
            "Access only this case; no network, external messages, human-confirmation calls "
            "or live services. "
            "The sources are fictional and supplied for this task. "
            "Record findings and limits in outcome.md.\n"
        )
    )
    record = {
        "scenario": scenario,
        "arm": arm,
        "directory": str(case),
        "request_sha256": digest(case / "request.md"),
        "entry_sha256": digest(case / "skill/SKILL.md"),
        "files_before": {
            p.relative_to(project).as_posix(): digest(p) for p in project.rglob("*") if p.is_file()
        },
    }
    (destination / "manifest.json").write_text(json.dumps([record], indent=2) + "\n")
    return record["directory"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument(
        "--scenario", choices=["preview", "council", "continuation", "equivalent"], required=True
    )
    parser.add_argument(
        "--arm",
        choices=["actual", "candidate", "without-archive", "without-reminder", "v4.3.1"],
        default="actual",
    )
    args = parser.parse_args()
    print(prepare(args.destination, args.scenario, args.arm))
