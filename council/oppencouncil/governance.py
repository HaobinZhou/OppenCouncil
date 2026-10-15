"""Common local project-helper entry point; external MCP clients do not call it."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .memory import Memory
from .project import Project, unique_object
from .store import FreezeError, ordinary_file


def parser():
    root = argparse.ArgumentParser(description="OppenCouncil shared project helper")
    commands = root.add_subparsers(dest="command", required=True)
    for name in ("index", "validate"):
        command = commands.add_parser(name)
        command.add_argument("project", type=Path)
    canonical = commands.add_parser("canonical")
    canonical.add_argument("project", type=Path)
    for field in ("topic", "path", "verification"):
        canonical.add_argument("--" + field, required=True)
    canonical.add_argument("--section")
    canonical.add_argument("--status", choices=["draft", "partially-frozen", "frozen"])
    canonical.add_argument("--replace", action="store_true")
    contract = commands.add_parser("contract-audit", aliases=["module-audit"])
    contract.add_argument("project", type=Path)
    contract.add_argument("--topic", required=True)
    contract.add_argument("--source")
    contract.add_argument("--risk-reason")
    contract.add_argument("--input", type=Path)
    audit = commands.add_parser("audit").add_subparsers(dest="operation", required=True)
    promote = audit.add_parser("promote")
    promote.add_argument("project", type=Path)
    promote.add_argument("--stage", required=True)
    promote.add_argument("--input", type=Path, required=True)
    recover = audit.add_parser("recover")
    recover.add_argument("project", type=Path)
    recover.add_argument("--stage", required=True)
    review = commands.add_parser("review", aliases=["attention"]).add_subparsers(
        dest="operation", required=True
    )
    listing = review.add_parser("list")
    listing.add_argument("project", type=Path)
    listing.add_argument("--offset", type=int, default=0)
    listing.add_argument("--limit", type=int, default=100)
    listing.add_argument("--actionable", action="store_true")
    raising = review.add_parser("raise")
    raising.add_argument("project", type=Path)
    raising.add_argument("--input", type=Path, required=True)
    raising.add_argument("--request-id")
    resolving = review.add_parser("resolve")
    resolving.add_argument("project", type=Path)
    resolving.add_argument("--id", required=True)
    resolving.add_argument("--reason")
    resolving.add_argument(
        "--conclusion", choices=["fact_lookup", "covered", "not_applicable"], default="fact_lookup"
    )
    resolving.add_argument("--expected-revision", type=int)
    resolving.add_argument("--request-id")
    init = commands.add_parser("init")
    init.add_argument("project", type=Path)
    init.add_argument("--project-type", choices=["research", "general"], required=True)
    init.add_argument("--layout", choices=["root", "namespace"])
    adopt = commands.add_parser("adopt")
    adopt.add_argument("project", type=Path)
    mode = adopt.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    adopt.add_argument("--project-type", choices=["research", "general"])
    adopt.add_argument("--layout", choices=["root", "namespace"])
    adopt.add_argument("--input", type=Path)
    for name in ("result", "deliverable"):
        output = commands.add_parser(name)
        output.add_argument("project", type=Path)
        output.add_argument("--input", type=Path)
        for field in ("id", "path", "kind", "audience", "producer"):
            output.add_argument("--" + field)
        output.add_argument("--replace", action="store_true")
        output.add_argument(
            "--specification", type=Path, help="JSON specification binding (use --input for groups)"
        )
    data = commands.add_parser("data").add_subparsers(dest="operation", required=True)
    register = data.add_parser("register")
    register.add_argument("project", type=Path)
    register.add_argument("--input", type=Path, required=True)
    for name, operations in {
        "scripts": ("renumber", "rename-directory"),
        "explore": ("create", "update", "archive", "promote"),
        "release": ("create",),
    }.items():
        group = commands.add_parser(name).add_subparsers(dest="operation", required=True)
        for operation in operations:
            command = group.add_parser(operation)
            command.add_argument("project", type=Path)
            mode = command.add_mutually_exclusive_group(required=True)
            mode.add_argument("--check", action="store_true")
            mode.add_argument("--apply", action="store_true")
            command.add_argument("--input", type=Path)
            command.add_argument("--plan", type=Path)
        if name in {"explore", "release"}:
            command = group.add_parser("index" if name == "explore" else "verify")
            command.add_argument("project", type=Path)
    memory = commands.add_parser("memory").add_subparsers(dest="operation", required=True)
    for operation in ("add", "read", "index"):
        command = memory.add_parser(operation)
        command.add_argument("project", type=Path)
        if operation == "add":
            command.add_argument("--input", type=Path, required=True)
        if operation == "read":
            command.add_argument("--id", required=True)
    project_type = commands.add_parser("project-type")
    project_type.add_argument("project", type=Path)
    project_type.add_argument("--set", choices=["research", "general"])
    project_type.add_argument("--reason")
    upgrade = commands.add_parser("upgrade-v5")
    upgrade.add_argument("project", type=Path)
    mode = upgrade.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    upgrade.add_argument("--plan", type=Path)
    upgrade.add_argument("--project-type", choices=["research", "general"])
    upgrade.add_argument("--council-directory", type=Path)
    upgrade.add_argument("--mcp-root", type=Path)
    upgrade.add_argument("--mcp-config", type=Path)
    return root


def read_input(path, label="Input", limit=1024 * 1024):
    raw = ordinary_file(path, limit)
    if raw is None:
        raise FreezeError(label + " file does not exist")
    return json.loads(raw, object_pairs_hook=unique_object)


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = parser().parse_args(argv)
    try:
        if args.command in {"index", "validate"}:
            from . import project_checks

            result = getattr(project_checks, args.command)(args.project)
        elif args.command == "canonical":
            from .canonical import register

            result = register(
                args.project,
                topic=args.topic,
                path=args.path,
                verification=args.verification,
                section=args.section,
                status=args.status,
                replace=args.replace,
            )
        elif args.command in {"contract-audit", "module-audit", "audit"}:
            from . import audits

            if args.command == "audit":
                result = (
                    audits.promote(args.project, args.stage, args.input)
                    if args.operation == "promote"
                    else audits.recover(args.project, args.stage)
                )
            else:
                result = audits.contract(
                    args.project,
                    args.topic,
                    source=args.source,
                    risk_reason=args.risk_reason,
                    payload=read_input(args.input) if args.input else None,
                )
        elif args.command in {"review", "attention"}:
            from . import review

            if args.operation == "list":
                result = review.listing(
                    args.project, offset=args.offset, limit=args.limit, actionable=args.actionable
                )
            elif args.operation == "raise":
                result = review.raise_issue(args.project, read_input(args.input), request_id=args.request_id)
            else:
                result = review.resolve(
                    args.project,
                    args.id,
                    reason=args.reason,
                    conclusion=args.conclusion,
                    expected_revision=args.expected_revision,
                    request_id=args.request_id,
                )
        elif args.command in {"init", "adopt"}:
            from . import bootstrap

            if args.command == "adopt" and args.check:
                result = bootstrap.inspect(args.project)
                if args.input:
                    if not args.project_type:
                        raise FreezeError("Checking an adoption payload requires --project-type")
                    if result["state"] != "ADOPTION_REQUIRED":
                        raise FreezeError("Cannot adopt: " + result["state"])
                    layout = args.layout or ("root" if args.project_type == "research" else "namespace")
                    writes, reads, directories = bootstrap.prepare(
                        args.project.expanduser().resolve(strict=True),
                        args.project_type,
                        layout,
                        read_input(args.input),
                        adoption=True,
                    )
                    result.update(write_paths=list(writes), read_hashes=reads, new_directories=directories)
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 0 if result["state"] in {"ADOPTION_REQUIRED", "MANAGED_READY"} else 2
            if args.command == "adopt" and (not args.input or not args.project_type):
                raise FreezeError("adopt --apply requires --input and an explicit --project-type")
            result = bootstrap.create(
                args.project,
                project_type=args.project_type,
                layout=args.layout,
                payload=read_input(args.input) if args.command == "adopt" else None,
                adoption=args.command == "adopt",
            )
        elif args.command in {"scripts", "explore", "release"}:
            from . import explore, releases, script_ops

            service = {"scripts": script_ops, "explore": explore, "release": releases}[args.command]
            if args.operation in {"index", "verify"}:
                result = (
                    service.index(args.project)
                    if args.operation == "index"
                    else service.validate(args.project)
                )
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 2 if isinstance(result, dict) and result.get("errors") else 0

            target = args.project.expanduser().resolve(strict=True)
            plan_path = args.plan.expanduser().absolute() if args.plan else None
            if plan_path and (plan_path.is_symlink() or plan_path.resolve().is_relative_to(target)):
                raise FreezeError("Keep the operation plan outside the target project")
            if args.check:
                if not args.input:
                    raise FreezeError("--check requires --input")
                result = (
                    service.check(target, read_input(args.input))
                    if args.command == "release"
                    else service.check(target, args.operation, read_input(args.input)).public()
                )
                if plan_path:
                    with plan_path.open("x", encoding="utf-8") as handle:
                        json.dump(result, handle, ensure_ascii=False, indent=2)
                        handle.write("\n")
            else:
                if not plan_path or args.input:
                    raise FreezeError("--apply requires only the saved external --plan")
                saved = read_input(plan_path, "Operation plan", 16 * 1024 * 1024)
                if not isinstance(saved, dict) or saved.get("operation") != args.operation:
                    raise FreezeError("Saved plan does not match the requested operation")
                result = service.apply(target, saved)
        elif args.command in {"result", "deliverable", "data"}:
            from .outputs import Outputs

            service = Outputs(args.project)
            if args.command == "data":
                result = service.register_data(read_input(args.input))
            else:
                fields = {key: getattr(args, key) for key in ("id", "path", "kind", "audience", "producer")}
                if args.input:
                    if any(fields.values()) or args.specification:
                        raise FreezeError("Use either an output --input or individual output fields")
                    payload = read_input(args.input)
                else:
                    if not all(fields.values()):
                        raise FreezeError("Output requires --input or id, path, kind, audience and producer")
                    payload = fields
                    if args.specification:
                        payload["specification"] = read_input(args.specification)
                result = service.register(payload, replace=args.replace)
        elif args.command == "upgrade-v5":
            from . import capabilities, migration

            target = args.project.expanduser().resolve(strict=True)
            plan_path = args.plan.expanduser().absolute() if args.plan else None
            if plan_path and (plan_path.is_symlink() or plan_path.resolve().is_relative_to(target)):
                raise FreezeError("Keep the migration plan outside the target project")
            if args.apply and plan_path is None:
                raise FreezeError("--apply requires an external --plan saved by --check")
            versions = capabilities.inspect(
                target,
                council_directory=args.council_directory,
                mcp_root=args.mcp_root,
                mcp_config=args.mcp_config,
            )
            if args.check:
                result = migration.check(target, versions, project_type=args.project_type).public()
                # Exclusive creation prevents overwriting an earlier reviewed plan.
                if plan_path:
                    with plan_path.open("x", encoding="utf-8") as handle:
                        json.dump(result, handle, ensure_ascii=False, indent=2)
                        handle.write("\n")
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 2 if result["blockers"] else 0
            if args.project_type:
                raise FreezeError("Choose project type during --check; --apply uses the saved plan")
            raw = ordinary_file(plan_path, 16 * 1024 * 1024)
            if raw is None:
                raise FreezeError("Migration plan does not exist")
            result = migration.apply(target, json.loads(raw, object_pairs_hook=unique_object), versions)
        elif args.command == "memory":
            service = Memory(args.project)
            if args.operation == "add":
                result = service.add(read_input(args.input, "Memory input"))
            elif args.operation == "read":
                result = service.read(args.id)
            else:
                result = service.index()
        else:
            project = Project(args.project)
            result = (
                project.change_type(args.set, args.reason)
                if args.set
                else {
                    "project_type": project.project_type,
                    "history": project.metadata.get("type_history", []),
                }
            )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if args.command == "validate" and result["errors"] else 0
    except (FreezeError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
