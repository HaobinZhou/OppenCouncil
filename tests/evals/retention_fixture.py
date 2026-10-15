"""Trial-only condensed 4.3.1 review instructions, with independent deletion arms."""

import argparse
import json
import shutil
import subprocess
from pathlib import Path

from oppencouncil.bootstrap import create
from oppencouncil.store import FreezeStore
from oppencouncil.workstore import WorkStore
from review_fixture import council_review, prepare, write
from stage_fixture import BASE, ROOT

COMPLETE_RULE = (
    "Before marking a candidate ready, check its actual decision scope: resolve the source rule and "
    "implementation; state the operative inputs, predicates/actions and relevant time, threshold or "
    "exception conventions; bind consumed definitions by exact version; and walk through normal and "
    "relevant boundary cases. If materially different outcomes still fit, resolve or explicitly propose "
    "the missing decision now. Keep an unresolved necessary gap out of human-review readiness; "
    "promising to specify it later is not completeness."
)
SCIENTIFIC_RULE = (
    "For affected scientific choices, explain the population, time zero and follow-up, treatment/event "
    "attribution, estimand and required data or work. Use only the time resolution supported by the data."
)
FOCUSED_RULE = (
    "Keep each separable necessary decision in its own F and group related choices. Lead review text "
    "with the decision and practical effect, using descriptive headings and short parallel comparisons. "
    "Explain shared rules once; for independent parameter values within one approach, use the inline "
    "choices in selectors.md rather than whole-plan columns for every value combination. "
    "Candidates use concrete proposed values; selections are not confirmation."
)


def scientific(project, case):
    create(project, project_type="research")
    write(
        project,
        "README.md",
        """# Fictional treatment study

The proposed question is whether initiating A rather than B changes one-year risk
of first admission among eligible new users. Only monthly extracts are available.
Audit/source-data.json is the complete fictional field and timing description.
No treatment assignment, time-zero or event attribution rule is confirmed yet.
The collaborator's proposed shortcut is in Audit/proposal.md. Prepare the needed
scientific choices and explain their meaning for human review; do not fit a model.
""",
    )
    write(
        project,
        "Audit/source-data.json",
        json.dumps(
            {
                "population": "eligible adults with no A/B use in the preceding 12 observed months",
                "fields": ["person_id", "month", "A_started", "B_started", "first_admission"],
                "resolution": "calendar month only; no day or within-month order",
                "rows": [
                    {
                        "person_id": "p1",
                        "month": "2026-01",
                        "A_started": 1,
                        "B_started": 0,
                        "first_admission": 1,
                    },
                    {
                        "person_id": "p2",
                        "month": "2026-01",
                        "A_started": 1,
                        "B_started": 1,
                        "first_admission": 0,
                    },
                    {
                        "person_id": "p3",
                        "month": "2026-01",
                        "A_started": 0,
                        "B_started": 1,
                        "first_admission": 0,
                    },
                ],
                "access": "Day-level data are not available in this project",
            },
            indent=2,
        ),
    )
    write(
        project,
        "Audit/proposal.md",
        """Collaborator proposal, not an approved rule:
For everyone starting A and/or B in January, start follow-up at their exact first
prescription day. Assign a person to whichever drug was first. If admission occurs
in that same month, count it only if it happened after treatment. This should let
us report the requested one-year initiation effect without changing the question.
""",
    )
    work = WorkStore(FreezeStore(project))
    work.investigation(
        {
            "title": "Treatment initiation and follow-up",
            "why": "Evaluate the collaborator proposal against available data",
            "dedupe_key": "initiation",
        },
        request_id="seed-i",
    )
    return "核查合作者这份方案，准备需要我确认的科研口径，并说明具体会影响什么。"


