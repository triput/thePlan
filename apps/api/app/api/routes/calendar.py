"""Google Calendar OAuth, account management, and busy-event sync (W2a)."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.errors import ApiError
from app.config import get_settings
from app.db import get_db
from app.models import CalendarAccount, CalendarSubscription, ExternalCalendarEvent, User
from app.models.enums import CalendarProvider, CalendarSubscriptionRole
from app.schemas import (
    CalendarAccountOut,
    CalendarAccountUpdate,
    CalendarSubscriptionOut,
    CalendarSubscriptionsPut,
    CalendarSyncResult,
    ExternalCalendarEventOut,
    GoogleCalendarListItem,
    PaginatedResponse,
)
from app.services.google_calendar import (
    build_authorize_url,
    exchange_code_for_tokens,
    fetch_google_email,
    get_valid_access_token,
    list_google_calendars,
    load_google_oauth_config,
    sync_account_events,
    upsert_account_tokens,
)

router = APIRouter(prefix="/calendar", tags=["calendar"])

_OAUTH_STATE_KEY = "google_oauth_state"


def _account_out(account: CalendarAccount) -> CalendarAccountOut:
    return CalendarAccountOut(
        id=account.id,
        provider=account.provider.value if hasattr(account.provider, "value") else str(account.provider),
        account_email=account.account_email,
        is_enabled=account.is_enabled,
        mirror_blocks_to_google=account.mirror_blocks_to_google,
        sync_cursor=account.sync_cursor,
        last_synced_at=account.last_synced_at,
        token_expires_at=account.token_expires_at,
        created_at=account.created_at,
        updated_at=account.updated_at,
    )


def _subscription_out(sub: CalendarSubscription) -> CalendarSubscriptionOut:
    return CalendarSubscriptionOut(
        id=sub.id,
        calendar_account_id=sub.calendar_account_id,
        external_calendar_id=sub.external_calendar_id,
        summary=sub.summary,
        role=sub.role,
        is_enabled=sub.is_enabled,
        sync_cursor=sub.sync_cursor,
    )


def _event_out(event: ExternalCalendarEvent) -> ExternalCalendarEventOut:
    return ExternalCalendarEventOut(
        id=event.id,
        calendar_account_id=event.calendar_account_id,
        provider=event.provider.value if hasattr(event.provider, "value") else str(event.provider),
        external_event_id=event.external_event_id,
        calendar_id=event.calendar_id,
        title=event.title,
        start_time=event.start_time,
        end_time=event.end_time,
        is_all_day=event.is_all_day,
        last_synced_at=event.last_synced_at,
    )


def _owned_account(db: Session, account_id: UUID, user: User) -> CalendarAccount:
    account = db.get(CalendarAccount, account_id)
    if account is None or account.owner_id != user.id:
        raise ApiError(404, "Calendar account not found", "CALENDAR_ACCOUNT_NOT_FOUND")
    return account


@router.get("/accounts", response_model=PaginatedResponse)
def list_calendar_accounts(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PaginatedResponse:
    items = (
        db.query(CalendarAccount)
        .filter(CalendarAccount.owner_id == user.id)
        .order_by(CalendarAccount.created_at)
        .all()
    )
    return PaginatedResponse(
        items=[_account_out(item) for item in items],
        total=len(items),
        limit=len(items) or 50,
        offset=0,
    )


@router.patch("/accounts/{account_id}", response_model=CalendarAccountOut)
def update_calendar_account(
    account_id: UUID,
    body: CalendarAccountUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CalendarAccountOut:
    account = _owned_account(db, account_id, user)
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(account, field, value)
    db.commit()
    db.refresh(account)
    return _account_out(account)


@router.get("/calendars", response_model=PaginatedResponse)
def list_google_calendars_for_account(
    account_id: UUID = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PaginatedResponse:
    account = _owned_account(db, account_id, user)
    if account.provider != CalendarProvider.google:
        raise ApiError(400, "Account is not a Google calendar", "CALENDAR_NOT_GOOGLE")
    settings = get_settings()
    access = get_valid_access_token(db, settings=settings, account=account)
    raw = list_google_calendars(access)
    items = [
        GoogleCalendarListItem(
            id=str(entry.get("id") or ""),
            summary=entry.get("summary"),
            primary=bool(entry.get("primary")),
            access_role=entry.get("accessRole"),
        )
        for entry in raw
        if entry.get("id")
    ]
    return PaginatedResponse(
        items=items,
        total=len(items),
        limit=len(items) or 50,
        offset=0,
    )


@router.get("/accounts/{account_id}/subscriptions", response_model=PaginatedResponse)
def list_calendar_subscriptions(
    account_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PaginatedResponse:
    account = _owned_account(db, account_id, user)
    items = (
        db.query(CalendarSubscription)
        .filter(CalendarSubscription.calendar_account_id == account.id)
        .order_by(CalendarSubscription.created_at)
        .all()
    )
    return PaginatedResponse(
        items=[_subscription_out(item) for item in items],
        total=len(items),
        limit=len(items) or 50,
        offset=0,
    )


@router.put("/accounts/{account_id}/subscriptions", response_model=PaginatedResponse)
def put_calendar_subscriptions(
    account_id: UUID,
    body: CalendarSubscriptionsPut,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PaginatedResponse:
    account = _owned_account(db, account_id, user)
    items = body.items

    primary_candidates = [item for item in items if item.role == CalendarSubscriptionRole.primary]
    if len(primary_candidates) != 1:
        raise ApiError(
            422,
            "Exactly one primary calendar subscription is required",
            "CALENDAR_PRIMARY_REQUIRED",
        )

    requested_ids = {item.external_calendar_id for item in items}
    existing = (
        db.query(CalendarSubscription)
        .filter(CalendarSubscription.calendar_account_id == account.id)
        .all()
    )
    existing_by_id = {sub.external_calendar_id: sub for sub in existing}

    for item in items:
        sub = existing_by_id.get(item.external_calendar_id)
        is_new = sub is None
        if is_new:
            sub = CalendarSubscription(
                owner_id=user.id,
                calendar_account_id=account.id,
                external_calendar_id=item.external_calendar_id,
            )
            db.add(sub)
            existing_by_id[item.external_calendar_id] = sub
        sub.summary = item.summary
        sub.role = item.role
        sub.is_enabled = item.is_enabled
        if is_new:
            sub.sync_cursor = None

    for sub in existing:
        if sub.external_calendar_id not in requested_ids:
            sub.is_enabled = False

    db.commit()
    updated = (
        db.query(CalendarSubscription)
        .filter(CalendarSubscription.calendar_account_id == account.id)
        .order_by(CalendarSubscription.created_at)
        .all()
    )
    return PaginatedResponse(
        items=[_subscription_out(item) for item in updated],
        total=len(updated),
        limit=len(updated) or 50,
        offset=0,
    )


@router.get("/oauth/google/start")
def google_oauth_start(
    request: Request,
    user: User = Depends(get_current_user),
) -> RedirectResponse:
    _ = user
    settings = get_settings()
    config = load_google_oauth_config(settings)
    if not (settings.token_encryption_key or "").strip():
        raise ApiError(503, "TOKEN_ENCRYPTION_KEY is not configured", "CALENDAR_CRYPTO_NOT_CONFIGURED")
    state = secrets.token_urlsafe(24)
    request.session[_OAUTH_STATE_KEY] = state
    return RedirectResponse(url=build_authorize_url(config, state), status_code=status.HTTP_302_FOUND)


@router.get("/oauth/google/callback")
def google_oauth_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RedirectResponse:
    settings = get_settings()
    frontend = settings.frontend_origin.rstrip("/")
    if error:
        return RedirectResponse(url=f"{frontend}/?gcal=error&reason={error}", status_code=302)
    expected = request.session.pop(_OAUTH_STATE_KEY, None)
    if not code or not state or not expected or state != expected:
        return RedirectResponse(url=f"{frontend}/?gcal=error&reason=state", status_code=302)

    config = load_google_oauth_config(settings)
    tokens = exchange_code_for_tokens(config, code)
    access = tokens.get("access_token")
    if not access:
        return RedirectResponse(url=f"{frontend}/?gcal=error&reason=token", status_code=302)
    email = fetch_google_email(access)
    account = upsert_account_tokens(
        db,
        settings=settings,
        owner_id=user.id,
        account_email=email,
        token_payload=tokens,
    )
    now = datetime.now(timezone.utc)
    sync_account_events(
        db,
        settings=settings,
        account=account,
        time_min=now - timedelta(days=7),
        time_max=now + timedelta(days=21),
    )
    db.commit()
    return RedirectResponse(url=f"{frontend}/?gcal=connected", status_code=302)


@router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def disconnect_calendar_account(
    account_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    account = _owned_account(db, account_id, user)
    db.query(ExternalCalendarEvent).filter(
        ExternalCalendarEvent.calendar_account_id == account.id
    ).delete(synchronize_session=False)
    db.delete(account)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/accounts/{account_id}/sync", response_model=CalendarSyncResult)
def sync_calendar_account(
    account_id: UUID,
    start: datetime | None = None,
    end: datetime | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CalendarSyncResult:
    account = _owned_account(db, account_id, user)
    settings = get_settings()
    now = datetime.now(timezone.utc)
    time_min = start or (now - timedelta(days=7))
    time_max = end or (now + timedelta(days=21))
    if time_max <= time_min:
        raise ApiError(422, "end must be after start", "INVALID_TIME_RANGE")
    upserted = sync_account_events(
        db,
        settings=settings,
        account=account,
        time_min=time_min,
        time_max=time_max,
    )
    db.commit()
    return CalendarSyncResult(account_id=account.id, upserted=upserted)


@router.get("/events", response_model=PaginatedResponse)
def list_external_events(
    start: datetime = Query(...),
    end: datetime = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PaginatedResponse:
    if end <= start:
        raise ApiError(422, "end must be after start", "INVALID_TIME_RANGE")
    items = (
        db.query(ExternalCalendarEvent)
        .filter(
            ExternalCalendarEvent.owner_id == user.id,
            ExternalCalendarEvent.scheduled_block_id.is_(None),
            ExternalCalendarEvent.start_time < end,
            ExternalCalendarEvent.end_time > start,
        )
        .order_by(ExternalCalendarEvent.start_time)
        .limit(500)
        .all()
    )
    return PaginatedResponse(
        items=[_event_out(item) for item in items],
        total=len(items),
        limit=500,
        offset=0,
    )
