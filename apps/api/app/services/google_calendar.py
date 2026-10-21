"""Google Calendar OAuth, sync, and mirror helpers."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
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
from app.scheduler.free_busy import apply_transparency_update, resolve_google_transparency
from app.services.source_timezone import (
    IndeterminateLocalTime,
    ParsedEventBounds,
    all_day_bounds_utc,
    attach_naive_wall_clock,
    parse_civil_date,
    pick_consistent_zone,
    resolve_iana_zone,
    utc_midnight_placeholder,
)
from app.services.export_baseline import (
    GOOGLE_MIRROR_PUSH_SOURCE,
    apply_export_baseline_after_mirror_push,
    google_mirror_datetime_token,
)
from app.services.calendar_refresh_failures import (
    FAILURE_PERSIST_EXPIRE_ATTRS as _FAILURE_PERSIST_EXPIRE_ATTRS,
    commit_pre_pull_refresh_failure as _commit_pre_pull_refresh_failure,
    commit_refresh_failure as _commit_refresh_failure,
    failure_committed as _failure_committed,
    mark_failure_committed as _mark_failure_committed,
)
from app.services.token_crypto import decrypt_token, encrypt_token

logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
GOOGLE_CALENDAR_LIST_URL = "https://www.googleapis.com/calendar/v3/users/me/calendarList"


class GoogleSyncTokenExpired(Exception):
    """Raised when Google returns 410 for an incremental sync token."""


# Production drains every page. Tests may set a positive cap so a remaining
# nextPageToken fails closed (no success mint, no cursor advance).
pagination_max_pages: int | None = None
# Real paginator sets this. Mocked list_* leaves the pull default of True.
_pull_pagination_complete: bool = True


@dataclass(frozen=True)
class GoogleOAuthConfig:
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: str


def _calendar_events_base(calendar_id: str) -> str:
    return f"https://www.googleapis.com/calendar/v3/calendars/{quote(calendar_id, safe='')}/events"


def _iso_z(dt: datetime) -> str:
    return google_mirror_datetime_token(dt)


def load_google_oauth_config(settings: Settings | None = None) -> GoogleOAuthConfig:
    settings = settings or get_settings()
    client_id = (settings.google_client_id or "").strip() or None
    client_secret = (settings.google_client_secret or "").strip() or None
    redirect_uri = (settings.google_redirect_uri or "").strip() or None

    secrets_path = (settings.google_client_secrets_file or "").strip()
    if secrets_path:
        path = Path(secrets_path)
        if not path.is_file():
            raise ApiError(503, f"Google secrets file not found: {path}", "GOOGLE_SECRETS_MISSING")
        data = json.loads(path.read_text(encoding="utf-8"))
        block = data.get("web") or data.get("installed")
        if not isinstance(block, dict):
            raise ApiError(503, "Google secrets JSON missing web/installed block", "GOOGLE_SECRETS_INVALID")
        client_id = client_id or block.get("client_id")
        client_secret = client_secret or block.get("client_secret")
        if not redirect_uri:
            uris = block.get("redirect_uris") or []
            if uris:
                redirect_uri = uris[0]

    if not client_id or not client_secret or not redirect_uri:
        raise ApiError(
            503,
            "Google Calendar OAuth is not configured (client id/secret/redirect)",
            "GOOGLE_OAUTH_NOT_CONFIGURED",
        )

    return GoogleOAuthConfig(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scopes=settings.google_oauth_scopes.strip(),
    )


def build_authorize_url(config: GoogleOAuthConfig, state: str) -> str:
    params = {
        "client_id": config.client_id,
        "redirect_uri": config.redirect_uri,
        "response_type": "code",
        "scope": config.scopes,
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": state,
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def exchange_code_for_tokens(config: GoogleOAuthConfig, code: str) -> dict[str, Any]:
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": config.client_id,
                "client_secret": config.client_secret,
                "redirect_uri": config.redirect_uri,
                "grant_type": "authorization_code",
            },
        )
    if response.status_code >= 400:
        raise ApiError(502, "Google token exchange failed", "GOOGLE_TOKEN_EXCHANGE", body=response.text[:500])
    return response.json()


def refresh_access_token(config: GoogleOAuthConfig, refresh_token: str) -> dict[str, Any]:
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": config.client_id,
                "client_secret": config.client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
    if response.status_code >= 400:
        raise ApiError(502, "Google token refresh failed", "GOOGLE_TOKEN_REFRESH", body=response.text[:500])
    return response.json()


def fetch_google_email(access_token: str) -> str | None:
    with httpx.Client(timeout=20.0) as client:
        response = client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if response.status_code >= 400:
        return None
    data = response.json()
    email = data.get("email")
    return str(email) if email else None


def _ensure_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _google_datetime_has_offset(raw: Any) -> bool:
    if not isinstance(raw, str) or not raw:
        return False
    return raw.endswith("Z") or "+" in raw[10:] or raw.count("-") >= 3


def _attach_google_zone(raw: str, zone_name: str | None) -> datetime:
    """Attach zone to Google dateTime; raises IndeterminateLocalTime on DST gaps/folds."""
    text = raw.replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc)
    iana = resolve_iana_zone(zone_name)
    if iana is None:
        # Naive without resolvable zone — UTC storage only; caller flags missing.
        return dt.replace(tzinfo=timezone.utc)
    return attach_naive_wall_clock(dt, iana)


def parse_google_event_times(
    event: dict[str, Any],
    *,
    calendar_timezone: str | None = None,
) -> ParsedEventBounds | None:
    """Parse Google start/end with source-zone provenance (T1-B).

    Date-only: convert exclusive-end civil days in the source zone (event
    ``timeZone`` or owning calendar zone). Never uses owner settings timezone.
    Missing / unsupported / indeterminate zone → ``source_zone_missing=True``.
    """
    start = event.get("start") or {}
    end = event.get("end") or {}
    if "dateTime" in start and "dateTime" in end:
        start_raw = str(start["dateTime"])
        end_raw = str(end["dateTime"])
        start_zone = start.get("timeZone")
        end_zone = end.get("timeZone")
        has_offsets = _google_datetime_has_offset(start_raw) and _google_datetime_has_offset(
            end_raw
        )
        zone, indeterminate = pick_consistent_zone(
            start_zone, end_zone, calendar_timezone if not has_offsets else None
        )
        if has_offsets:
            start_dt = _ensure_aware(
                datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
            )
            end_dt = _ensure_aware(datetime.fromisoformat(end_raw.replace("Z", "+00:00")))
            return ParsedEventBounds(
                start=start_dt,
                end=end_dt,
                is_all_day=False,
                source_timezone=zone,
                source_zone_missing=False,
            )
        if indeterminate or zone is None:
            # Cannot attach a trusted zone to naive timed values.
            start_dt = _attach_google_zone(start_raw, None)
            end_dt = _attach_google_zone(end_raw, None)
            return ParsedEventBounds(
                start=start_dt,
                end=end_dt,
                is_all_day=False,
                source_timezone=None,
                source_zone_missing=True,
            )
        try:
            start_dt = _attach_google_zone(start_raw, zone)
            end_dt = _attach_google_zone(end_raw, zone)
        except IndeterminateLocalTime:
            start_dt = _attach_google_zone(start_raw, None)
            end_dt = _attach_google_zone(end_raw, None)
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
            source_timezone=zone,
            source_zone_missing=False,
        )

    if "date" in start and "date" in end:
        start_day = parse_civil_date(start["date"])
        end_day = parse_civil_date(end["date"])
        zone, indeterminate = pick_consistent_zone(
            start.get("timeZone"),
            end.get("timeZone"),
            calendar_timezone,
        )
        if indeterminate or zone is None:
            placeholder = utc_midnight_placeholder(start_day, end_day)
            return ParsedEventBounds(
                start=placeholder[0],
                end=placeholder[1],
                is_all_day=True,
                source_timezone=None,
                source_zone_missing=True,
            )
        try:
            start_dt, end_dt = all_day_bounds_utc(start_day, end_day, zone)
        except ValueError:
            placeholder = utc_midnight_placeholder(start_day, end_day)
            return ParsedEventBounds(
                start=placeholder[0],
                end=placeholder[1],
                is_all_day=True,
                source_timezone=None,
                source_zone_missing=True,
            )
        return ParsedEventBounds(
            start=start_dt,
            end=end_dt,
            is_all_day=True,
            source_timezone=zone,
            source_zone_missing=False,
        )
    return None


def google_source_zone_missing(
    event: dict[str, Any],
    *,
    calendar_timezone: str | None = None,
) -> bool:
    """True when Google payload lacks attributable / resolvable source zone."""
    parsed = parse_google_event_times(event, calendar_timezone=calendar_timezone)
    if parsed is None:
        return True
    return parsed.source_zone_missing


def _paginate_events(
    access_token: str,
    url: str,
    *,
    params: dict[str, str],
) -> tuple[list[dict[str, Any]], str | None, int]:
    global _pull_pagination_complete
    items: list[dict[str, Any]] = []
    page_token: str | None = None
    next_sync_token: str | None = None
    page_count = 0
    with httpx.Client(timeout=60.0) as client:
        while True:
            page_count += 1
            query = dict(params)
            if page_token:
                query["pageToken"] = page_token
            response = client.get(
                url,
                params=query,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if response.status_code == 410:
                raise GoogleSyncTokenExpired()
            if response.status_code >= 400:
                raise ApiError(
                    502,
                    "Google Calendar events list failed",
                    "GOOGLE_EVENTS_LIST",
                    body=response.text[:500],
                )
            payload = response.json()
            items.extend(payload.get("items") or [])
            page_token = payload.get("nextPageToken")
            if payload.get("nextSyncToken"):
                next_sync_token = payload["nextSyncToken"]
            if not page_token:
                _pull_pagination_complete = True
                break
            if pagination_max_pages is not None and page_count >= pagination_max_pages:
                # Prefix only. Drop any token so a partial chain cannot advance the cursor.
                _pull_pagination_complete = False
                return items, None, page_count
    return items, next_sync_token, page_count


def list_google_calendars(access_token: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    page_token: str | None = None
    with httpx.Client(timeout=30.0) as client:
        while True:
            params: dict[str, str] = {"maxResults": "250"}
            if page_token:
                params["pageToken"] = page_token
            response = client.get(
                GOOGLE_CALENDAR_LIST_URL,
                params=params,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if response.status_code >= 400:
                raise ApiError(
                    502,
                    "Google Calendar list failed",
                    "GOOGLE_CALENDAR_LIST",
                    body=response.text[:500],
                )
            payload = response.json()
            items.extend(payload.get("items") or [])
            page_token = payload.get("nextPageToken")
            if not page_token:
                break
    return items


def list_calendar_events(
    access_token: str,
    calendar_id: str,
    *,
    time_min: datetime,
    time_max: datetime,
) -> tuple[list[dict[str, Any]], str | None, int]:
    params = {
        "timeMin": _iso_z(time_min),
        "timeMax": _iso_z(time_max),
        "singleEvents": "true",
        "showDeleted": "true",
        "orderBy": "startTime",
        "maxResults": "2500",
    }
    return _paginate_events(access_token, _calendar_events_base(calendar_id), params=params)


def list_calendar_events_incremental(
    access_token: str,
    calendar_id: str,
    sync_token: str,
) -> tuple[list[dict[str, Any]], str | None, int]:
    params = {"syncToken": sync_token, "singleEvents": "true"}
    return _paginate_events(access_token, _calendar_events_base(calendar_id), params=params)


def _event_time_body(start: datetime, end: datetime) -> dict[str, Any]:
    return {
        "start": {"dateTime": _iso_z(start), "timeZone": "UTC"},
        "end": {"dateTime": _iso_z(end), "timeZone": "UTC"},
    }


def create_google_event(
    access_token: str,
    calendar_id: str,
    *,
    title: str,
    start: datetime,
    end: datetime,
) -> dict[str, Any]:
    body = {"summary": title, **_event_time_body(start, end)}
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            _calendar_events_base(calendar_id),
            json=body,
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if response.status_code >= 400:
        raise ApiError(
            502,
            "Google Calendar event create failed",
            "GOOGLE_EVENT_CREATE",
            body=response.text[:500],
        )
    return response.json()


def patch_google_event(
    access_token: str,
    calendar_id: str,
    event_id: str,
    *,
    title: str,
    start: datetime,
    end: datetime,
) -> dict[str, Any]:
    body = {"summary": title, **_event_time_body(start, end)}
    event_path = f"{_calendar_events_base(calendar_id)}/{quote(event_id, safe='')}"
    with httpx.Client(timeout=30.0) as client:
        response = client.patch(
            event_path,
            json=body,
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if response.status_code >= 400:
        raise ApiError(
            502,
            "Google Calendar event patch failed",
            "GOOGLE_EVENT_PATCH",
            body=response.text[:500],
        )
    return response.json()


def delete_google_event(access_token: str, calendar_id: str, event_id: str) -> None:
    event_path = f"{_calendar_events_base(calendar_id)}/{quote(event_id, safe='')}"
    with httpx.Client(timeout=30.0) as client:
        response = client.delete(
            event_path,
            headers={"Authorization": f"Bearer {access_token}"},
        )
    # 404 and 410 both mean the event is already gone (Google uses 410 after delete).
    if response.status_code >= 400 and response.status_code not in (404, 410):
        raise ApiError(
            502,
            "Google Calendar event delete failed",
            "GOOGLE_EVENT_DELETE",
            body=response.text[:500],
        )


def ensure_primary_subscription(db: Session, account: CalendarAccount) -> CalendarSubscription:
    from app.config import get_settings
    from app.services.calendar_alias_canonicalize import (
        canonicalize_calendar_account,
        fetch_account_identity_evidence,
        lock_calendar_account_for_identity,
    )

    settings = get_settings()
    now = datetime.now(timezone.utc)
    lock_calendar_account_for_identity(db, account.id)
    sub = (
        db.query(CalendarSubscription)
        .filter(
            CalendarSubscription.calendar_account_id == account.id,
            CalendarSubscription.external_calendar_id == "primary",
        )
        .one_or_none()
    )
    if sub is None:
        sub = CalendarSubscription(
            owner_id=account.owner_id,
            calendar_account_id=account.id,
            external_calendar_id="primary",
            summary="Primary",
            role=CalendarSubscriptionRole.primary,
            is_enabled=True,
        )
        db.add(sub)
    else:
        sub.role = CalendarSubscriptionRole.primary
        sub.is_enabled = True
    db.flush()
    try:
        access = get_valid_access_token(db, settings=settings, account=account)
        evidence = fetch_account_identity_evidence(
            db, account, settings=settings, access_token=access
        )
    except ApiError:
        evidence = None
    canonicalize_calendar_account(db, account, evidence=evidence, now=now)
    db.flush()
    refreshed = (
        db.query(CalendarSubscription)
        .filter(
            CalendarSubscription.calendar_account_id == account.id,
            CalendarSubscription.role == CalendarSubscriptionRole.primary,
            CalendarSubscription.is_enabled.is_(True),
        )
        .order_by(CalendarSubscription.created_at)
        .first()
    )
    return refreshed or sub


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
        raise ApiError(502, "Google did not return an access token", "GOOGLE_NO_ACCESS_TOKEN")
    expires_in = int(token_payload.get("expires_in") or 3600)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=max(60, expires_in - 60))

    account = existing
    if account is None:
        account = (
            db.query(CalendarAccount)
            .filter(
                CalendarAccount.owner_id == owner_id,
                CalendarAccount.provider == CalendarProvider.google,
                CalendarAccount.account_email == account_email,
            )
            .one_or_none()
        )
    if account is None:
        account = CalendarAccount(
            owner_id=owner_id,
            provider=CalendarProvider.google,
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
            "Google did not return a refresh token; disconnect and reconnect with consent",
            "GOOGLE_NO_REFRESH_TOKEN",
        )
    account.token_expires_at = expires_at
    account.is_enabled = True
    db.flush()
    ensure_primary_subscription(db, account)
    return account


def get_valid_access_token(
    db: Session,
    *,
    settings: Settings,
    account: CalendarAccount,
) -> str:
    if not account.access_token_enc:
        raise ApiError(400, "Calendar account has no access token", "GOOGLE_ACCOUNT_NO_TOKEN")
    now = datetime.now(timezone.utc)
    expires = account.token_expires_at
    if expires is not None and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires and expires > now + timedelta(seconds=30):
        return decrypt_token(settings, account.access_token_enc)

    if not account.refresh_token_enc:
        raise ApiError(401, "Calendar account needs re-authorization", "GOOGLE_REAUTH_REQUIRED")

    config = load_google_oauth_config(settings)
    refresh = decrypt_token(settings, account.refresh_token_enc)
    payload = refresh_access_token(config, refresh)
    access = payload.get("access_token")
    if not access:
        raise ApiError(502, "Google refresh did not return access token", "GOOGLE_NO_ACCESS_TOKEN")
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
    for_update: bool = False,
) -> ExternalCalendarEvent | None:
    query = (
        db.query(ExternalCalendarEvent)
        .filter(
            ExternalCalendarEvent.provider == CalendarProvider.google,
            ExternalCalendarEvent.external_event_id == external_id,
            ExternalCalendarEvent.owner_id == owner_id,
        )
    )
    if for_update:
        query = query.with_for_update().populate_existing()
    return query.one_or_none()


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
    # Owning-calendar zone when known; never owner settings TZ.
    times = parse_google_event_times(
        event, calendar_timezone=subscription.provider_timezone
    )
    if times is None:
        return False
    if times.end <= times.start:
        return False

    from app.services.free_busy_series_policy import (
        SERIES_IDENTITY_VERIFIED_NON_RECURRING,
        SERIES_IDENTITY_VERIFIED_SERIES,
        UpsertPostLockIdentityDriftError,
        acquire_identity_advisory_locks,
        apply_post_transparency_policy_effects,
        google_upsert_identity_keys_for_lock,
        identity_key_from_row,
    )

    recurring = event.get("recurringEventId")
    new_series = str(recurring) if recurring else None

    row = _find_external_event(db, owner_id=account.owner_id, external_id=external_id)
    if row is not None and row.pending_deletion:
        return False

    old_cal = row.calendar_id if row is not None else None
    old_series = row.provider_series_id if row is not None else None
    identity_snapshot = identity_key_from_row(row) if row is not None else None

    lock_keys = google_upsert_identity_keys_for_lock(
        row=row,
        new_calendar_id=subscription.external_calendar_id,
        new_series_id=new_series,
        old_calendar_id=old_cal,
        old_series_id=old_series,
        owner_id=account.owner_id,
    )
    if lock_keys:
        acquire_identity_advisory_locks(db, lock_keys)
        row = _find_external_event(
            db,
            owner_id=account.owner_id,
            external_id=external_id,
            for_update=True,
        )
        if row is not None and identity_snapshot is not None:
            identity_locked = identity_key_from_row(row)
            if identity_locked != identity_snapshot:
                raise UpsertPostLockIdentityDriftError(
                    f"identity drift for {external_id}"
                )

    if row is None:
        row = ExternalCalendarEvent(
            owner_id=account.owner_id,
            calendar_account_id=account.id,
            provider=CalendarProvider.google,
            external_event_id=external_id,
            calendar_id=subscription.external_calendar_id,
            start_time=times.start,
            end_time=times.end,
        )
        db.add(row)
        db.flush()

    old_cal = old_cal if old_cal is not None else row.calendar_id
    old_series = old_series if old_series is not None else row.provider_series_id
    row.calendar_account_id = account.id
    row.title = (event.get("summary") or "Busy")[:500]
    row.start_time = times.start
    row.end_time = times.end
    row.is_all_day = times.is_all_day
    row.calendar_id = subscription.external_calendar_id
    row.last_synced_at = now
    row.source_zone_missing = times.source_zone_missing
    row.source_timezone = times.source_timezone
    # T1-A: Google transparency + provenance (append-only history on change).
    stored, provenance, _kind = resolve_google_transparency(
        event, complete_representation=True, field_projected=False
    )
    apply_transparency_update(
        row, stored=stored, provenance=provenance, sync_run_id=sync_run_id
    )
    # Calendar move, series id change, or series identity loss → pending (§3.4).
    if old_series and (
        old_series != new_series or old_cal != subscription.external_calendar_id
    ):
        row.free_busy_pending_exception = True
    row.provider_series_id = new_series
    if new_series:
        row.series_identity_state = SERIES_IDENTITY_VERIFIED_SERIES
        row.series_identity_incomplete_reason = None
    else:
        row.series_identity_state = SERIES_IDENTITY_VERIFIED_NON_RECURRING
        row.series_identity_incomplete_reason = None
    row.is_provider_cancelled = False
    apply_post_transparency_policy_effects(
        db,
        row,
        identity_keys=lock_keys,
        old_calendar_id=old_cal,
        old_series_id=old_series,
    )
    db.flush()
    return True


def _mark_provider_cancelled(
    db: Session,
    *,
    owner_id,
    external_id: str,
    now: datetime,
) -> None:
    row = _find_external_event(db, owner_id=owner_id, external_id=external_id)
    if row is None:
        return
    row.is_provider_cancelled = True
    row.last_synced_at = now


def _unpack_listed_events(
    result: tuple[Any, ...],
) -> tuple[list[dict[str, Any]], str | None, int]:
    """Accept 2-tuples from older test doubles and 3-tuples from the paginator."""
    if len(result) == 2:
        events, token = result
        return list(events or []), token, 1
    events, token, page_count = result
    return list(events or []), token, int(page_count)


def _pull_subscription_changes(
    db: Session,
    *,
    access: str,
    subscription: CalendarSubscription,
    time_min: datetime,
    time_max: datetime,
) -> tuple[list[dict[str, Any]], str | None, bool, int]:
    """Fetch provider events before the owner scheduling lock."""
    global _pull_pagination_complete
    from app.services.calendar_coverage import invalidate_subscription_coverage

    # Mocked list_* never enters _paginate_events; default is a complete drain.
    _pull_pagination_complete = True

    if subscription.sync_cursor:
        try:
            events, next_sync_token, page_count = _unpack_listed_events(
                list_calendar_events_incremental(
                    access,
                    subscription.external_calendar_id,
                    subscription.sync_cursor,
                )
            )
            return events, next_sync_token, False, page_count
        except GoogleSyncTokenExpired:
            invalidate_subscription_coverage(
                subscription,
                now=datetime.now(timezone.utc),
                cause="google_sync_token_expired",
                clear_sync_cursor=True,
            )
            db.flush()

    events, next_sync_token, page_count = _unpack_listed_events(
        list_calendar_events(
            access,
            subscription.external_calendar_id,
            time_min=time_min,
            time_max=time_max,
        )
    )
    return events, next_sync_token, True, page_count


def _apply_subscription_full(
    db: Session,
    *,
    account: CalendarAccount,
    subscription: CalendarSubscription,
    events: list[dict[str, Any]],
    next_sync_token: str | None,
    time_min: datetime,
    time_max: datetime,
    now: datetime,
    coverage_generation: int,
    page_count: int,
    pagination_complete: bool = True,
    suppressed_external_ids: set[str] | None = None,
) -> int:
    from app.services.calendar_coverage import (
        commit_subscription_coverage_success,
        record_subscription_refresh_failure,
    )

    suppressed = suppressed_external_ids or set()
    seen_external_ids: set[str] = set()
    cancelled_ids: set[str] = set()
    upserted = 0
    sync_run_id = f"google-full-{now.strftime('%Y%m%dT%H%M%SZ')}-{subscription.id.hex[:8]}"

    try:
        if not pagination_complete:
            raise ApiError(
                502,
                "Calendar event page chain was not fully drained",
                "CALENDAR_PAGINATION_INCOMPLETE",
            )
        for event in events:
            status = event.get("status")
            external_id = event.get("id")
            if not external_id or status == "cancelled":
                if external_id and status == "cancelled":
                    cancelled_ids.add(external_id)
                    pending = _find_external_event(
                        db, owner_id=account.owner_id, external_id=external_id
                    )
                    if pending is not None and pending.pending_deletion:
                        db.delete(pending)
                    else:
                        _mark_provider_cancelled(
                            db,
                            owner_id=account.owner_id,
                            external_id=external_id,
                            now=now,
                        )
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
                *ExternalCalendarEvent.immovable_busy_clause(),
                ExternalCalendarEvent.start_time < time_max,
                ExternalCalendarEvent.end_time > time_min,
            )
            .all()
        )
        for row in stale:
            # Cancelled payload rows are not "missing"; soft-cancel must survive reconcile.
            if row.external_event_id in seen_external_ids or row.external_event_id in cancelled_ids:
                continue
            db.delete(row)

        if next_sync_token:
            subscription.sync_cursor = next_sync_token
        commit_subscription_coverage_success(
            subscription,
            now=now,
            window_start=time_min,
            window_end=time_max,
            mode="full",
            pagination_complete=pagination_complete,
            page_count=page_count,
            item_count=len(events),
            show_deleted=True,
            single_events=True,
            sync_token=next_sync_token,
            generation=coverage_generation,
        )
        db.flush()
        return upserted
    except Exception:
        record_subscription_refresh_failure(
            subscription,
            now=now,
            cause="google_apply_full_failed",
        )
        db.flush()
        raise


def _apply_subscription_incremental(
    db: Session,
    *,
    account: CalendarAccount,
    subscription: CalendarSubscription,
    events: list[dict[str, Any]],
    next_sync_token: str | None,
    now: datetime,
    coverage_generation: int,
    page_count: int,
    window_start: datetime | None,
    window_end: datetime | None,
    show_deleted: bool | None,
    pagination_complete: bool = True,
    suppressed_external_ids: set[str] | None = None,
) -> int:
    from app.services.calendar_coverage import (
        commit_subscription_coverage_success,
        record_subscription_refresh_failure,
    )

    suppressed = suppressed_external_ids or set()
    upserted = 0
    sync_run_id = f"google-incr-{now.strftime('%Y%m%dT%H%M%SZ')}-{subscription.id.hex[:8]}"

    try:
        if not pagination_complete:
            raise ApiError(
                502,
                "Calendar event page chain was not fully drained",
                "CALENDAR_PAGINATION_INCOMPLETE",
            )
        if window_start is None or window_end is None:
            raise RuntimeError("incremental apply requires prior full coverage window")
        for event in events:
            status = event.get("status")
            external_id = event.get("id")
            if not external_id:
                continue
            if status == "cancelled":
                pending = _find_external_event(
                    db, owner_id=account.owner_id, external_id=external_id
                )
                if pending is not None and pending.pending_deletion:
                    db.delete(pending)
                else:
                    _mark_provider_cancelled(
                        db,
                        owner_id=account.owner_id,
                        external_id=external_id,
                        now=now,
                    )
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

        if next_sync_token:
            subscription.sync_cursor = next_sync_token
        commit_subscription_coverage_success(
            subscription,
            now=now,
            window_start=window_start,
            window_end=window_end,
            mode="incremental",
            pagination_complete=pagination_complete,
            page_count=page_count,
            item_count=len(events),
            show_deleted=show_deleted,
            single_events=True,
            sync_token=next_sync_token,
            generation=coverage_generation,
        )
        db.flush()
        return upserted
    except Exception:
        record_subscription_refresh_failure(
            subscription,
            now=now,
            cause="google_apply_incremental_failed",
        )
        db.flush()
        raise


def sync_account_events(
    db: Session,
    *,
    settings: Settings,
    account: CalendarAccount,
    time_min: datetime,
    time_max: datetime,
) -> int:
    from app.models import UserSettings
    from app.services.calendar_coverage import (
        begin_subscription_refresh,
        coverage_window_wider_than,
        invalidate_subscription_coverage,
        subscription_refresh_lock,
    )
    from app.services.mirror_tombstone import retry_pending_deletions
    from app.scheduler.horizon import compute_horizon
    from app.services.scheduling_revision import (
        immovable_busy_signature,
        increment_scheduling_revision_if_busy_or_trust_changed,
        lock_owner_scheduling,
        trust_blocking_signature,
    )

    now = datetime.now(timezone.utc)
    user_settings = (
        db.query(UserSettings).filter(UserSettings.owner_id == account.owner_id).one_or_none()
    )

    try:
        access = get_valid_access_token(db, settings=settings, account=account)
    except (ApiError, httpx.TransportError):
        subscriptions = (
            db.query(CalendarSubscription)
            .filter(
                CalendarSubscription.calendar_account_id == account.id,
                CalendarSubscription.is_enabled.is_(True),
            )
            .all()
        )
        _commit_pre_pull_refresh_failure(
            db,
            subscriptions,
            now=now,
            cause="calendar_refresh_failed",
        )
        raise

    from app.services.calendar_alias_canonicalize import (
        account_should_bootstrap_primary_on_sync,
        prepare_subscriptions_for_sync,
    )

    subscriptions = prepare_subscriptions_for_sync(
        db,
        account,
        settings=settings,
        access_token=access,
        now=now,
    )
    if account_should_bootstrap_primary_on_sync(
        db, account.id, eligible=subscriptions
    ):
        ensure_primary_subscription(db, account)
        subscriptions = prepare_subscriptions_for_sync(
            db,
            account,
            settings=settings,
            access_token=access,
            now=now,
        )

    scheduling_settings = lock_owner_scheduling(db, account.owner_id)
    # One sync_now + compute_horizon pair for before/after trust compare (Boundary B).
    sync_now = datetime.now(timezone.utc)
    horizon_start, horizon_end = compute_horizon(scheduling_settings, sync_now)
    before_busy = immovable_busy_signature(db, account.owner_id)
    before_trust = trust_blocking_signature(
        db,
        account.owner_id,
        horizon_start=horizon_start,
        horizon_end=horizon_end,
    )
    suppressed = retry_pending_deletions(
        db,
        account=account,
        access=access,
        delete_event=delete_google_event,
    )
    upserted = 0
    for subscription in subscriptions:
        with subscription_refresh_lock(subscription.id):
            refresh_scope = db.begin_nested()
            try:
                if user_settings is not None and coverage_window_wider_than(
                    subscription,
                    required_start=time_min,
                    required_end=time_max,
                ):
                    invalidate_subscription_coverage(
                        subscription,
                        now=now,
                        cause="coverage_horizon_widened",
                        clear_sync_cursor=True,
                    )
                    db.flush()
                events, next_cursor, is_full, page_count = _pull_subscription_changes(
                    db,
                    access=access,
                    subscription=subscription,
                    time_min=time_min,
                    time_max=time_max,
                )
                if not _pull_pagination_complete:
                    begin_subscription_refresh(subscription, now=now)
                    if refresh_scope.is_active:
                        refresh_scope.rollback()
                    _commit_refresh_failure(
                        db,
                        subscription,
                        now=now,
                        cause="calendar_pagination_incomplete",
                    )
                    incomplete = ApiError(
                        502,
                        "Calendar event page chain was not fully drained",
                        "CALENDAR_PAGINATION_INCOMPLETE",
                    )
                    _mark_failure_committed(incomplete)
                    raise incomplete
                prior_start = subscription.coverage_window_start
                prior_end = subscription.coverage_window_end
                prior_show_deleted = subscription.coverage_show_deleted
                generation = begin_subscription_refresh(subscription, now=now)
                db.flush()
                nested = db.begin_nested()
                try:
                    if is_full:
                        upserted += _apply_subscription_full(
                            db,
                            account=account,
                            subscription=subscription,
                            events=events,
                            next_sync_token=next_cursor,
                            time_min=time_min,
                            time_max=time_max,
                            now=now,
                            coverage_generation=generation,
                            page_count=page_count,
                            pagination_complete=True,
                            suppressed_external_ids=suppressed,
                        )
                    else:
                        upserted += _apply_subscription_incremental(
                            db,
                            account=account,
                            subscription=subscription,
                            events=events,
                            next_sync_token=next_cursor,
                            now=now,
                            coverage_generation=generation,
                            page_count=page_count,
                            window_start=prior_start,
                            window_end=prior_end,
                            show_deleted=prior_show_deleted,
                            pagination_complete=True,
                            suppressed_external_ids=suppressed,
                        )
                    nested.commit()
                except Exception as exc:
                    if nested.is_active:
                        nested.rollback()
                    if refresh_scope.is_active:
                        refresh_scope.rollback()
                    cause = (
                        "google_apply_full_failed"
                        if is_full
                        else "google_apply_incremental_failed"
                    )
                    _commit_refresh_failure(db, subscription, now=now, cause=cause)
                    _mark_failure_committed(exc)
                    raise
                if refresh_scope.is_active:
                    refresh_scope.commit()
            except Exception as exc:
                if not _failure_committed(exc):
                    if refresh_scope.is_active:
                        refresh_scope.rollback()
                    _commit_refresh_failure(
                        db,
                        subscription,
                        now=now,
                        cause="google_subscription_refresh_failed",
                    )
                    _mark_failure_committed(exc)
                raise

    account.last_synced_at = now
    db.flush()
    increment_scheduling_revision_if_busy_or_trust_changed(
        db,
        scheduling_settings,
        account.owner_id,
        before_busy=before_busy,
        before_trust=before_trust,
        horizon_start=horizon_start,
        horizon_end=horizon_end,
    )
    return upserted


def _mirror_account_and_calendar(
    db: Session,
    owner_id,
) -> tuple[CalendarAccount | None, str]:
    account = (
        db.query(CalendarAccount)
        .filter(
            CalendarAccount.owner_id == owner_id,
            CalendarAccount.provider == CalendarProvider.google,
            CalendarAccount.is_enabled.is_(True),
            CalendarAccount.mirror_blocks.is_(True),
        )
        .first()
    )
    if account is None:
        return None, "primary"

    primary_sub = (
        db.query(CalendarSubscription)
        .filter(
            CalendarSubscription.calendar_account_id == account.id,
            CalendarSubscription.role == CalendarSubscriptionRole.primary,
            CalendarSubscription.is_enabled.is_(True),
        )
        .first()
    )
    calendar_id = primary_sub.external_calendar_id if primary_sub else "primary"
    return account, calendar_id


def push_scheduled_block(db: Session, settings: Settings, block: ScheduledBlock) -> None:
    account, calendar_id = _mirror_account_and_calendar(db, block.owner_id)
    if account is None:
        return

    task = db.get(Task, block.task_id)
    title = (task.title if task else "Scheduled block")[:500]
    try:
        access = get_valid_access_token(db, settings=settings, account=account)
    except ApiError as exc:
        # Account row can exist while Compose/test env lacks OAuth client config.
        if exc.content.get("code") == "GOOGLE_OAUTH_NOT_CONFIGURED":
            return
        raise
    existing = (
        db.query(ExternalCalendarEvent)
        .filter(
            ExternalCalendarEvent.scheduled_block_id == block.id,
            ExternalCalendarEvent.provider == CalendarProvider.google,
        )
        .one_or_none()
    )
    now = datetime.now(timezone.utc)

    is_all_day = False
    if existing:
        event = patch_google_event(
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
        apply_export_baseline_after_mirror_push(
            existing,
            source=GOOGLE_MIRROR_PUSH_SOURCE,
            export_calendar_id=calendar_id,
            title=title,
            start=block.start_time,
            end=block.end_time,
            is_all_day=is_all_day,
            provider=CalendarProvider.google,
            api_response=event,
            exported_at=now,
        )
    else:
        event = create_google_event(
            access,
            calendar_id,
            title=title,
            start=block.start_time,
            end=block.end_time,
        )
        external_id = event.get("id")
        if not external_id:
            raise ApiError(502, "Google did not return event id", "GOOGLE_EVENT_NO_ID")
        row = ExternalCalendarEvent(
            owner_id=block.owner_id,
            calendar_account_id=account.id,
            scheduled_block_id=block.id,
            task_id=block.task_id,
            provider=CalendarProvider.google,
            external_event_id=external_id,
            calendar_id=calendar_id,
            title=title,
            start_time=block.start_time,
            end_time=block.end_time,
            is_all_day=is_all_day,
            last_synced_at=now,
        )
        db.add(row)
        apply_export_baseline_after_mirror_push(
            row,
            source=GOOGLE_MIRROR_PUSH_SOURCE,
            export_calendar_id=calendar_id,
            title=title,
            start=block.start_time,
            end=block.end_time,
            is_all_day=is_all_day,
            provider=CalendarProvider.google,
            api_response=event,
            exported_at=now,
        )

    db.flush()


def delete_mirrored_block(db: Session, settings: Settings, block: ScheduledBlock) -> None:
    existing = (
        db.query(ExternalCalendarEvent)
        .filter(
            ExternalCalendarEvent.scheduled_block_id == block.id,
            ExternalCalendarEvent.provider == CalendarProvider.google,
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
    access = get_valid_access_token(db, settings=settings, account=account)
    delete_google_event(access, calendar_id, existing.external_event_id)
    db.delete(existing)
    db.flush()
