---
name: oppencouncil
metadata:
  version: "5.0.0"
description: Govern research and general projects through OppenCouncil, including project operations, evidence review and human-confirmed output specifications.
---

# OppenCouncil

The project registry declares `research` or `general`; language and directory layout do not select the type. The helper command is `python ABSOLUTE_SKILL/scripts/oppencouncil.py COMMAND TARGET`. `index` returns the declared type and registered owners; `validate` checks managed structures. Existing v3/v4 markers use their original implementation; their operations are in [legacy-projects.md](references/legacy-projects.md). Product installation does not upgrade a project.

For research Council work, read [research-handoff.md](references/research-handoff.md) first. By default, check local facts, save a shared literature brief and a persistent wait, then **end the turn and hand control back to the human**. Web AI supplies literature; resume appraisal, synthesis and review preparation only after an explicit human instruction to continue. New material or an AI's claim of completion does not release this wait. Follow an explicit human instruction assigning the entire round to the local agent instead. Executing an already-confirmed analysis or routine repair does not start a new review round.

Load the reference for the current task, following an operation link when needed:

| Task | Reference |
| --- | --- |
| Council investigation | [triage.md](references/triage.md) |
| Source or claim appraisal | [evidence.md](references/evidence.md) |
| Candidate and human review | [review-packet.md](references/review-packet.md) |
| Feedback or unfinished work | [resume.md](references/resume.md) |
| External Council contribution over MCP | [council.md](references/council.md) |
| General project work, ownership or registration | [project-operations.md](references/project-operations.md) |
| Research: import and clean data | [research-stage-cleaning.md](references/research-stage-cleaning.md) |
| Research: build the cohort | [research-stage-cohort.md](references/research-stage-cohort.md) |
| Research: descriptive analysis | [research-stage-descriptive.md](references/research-stage-descriptive.md) |
| Research: primary analysis | [research-stage-primary.md](references/research-stage-primary.md) |
| Research: sensitivity or subgroup analysis | [research-stage-sensitivity.md](references/research-stage-sensitivity.md) |
| Research: assemble final report outputs | [research-stage-reporting.md](references/research-stage-reporting.md) |
| Product update or connection repair | [maintenance.md](references/maintenance.md) |
| Explicit project migration | [migration.md](references/migration.md) |
| Requested local snapshot | [releases.md](references/releases.md) |

The six research stages are adjustable defaults, separate from a Council item's work phase. Use the project's stage definition when it differs. The helper owns IDs, managed writes and validation; its field checks do not establish scientific meaning or visual correctness.

## Decision Memory

Create Decision Memory only for a consequential scientific or technical decision that passes this counterfactual test: could a future agent with the current project and complete Git history plausibly fail to explain why the decision was made, or unknowingly reintroduce a rejected direction?
Write one entry per consequential decision, not one per task, conversation, change, commit, rerun, or verification.
A task ending is never a trigger.
Record the prior approach, actual trigger, decision and rationale, rejected directions, and consequences.
Do not duplicate rationale already recorded in Council.

Scientific cases include failed prior designs, changes in analysis strategy prompted by diagnostic findings, collaborator or reviewer requirements, compromises forced by data conditions, and deliberately rejected credible methods.
Technical cases include consequential decisions about architecture, execution, storage, concurrency, resources and memory, reliability, performance policy, operational safety, dependencies, deployment, and state management.
Both require a consequential decision whose causal context is durable and cannot be reconstructed from existing code, definitions, and Git history.
Technical difficulty or an incident alone does not justify a Memory entry.

Do not record routine bug fixes, compatibility work, routine cleanup, local optimization, refactors, tests, reruns, commands, file lists, benchmarks, progress or status summaries, unchanged results, Audit evidence, or unresolved concerns unless they caused a consequential decision of the kind above whose rationale would otherwise be lost.

Memory records causal history; current definitions belong in Council, verification in Audit, and unresolved issues in investigations.
Do not store chain of thought, scratchpads, discussion transcripts, verification logs, or unresolved-risk records in Memory.

`related_topics` may be empty.
Use `supersedes` when a later decision changes direction.
Use `invalidates` when later evidence shows that a key fact or assumption was wrong.
The helper updates the referenced entries’ status and reverse links; existing entries are otherwise never edited.
Read [memory.md](references/memory.md) before adding an entry or declaring relationships.
