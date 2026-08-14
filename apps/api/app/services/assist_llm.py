"""OpenAI-compatible chat client for Assist (default: Ollama). ADR-010."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.api.errors import ApiError
from app.config import Settings, get_settings
from app.schemas import AssistCreateTaskAction

_SYSTEM_PROMPT = """You are a planning assistant for thePlan, a personal task manager.
Given the user's request, propose zero or more create_task actions as JSON only.

Return exactly this shape:
{"actions":[{"type":"create_task","title":"...","description":null,"project_name":null,"section_name":null,"priority":null,"due_at":null,"label_names":[],"estimated_duration_minutes":null}]}

Rules:
- type must be "create_task" only (no deletes, schedule changes, or calendar writes).
- title is required and concise.
- priority if set must be one of: p1, p2, p3, p4.
- due_at if set must be ISO-8601 datetime (include timezone offset when known).
- project_name / section_name / label_names are human names to resolve later; omit or null when unknown.
- Prefer multiple actions when the user listed multiple distinct tasks.
- Do not invent unrelated work. If nothing actionable, return {"actions":[]}.
"""


def _strip_json_fence(text: str) -> str:
    stripped = text.strip()
    fence = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", stripped, re.IGNORECASE)
    if fence:
        return fence.group(1).strip()
    return stripped


def parse_actions_payload(content: str) -> list[AssistCreateTaskAction]:
    raw = _strip_json_fence(content)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ApiError(502, "Assist model returned invalid JSON", "ASSIST_BAD_RESPONSE") from exc

    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = data.get("actions", data.get("Tasks", data.get("tasks")))
        if items is None and data.get("type") == "create_task":
            items = [data]
        if items is None:
            raise ApiError(502, "Assist model JSON missing actions", "ASSIST_BAD_RESPONSE")
    else:
        raise ApiError(502, "Assist model JSON has unexpected shape", "ASSIST_BAD_RESPONSE")

    if not isinstance(items, list):
        raise ApiError(502, "Assist model actions must be a list", "ASSIST_BAD_RESPONSE")

    actions: list[AssistCreateTaskAction] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        payload = {**item, "type": "create_task"}
        try:
            actions.append(AssistCreateTaskAction.model_validate(payload))
        except Exception:
            # Skip malformed rows; keep the rest usable for review.
            continue
    return actions


def propose_actions(text: str, *, settings: Settings | None = None) -> tuple[list[AssistCreateTaskAction], str]:
    cfg = settings or get_settings()
    if not cfg.assist_enabled:
        raise ApiError(503, "Assist is disabled", "ASSIST_UNAVAILABLE")

    base = cfg.assist_base_url.rstrip("/")
    url = f"{base}/chat/completions"
    body: dict[str, Any] = {
        "model": cfg.assist_model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
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

    return parse_actions_payload(content), cfg.assist_model


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
