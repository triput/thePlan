from __future__ import annotations

import argparse
import sys

from theplan import __version__
from theplan.commands.assist import register_assist, run_assist
from theplan.commands.auth import register_auth, run_auth
from theplan.commands.deps import register_deps, run_deps
from theplan.commands.handoffs import register_handoff, run_handoff
from theplan.commands.templates import register_templates, run_templates
from theplan.commands.hierarchy import (
    register_epics,
    register_projects,
    register_sections,
    run_epics,
    run_projects,
    run_sections,
)
from theplan.commands.schedule import register_schedule, run_schedule
from theplan.commands.status import register_status, run_status
from theplan.commands.tasks import register_tasks, run_tasks
from theplan.commands.overrides import register_overrides, run_overrides
from theplan.commands.settings import register_settings, run_settings
from theplan.commands.availability import register_availability, run_availability
from theplan.commands.focus_windows import register_focus_windows, run_focus_windows
from theplan.commands.scheduling import register_scheduling, run_scheduling
from theplan.commands.views import register_views, run_views
from theplan.errors import CliError
from theplan.output import emit_ok, handle_cli_error, set_output_format


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="theplan", description="thePlan agent-friendly CLI")
    parser.add_argument(
        "--format",
        choices=("json", "text"),
        default="json",
        help="Output format (default: json)",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Allow interactive prompts (default: disabled for agents)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    version = sub.add_parser("version", help="CLI version")
    version.set_defaults(handler=_run_version)

    register_auth(sub)
    register_status(sub)
    register_tasks(sub)
    register_assist(sub)
    register_handoff(sub)
    register_templates(sub)
    register_epics(sub)
    register_projects(sub)
    register_sections(sub)
    register_deps(sub)
    register_schedule(sub)
    register_views(sub)
    register_overrides(sub)
    register_settings(sub)
    register_availability(sub)
    register_focus_windows(sub)
    register_scheduling(sub)

    return parser


def _run_version(_args: argparse.Namespace) -> None:
    emit_ok({"version": __version__, "name": "theplan-cli"})


def _dispatch(args: argparse.Namespace) -> None:
    if args.command == "version":
        _run_version(args)
        return
    if args.command == "auth":
        run_auth(args)
        return
    if args.command == "status":
        run_status(args)
        return
    if args.command == "tasks":
        run_tasks(args)
        return
    if args.command == "assist":
        run_assist(args)
        return
    if args.command == "handoff":
        run_handoff(args)
        return
    if args.command == "templates":
        run_templates(args)
        return
    if args.command == "epics":
        run_epics(args)
        return
    if args.command == "projects":
        run_projects(args)
        return
    if args.command == "sections":
        run_sections(args)
        return
    if args.command == "deps":
        run_deps(args)
        return
    if args.command == "schedule":
        run_schedule(args)
        return
    if args.command == "views":
        run_views(args)
        return
    if args.command == "overrides":
        run_overrides(args)
        return
    if args.command == "settings":
        run_settings(args)
        return
    if args.command == "availability":
        run_availability(args)
        return
    if args.command == "focus-windows":
        run_focus_windows(args)
        return
    if args.command == "scheduling":
        run_scheduling(args)
        return
    raise CliError(code="INVALID_USAGE", message=f"Unknown command: {args.command}", exit_code=1)


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        if exc.code not in (0, None):
            from theplan.output import emit_error

            emit_error(
                code="INVALID_USAGE",
                message="Invalid arguments; use --help",
                exit_code=1,
            )
        raise

    set_output_format(args.format)

    if args.interactive:
        import os

        os.environ["THEPLAN_CLI_INTERACTIVE"] = "1"

    try:
        _dispatch(args)
    except CliError as exc:
        handle_cli_error(exc)


if __name__ == "__main__":
    main()