def focused(project, case):
    create(project, project_type="general")
    write(
        project,
        "README.md",
        """# Fictional receipt service

This is a general software project. The established durable-write contract is in
F-000001. Three requested product choices are still open: receipt retention,
comment visibility, and the automatic retry policy. All allowed values work with
the existing durable-write contract and with each other. Audit/options.json contains
the verified allowed values and measured/qualitative effects. There is no need for
new scientific evidence, implementation, or deployment in this task.
""",
    )
    write(
        project,
        "Audit/options.json",
        json.dumps(
            {
                "retention_days": [7, 30, 90],
                "retention_effect": (
                    "Longer recovery history uses more storage; no legal minimum in this fictional service"
                ),
                "comment_visibility": ["owner_only", "team"],
                "visibility_effect": (
                    "Team visibility helps shared review but exposes comments to the current project team"
                ),
                "retry_delay_seconds": [5, 10, 30],
                "retry_attempt_limit": [1, 2, 3],
                "retry_effect": (
                    "Shorter delay/more attempts increase recovery opportunities and request load; "
                    "longer delay/fewer attempts reduce load and delay or limit automatic recovery"
                ),
                "retry_contract": (
                    "Same operation ID and payload on every retry; receipt matching and local drafts "
                    "follow F-000001"
                ),
                "independence": (
                    "Every retention/visibility combination is allowed; every delay/attempt pair is "
                    "allowed within the same retry approach"
                ),
                "default_constraints": (
                    "No current human preference among allowed values; recommendations may use the "
                    "stated product tradeoffs"
                ),
            },
            indent=2,
        ),
    )
    work = WorkStore(FreezeStore(project))
    work.add(
        [{"title": "Durable writes", "why": "Previously confirmed service contract"}],
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
                    "definition": {
                        "operation": "definition_draft",
                        "value": (
                            "Each logical write has a stable operation ID and payload. "
                            "Identical replay returns its durable receipt; a changed payload "
                            "cannot reuse the ID. Retain the local draft "
                            "until the matching durable receipt is observed."
                        ),
                    },
                    "phase": {
                        "phase": "human_review",
                        "conclusion_type": "single_recommendation",
                        "reason": "Existing explicit contract",
                        "trigger_refs": ["existing-contract"],
                        "affected_refs": ["F-000001"],
                        "completion_conditions": ["Confirm"],
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
    return (
        "准备保存功能这三项未定口径供我审阅，相关问题放同一主题。"
        "把可选值做成我能选择的比较，说明影响并给推荐值。"
    )


if __name__ == "__main__":
    import review_fixture

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--scenario", choices=["complete", "scientific", "focused"], required=True)
    parser.add_argument("--arm", choices=["actual", "candidate", "without-rule", "v4.3.1"], required=True)
    args = parser.parse_args()
    # Reuse the same audited wrapper; only task source preparation is substituted.
    review_fixture.council_review = {
        "complete": council_review,
        "scientific": scientific,
        "focused": focused,
    }[args.scenario]
    directory = Path(prepare(args.destination, "council", "v4.3.1" if args.arm == "v4.3.1" else "actual"))
    if args.arm == "v4.3.1" and args.scenario == "focused":
        # A general project uses the original Steward entry, not the research governor.
        destination = directory / "skill"
        shutil.rmtree(destination)
        source = "skills/oppen-project-steward"
        names = subprocess.check_output(
            ["git", "ls-tree", "-r", "--name-only", BASE, source], cwd=ROOT, text=True
        ).splitlines()
        for name in names:
            if name.endswith(".md") and "/tests/" not in name:
                target = destination / Path(name).relative_to(source)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(subprocess.check_output(["git", "show", BASE + ":" + name], cwd=ROOT))
    if args.arm in {"candidate", "without-rule"}:
        target = directory / "skill/references/review-packet.md"
        content = target.read_text()
        if "## Prepare the decision" in content:
            before, remainder = content.split("## Prepare the decision", 1)
            content = before + remainder.split("## Save the review\n\n", 1)[1]
            target.write_text(content)
            (directory / "skill/references/research-review.md").unlink(missing_ok=True)
    if args.arm == "candidate":
        target = directory / "skill/references/review-packet.md"
        target.write_text(
            target.read_text()
            + "\n"
            + {"complete": COMPLETE_RULE, "scientific": SCIENTIFIC_RULE, "focused": FOCUSED_RULE}[
                args.scenario
            ]
            + "\n"
        )
    manifest = args.destination / "manifest.json"
    rows = json.loads(manifest.read_text())
    rows[0].update(scenario=args.scenario, arm=args.arm)
    if args.arm == "v4.3.1" and args.scenario == "focused":
        from stage_fixture import digest

        rows[0]["entry_sha256"] = digest(directory / "skill/SKILL.md")
    manifest.write_text(json.dumps(rows, indent=2) + "\n")
    print(directory)
