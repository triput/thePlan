"""Pure checks for covering-refresh window, prepare diff, and V38 refusal.

DB contention (V1–V39) stays with the route tests. These lock the formulas
Justin calls: effective window, subset diff, and same-sub failure compare.
"""

from __future__ import annotations

import ast
import inspect
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.models import CalendarAccount, CalendarSubscription
from app.models.enums import CalendarProvider, CalendarSubscriptionRole
from app.services import covering_refresh_failure, covering_refresh_import
from app.services.covering_refresh_failure import (
    REFUSE_ACCOUNT_DISABLED,
    REFUSE_SUBSCRIPTION_DISABLED,
    REFUSE_SUBSCRIPTION_MISSING,
    REFUSE_SUPERSEDED_GENERATION,
    REFUSE_SUPERSEDED_IDENTITY,
    REFUSE_SUPERSEDED_SUCCESS,
    covering_failure_overwrite_refusal,
)
from app.services.covering_refresh_import import (
    _GUARD_FIELDS,
    classify_covering_prepare_mutation,
    import_covering_subscription_cache,
    subscription_guard_view,
)
from app.services.covering_refresh_locks import (
    CoveringAttemptSnapshot,
    snapshot_covering_attempt,
)
from app.services.covering_refresh_window import (
    WINDOW_CODE_INVALID,
    WINDOW_CODE_TOO_LARGE,
    CoveringWindowError,
    effective_covering_pull_window,
)

_FORBIDDEN_CALLS = frozenset(
    {
        "retry_pending_deletions",
        "delete_google_event",
        "delete_microsoft_event",
        "ensure_primary_subscription",
        "persist_subscription_refresh_failures_autonomous",
        "_apply_subscription_incremental",
        "sync_account_events",
    }
)


def _calls(source: str) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            found.add(func.id)
        elif isinstance(func, ast.Attribute):
            found.add(func.attr)
    return found


def _view(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {field: None for field in _GUARD_FIELDS}
    base.update(
        external_calendar_id="cal-1",
        role="informational",
        is_enabled=True,
        coverage_active_generation=4,
        coverage_success_generation=4,
    )
    base.update(overrides)
    return base


def _pair() -> tuple[CalendarAccount, CalendarSubscription, datetime]:
    owner_id = uuid4()
    account_id = uuid4()
    success_at = datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)
    account = CalendarAccount(
        id=account_id,
        owner_id=owner_id,
        provider=CalendarProvider.google,
        is_enabled=True,
        access_token_enc="enc",
    )
    subscription = CalendarSubscription(
        id=uuid4(),
        owner_id=owner_id,
        calendar_account_id=account_id,
        external_calendar_id="cal-1",
        role=CalendarSubscriptionRole.informational,
        is_enabled=True,
        coverage_active_generation=5,
        coverage_success_generation=5,
        coverage_success_at=success_at,
    )
    return account, subscription, success_at


