"""Mechanical output and project-area rules, shared by migration and validation."""

import re
from pathlib import PurePosixPath

RESULT_SUFFIXES = {
    ".csv",
    ".tsv",
    ".xlsx",
    ".md",
    ".html",
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".svg",
    ".tif",
    ".tiff",
    ".docx",
}
RESULT_KINDS = {
    "table": {".csv", ".tsv", ".xlsx", ".md", ".html", ".pdf", ".docx"},
    "figure": {".pdf", ".png", ".jpg", ".jpeg", ".svg", ".tif", ".tiff"},
    "cohort-flow": {".csv", ".tsv", ".xlsx", ".md", ".html", ".pdf", ".png", ".svg", ".docx"},
    "report": {".md", ".html", ".pdf", ".docx"},
}
DELIVERABLE_SUFFIXES = RESULT_SUFFIXES | {".ods", ".pptx", ".txt"}
FORBIDDEN_DELIVERABLE = re.compile(
    r"(?:^|[_\-.])(?:audit|trace|acceptance|manifest|session|cache|qa|qc|diagnostic|debug|"
    r"intermediate|draft|staging|tmp|temp|old|backup|legacy|invalidated|run[_\-.]?\d+)(?:[_\-.]|$)",
    re.I,
)
FORBIDDEN_OUTPUT = re.compile(
    r"(?:^|[_\-.])(?:audit|trace|acceptance|manifest|session|cache|qa|qc|diagnostic|debug|"
    r"intermediate|draft|staging|tmp|old|new|backup|legacy|invalidated)(?:[_\-.]|$)|"
    r"(?:^|[_\-.])(?:run|runtime|execution|pipeline|stage)[_\-.]?(?:status|log)(?:[_\-.]|$)|"
    r"(?:^|[_\-.])(?:status|log)[_\-.]?(?:run|runtime|execution|pipeline|stage)(?:[_\-.]|$)|"
    r"(?:^|[_\-.])20\d{2}[-_]?\d{2}[-_]?\d{2}(?:[_\-.]|$)",
    re.I,
)
NUMBERED = re.compile(r"^[0-9]{2}[_-].+\.[A-Za-z0-9]+$")
SCRIPT_SUFFIXES = {".r", ".py", ".jl", ".sh", ".m", ".ipynb", ".do", ".sas", ".sql"}
IGNORED_AREAS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".Rproj.user",
    ".quarto",
    ".cache",
    ".DS_Store",
}
KNOWN_AREAS = {
    "Scripts",
    "R",
    "Data",
    "Results",
    "Releases",
    "Explore",
    "Audit",
    "Freeze",
    "Memory",
    "Attention",
    "Discussion",
    ".oppen-project-steward",
    "tests",
    "test",
    "renv",
    ".agents",
    ".codex",
    ".oppencouncil-migration",
}
KNOWN_ROOT_FILES = {
    "project.md",
    "AGENTS.md",
    "LICENSE",
    "LICENSE.md",
    ".gitignore",
    ".gitattributes",
    ".editorconfig",
    ".Rprofile",
    ".Renviron",
    "renv.lock",
    "requirements.txt",
    "pyproject.toml",
    "uv.lock",
    "environment.yml",
    "environment.yaml",
    "Project.toml",
    "Manifest.toml",
    "DESCRIPTION",
    "NAMESPACE",
    "Makefile",
    ".oppencouncil-state.json",
    ".oppencouncil-project.lock",
}


def artifact_error(path, kind=None, *, research=True):
    path = PurePosixPath(path)
    if path.suffix.lower() not in (RESULT_SUFFIXES if research else DELIVERABLE_SUFFIXES):
        return "not a human-facing table, figure or report format"
    pattern = FORBIDDEN_OUTPUT if research else FORBIDDEN_DELIVERABLE
    if any(pattern.search(part) for part in path.parts):
        return "process output or parallel historical copy belongs outside Results"
    if research and kind in RESULT_KINDS and path.suffix.lower() not in RESULT_KINDS[kind]:
        return "file format does not match the registered output kind"
    return None


def known_area(path, roles=()):
    path = PurePosixPath(path)
    if path.parts[0] in KNOWN_AREAS | IGNORED_AREAS:
        return True
    if len(path.parts) == 1 and (
        path.name in KNOWN_ROOT_FILES or path.name.lower().startswith("readme") or path.suffix == ".Rproj"
    ):
        return True
    return any(path == PurePosixPath(role) or PurePosixPath(role) in path.parents for role in roles)
