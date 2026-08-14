"""Microsoft Calendar (Graph) OAuth, sync, and mirror helpers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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


def _parse_graph_datetime(value: str, time_zone: str | None = None) -> datetime:
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
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        # Prefer: outlook.timezone="UTC" on Graph reads; treat leftover naive as UTC.
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def parse_microsoft_event_times(event: dict[str, Any]) -> tuple[datetime, datetime, bool] | None:
    start = event.get("start") or {}
    end = event.get("end") or {}
    if start.get("date") and end.get("date"):
        start_dt = datetime.fromisoformat(str(start["date"])).replace(tzinfo=timezone.utc)
        end_dt = datetime.fromisoformat(str(end["date"])).replace(tzinfo=timezone.utc)
        return start_dt, end_dt, True
    start_raw = start.get("dateTime")
    end_raw = end.get("dateTime")
    if not start_raw or not end_raw:
        return None
    start_dt = _parse_graph_datetime(str(start_raw), start.get("timeZone"))
    end_dt = _parse_graph_datetime(str(end_raw), end.get("timeZone"))
    return start_dt, end_dt, bool(event.get("isAllDay"))


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


def list_calendar_events(
    access_token: str,
    calendar_id: str,
    *,
    time_min: datetime,
    time_max: datetime,
) -> tuple[list[dict[str, Any]], str | None]:
    params = {
        "startDateTime": _iso_z(time_min),
        "endDateTime": _iso_z(time_max),
    }
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
    params = {
        "startDateTime": _iso_z(time_min),
        "endDateTime": _iso_z(time_max),
        "$top": "100",
    }
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


def _upsert_external_event(
    db: Session,
    *,
    account: CalendarAccount,
    subscription: CalendarSubscription,
    event: dict[str, Any],
    now: datetime,
) -> bool:
    external_id = event.get("id")
    if not external_id:
        return False
    times = parse_microsoft_event_times(event)
    if times is None:
        return False
    start_dt, end_dt, is_all_day = times
    if end_dt <= start_dt:
        return False

    row = _find_external_event(db, owner_id=account.owner_id, external_id=external_id)
    if row is None:
        row = ExternalCalendarEvent(
            owner_id=account.owner_id,
            calendar_account_id=account.id,
            provider=CalendarProvider.microsoft,
            external_event_id=external_id,
            calendar_id=subscription.external_calendar_id,
            start_time=start_dt,
            end_time=end_dt,
        )
        db.add(row)

    row.calendar_account_id = account.id
    row.title = (event.get("subject") or "Busy")[:500]
    row.start_time = start_dt
    row.end_time = end_dt
    row.is_all_day = is_all_day
    row.calendar_id = subscription.external_calendar_id
    row.last_synced_at = now
    return True


def _sync_subscription_full(
    db: Session,
    *,
    access: str,
    account: CalendarAccount,
    subscription: CalendarSubscription,
    time_min: datetime,
    time_max: datetime,
    now: datetime,
) -> int:
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
    seen_external_ids: set[str] = set()
    upserted = 0

    for event in events:
        external_id = event.get("id")
        if not external_id or _event_removed(event):
            continue
        seen_external_ids.add(external_id)
        if _upsert_external_event(
            db,
            account=account,
            subscription=subscription,
            event=event,
            now=now,
        ):
            upserted += 1

    stale = (
        db.query(ExternalCalendarEvent)
        .filter(
            ExternalCalendarEvent.calendar_account_id == account.id,
            ExternalCalendarEvent.calendar_id == subscription.external_calendar_id,
            ExternalCalendarEvent.provider == CalendarProvider.microsoft,
            ExternalCalendarEvent.scheduled_block_id.is_(None),
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


def _sync_subscription_incremental(
    db: Session,
    *,
    access: str,
    account: CalendarAccount,
    subscription: CalendarSubscription,
    now: datetime,
) -> int:
    assert subscription.sync_cursor
    events, next_delta_link = list_calendar_events_incremental(
        access,
        subscription.sync_cursor,
    )
    upserted = 0

    for event in events:
        external_id = event.get("id")
        if not external_id:
            continue
        if _event_removed(event):
            row = _find_external_event(db, owner_id=account.owner_id, external_id=external_id)
            if row is not None:
                db.delete(row)
            continue
        if _upsert_external_event(
            db,
            account=account,
            subscription=subscription,
            event=event,
            now=now,
        ):
            upserted += 1

    if next_delta_link:
        subscription.sync_cursor = next_delta_link
    db.flush()
    return upserted


def _sync_subscription(
    db: Session,
    *,
    settings: Settings,
    account: CalendarAccount,
    subscription: CalendarSubscription,
    time_min: datetime,
    time_max: datetime,
    access: str,
    now: datetime,
) -> int:
    if subscription.sync_cursor:
        try:
            return _sync_subscription_incremental(
                db,
                access=access,
                account=account,
                subscription=subscription,
                now=now,
            )
        except MicrosoftDeltaExpired:
            logger.warning(
                "Microsoft delta expired for subscription %s; falling back to full window",
                subscription.id,
            )
            subscription.sync_cursor = None
            db.flush()

    return _sync_subscription_full(
        db,
        access=access,
        account=account,
        subscription=subscription,
        time_min=time_min,
        time_max=time_max,
        now=now,
    )


def sync_account_events(
    db: Session,
    *,
    settings: Settings,
    account: CalendarAccount,
    time_min: datetime,
    time_max: datetime,
) -> int:
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

    upserted = 0
    for subscription in subscriptions:
        upserted += _sync_subscription(
            db,
            settings=settings,
            account=account,
            subscription=subscription,
            time_min=time_min,
            time_max=time_max,
            access=access,
            now=now,
        )

    account.last_synced_at = now
    db.flush()
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
