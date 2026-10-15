"""Prepare opaque, isolated Memory tasks for independent agents; never score prose here.

Run with the Council development Python. The evaluator keeps manifest.json outside
the assigned case directories; agents receive only request.md and their case path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import uuid
from pathlib import Path

from oppencouncil.bootstrap import create
from oppencouncil.memory import Memory
from oppencouncil.store import FreezeStore
from oppencouncil.workstore import WorkStore

ROOT = Path(__file__).resolve().parents[2]


def git(root, *args):
    return subprocess.run(
        ["git", "-c", "user.name=Evaluation Fixture", "-c", "user.email=fixture@example.invalid",
         "-C", str(root), *args], check=True, capture_output=True, text=True,
    ).stdout


def prepare(destination):
    destination.mkdir(parents=True, exist_ok=False)
    cases = json.loads((ROOT / "tests/evals/skill_decisions.json").read_text())["cases"]
    manifest = []
    for case in cases:
        if not case["id"].startswith("memory_"):
            continue
        location = destination / uuid.uuid4().hex[:12]
        location.mkdir()
        project = location / "project"
        research = case["id"] in {
            "memory_execution_unsafe_at_project_scale", "memory_diagnostics_change_analysis_strategy",
            "memory_one_decision_across_multiple_turns", "memory_false_assumption_uses_invalidates",
        }
        create(project, project_type="research" if research else "general")
        skill = location / "skill"
        for name in ("SKILL.md", "references/memory.md", "scripts/oppencouncil.py"):
            target = skill / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / "skills/oppencouncil" / name, target)
        facts = {k: v for k, v in case["context"].items() if k != "fixture"}
        (project / "handoff.md").write_text(
            "# Synthetic project handoff\n\nAll events and sources in this fixture are fictional. "
            "The described implementation and checks are already complete; this task concerns records.\n\n"
            + "\n\n".join(f"## {k.replace('_', ' ')}\n\n{v}" for k, v in facts.items()) + "\n",
            encoding="utf-8",
        )
        if "synthetic_memory" in facts:
            invalidates = case["id"].endswith("uses_invalidates")
            Memory(project).add({
                "title": "Original processing direction",
                "before": "Manual processing of incoming events.",
                "trigger": "A human requested a repeatable event processing service.",
                "decision": "Use incoming keys to deduplicate." if invalidates else "Use daily batch processing.",
                "why": "Every supported event is assumed to have a stable key." if invalidates else
                       "The original requirement permits a daily reporting delay.",
                "basis": "The original project requirements stated this input contract or response time.",
                "rejected_or_prior_approach": "Continue manual processing.",
                "consequence": "Processing is automatic under this input and timing contract.",
            })
        if "existing_council" in facts:
            work = WorkStore(FreezeStore(project))
            rationale = (
                "Formerly every worker materialized the full dataset. A full-scale reproduction exceeded "
                "available memory and made spill unsafe. The human chose shared on-disk storage with bounded "
                "concurrency because it prevents per-worker materialization. Unbounded copies were rejected "
                "despite their simpler implementation. Future concurrency changes require new scale evidence. "
                "Source: the synthetic scale experiment described in handoff.md."
            )
            work.add([{"title": "Processing architecture", "why": rationale}], request_id="fixture", actor="codex")
            work.commit_work({"read_set": {"F-000001": 1}, "changes": [{
                "id": "F-000001", "problem_type": "project_fact",
                "definition": {"operation": "definition_draft", "value":
                    "Use shared on-disk storage and bounded concurrency for processing."},
                "phase": {"phase": "human_review", "reason": "The fictional scale experiment prompted this decision.",
                          "affected_refs": ["F-000001"], "completion_conditions": ["Human decision"],
                          "trigger_refs": ["synthetic-scale-experiment"], "conclusion_type": "single_recommendation"},
            }]}, request_id="fixture-draft")
            candidate = work.read("F-000001")["candidate"]
            work.commit_work({"read_set": {"F-000001": 2}, "changes": [{
                "id": "F-000001", "definition": {"operation": "definition_approve",
                "value": candidate["approval_token"]},
            }]}, request_id="fixture-confirmed", actor="user")
        git(project, "init", "-q")
        git(project, "add", ".", ":(exclude)handoff.md")
        git(project, "commit", "-qm", "Synthetic starting state")
        (location / "request.md").write_text(
            case["task"] + "\n\nUse the provided skill/SKILL.md for this already-v5 synthetic project. "
            "The task input is project/handoff.md. Perform only record work warranted by these facts. "
            "Write only under this case directory. Existing implementation is complete; no external systems, "
            "real projects, network, other cases, or repository edits are authorized. "
            "The supplied helper runs with " + str(ROOT / "council/.venv/bin/python") + ". "
            "Council records, when present, can be read with that Python -m oppencouncil work-read PROJECT --id ID. "
            "Save a brief handoff and the paths of the instruction files actually read to outcome.md.\n",
            encoding="utf-8",
        )
        entries = Memory(project).index()
        manifest.append({"case": case["id"], "directory": str(location), "project_type": "research" if research else "general",
                         "before": {entry["id"]: Memory(project).read(entry["id"]) for entry in entries},
                         "council_before": {str(p.relative_to(project)): hashlib.sha256(p.read_bytes()).hexdigest()
                                            for p in project.rglob("F-*.json")},
                         "helper_sha256": hashlib.sha256((skill / "scripts/oppencouncil.py").read_bytes()).hexdigest(),
                         "memory_reference_sha256": hashlib.sha256((skill / "references/memory.md").read_bytes()).hexdigest(),
                         "skill_sha256": hashlib.sha256((skill / "SKILL.md").read_bytes()).hexdigest()})
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.destination), indent=2))
