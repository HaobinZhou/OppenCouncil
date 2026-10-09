"""Local project registration and Codex collaboration commands."""

from __future__ import annotations

import argparse
import json
import secrets
import sys
from pathlib import Path

from . import __version__
from .definitions import read_definition, render_definition
from .recovery import recover_records
from .registry import Registry, default_directory, project_identity
from .service import info, serve, start, stop, urls
from .store import FreezeError, FreezeStore


def parser():
    root = argparse.ArgumentParser(description="OppenCouncil unified project review site")
    root.add_argument("--version", action="version", version=f"OppenCouncil {__version__}")
    root.add_argument("--directory", type=Path, default=default_directory())
    commands = root.add_subparsers(dest="command", required=True)
    for name in ("open", "register", "disable", "snapshot", "import", "recover", "reconcile",
                 "ai-change", "group-change", "definition"):
        command = commands.add_parser(name)
        command.add_argument("project", type=Path)
        if name in {"open", "register"}:
            command.add_argument("--name")
        if name in {"import", "recover", "reconcile", "ai-change", "group-change"}:
            command.add_argument("--input", type=Path, required=True)
        if name in {"recover", "reconcile"}:
            command.add_argument("--check", action="store_true", help="Validate and preview without writing")
        if name == "definition":
            command.add_argument("--question", required=True)
            command.add_argument("--version-number", type=int)
            command.add_argument("--format", choices=["json", "markdown"], default="json")
        if name == "open":
            service_options(command)
    service_options(commands.add_parser("start"))
    service_options(commands.add_parser("_serve"))
    commands.add_parser("stop")
    status = commands.add_parser("status")
    status.add_argument("project", type=Path, nargs="?")
    return root


def service_options(command):
    command.add_argument("--host", choices=["127.0.0.1", "0.0.0.0"])
    command.add_argument("--port", type=int)
    command.add_argument("--public-origin")
    command.add_argument("--no-auth", action="store_true", default=None)
    command.add_argument(
        "--legacy-project",
        type=Path,
        help="Explicit project for compatibility with previously opened single-project pages",
    )


def configure_cli_output() -> None:
    """Emit UTF-8 even when Windows redirects output through a legacy code page."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    configure_cli_output()
    args = parser().parse_args(argv)
    directory = args.directory.expanduser().absolute()
    registry = Registry(directory)
    try:
        legacy = None
        if getattr(args, "legacy_project", None):
            legacy = project_identity(args.legacy_project.expanduser().resolve(strict=True))
            registry.project(legacy)
        if args.command == "_serve":
            serve(
                directory,
                args.host or "127.0.0.1",
                args.port if args.port is not None else 5322,
                args.public_origin or "",
                bool(args.no_auth),
                legacy or "",
            )
            return 0
        if args.command in {"open", "register"}:
            item = registry.register(args.project, args.name)
            result = {"project_id": item["id"], "name": item["name"], "registered": True}
            if args.command == "open":
                result.update(
                    start(directory, args.host, args.port, args.public_origin, args.no_auth, legacy)
                )
                result.update(urls(info(directory), item["id"]))
        elif args.command == "start":
            result = start(directory, args.host, args.port, args.public_origin, args.no_auth, legacy)
        elif args.command == "stop":
            result = stop(directory)
        elif args.command == "disable":
            result = {"disabled": True, "project_id": registry.disable(args.project)["id"]}
        elif args.command == "status":
            current = info(directory)
            identity = None
            if args.project:
                identity = project_identity(args.project.expanduser().resolve())
                item = registry.project(identity)
                result = {"registered": item["enabled"], "project_id": identity}
            else:
                result = {}
            result.update(urls(current, identity) if current else {"running": False})
        elif args.command == "definition":
            result = read_definition(FreezeStore(args.project), args.question, args.version_number)
            if args.format == "markdown":
                print(render_definition(result), end="")
                return 0
        elif args.command == "snapshot":
            result = FreezeStore(args.project).snapshot()
        elif args.command in {"import", "recover", "reconcile", "ai-change", "group-change"}:
            payload = json.loads(args.input.read_text(encoding="utf-8"))
            store = FreezeStore(args.project)
            request_id = payload.get("request_id") or secrets.token_urlsafe(18)
            if args.command == "group-change":
                result = store.change_group(payload.get("group_id"), payload["operation"], payload["value"],
                    expected_revision=payload["expected_revision"], request_id=request_id, actor="codex")
            elif args.command == "import":
                result = store.add_questions(payload["questions"], request_id=request_id, actor="codex")
                item = registry.register(args.project)
                result.update(registered=True, project_id=item["id"])
            elif args.command in {"recover", "reconcile"}:
                result = recover_records(
                    store, payload["records"], reconcile=args.command == "reconcile", dry_run=args.check
                )
                if not args.check:
                    item = registry.register(args.project)
                    result.update(registered=True, project_id=item["id"])
            else:
                result = store.change(
                    payload["question_id"],
                    payload["operation"],
                    payload["value"],
                    expected_revision=payload["expected_revision"],
                    request_id=request_id,
                    actor="codex",
                )
        else:
            raise FreezeError("Unknown command")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (FreezeError, KeyError, OSError, ValueError) as error:
        print(f"OppenCouncil: {error}", file=sys.stderr)
        return 2
