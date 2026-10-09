from __future__ import annotations

import argparse
from typing import Any

from theplan.api_client import api_json
from theplan.errors import CliError
from theplan.output import emit_ok

_SCHEDULE_STYLE_CHOICES = ("standalone", "time_block", "bundle", "manual")


def _list_params(args: argparse.Namespace, *, with_epic: bool = False) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if with_epic and getattr(args, "epic_id", None) is not None:
        params["epic_id"] = args.epic_id
    if getattr(args, "archived", False):
        params["archived"] = True
    for key in ("limit", "offset", "project_id"):
        value = getattr(args, key, None)
        if value is not None:
            params[key] = value
    return params


def _optional_fields(
    args: argparse.Namespace,
    *,
    for_create: bool,
    create_required: tuple[str, ...],
    field_map: tuple[tuple[str, str], ...],
) -> dict[str, Any]:
    body: dict[str, Any] = {}
    for arg_name in create_required:
        if for_create:
            value = getattr(args, arg_name, None)
            if value is None:
                raise CliError(
                    code="INVALID_USAGE",
                    message=f"--{arg_name.replace('_', '-')} is required",
                    exit_code=1,
                )
            if isinstance(value, str):
                value = value.strip()
            body[arg_name if arg_name != "title" else "title"] = value
    for arg_name, json_key in field_map:
        value = getattr(args, arg_name, None)
        if value is not None:
            if isinstance(value, str) and arg_name == "title":
                value = value.strip()
            body[json_key] = value
    if not for_create and not body:
        raise CliError(
            code="INVALID_USAGE",
            message="Provide at least one field to patch",
            exit_code=1,
        )
    return body


def register_epics(sub: argparse._SubParsersAction) -> None:
    epics = sub.add_parser("epics", help="Epic CRUD via API")
    epics_sub = epics.add_subparsers(dest="epics_command", required=True)

    list_p = epics_sub.add_parser("list", help="List epics")
    list_p.add_argument("--archived", action="store_true")
    list_p.add_argument("--limit", type=int, default=None)
    list_p.add_argument("--offset", type=int, default=None)

    get_p = epics_sub.add_parser("get", help="Get one epic")
    get_p.add_argument("--id", required=True, dest="epic_id", metavar="UUID")

    create_p = epics_sub.add_parser("create", help="Create epic")
    create_p.add_argument("--title", required=True)
    create_p.add_argument("--description", default=None)
    create_p.add_argument("--color-hex", dest="color_hex", default=None)
    create_p.add_argument("--start-date", dest="start_date", default=None, metavar="YYYY-MM-DD")
    create_p.add_argument("--target-date", dest="target_date", default=None, metavar="YYYY-MM-DD")
    create_p.add_argument(
        "--preferred-time-window-id",
        dest="preferred_time_window_id",
        default=None,
        metavar="UUID",
    )
    create_p.add_argument(
        "--schedule-style",
        dest="schedule_style",
        choices=_SCHEDULE_STYLE_CHOICES,
        default=None,
    )

    patch_p = epics_sub.add_parser("patch", help="Patch epic")
    patch_p.add_argument("--id", required=True, dest="epic_id", metavar="UUID")
    patch_p.add_argument("--title", default=None)
    patch_p.add_argument("--description", default=None)
    patch_p.add_argument("--color-hex", dest="color_hex", default=None)
    patch_p.add_argument("--start-date", dest="start_date", default=None, metavar="YYYY-MM-DD")
    patch_p.add_argument("--target-date", dest="target_date", default=None, metavar="YYYY-MM-DD")
    patch_p.add_argument("--sort-order", dest="sort_order", type=int, default=None)
    patch_p.add_argument("--archived", dest="is_archived", action="store_true", default=None)
    patch_p.add_argument("--unarchived", dest="is_archived", action="store_false", default=None)
    patch_p.add_argument(
        "--preferred-time-window-id",
        dest="preferred_time_window_id",
        default=None,
        metavar="UUID",
    )
    patch_p.add_argument(
        "--schedule-style",
        dest="schedule_style",
        choices=_SCHEDULE_STYLE_CHOICES,
        default=None,
    )


