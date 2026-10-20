"""Microsoft Calendar (Graph) OAuth, sync, and mirror helpers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote, urlencode

import httpx
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.config import Settings, get_settings
from app.models import (
    CalendarAccount,
    CalendarSubscription,
    ExternalCalendarEvent,
    ScheduledBlock,
    Task,
)
from app.models.enums import CalendarProvider, CalendarSubscriptionRole
from app.scheduler.free_busy import apply_transparency_update, resolve_microsoft_show_as
from app.services.source_timezone import (
    IndeterminateLocalTime,
    ParsedEventBounds,
    all_day_bounds_utc,
    attach_naive_wall_clock,
    is_local_midnight,
    parse_civil_date,
    pick_consistent_zone,
    resolve_iana_zone,
    utc_midnight_placeholder,
)
from app.services.token_crypto import decrypt_token, encrypt_token

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
_GRAPH_ORIGIN = "https://graph.microsoft.com/"
_LOGIN_BASE = "https://login.microsoftonline.com"

_DELTA_RESYNC_CODES = frozenset(
    {
        "syncstatenotfound",
        "resyncrequired",
        "errorresyncrequired",
        "fullsyncrequired",
        "invaliddeltatoken",
    }
)


class MicrosoftDeltaExpired(Exception):
    """Raised when Graph rejects a calendarView delta token (resync required)."""


@dataclass(frozen=True)
class MicrosoftOAuthConfig:
    client_id: str
    client_secret: str
    redirect_uri: str
    tenant_id: str
    scopes: str


def _authorize_url(tenant_id: str) -> str:
    return f"{_LOGIN_BASE}/{tenant_id}/oauth2/v2.0/authorize"


def _token_url(tenant_id: str) -> str:
    return f"{_LOGIN_BASE}/{tenant_id}/oauth2/v2.0/token"


def _calendar_events_url(calendar_id: str) -> str:
    return f"{GRAPH_BASE}/me/calendars/{quote(calendar_id, safe='')}/events"


def _calendar_view_url(calendar_id: str) -> str:
    return f"{GRAPH_BASE}/me/calendars/{quote(calendar_id, safe='')}/calendarView"


def _calendar_view_delta_url(calendar_id: str) -> str:
    return f"{GRAPH_BASE}/me/calendars/{quote(calendar_id, safe='')}/calendarView/delta"


def _graph_headers(access_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Prefer": 'outlook.timezone="UTC"',
    }


def _normalize_tenant(raw: str | None) -> str:
    tenant = (raw or "common").strip().strip("/")
    if not tenant or not all(ch.isalnum() or ch == "-" for ch in tenant):
        return "common"
    return tenant


def load_microsoft_oauth_config(settings: Settings | None = None) -> MicrosoftOAuthConfig:
    settings = settings or get_settings()
    client_id = (settings.microsoft_client_id or "").strip() or None
    client_secret = (settings.microsoft_client_secret or "").strip() or None
    redirect_uri = (settings.microsoft_redirect_uri or "").strip() or None
    tenant_id = _normalize_tenant(settings.microsoft_tenant_id)

    if not client_id or not client_secret or not redirect_uri:
        raise ApiError(
            503,
            "Microsoft Calendar OAuth is not configured (client id/secret/redirect)",
            "MICROSOFT_OAUTH_NOT_CONFIGURED",
        )

    return MicrosoftOAuthConfig(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        tenant_id=tenant_id,
        scopes=settings.microsoft_oauth_scopes.strip(),
    )


def build_authorize_url(config: MicrosoftOAuthConfig, state: str) -> str:
    params = {
        "client_id": config.client_id,
        "redirect_uri": config.redirect_uri,
        "response_type": "code",
        "response_mode": "query",
        "scope": config.scopes,
        "prompt": "consent",
        "state": state,
    }
    return f"{_authorize_url(config.tenant_id)}?{urlencode(params)}"


def exchange_code_for_tokens(config: MicrosoftOAuthConfig, code: str) -> dict[str, Any]:
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            _token_url(config.tenant_id),
            data={
                "code": code,
                "client_id": config.client_id,
                "client_secret": config.client_secret,
                "redirect_uri": config.redirect_uri,
                "grant_type": "authorization_code",
                "scope": config.scopes,
            },
        )
    if response.status_code >= 400:
        raise ApiError(
            502,
            "Microsoft token exchange failed",
            "MICROSOFT_TOKEN_EXCHANGE",
            body=response.text[:500],
        )
    return response.json()


def refresh_access_token(config: MicrosoftOAuthConfig, refresh_token: str) -> dict[str, Any]:
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            _token_url(config.tenant_id),
            data={
                "client_id": config.client_id,
                "client_secret": config.client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
                "scope": config.scopes,
            },
        )
    if response.status_code >= 400:
        raise ApiError(
            502,
            "Microsoft token refresh failed",
            "MICROSOFT_TOKEN_REFRESH",
            body=response.text[:500],
        )
    return response.json()


def fetch_microsoft_email(access_token: str) -> str | None:
    with httpx.Client(timeout=20.0) as client:
        response = client.get(
            f"{GRAPH_BASE}/me",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"$select": "mail,userPrincipalName"},
        )
    if response.status_code >= 400:
        return None
    data = response.json()
    email = data.get("mail") or data.get("userPrincipalName")
    return str(email) if email else None


def _ensure_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _iso_z(dt: datetime) -> str:
    return _ensure_aware(dt).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _graph_local_utc(dt: datetime) -> str:
    return _ensure_aware(dt).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _normalize_graph_datetime_text(value: str) -> str:
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    if "." in text:
        head, rest = text.split(".", 1)
        digits: list[str] = []
        idx = 0
        while idx < len(rest) and rest[idx].isdigit():
            digits.append(rest[idx])
            idx += 1
        frac = "".join(digits)[:6].ljust(6, "0")
        text = f"{head}.{frac}{rest[idx:]}"
    return text


def _graph_datetime_has_offset(text: str) -> bool:
    return text.endswith("Z") or "+" in text[10:] or (
        text.count("-") >= 3 and "T" in text
    )


def _parse_graph_datetime(value: str, time_zone: str | None = None) -> datetime:
    """Parse Graph dateTime; attach ``time_zone`` only when the value is naive.

    Raises ``IndeterminateLocalTime`` when naive attachment is DST-ambiguous or
    nonexistent (never silent ``fold=0``).
    """
    text = _normalize_graph_datetime_text(value)
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc)
    iana = resolve_iana_zone(time_zone)
    if iana is not None:
        return attach_naive_wall_clock(dt, iana)
    # Naive with no resolvable zone — UTC attach is storage only; caller must flag.
    return dt.replace(tzinfo=timezone.utc)


def _ms_provenance_zone(
    event: dict[str, Any],
    *,
    calendar_timezone: str | None,
) -> tuple[str | None, bool]:
    """Resolve MS *source provenance*: original* else calendar default.

    Precedence (Track-1-Contracts §1.3 / Dex):

    1. ``originalStartTimeZone`` / ``originalEndTimeZone`` — considered together;
       must agree when both present. Explicit unsupported values fail closed
       (never fall through to the calendar default).
    2. Else owning-calendar default (``calendar_timezone``).

    Display ``start/end.timeZone`` is Prefer/display only and is never used as
    provenance here. Returns ``(iana, missing)``.
    """

    def _nonempty(raw: Any) -> bool:
        return raw is not None and str(raw).strip() != ""

    orig_start = event.get("originalStartTimeZone")
    orig_end = event.get("originalEndTimeZone")
    if _nonempty(orig_start) or _nonempty(orig_end):
        zone, indeterminate = pick_consistent_zone(orig_start, orig_end)
        if indeterminate or zone is None:
            return None, True
        return zone, False

    zone, indeterminate = pick_consistent_zone(calendar_timezone)
    if indeterminate or zone is None:
        return None, True
    return zone, False


def _ms_response_decode_zone(
    start: dict[str, Any],
    end: dict[str, Any],
) -> tuple[str | None, bool]:
    """Zone used to decode returned wall-clock ``dateTime`` values.

    Prefer/display ``timeZone`` on start/end — distinct from original* provenance.
    """
    zone, indeterminate = pick_consistent_zone(
        start.get("timeZone"),
        end.get("timeZone"),
    )
    if indeterminate:
        return None, True
    return zone, zone is None


def _untrusted_all_day(
    start_day: date,
    end_day: date,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
) -> ParsedEventBounds:
    if start is None or end is None:
        placeholder = utc_midnight_placeholder(start_day, end_day)
        start, end = placeholder[0], placeholder[1]
    return ParsedEventBounds(
        start=start,
        end=end,
        is_all_day=True,
        source_timezone=None,
        source_zone_missing=True,
    )


def parse_microsoft_event_times(
    event: dict[str, Any],
    *,
    calendar_timezone: str | None = None,
) -> ParsedEventBounds | None:
    """Parse Graph event times with source-zone provenance (T1-B).

    Decode zone (response Prefer/display ``timeZone`` / offset) is separate from
    provenance (``original*`` / calendar). Timed Prefer-UTC wall clocks decode as
    UTC absolutes even when original* is Pacific. All-day recovers civil midnights
    via absolute→provenance conversion — never by slicing the UTC date string.
    Non-canonical ``start.date`` / ``end.date`` keys → unsupported / missing zone.
    """
    from zoneinfo import ZoneInfo

    start = event.get("start") or {}
    end = event.get("end") or {}

    # Non-canonical Graph shape — do not invent UTC date-only busy bounds.
    if start.get("date") and end.get("date"):
        start_day = parse_civil_date(start["date"])
        end_day = parse_civil_date(end["date"])
        return _untrusted_all_day(start_day, end_day)

    start_raw = start.get("dateTime")
    end_raw = end.get("dateTime")
    if not start_raw or not end_raw:
        return None

    is_all_day = bool(event.get("isAllDay"))
    provenance, provenance_missing = _ms_provenance_zone(
        event, calendar_timezone=calendar_timezone
    )
    decode_zone, decode_missing = _ms_response_decode_zone(start, end)

    start_text = str(start_raw).strip()
    end_text = str(end_raw).strip()
    start_has_offset = _graph_datetime_has_offset(start_text)
    end_has_offset = _graph_datetime_has_offset(end_text)

    def _decode_abs(raw: str, has_offset: bool) -> datetime | None:
        try:
            if has_offset:
                return _parse_graph_datetime(raw)
            if decode_missing or decode_zone is None:
                return None
            return _parse_graph_datetime(raw, decode_zone)
        except IndeterminateLocalTime:
            return None

    if is_all_day:
        start_day = parse_civil_date(start_text)
        end_day = parse_civil_date(end_text)
        start_abs = _decode_abs(start_text, start_has_offset)
        end_abs = _decode_abs(end_text, end_has_offset)
        if start_abs is None or end_abs is None:
            return _untrusted_all_day(start_day, end_day)
        if provenance_missing or provenance is None:
            # Absolute Prefer instants may be known, but floating civil trust needs
            # provenance — fail closed for busy merge.
            return _untrusted_all_day(
                start_day, end_day, start=start_abs, end=end_abs
            )
        try:
            tz = ZoneInfo(provenance)
        except (KeyError, ValueError):
            return _untrusted_all_day(
                start_day, end_day, start=start_abs, end=end_abs
            )
        start_local = start_abs.astimezone(tz)
        end_local = end_abs.astimezone(tz)
        if not is_local_midnight(start_local) or not is_local_midnight(end_local):
            # Not source-local midnights — do not slice UTC date + reattach zone.
            return _untrusted_all_day(
                start_day, end_day, start=start_abs, end=end_abs
            )
        civil_start: date = start_local.date()
        civil_end: date = end_local.date()
        try:
            start_dt, end_dt = all_day_bounds_utc(civil_start, civil_end, provenance)
        except (ValueError, IndeterminateLocalTime):
            return _untrusted_all_day(
                civil_start, civil_end, start=start_abs, end=end_abs
            )
        return ParsedEventBounds(
            start=start_dt,
            end=end_dt,
            is_all_day=True,
            source_timezone=provenance,
            source_zone_missing=False,
        )

    # Timed: decode with response zone / offset; store original* as provenance only.
    if start_has_offset and end_has_offset:
        start_dt = _parse_graph_datetime(start_text)
        end_dt = _parse_graph_datetime(end_text)
        return ParsedEventBounds(
            start=start_dt,
            end=end_dt,
            is_all_day=False,
            source_timezone=None if provenance_missing else provenance,
            source_zone_missing=False,
        )

    if decode_missing or decode_zone is None:
        start_dt = _parse_graph_datetime(start_text)
        end_dt = _parse_graph_datetime(end_text)
        return ParsedEventBounds(
            start=start_dt,
            end=end_dt,
            is_all_day=False,
            source_timezone=None,
            source_zone_missing=True,
        )
    try:
        start_dt = _parse_graph_datetime(start_text, decode_zone)
        end_dt = _parse_graph_datetime(end_text, decode_zone)
    except IndeterminateLocalTime:
        start_dt = _parse_graph_datetime(start_text)
        end_dt = _parse_graph_datetime(end_text)
        return ParsedEventBounds(
            start=start_dt,
            end=end_dt,
            is_all_day=False,
            source_timezone=None,
            source_zone_missing=True,
        )
    return ParsedEventBounds(
        start=start_dt,
        end=end_dt,
        is_all_day=False,
        source_timezone=None if provenance_missing else provenance,
        source_zone_missing=False,
    )


def _graph_error_code(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return ""
    if not isinstance(payload, dict):
        return ""
    error = payload.get("error") or {}
    if not isinstance(error, dict):
        return ""
    return str(error.get("code") or "")


def _is_delta_resync(response: httpx.Response) -> bool:
    if response.status_code == 410:
        return True
    code = _graph_error_code(response).lower()
    if code in _DELTA_RESYNC_CODES:
        return True
    if response.status_code == 400:
        try:
            payload = response.json()
            err = payload.get("error") if isinstance(payload, dict) else {}
            message = str(err.get("message") or "") if isinstance(err, dict) else ""
        except ValueError:
            message = response.text or ""
        blob = message.lower()
        if "delta" in blob and any(word in blob for word in ("invalid", "expired", "gone", "sync", "token")):
            return True
    return False


def _absolute_graph_url(url: str) -> str:
    if url.startswith(_GRAPH_ORIGIN):
        return url
    if url.startswith("/"):
        return f"https://graph.microsoft.com{url}"
    raise MicrosoftDeltaExpired()


def _graph_collect(
    access_token: str,
    url: str,
    *,
    params: dict[str, str] | None = None,
    list_error_code: str,
    list_error_detail: str,
    delta_mode: bool = False,
) -> tuple[list[dict[str, Any]], str | None]:
    items: list[dict[str, Any]] = []
    delta_link: str | None = None
    headers = _graph_headers(access_token)
    next_url = url
    next_params = params
    with httpx.Client(timeout=60.0) as client:
        while next_url:
            next_url = _absolute_graph_url(next_url)
            response = client.get(next_url, params=next_params, headers=headers)
            if delta_mode and _is_delta_resync(response):
                raise MicrosoftDeltaExpired()
            if response.status_code >= 400:
                raise ApiError(
                    502,
                    list_error_detail,
                    list_error_code,
                    body=response.text[:500],
                )
            payload = response.json()
            items.extend(payload.get("value") or [])
            next_link = payload.get("@odata.nextLink")
            if payload.get("@odata.deltaLink"):
                delta_link = str(payload["@odata.deltaLink"])
            next_url = str(next_link) if next_link else None
            next_params = None
    return items, delta_link


def _graph_access_role(cal: dict[str, Any]) -> str:
    if cal.get("canEdit"):
        if cal.get("canShare") or cal.get("isDefaultCalendar"):
            return "owner"
        return "writer"
    if cal.get("canViewPrivateItems"):
        return "reader"
    return "freeBusyReader"


def list_microsoft_calendars(access_token: str) -> list[dict[str, Any]]:
    raw, _ = _graph_collect(
        access_token,
        f"{GRAPH_BASE}/me/calendars",
        params={
            "$top": "100",
            "$select": "id,name,isDefaultCalendar,canEdit,canShare,canViewPrivateItems",
        },
        list_error_code="MICROSOFT_CALENDAR_LIST",
        list_error_detail="Microsoft Calendar list failed",
    )
    normalized: list[dict[str, Any]] = []
    for cal in raw:
        calendar_id = cal.get("id")
        if not calendar_id:
            continue
        role = _graph_access_role(cal)
        normalized.append(
            {
                "id": str(calendar_id),
                "summary": cal.get("name"),
                "primary": bool(cal.get("isDefaultCalendar")),
                "access_role": role,
                "accessRole": role,
            }
        )
    return normalized


# Evidence for complete_representation on upsert: event-list Graph calls
# (calendarView / calendarView/delta) do not pass event `$select`. Params are
# only window bounds (and optional `$top`); incremental delta follows the
# link with no params. Do not claim complete_representation when upsert
# payloads lack parseable times.
MS_EVENT_LIST_SELECT_PARAM = "$select"


def microsoft_event_list_window_params(
    *,
    time_min: datetime,
    time_max: datetime,
    top: str | None = None,
) -> dict[str, str]:
    """Build calendarView / delta list params — window bounds only, no `$select`."""
    params: dict[str, str] = {
        "startDateTime": _iso_z(time_min),
        "endDateTime": _iso_z(time_max),
    }
    if top is not None:
        params["$top"] = top
    return params


def microsoft_event_list_omits_event_select(
    params: dict[str, str] | None,
) -> bool:
    """True when a Graph event-list call does not project via event `$select`."""
    if params is None:
        return True
    return MS_EVENT_LIST_SELECT_PARAM not in params


def list_calendar_events(
    access_token: str,
    calendar_id: str,
    *,
    time_min: datetime,
    time_max: datetime,
) -> tuple[list[dict[str, Any]], str | None]:
    params = microsoft_event_list_window_params(time_min=time_min, time_max=time_max)
    return _graph_collect(
        access_token,
        _calendar_view_delta_url(calendar_id),
        params=params,
        list_error_code="MICROSOFT_EVENTS_LIST",
        list_error_detail="Microsoft Calendar events list failed",
        delta_mode=True,
    )


def list_calendar_view(
    access_token: str,
    calendar_id: str,
    *,
    time_min: datetime,
    time_max: datetime,
) -> list[dict[str, Any]]:
    params = microsoft_event_list_window_params(
        time_min=time_min, time_max=time_max, top="100"
    )
    items, _ = _graph_collect(
        access_token,
        _calendar_view_url(calendar_id),
        params=params,
        list_error_code="MICROSOFT_EVENTS_LIST",
        list_error_detail="Microsoft Calendar events list failed",
    )
    return items


def list_calendar_events_incremental(
    access_token: str,
    delta_link: str,
) -> tuple[list[dict[str, Any]], str | None]:
    # Delta-link follow: no query params (hence no event $select).
    return _graph_collect(
        access_token,
        _absolute_graph_url(delta_link),
        list_error_code="MICROSOFT_EVENTS_LIST",
        list_error_detail="Microsoft Calendar events list failed",
        delta_mode=True,
    )


def _event_time_body(start: datetime, end: datetime) -> dict[str, Any]:
    return {
        "start": {"dateTime": _graph_local_utc(start), "timeZone": "UTC"},
        "end": {"dateTime": _graph_local_utc(end), "timeZone": "UTC"},
    }


def create_microsoft_event(
    access_token: str,
    calendar_id: str,
    *,
    title: str,
    start: datetime,
    end: datetime,
) -> dict[str, Any]:
    body = {"subject": title, **_event_time_body(start, end)}
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            _calendar_events_url(calendar_id),
            json=body,
            headers=_graph_headers(access_token),
        )
    if response.status_code >= 400:
        raise ApiError(
            502,
            "Microsoft Calendar event create failed",
            "MICROSOFT_EVENT_CREATE",
            body=response.text[:500],
        )
    return response.json()


def patch_microsoft_event(
    access_token: str,
    calendar_id: str,
    event_id: str,
    *,
    title: str,
    start: datetime,
    end: datetime,
) -> dict[str, Any]:
    body = {"subject": title, **_event_time_body(start, end)}
    event_path = f"{_calendar_events_url(calendar_id)}/{quote(event_id, safe='')}"
    with httpx.Client(timeout=30.0) as client:
        response = client.patch(
            event_path,
            json=body,
            headers=_graph_headers(access_token),
        )
    if response.status_code >= 400:
        raise ApiError(
            502,
            "Microsoft Calendar event patch failed",
            "MICROSOFT_EVENT_PATCH",
            body=response.text[:500],
        )
    return response.json()


def delete_microsoft_event(access_token: str, calendar_id: str, event_id: str) -> None:
    event_path = f"{_calendar_events_url(calendar_id)}/{quote(event_id, safe='')}"
    with httpx.Client(timeout=30.0) as client:
        response = client.delete(
            event_path,
            headers=_graph_headers(access_token),
        )
    if response.status_code >= 400 and response.status_code != 404:
        raise ApiError(
            502,
            "Microsoft Calendar event delete failed",
            "MICROSOFT_EVENT_DELETE",
            body=response.text[:500],
        )


def _fetch_default_calendar(access_token: str) -> tuple[str, str | None]:
    with httpx.Client(timeout=20.0) as client:
        response = client.get(
            f"{GRAPH_BASE}/me/calendar",
            headers=_graph_headers(access_token),
            params={"$select": "id,name,isDefaultCalendar"},
        )
    if response.status_code >= 400:
        raise ApiError(
            502,
            "Microsoft default calendar lookup failed",
            "MICROSOFT_PRIMARY_CALENDAR",
            body=response.text[:500],
        )
    payload = response.json()
    calendar_id = payload.get("id")
    if not calendar_id:
        raise ApiError(
            502,
            "Microsoft default calendar did not return an id",
            "MICROSOFT_PRIMARY_CALENDAR",
        )
    return str(calendar_id), payload.get("name")


def ensure_primary_subscription(
    db: Session,
    account: CalendarAccount,
    *,
    settings: Settings | None = None,
    access_token: str | None = None,
) -> CalendarSubscription:
    token = access_token
    if token is None:
        token = get_valid_access_token(db, settings=settings or get_settings(), account=account)
    calendar_id, summary = _fetch_default_calendar(token)

    sub = (
        db.query(CalendarSubscription)
        .filter(
            CalendarSubscription.calendar_account_id == account.id,
            CalendarSubscription.external_calendar_id == calendar_id,
        )
        .one_or_none()
    )
    if sub is None:
        legacy = (
            db.query(CalendarSubscription)
            .filter(
                CalendarSubscription.calendar_account_id == account.id,
                CalendarSubscription.external_calendar_id == "primary",
            )
            .one_or_none()
        )
        if legacy is not None:
            legacy.external_calendar_id = calendar_id
            sub = legacy
        else:
            sub = CalendarSubscription(
                owner_id=account.owner_id,
                calendar_account_id=account.id,
                external_calendar_id=calendar_id,
                summary=summary or "Calendar",
                role=CalendarSubscriptionRole.primary,
                is_enabled=True,
            )
            db.add(sub)

    if summary:
        sub.summary = summary[:255]
    elif not sub.summary:
        sub.summary = "Calendar"
    sub.role = CalendarSubscriptionRole.primary
    sub.is_enabled = True
    db.flush()
    return sub


def upsert_account_tokens(
    db: Session,
    *,
    settings: Settings,
    owner_id,
    account_email: str | None,
    token_payload: dict[str, Any],
    existing: CalendarAccount | None = None,
) -> CalendarAccount:
    access = token_payload.get("access_token")
    if not access:
        raise ApiError(502, "Microsoft did not return an access token", "MICROSOFT_NO_ACCESS_TOKEN")
    expires_in = int(token_payload.get("expires_in") or 3600)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=max(60, expires_in - 60))

    account = existing
    if account is None:
        account = (
            db.query(CalendarAccount)
            .filter(
                CalendarAccount.owner_id == owner_id,
                CalendarAccount.provider == CalendarProvider.microsoft,
                CalendarAccount.account_email == account_email,
            )
            .one_or_none()
        )
    if account is None:
        account = CalendarAccount(
            owner_id=owner_id,
            provider=CalendarProvider.microsoft,
            account_email=account_email,
        )
        db.add(account)

    account.account_email = account_email or account.account_email
    account.access_token_enc = encrypt_token(settings, access)
    refresh = token_payload.get("refresh_token")
    if refresh:
        account.refresh_token_enc = encrypt_token(settings, refresh)
    elif not account.refresh_token_enc:
        raise ApiError(
            502,
            "Microsoft did not return a refresh token; disconnect and reconnect with consent",
            "MICROSOFT_NO_REFRESH_TOKEN",
        )
    account.token_expires_at = expires_at
    account.is_enabled = True
    db.flush()
    ensure_primary_subscription(db, account, settings=settings, access_token=access)
    return account


def get_valid_access_token(
    db: Session,
    *,
    settings: Settings,
    account: CalendarAccount,
) -> str:
    if not account.access_token_enc:
        raise ApiError(400, "Calendar account has no access token", "MICROSOFT_ACCOUNT_NO_TOKEN")
    now = datetime.now(timezone.utc)
    expires = account.token_expires_at
    if expires is not None and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires and expires > now + timedelta(seconds=30):
        return decrypt_token(settings, account.access_token_enc)

    if not account.refresh_token_enc:
        raise ApiError(401, "Calendar account needs re-authorization", "MICROSOFT_REAUTH_REQUIRED")

    config = load_microsoft_oauth_config(settings)
    refresh = decrypt_token(settings, account.refresh_token_enc)
    payload = refresh_access_token(config, refresh)
    access = payload.get("access_token")
    if not access:
        raise ApiError(502, "Microsoft refresh did not return access token", "MICROSOFT_NO_ACCESS_TOKEN")
    account.access_token_enc = encrypt_token(settings, access)
    expires_in = int(payload.get("expires_in") or 3600)
    account.token_expires_at = now + timedelta(seconds=max(60, expires_in - 60))
    if payload.get("refresh_token"):
        account.refresh_token_enc = encrypt_token(settings, payload["refresh_token"])
    db.flush()
    return access


def _find_external_event(
    db: Session,
    *,
    owner_id,
    external_id: str,
) -> ExternalCalendarEvent | None:
    return (
        db.query(ExternalCalendarEvent)
        .filter(
            ExternalCalendarEvent.provider == CalendarProvider.microsoft,
            ExternalCalendarEvent.external_event_id == external_id,
            ExternalCalendarEvent.owner_id == owner_id,
        )
        .one_or_none()
    )


def _event_removed(event: dict[str, Any]) -> bool:
    if event.get("@removed"):
        return True
    if event.get("isCancelled"):
        return True
    return False


def _row_has_usable_bounds(row: ExternalCalendarEvent) -> bool:
    start = row.start_time
    end = row.end_time
    if start is None or end is None:
        return False
    return end > start


def _upsert_external_event(
    db: Session,
    *,
    account: CalendarAccount,
    subscription: CalendarSubscription,
    event: dict[str, Any],
    now: datetime,
    sync_run_id: str,
) -> bool:
    external_id = event.get("id")
    if not external_id:
        return False

    row = _find_external_event(db, owner_id=account.owner_id, external_id=external_id)
    if row is not None and row.pending_deletion:
        return False

    times = parse_microsoft_event_times(
        event, calendar_timezone=subscription.provider_timezone
    )
    times_ok = times is not None and times.end > times.start
    # complete_representation only when this upsert payload has parseable times
    # (complete-enough for the showAs boundary). Fetch shape evidence: event-list
    # Graph calls omit event $select (see microsoft_event_list_omits_event_select).
    complete_representation = times_ok

    if not times_ok:
        # Incomplete update: preserve known bounds on an existing row; never
        # fabricate times or leave falsely trusted free without a transparency pass.
        if row is None or not _row_has_usable_bounds(row):
            return False
    else:
        assert times is not None  # times_ok
        if row is None:
            row = ExternalCalendarEvent(
                owner_id=account.owner_id,
                calendar_account_id=account.id,
                provider=CalendarProvider.microsoft,
                external_event_id=external_id,
                calendar_id=subscription.external_calendar_id,
                start_time=times.start,
                end_time=times.end,
            )
            db.add(row)
        row.start_time = times.start
        row.end_time = times.end
        row.is_all_day = times.is_all_day
        row.source_zone_missing = times.source_zone_missing
        row.source_timezone = times.source_timezone

    row.calendar_account_id = account.id
    if "subject" in event or times_ok:
        row.title = (event.get("subject") or "Busy")[:500]
    row.calendar_id = subscription.external_calendar_id
    row.last_synced_at = now
    # T1-D: Graph showAs → stored transparency/provenance. No busy default.
    # Incomplete + explicit showAs maps that value; incomplete + omitted showAs
    # → unknown_projection. Complete + omitted showAs → unknown_missing.
    stored, provenance, _kind = resolve_microsoft_show_as(
        event,
        complete_representation=complete_representation,
        field_projected=False,
    )
    apply_transparency_update(
        row, stored=stored, provenance=provenance, sync_run_id=sync_run_id
    )
    return True


def _pull_subscription_changes(
    db: Session,
    *,
    access: str,
    subscription: CalendarSubscription,
    time_min: datetime,
    time_max: datetime,
) -> tuple[list[dict[str, Any]], str | None, bool]:
    """Fetch provider events before the owner scheduling lock. Returns (events, cursor, is_full)."""
    if subscription.sync_cursor:
        try:
            events, next_delta_link = list_calendar_events_incremental(
                access,
                subscription.sync_cursor,
            )
            return events, next_delta_link, False
        except MicrosoftDeltaExpired:
            logger.warning(
                "Microsoft delta expired for subscription %s; falling back to full window",
                subscription.id,
            )
            subscription.sync_cursor = None
            db.flush()

    try:
        events, next_delta_link = list_calendar_events(
            access,
            subscription.external_calendar_id,
            time_min=time_min,
            time_max=time_max,
        )
    except MicrosoftDeltaExpired:
        events = list_calendar_view(
            access,
            subscription.external_calendar_id,
            time_min=time_min,
            time_max=time_max,
        )
        next_delta_link = None
    return events, next_delta_link, True


def _apply_subscription_full(
    db: Session,
    *,
    account: CalendarAccount,
    subscription: CalendarSubscription,
    events: list[dict[str, Any]],
    next_delta_link: str | None,
    time_min: datetime,
    time_max: datetime,
    now: datetime,
    suppressed_external_ids: set[str] | None = None,
) -> int:
    suppressed = suppressed_external_ids or set()
    seen_external_ids: set[str] = set()
    upserted = 0
    sync_run_id = f"ms-full-{now.strftime('%Y%m%dT%H%M%SZ')}-{subscription.id.hex[:8]}"

    for event in events:
        external_id = event.get("id")
        if not external_id or _event_removed(event):
            if external_id and _event_removed(event):
                pending = _find_external_event(
                    db, owner_id=account.owner_id, external_id=external_id
                )
                if pending is not None and pending.pending_deletion:
                    db.delete(pending)
            continue
        if external_id in suppressed:
            continue
        seen_external_ids.add(external_id)
        if _upsert_external_event(
            db,
            account=account,
            subscription=subscription,
            event=event,
            now=now,
            sync_run_id=sync_run_id,
        ):
            upserted += 1

    stale = (
        db.query(ExternalCalendarEvent)
        .filter(
            ExternalCalendarEvent.calendar_account_id == account.id,
            ExternalCalendarEvent.calendar_id == subscription.external_calendar_id,
            ExternalCalendarEvent.provider == CalendarProvider.microsoft,
            *ExternalCalendarEvent.immovable_busy_clause(),
            ExternalCalendarEvent.start_time < time_max,
            ExternalCalendarEvent.end_time > time_min,
        )
        .all()
    )
    for row in stale:
        if row.external_event_id not in seen_external_ids:
            db.delete(row)

    if next_delta_link:
        subscription.sync_cursor = next_delta_link
    db.flush()
    return upserted


def _apply_subscription_incremental(
    db: Session,
    *,
    account: CalendarAccount,
    subscription: CalendarSubscription,
    events: list[dict[str, Any]],
    next_delta_link: str | None,
    now: datetime,
    suppressed_external_ids: set[str] | None = None,
) -> int:
    suppressed = suppressed_external_ids or set()
    upserted = 0
    sync_run_id = f"ms-incr-{now.strftime('%Y%m%dT%H%M%SZ')}-{subscription.id.hex[:8]}"

    for event in events:
        external_id = event.get("id")
        if not external_id:
            continue
        if _event_removed(event):
            row = _find_external_event(db, owner_id=account.owner_id, external_id=external_id)
            if row is not None:
                db.delete(row)
            continue
        if external_id in suppressed:
            continue
        if _upsert_external_event(
            db,
            account=account,
            subscription=subscription,
            event=event,
            now=now,
            sync_run_id=sync_run_id,
        ):
            upserted += 1

    if next_delta_link:
        subscription.sync_cursor = next_delta_link
    db.flush()
    return upserted


def sync_account_events(
    db: Session,
    *,
    settings: Settings,
    account: CalendarAccount,
    time_min: datetime,
    time_max: datetime,
) -> int:
    from app.services.mirror_tombstone import retry_pending_deletions
    from app.services.scheduling_revision import (
        immovable_busy_signature,
        increment_scheduling_revision,
        lock_owner_scheduling,
    )

    access = get_valid_access_token(db, settings=settings, account=account)
    now = datetime.now(timezone.utc)
    subscriptions = (
        db.query(CalendarSubscription)
        .filter(
            CalendarSubscription.calendar_account_id == account.id,
            CalendarSubscription.is_enabled.is_(True),
        )
        .all()
    )
    if not subscriptions:
        ensure_primary_subscription(db, account, settings=settings, access_token=access)
        subscriptions = (
            db.query(CalendarSubscription)
            .filter(
                CalendarSubscription.calendar_account_id == account.id,
                CalendarSubscription.is_enabled.is_(True),
            )
            .all()
        )

    pulled: list[tuple[CalendarSubscription, list[dict[str, Any]], str | None, bool]] = []
    for subscription in subscriptions:
        events, next_cursor, is_full = _pull_subscription_changes(
            db,
            access=access,
            subscription=subscription,
            time_min=time_min,
            time_max=time_max,
        )
        pulled.append((subscription, events, next_cursor, is_full))

    scheduling_settings = lock_owner_scheduling(db, account.owner_id)
    before_busy = immovable_busy_signature(db, account.owner_id)
    suppressed = retry_pending_deletions(
        db,
        account=account,
        access=access,
        delete_event=delete_microsoft_event,
    )
    upserted = 0
    for subscription, events, next_cursor, is_full in pulled:
        if is_full:
            upserted += _apply_subscription_full(
                db,
                account=account,
                subscription=subscription,
                events=events,
                next_delta_link=next_cursor,
                time_min=time_min,
                time_max=time_max,
                now=now,
                suppressed_external_ids=suppressed,
            )
        else:
            upserted += _apply_subscription_incremental(
                db,
                account=account,
                subscription=subscription,
                events=events,
                next_delta_link=next_cursor,
                now=now,
                suppressed_external_ids=suppressed,
            )

    account.last_synced_at = now
    db.flush()
    if immovable_busy_signature(db, account.owner_id) != before_busy:
        increment_scheduling_revision(db, scheduling_settings)
    return upserted


def _mirror_account_and_calendar(
    db: Session,
    owner_id,
) -> tuple[CalendarAccount | None, str | None]:
    account = (
        db.query(CalendarAccount)
        .filter(
            CalendarAccount.owner_id == owner_id,
            CalendarAccount.provider == CalendarProvider.microsoft,
            CalendarAccount.is_enabled.is_(True),
            CalendarAccount.mirror_blocks.is_(True),
        )
        .first()
    )
    if account is None:
        return None, None

    primary_sub = (
        db.query(CalendarSubscription)
        .filter(
            CalendarSubscription.calendar_account_id == account.id,
            CalendarSubscription.role == CalendarSubscriptionRole.primary,
            CalendarSubscription.is_enabled.is_(True),
        )
        .first()
    )
    if primary_sub is None:
        return None, None
    return account, primary_sub.external_calendar_id


def push_scheduled_block(db: Session, settings: Settings, block: ScheduledBlock) -> None:
    account, calendar_id = _mirror_account_and_calendar(db, block.owner_id)
    if account is None or not calendar_id:
        return

    task = db.get(Task, block.task_id)
    title = (task.title if task else "Scheduled block")[:500]
    try:
        access = get_valid_access_token(db, settings=settings, account=account)
    except ApiError as exc:
        if exc.content.get("code") == "MICROSOFT_OAUTH_NOT_CONFIGURED":
            return
        raise
    existing = (
        db.query(ExternalCalendarEvent)
        .filter(
            ExternalCalendarEvent.scheduled_block_id == block.id,
            ExternalCalendarEvent.provider == CalendarProvider.microsoft,
        )
        .one_or_none()
    )
    now = datetime.now(timezone.utc)

    if existing:
        patch_microsoft_event(
            access,
            calendar_id,
            existing.external_event_id,
            title=title,
            start=block.start_time,
            end=block.end_time,
        )
        existing.title = title
        existing.start_time = block.start_time
        existing.end_time = block.end_time
        existing.calendar_id = calendar_id
        existing.last_synced_at = now
    else:
        event = create_microsoft_event(
            access,
            calendar_id,
            title=title,
            start=block.start_time,
            end=block.end_time,
        )
        external_id = event.get("id")
        if not external_id:
            raise ApiError(502, "Microsoft did not return event id", "MICROSOFT_EVENT_NO_ID")
        row = ExternalCalendarEvent(
            owner_id=block.owner_id,
            calendar_account_id=account.id,
            scheduled_block_id=block.id,
            task_id=block.task_id,
            provider=CalendarProvider.microsoft,
            external_event_id=external_id,
            calendar_id=calendar_id,
            title=title,
            start_time=block.start_time,
            end_time=block.end_time,
            is_all_day=False,
            last_synced_at=now,
        )
        db.add(row)

    db.flush()


def delete_mirrored_block(db: Session, settings: Settings, block: ScheduledBlock) -> None:
    existing = (
        db.query(ExternalCalendarEvent)
        .filter(
            ExternalCalendarEvent.scheduled_block_id == block.id,
            ExternalCalendarEvent.provider == CalendarProvider.microsoft,
        )
        .one_or_none()
    )
    if existing is None:
        return

    account = db.get(CalendarAccount, existing.calendar_account_id)
    if account is None or not account.is_enabled:
        db.delete(existing)
        db.flush()
        return

    calendar_id = existing.calendar_id
    try:
        access = get_valid_access_token(db, settings=settings, account=account)
    except ApiError as exc:
        if exc.content.get("code") == "MICROSOFT_OAUTH_NOT_CONFIGURED":
            db.delete(existing)
            db.flush()
            return
        raise
    delete_microsoft_event(access, calendar_id, existing.external_event_id)
    db.delete(existing)
    db.flush()
