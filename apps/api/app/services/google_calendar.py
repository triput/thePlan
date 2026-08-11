"""Google Calendar OAuth + events sync helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.config import Settings, get_settings
from app.models import CalendarAccount, ExternalCalendarEvent
from app.models.enums import CalendarProvider
from app.services.token_crypto import decrypt_token, encrypt_token

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
GOOGLE_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"


@dataclass(frozen=True)
class GoogleOAuthConfig:
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: str


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


def parse_google_event_times(event: dict[str, Any]) -> tuple[datetime, datetime, bool] | None:
    start = event.get("start") or {}
    end = event.get("end") or {}
    if "dateTime" in start and "dateTime" in end:
        start_dt = datetime.fromisoformat(start["dateTime"].replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end["dateTime"].replace("Z", "+00:00"))
        return _ensure_aware(start_dt), _ensure_aware(end_dt), False
    if "date" in start and "date" in end:
        start_dt = datetime.fromisoformat(start["date"]).replace(tzinfo=timezone.utc)
        # Google end date is exclusive for all-day events
        end_exclusive = datetime.fromisoformat(end["date"]).replace(tzinfo=timezone.utc)
        end_dt = end_exclusive
        return start_dt, end_dt, True
    return None


def list_primary_events(
    access_token: str,
    *,
    time_min: datetime,
    time_max: datetime,
) -> list[dict[str, Any]]:
    params = {
        "timeMin": _ensure_aware(time_min).astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "timeMax": _ensure_aware(time_max).astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "singleEvents": "true",
        "orderBy": "startTime",
        "maxResults": "2500",
    }
    items: list[dict[str, Any]] = []
    page_token: str | None = None
    with httpx.Client(timeout=60.0) as client:
        while True:
            query = dict(params)
            if page_token:
                query["pageToken"] = page_token
            response = client.get(
                GOOGLE_EVENTS_URL,
                params=query,
                headers={"Authorization": f"Bearer {access_token}"},
            )
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
            if not page_token:
                break
    return items


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


def sync_account_events(
    db: Session,
    *,
    settings: Settings,
    account: CalendarAccount,
    time_min: datetime,
    time_max: datetime,
) -> int:
    access = get_valid_access_token(db, settings=settings, account=account)
    events = list_primary_events(access, time_min=time_min, time_max=time_max)
    now = datetime.now(timezone.utc)
    seen_external_ids: set[str] = set()
    upserted = 0

    for event in events:
        status = event.get("status")
        external_id = event.get("id")
        if not external_id or status == "cancelled":
            continue
        times = parse_google_event_times(event)
        if times is None:
            continue
        start_dt, end_dt, is_all_day = times
        if end_dt <= start_dt:
            continue
        seen_external_ids.add(external_id)
        row = (
            db.query(ExternalCalendarEvent)
            .filter(
                ExternalCalendarEvent.provider == CalendarProvider.google,
                ExternalCalendarEvent.external_event_id == external_id,
                ExternalCalendarEvent.owner_id == account.owner_id,
            )
            .one_or_none()
        )
        if row is None:
            row = ExternalCalendarEvent(
                owner_id=account.owner_id,
                calendar_account_id=account.id,
                provider=CalendarProvider.google,
                external_event_id=external_id,
                calendar_id="primary",
                start_time=start_dt,
                end_time=end_dt,
            )
            db.add(row)
        row.calendar_account_id = account.id
        row.title = (event.get("summary") or "Busy")[:500]
        row.start_time = start_dt
        row.end_time = end_dt
        row.is_all_day = is_all_day
        row.calendar_id = "primary"
        row.last_synced_at = now
        upserted += 1

    # Drop prior mirrors for this account that fall in the window but vanished upstream
    stale = (
        db.query(ExternalCalendarEvent)
        .filter(
            ExternalCalendarEvent.calendar_account_id == account.id,
            ExternalCalendarEvent.start_time < time_max,
            ExternalCalendarEvent.end_time > time_min,
        )
        .all()
    )
    for row in stale:
        if row.external_event_id not in seen_external_ids:
            db.delete(row)

    account.sync_cursor = now.isoformat()
    db.flush()
    return upserted