def register_projects(sub: argparse._SubParsersAction) -> None:
    projects = sub.add_parser("projects", help="Project CRUD via API")
    projects_sub = projects.add_subparsers(dest="projects_command", required=True)

    list_p = projects_sub.add_parser("list", help="List projects")
    list_p.add_argument("--epic-id", dest="epic_id", metavar="UUID")
    list_p.add_argument("--archived", action="store_true")
    list_p.add_argument("--limit", type=int, default=None)
    list_p.add_argument("--offset", type=int, default=None)

    get_p = projects_sub.add_parser("get", help="Get one project")
    get_p.add_argument("--id", required=True, dest="project_id", metavar="UUID")

    create_p = projects_sub.add_parser("create", help="Create project")
    create_p.add_argument("--title", required=True)
    create_p.add_argument("--description", default=None)
    create_p.add_argument("--epic-id", dest="epic_id", default=None, metavar="UUID")
    create_p.add_argument("--color-hex", dest="color_hex", default=None)
    create_p.add_argument(
        "--preferred-time-window-id",
        dest="preferred_time_window_id",
        default=None,
        metavar="UUID",
    )
    create_p.add_argument(
        "--schedule-style",
        dest="schedule_style",
        choices=_SCHEDULE_STYLE_CHOICES,
        default=None,
    )

    patch_p = projects_sub.add_parser("patch", help="Patch project")
    patch_p.add_argument("--id", required=True, dest="project_id", metavar="UUID")
    patch_p.add_argument("--title", default=None)
    patch_p.add_argument("--description", default=None)
    patch_p.add_argument("--epic-id", dest="epic_id", default=None, metavar="UUID")
    patch_p.add_argument("--color-hex", dest="color_hex", default=None)
    patch_p.add_argument("--sort-order", dest="sort_order", type=int, default=None)
    patch_p.add_argument("--archived", dest="is_archived", action="store_true", default=None)
    patch_p.add_argument("--unarchived", dest="is_archived", action="store_false", default=None)
    patch_p.add_argument(
        "--preferred-time-window-id",
        dest="preferred_time_window_id",
        default=None,
        metavar="UUID",
    )
    patch_p.add_argument(
        "--schedule-style",
        dest="schedule_style",
        choices=_SCHEDULE_STYLE_CHOICES,
        default=None,
    )


def register_sections(sub: argparse._SubParsersAction) -> None:
    sections = sub.add_parser("sections", help="Section CRUD via API")
    sections_sub = sections.add_subparsers(dest="sections_command", required=True)

    list_p = sections_sub.add_parser("list", help="List sections for a project")
    list_p.add_argument("--project-id", dest="project_id", required=True, metavar="UUID")
    list_p.add_argument("--limit", type=int, default=None)
    list_p.add_argument("--offset", type=int, default=None)

    get_p = sections_sub.add_parser("get", help="Get one section")
    get_p.add_argument("--id", required=True, dest="section_id", metavar="UUID")

    create_p = sections_sub.add_parser("create", help="Create section")
    create_p.add_argument("--project-id", dest="project_id", required=True, metavar="UUID")
    create_p.add_argument("--title", required=True)
    create_p.add_argument("--sort-order", dest="sort_order", type=int, default=None)

    patch_p = sections_sub.add_parser("patch", help="Patch section")
    patch_p.add_argument("--id", required=True, dest="section_id", metavar="UUID")
    patch_p.add_argument("--title", default=None)
    patch_p.add_argument("--sort-order", dest="sort_order", type=int, default=None)


_EPIC_FIELDS = (
    ("description", "description"),
    ("color_hex", "color_hex"),
    ("start_date", "start_date"),
    ("target_date", "target_date"),
    ("preferred_time_window_id", "preferred_time_window_id"),
    ("schedule_style", "schedule_style"),
    ("sort_order", "sort_order"),
    ("is_archived", "is_archived"),
)

