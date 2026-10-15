"""Trial-only unified instructions; promotion requires behavioral admission.

The approved Memory section is copied from its single runtime source unchanged.
These trial sentences are not installed instructions.
"""

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

ENTRY = """---
name: oppencouncil
metadata:
  version: "4.3.1"
description: Govern research and general projects through OppenCouncil, including project operations, evidence review and human-confirmed output specifications.
---

# OppenCouncil

The project registry declares `research` or `general`; language and directory layout do not select the type. The helper command is `python ABSOLUTE_SKILL/scripts/oppencouncil.py COMMAND TARGET`. `index` returns the declared type and registered owners; `validate` checks managed structures. Existing v3/v4 markers use their original implementation until an explicit upgrade.

Load the reference for the current task, following an operation link when needed:

| Task | Reference |
| --- | --- |
| Council investigation, evidence, candidate or feedback | [local-council.md](references/local-council.md) |
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

"""

STAGES = {
    "cleaning": (
        "Data import and cleaning",
        "Cleaning normally has no article output. Store reusable cleaned data in Data/derived and checks in Audit; a cleaned dataset or quality report is not a Results table.",
    ),
    "cohort": (
        "Cohort construction",
        "The article output is the cohort flow with labelled inclusion and exclusion counts. Keep person-level cohort data in Data/derived and reconciliation checks in Audit. Compare the visible flow, labels and totals with the confirmed specification.",
    ),
    "descriptive": (
        "Descriptive analysis",
        "The article output is the baseline characteristics table. Compare the actual table with the confirmed specification: readable labels, group sizes, units, summaries and precision. Internal variable names, calculation columns and intermediate summaries belong in Audit or Data, not the published table.",
    ),
    "primary": (
        "Primary analysis",
        "The article outputs are the confirmed main result tables and figures. Check displayed contrasts, scale, units and uncertainty against their specifications. Model objects and machine-readable intermediate estimates belong in Data/derived or Audit, not Results.",
    ),
    "sensitivity": (
        "Sensitivity and subgroup analysis",
        "The article outputs are the confirmed supplementary tables and figures, with analysis and subgroup labels that identify what each estimate describes. Keep diagnostics and intermediate comparisons in Audit; use the output specification to distinguish final supplementary content from exploratory work.",
    ),
    "reporting": (
        "Report assembly",
        "Results contains the current article tables and figures in their confirmed form. Read back the delivered files to check titles, labels, units, footnotes and matching values across representations. Assembly notes, logs and superseded working copies are not article outputs.",
    ),
}


def write(destination, *, omit_stage_rule=False):
    shutil.copytree(ROOT / "skills/oppencouncil", destination)
    actual = (ROOT / "skills/oppencouncil/SKILL.md").read_text()
    memory = re.search(r"^## Decision Memory\n.*?(?=^## |\Z)", actual, re.M | re.S).group()
    (destination / "SKILL.md").write_text(ENTRY + memory)
    for name, (title, rule) in STAGES.items():
        content = "# " + title + "\n\n"
        if not omit_stage_rule:
            content += rule + "\n\n"
        content += (
            "Output and data registration, source/check bindings and validation use "
            "[project-operations.md](project-operations.md). Current formal specifications are readable with "
            "`python -m oppencouncil definition TARGET --question F-NNNNNN`. "
            "For a proposed change to a specification, use [local-council.md](local-council.md).\n"
        )
        (destination / "references" / ("research-stage-" + name + ".md")).write_text(content)
