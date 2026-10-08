"""OpenAI-compatible chat client for Assist (default: Ollama). ADR-010.

Service layer — propose JSON actions from natural language.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from app.api.errors import ApiError
from app.config import Settings, get_settings
from app.schemas import AssistAction, AssistCreateProjectAction, AssistCreateTaskAction
from app.services.quick_add import parse_quick_add

_SYSTEM_PROMPT = """You are a planning assistant for thePlan, a personal task manager.
Given the user's request, propose zero or more actions as JSON only.

Return exactly this shape (mix create_task and create_project as needed):
{"actions":[
  {"type":"create_task","title":"...","description":null,"project_name":null,"section_name":null,"priority":null,"due_at":null,"label_names":[],"estimated_duration_minutes":null},
  {"type":"create_project","title":"...","description":null,"epic_name":null,"epic_id":null,"color_hex":null}
]}

Rules:
- Allowed types: "create_task" and "create_project" only (no deletes, schedule changes, or calendar writes).
- create_task: title required; strip scheduling words (tonight, tomorrow, at 9pm, p1, etc.) from title when they are timing/priority cues.
- create_project: title is the new project name; use when the user asks to add/create/start a project (not merely mention an existing project for a task).
- description must be null unless the user clearly asked for notes/details beyond the name. NEVER copy the whole user request into description.
- create_task priority if set must be one of: p1, p2, p3, p4.
- create_task due_at if the user gave a time/date: ISO-8601 datetime WITH timezone offset, resolved against Current local time below.
- create_task estimated_duration_minutes if the user gave a duration (e.g. "60m", "for an hour").
- create_task project_name / section_name / label_names are human names to resolve later; omit or null when unknown.
- create_project epic_name / epic_id link to an existing epic when the user named one; omit when standalone. Do not set both epic_name and epic_id.
- create_project color_hex only when the user gave a color (e.g. #0A8558); otherwise null.
- Do not put due times, durations, or schedule blocks on create_project actions.
- Prefer multiple actions when the user listed multiple distinct items.
- Do not invent unrelated work. If nothing actionable, return {"actions":[]}.
"""


def _strip_json_fence(text: str) -> str:
    stripped = text.strip()
    fence = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", stripped, re.IGNORECASE)
    if fence:
        return fence.group(1).strip()
    return stripped


def _parse_one_action(item: dict[str, Any]) -> AssistAction | None:
    action_type = item.get("type")
    try:
        if action_type == "create_project":
            return AssistCreateProjectAction.model_validate(item)
        payload = {**item, "type": "create_task"}
        return AssistCreateTaskAction.model_validate(payload)
    except Exception:
        return None


def parse_actions_payload(content: str) -> list[AssistAction]:
    raw = _strip_json_fence(content)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ApiError(502, "Assist model returned invalid JSON", "ASSIST_BAD_RESPONSE") from exc

    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = data.get("actions", data.get("Tasks", data.get("tasks")))
        if items is None and data.get("type") in ("create_task", "create_project"):
            items = [data]
        if items is None:
            raise ApiError(502, "Assist model JSON missing actions", "ASSIST_BAD_RESPONSE")
    else:
        raise ApiError(502, "Assist model JSON has unexpected shape", "ASSIST_BAD_RESPONSE")

    if not isinstance(items, list):
        raise ApiError(502, "Assist model actions must be a list", "ASSIST_BAD_RESPONSE")

    actions: list[AssistAction] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        parsed = _parse_one_action(item)
        if parsed is not None:
            actions.append(parsed)
    return actions


def _enrich_project_from_quick_add(
    action: AssistCreateProjectAction,
    text: str,
    draft: Any,
) -> AssistCreateProjectAction:
    prompt = text.strip()
    updates: dict[str, Any] = {}

    if not action.epic_name and draft.epic_name:
        updates["epic_name"] = draft.epic_name

    if draft.project_name:
        pname = draft.project_name.strip()
        title = action.title.strip()
        if pname and (not title or title == prompt or title.lower() == prompt.lower()):
            updates["title"] = pname

    desc = (action.description or "").strip()
    title = action.title.strip()
    if desc and (desc == prompt or desc == title):
        updates["description"] = None
    elif desc and title:
        desc_l, title_l = desc.lower(), title.lower()
        if title_l in desc_l and desc_l.startswith(
            ("create a project", "create project", "new project", "add project")
        ):
            updates["description"] = None

    return action.model_copy(update=updates) if updates else action


def _enrich_task_from_quick_add(
    action: AssistCreateTaskAction,
    text: str,
    draft: Any,
) -> AssistCreateTaskAction:
    prompt = text.strip()
    updates: dict[str, Any] = {}

    draft_duration = draft.estimated_duration_minutes
    if draft_duration is not None:
        draft_duration = max(1, min(int(draft_duration), 24 * 60))

    if draft.due_at is not None:
        updates["due_at"] = draft.due_at
    if draft_duration is not None:
        updates["estimated_duration_minutes"] = draft_duration
    if action.priority is None and draft.priority is not None:
        updates["priority"] = draft.priority
    if not action.project_name and draft.project_name:
        updates["project_name"] = draft.project_name
    if not action.section_name and draft.section_name:
        updates["section_name"] = draft.section_name

    desc = (action.description or "").strip()
    if desc and (desc == prompt or desc == action.title.strip()):
        updates["description"] = None

    if draft.title and draft.title.strip() and draft.title.strip() != action.title.strip():
        draft_lower = draft.title.strip().lower()
        title_lower = action.title.strip().lower()
        if draft_lower in title_lower or any(
            token in title_lower for token in ("tonight", " tomorrow", " at ", " today")
        ):
            if len(draft.title.strip()) >= 3:
                updates["title"] = draft.title.strip()

    return action.model_copy(update=updates) if updates else action


def enrich_actions_from_quick_add(
    actions: list[AssistAction],
    text: str,
    *,
    timezone_name: str,
) -> list[AssistAction]:
    """Fill gaps with the deterministic quick-add parser; scrub prompt-as-description dumps.

    Parser owns due_at and estimated_duration_minutes for create_task when parseable.
    create_project gets epic/project name tokens only — no schedule fields.
    """
    draft = parse_quick_add(text, timezone_name=timezone_name)
    enriched: list[AssistAction] = []

    source = actions
    if not source and draft.title.strip():
        source = [
            AssistCreateTaskAction(
                title=draft.title,
                priority=draft.priority,
                due_at=draft.due_at,
                estimated_duration_minutes=(
                    max(1, min(int(draft.estimated_duration_minutes), 24 * 60))
                    if draft.estimated_duration_minutes is not None
                    else None
                ),
                project_name=draft.project_name,
                section_name=draft.section_name,
            )
        ]

    for action in source:
        if isinstance(action, AssistCreateProjectAction):
            enriched.append(_enrich_project_from_quick_add(action, text, draft))
        else:
            enriched.append(_enrich_task_from_quick_add(action, text, draft))
    return enriched


def propose_actions(
    text: str,
    *,
    timezone_name: str = "UTC",
    settings: Settings | None = None,
) -> tuple[list[AssistAction], str]:
    cfg = settings or get_settings()
    if not cfg.assist_enabled:
        raise ApiError(503, "Assist is disabled", "ASSIST_UNAVAILABLE")

    tz = ZoneInfo(timezone_name)
    now = datetime.now(tz)
    system = (
        f"{_SYSTEM_PROMPT}\n\n"
        f"Current local time: {now.isoformat()} (timezone {timezone_name}).\n"
        "Resolve relative phrases like tonight/today/tomorrow against that clock."
    )

    base = cfg.assist_base_url.rstrip("/")
    url = f"{base}/chat/completions"
    body: dict[str, Any] = {
        "model": cfg.assist_model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": text.strip()},
        ],
    }

    try:
        with httpx.Client(timeout=cfg.assist_timeout_seconds) as client:
            response = client.post(url, json=body)
    except httpx.HTTPError as exc:
        raise ApiError(
            503,
            f"Assist model unreachable at {base}",
            "ASSIST_UNAVAILABLE",
        ) from exc

    if response.status_code >= 400:
        raise ApiError(
            503,
            f"Assist model error ({response.status_code})",
            "ASSIST_UNAVAILABLE",
            body=response.text[:500],
        )

    try:
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise ApiError(502, "Assist model returned unexpected payload", "ASSIST_BAD_RESPONSE") from exc

    if not isinstance(content, str) or not content.strip():
        raise ApiError(502, "Assist model returned empty content", "ASSIST_BAD_RESPONSE")

    actions = parse_actions_payload(content)
    actions = enrich_actions_from_quick_add(actions, text, timezone_name=timezone_name)
    return actions, cfg.assist_model


def check_assist_reachable(*, settings: Settings | None = None) -> tuple[bool, str | None]:
    cfg = settings or get_settings()
    if not cfg.assist_enabled:
        return False, "Assist disabled via ASSIST_ENABLED"
    base = cfg.assist_base_url.rstrip("/")
    url = f"{base}/models"
    try:
        with httpx.Client(timeout=min(cfg.assist_timeout_seconds, 5.0)) as client:
            response = client.get(url)
        if response.status_code >= 400:
            return False, f"HTTP {response.status_code} from {url}"
        return True, None
    except httpx.HTTPError as exc:
        return False, str(exc)