_PROJECT_FIELDS = (
    ("description", "description"),
    ("epic_id", "epic_id"),
    ("color_hex", "color_hex"),
    ("preferred_time_window_id", "preferred_time_window_id"),
    ("schedule_style", "schedule_style"),
    ("sort_order", "sort_order"),
    ("is_archived", "is_archived"),
)

_SECTION_FIELDS = (("sort_order", "sort_order"),)


def run_epics(args: argparse.Namespace) -> None:
    cmd = args.epics_command
    if cmd == "list":
        body = api_json(
            "GET",
            "/api/v1/epics",
            params=_list_params(args),
            persist_session=True,
        )
        emit_ok(body or {})
        return
    if cmd == "get":
        body = api_json("GET", f"/api/v1/epics/{args.epic_id}", persist_session=True)
        emit_ok(body or {})
        return
    if cmd == "create":
        payload = _optional_fields(
            args,
            for_create=True,
            create_required=("title",),
            field_map=_EPIC_FIELDS,
        )
        body = api_json("POST", "/api/v1/epics", json_body=payload, persist_session=True)
        emit_ok(body or {})
        return
    if cmd == "patch":
        payload = _optional_fields(
            args,
            for_create=False,
            create_required=(),
            field_map=(("title", "title"), *_EPIC_FIELDS),
        )
        body = api_json(
            "PATCH",
            f"/api/v1/epics/{args.epic_id}",
            json_body=payload,
            persist_session=True,
        )
        emit_ok(body or {})
        return
    raise CliError(code="INVALID_USAGE", message=f"Unknown epics command: {cmd}", exit_code=1)


def run_projects(args: argparse.Namespace) -> None:
    cmd = args.projects_command
    if cmd == "list":
        body = api_json(
            "GET",
            "/api/v1/projects",
            params=_list_params(args, with_epic=True),
            persist_session=True,
        )
        emit_ok(body or {})
        return
    if cmd == "get":
        body = api_json("GET", f"/api/v1/projects/{args.project_id}", persist_session=True)
        emit_ok(body or {})
        return
    if cmd == "create":
        payload = _optional_fields(
            args,
            for_create=True,
            create_required=("title",),
            field_map=_PROJECT_FIELDS,
        )
        body = api_json("POST", "/api/v1/projects", json_body=payload, persist_session=True)
        emit_ok(body or {})
        return
    if cmd == "patch":
        payload = _optional_fields(
            args,
            for_create=False,
            create_required=(),
            field_map=(("title", "title"), *_PROJECT_FIELDS),
        )
        body = api_json(
            "PATCH",
            f"/api/v1/projects/{args.project_id}",
            json_body=payload,
            persist_session=True,
        )
        emit_ok(body or {})
        return
    raise CliError(code="INVALID_USAGE", message=f"Unknown projects command: {cmd}", exit_code=1)


def run_sections(args: argparse.Namespace) -> None:
    cmd = args.sections_command
    if cmd == "list":
        body = api_json(
            "GET",
            "/api/v1/sections",
            params=_list_params(args),
            persist_session=True,
        )
        emit_ok(body or {})
        return
    if cmd == "get":
        body = api_json("GET", f"/api/v1/sections/{args.section_id}", persist_session=True)
        emit_ok(body or {})
        return
    if cmd == "create":
        payload = _optional_fields(
            args,
            for_create=True,
            create_required=("project_id", "title"),
            field_map=_SECTION_FIELDS,
        )
        body = api_json("POST", "/api/v1/sections", json_body=payload, persist_session=True)
        emit_ok(body or {})
        return
    if cmd == "patch":
        payload = _optional_fields(
            args,
            for_create=False,
            create_required=(),
            field_map=(("title", "title"), *_SECTION_FIELDS),
        )
        body = api_json(
            "PATCH",
            f"/api/v1/sections/{args.section_id}",
            json_body=payload,
            persist_session=True,
        )
        emit_ok(body or {})
        return
    raise CliError(code="INVALID_USAGE", message=f"Unknown sections command: {cmd}", exit_code=1)