def test_effective_window_equals_requested_and_never_widens() -> None:
    start = datetime(2026, 6, 1, 7, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
    end = start + timedelta(days=7)
    window = effective_covering_pull_window(start, end)
    assert window.effective_start == start.astimezone(timezone.utc)
    assert window.effective_end == end.astimezone(timezone.utc)
    assert window.widened is False
    assert window.reason == "none"
    assert tuple(window) == (
        window.effective_start,
        window.effective_end,
        False,
        "none",
    )
    params = inspect.signature(effective_covering_pull_window).parameters
    assert list(params) == ["requested_start", "requested_end"]


def test_naive_window_is_utc_and_inverted_window_is_invalid() -> None:
    start = datetime(2026, 1, 1, 0, 0, 0)
    end = datetime(2026, 1, 2, 0, 0, 0)
    window = effective_covering_pull_window(start, end)
    assert window.effective_start.tzinfo == timezone.utc
    assert window.effective_end - window.effective_start == timedelta(days=1)
    with pytest.raises(CoveringWindowError) as caught:
        effective_covering_pull_window(end, start)
    assert caught.value.code == WINDOW_CODE_INVALID


def test_window_cap_is_42_days() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    exact = effective_covering_pull_window(start, start + timedelta(days=42))
    assert exact.widened is False
    with pytest.raises(CoveringWindowError) as caught:
        effective_covering_pull_window(start, start + timedelta(days=42, microseconds=1))
    assert caught.value.code == WINDOW_CODE_TOO_LARGE
    with pytest.raises(CoveringWindowError) as bad_type:
        effective_covering_pull_window("2026-01-01", "2026-01-02")  # type: ignore[arg-type]
    assert bad_type.value.code == WINDOW_CODE_INVALID


def test_prepare_diff_allows_requested_identity_rewrite_only() -> None:
    requested = uuid4()
    other = uuid4()
    before = {requested: _view(), other: _view(external_calendar_id="other")}
    after = {
        requested: _view(
            external_calendar_id="canonical-id",
            sync_cursor=None,
            coverage_active_generation=5,
        ),
        other: _view(external_calendar_id="other"),
    }
    decision = classify_covering_prepare_mutation(
        requested_id=requested,
        before=before,
        after=after,
    )
    assert decision.allowed is True
    assert decision.effects == ("canonicalize_identity",)
    assert decision.eligibility_mutated is True
    assert decision.preflight_code is None


def test_prepare_diff_aborts_other_row_role_and_enablement() -> None:
    requested = uuid4()
    other = uuid4()
    before = {requested: _view(), other: _view(external_calendar_id="other")}
    other_touched = classify_covering_prepare_mutation(
        requested_id=requested,
        before=before,
        after={
            requested: _view(),
            other: _view(external_calendar_id="other", is_enabled=False),
        },
    )
    assert other_touched.allowed is False
    assert other_touched.preflight_code == "CALENDAR_PREPARE_SUBSET_UNSAFE"

    role = classify_covering_prepare_mutation(
        requested_id=requested,
        before={requested: _view()},
        after={requested: _view(role="primary")},
    )
    assert role.preflight_code == "CALENDAR_PREPARE_ROLE_CHANGE"

    enabled = classify_covering_prepare_mutation(
        requested_id=requested,
        before={requested: _view()},
        after={requested: _view(is_enabled=False)},
    )
    assert enabled.preflight_code == "CALENDAR_PREPARE_SUBSET_UNSAFE"

    missing = classify_covering_prepare_mutation(
        requested_id=requested,
        before=before,
        after={requested: _view()},
    )
    assert missing.preflight_code == "CALENDAR_PREPARE_SUBSET_UNSAFE"


def test_prepare_diff_noop_is_not_a_mutation() -> None:
    requested = uuid4()
    decision = classify_covering_prepare_mutation(
        requested_id=requested,
        before={requested: _view()},
        after={requested: _view()},
    )
    assert decision.allowed is True
    assert decision.eligibility_mutated is False
    assert decision.effects == ()


def test_guard_view_covers_classified_fields() -> None:
    _account, subscription, _success_at = _pair()
    assert set(subscription_guard_view(subscription)) == set(_GUARD_FIELDS)


def test_failure_refusal_matches_durable_generation_not_a_bumped_copy() -> None:
    account, subscription, _success_at = _pair()
    attempt = snapshot_covering_attempt(account=account, subscription=subscription)
    assert attempt.durable_coverage_active_generation == 5
    assert covering_failure_overwrite_refusal(subscription, account, attempt) is None

    # A rolled-back begin would show generation 6 only in the caller's session.
    # The failure unit re-reads the row. Generation 6 against snapshot 5 refuses.
    newer = CalendarSubscription(
        id=subscription.id,
        owner_id=subscription.owner_id,
        calendar_account_id=account.id,
        external_calendar_id=subscription.external_calendar_id,
        role=subscription.role,
        is_enabled=True,
        coverage_active_generation=6,
        coverage_success_generation=6,
        coverage_success_at=datetime(2026, 10, 21, 13, 0, tzinfo=timezone.utc),
    )
    assert (
        covering_failure_overwrite_refusal(newer, account, attempt)
        == REFUSE_SUPERSEDED_GENERATION
    )


def test_failure_refusal_identity_disable_and_success_generation() -> None:
    account, subscription, success_at = _pair()
    attempt = snapshot_covering_attempt(account=account, subscription=subscription)

    disabled = CalendarSubscription(
        id=subscription.id,
        owner_id=subscription.owner_id,
        calendar_account_id=account.id,
        external_calendar_id=subscription.external_calendar_id,
        role=subscription.role,
        is_enabled=False,
        coverage_active_generation=5,
        coverage_success_generation=5,
        coverage_success_at=success_at,
    )
    assert (
        covering_failure_overwrite_refusal(disabled, account, attempt)
        == REFUSE_SUBSCRIPTION_DISABLED
    )

    account.is_enabled = False
    assert (
        covering_failure_overwrite_refusal(subscription, account, attempt)
        == REFUSE_ACCOUNT_DISABLED
    )
    account.is_enabled = True

    moved = CalendarSubscription(
        id=subscription.id,
        owner_id=subscription.owner_id,
        calendar_account_id=account.id,
        external_calendar_id="other-calendar",
        role=subscription.role,
        is_enabled=True,
        coverage_active_generation=5,
        coverage_success_generation=5,
        coverage_success_at=success_at,
    )
    assert covering_failure_overwrite_refusal(moved, account, attempt) == REFUSE_SUPERSEDED_IDENTITY

    minted = CalendarSubscription(
        id=subscription.id,
        owner_id=subscription.owner_id,
        calendar_account_id=account.id,
        external_calendar_id=subscription.external_calendar_id,
        role=subscription.role,
        is_enabled=True,
        coverage_active_generation=5,
        coverage_success_generation=9,
        coverage_success_at=success_at,
    )
    assert covering_failure_overwrite_refusal(minted, account, attempt) == REFUSE_SUPERSEDED_SUCCESS
    assert covering_failure_overwrite_refusal(None, account, attempt) == REFUSE_SUBSCRIPTION_MISSING


def test_snapshot_copies_current_durable_attributes() -> None:
    account, subscription, _success_at = _pair()
    subscription.coverage_active_generation = 5
    copied = snapshot_covering_attempt(account=account, subscription=subscription)
    subscription.coverage_active_generation = 99
    assert copied.durable_coverage_active_generation == 5
    assert isinstance(copied, CoveringAttemptSnapshot)


def test_covering_modules_do_not_call_legacy_write_seams() -> None:
    import_calls = _calls(inspect.getsource(covering_refresh_import))
    failure_calls = _calls(inspect.getsource(covering_refresh_failure))
    assert _FORBIDDEN_CALLS.isdisjoint(import_calls)
    assert _FORBIDDEN_CALLS.isdisjoint(failure_calls)
    assert "_apply_subscription_full" in import_calls
    assert "_apply_subscription_ms_view" in import_calls
    body = inspect.getsource(import_covering_subscription_cache)
    assert body.index("snapshot_covering_attempt") < body.index("begin_subscription_refresh")
