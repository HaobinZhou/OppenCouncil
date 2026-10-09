"""Narrow MCP adapter for native Stepwise R and Steward Freeze workspaces."""

from __future__ import annotations

import os
from pathlib import Path

from oppencouncil.store import FreezeStore

from .catalog import AccessDenied


class Freezes:
    def __init__(self, catalog):
        self.catalog = catalog
        self.settings = catalog.settings

    @staticmethod
    def supported(project) -> bool:
        return (project.skill in {"stepwise-r-project", "oppen-project-steward"}
                and project.version in {"v3", "v4"})

    def store(self, project_id: str):
        project = self.catalog.project(project_id)
        if not self.supported(project):
            raise AccessDenied("Freeze requires a registered native Stepwise R or Steward v3/v4 project")
        if not self.settings.freeze_allowed(project.root):
            raise AccessDenied("Freeze is not enabled for this project")
        root = Path(project.root)
        if self.catalog.excluded(root / "Freeze"):
            raise AccessDenied("Freeze workspace is excluded")
        stat = os.stat(root, follow_symlinks=False)
        if (stat.st_dev, stat.st_ino) != (project.device, project.inode):
            raise AccessDenied("Project root changed during access")
        return FreezeStore(root)

    def snapshot(self, project_id: str):
        return self.store(project_id).snapshot()

    def read(self, project_id: str, question_id: str, include_example: bool = False):
        return self.store(project_id).read_question(question_id, include_example)

    @staticmethod
    def actor(value: str):
        if value not in {"chatgpt", "codex"}:
            raise AccessDenied("MCP actor must be chatgpt or codex")
        return value

    def add(self, project_id: str, questions: list[dict], request_id: str, actor: str = "chatgpt"):
        actor = self.actor(actor)
        return self.store(project_id).add_questions(questions, request_id=request_id, actor=actor)

    def change(self, project_id: str, question_id: str, operation: str, value: object,
               expected_revision: int, request_id: str, actor: str = "chatgpt"):
        actor = self.actor(actor)
        if operation not in {"comment", "ai_position", "example", "reopen", "definition_draft",
                             "presentation", "review_note", "dependency_review"}:
            raise AccessDenied("MCP may discuss, revise candidate wording or reopen discussion; "
                               "human confirmation and formal publication are unavailable")
        return self.store(project_id).change(question_id, operation, value,
            expected_revision=expected_revision, request_id=request_id, actor=actor)

    def change_group(self, project_id: str, group_id: str | None, operation: str, value: object,
                     expected_revision: int, request_id: str, actor: str = "chatgpt"):
        actor = self.actor(actor)
        if operation not in {"create", "update", "comment", "example"}:
            raise AccessDenied("MCP cannot choose, open revisions or confirm a group")
        return self.store(project_id).change_group(group_id, operation, value,
            expected_revision=expected_revision, request_id=request_id, actor=actor)
