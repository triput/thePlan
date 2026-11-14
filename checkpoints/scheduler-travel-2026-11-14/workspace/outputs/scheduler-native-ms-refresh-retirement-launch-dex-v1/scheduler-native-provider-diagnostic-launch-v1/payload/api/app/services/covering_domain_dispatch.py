"""Bounded covering domain policy. No implicit session or provider factories.

All functions run on the single HTTP worker. Only immutable IDs/results cross
role scopes. Transport ports are mandatory, remain uninstalled, and must enforce
the supplied live deadline. This module never calls the legacy orchestrator.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable
from uuid import UUID

from sqlalchemy import text
from app.api import deps
from app.api.errors import ApiError
from app.models import User
from app.schemas.calendar import (
    CoveringActionOut, CoveringActionSummaryOut, CoveringRefreshResponse,
    SchedulingReadinessOut,
)
from app.services.agent_auth_context import bind_session_agent_guard
from app.services.agent_credentials import assert_agent_write_still_authorized
from app.services.covering_refresh import (
    CoveringSubscriptionNotEligible, _preflight_load_targets, _static_preflight_result,
    _result_row, _derive_overall_outcome, _fail_closed_coverage_action,
    _window_out, _assemble_final_assessment,
)
from app.services.covering_refresh_import import covering_import_eligibility_code
from app.services.covering_refresh_window import effective_covering_pull_window, CoveringWindowError
from app.services.covering_role_admission import CoveringRole
from app.services.covering_request_budget import CoveringDeadlineExceeded
from app.services.covering_target_transaction import CoveringRootOutcomeUnknown
from app.services.scheduling_revision import lock_owner_scheduling

DEADLINE = "CALENDAR_REFRESH_DEADLINE_EXCEEDED"


@dataclass(frozen=True)
class Identity:
    owner_id: UUID
    credential_id: UUID | None


@dataclass(frozen=True)
class Target:
    owner_id: UUID
    account_id: UUID
    subscription_id: UUID
    preflight_code: str | None


@dataclass(frozen=True)
class TokenReady:
    access_token: str


@dataclass(frozen=True)
class TokenRejected:
    # Only a classified preflight refusal, with no uncertain durable effect.
    code: str


@dataclass(frozen=True)
class CoveringDomainPorts:
    # token(session, target, live_remaining) -> TokenReady | TokenRejected.
    # TOKEN close must classify any token durable unit before retirement.
    token: Callable
    # locks(session, target, live_remaining) -> exact lock receipt context.
    locks: Callable
    # apply(session, target, token, window, receipt, adapter, now, remaining)
    # -> ImportCoveringCacheResult. No commit/side session; native adapter owns
    # terminal control. Provider I/O is covering-only and bounded.
    apply: Callable


def _classified_role(connector, role, operation):
    """Known policy refusal is raised only AFTER known retirement.

    Native exceptions/timeouts are not caught as policy refusals. The connector
    quarantines them and stops. Session close must classify rollback/commit.
    """
    error = None
    value = None
    with connector.session_scope(role) as session:
        try:
            value = operation(session)
        except (ApiError, CoveringSubscriptionNotEligible) as exc:
            error = exc
    if error is not None:
        raise error
    return value


def authenticate(request, session):
    # Preserve original password middleware precedence, including mixed auth.
    cookie_id = deps._parse_session_user_id(request)
    if cookie_id is not None:
        cookie_user = session.get(User, cookie_id)
        if (cookie_user is not None and not cookie_user.is_disabled
                and deps.session_epoch_matches(request, cookie_user)
                and cookie_user.must_change_password):
            raise ApiError(403, "Password change required before continuing",
                           "PASSWORD_CHANGE_REQUIRED")
    if deps.is_setup_required(session):
        raise ApiError(401, "Initial setup required", "SETUP_REQUIRED")
    if deps.request_has_bearer(request):
        touched = []
        user = deps._resolve_agent_user(
            request, session, deps.extract_bearer_token(request) or "",
            touch=touched.append,
        )
        if touched != [request.state.agent_credential_id]:
            raise CoveringRootOutcomeUnknown()
        return Identity(user.id, touched[0])
    user = deps._resolve_browser_user(request, session)
    if user is None:
        raise ApiError(401, "Not authenticated", "UNAUTHENTICATED")
    request.state.auth_channel = "browser"
    return Identity(user.id, None)


def _guard(session, identity):
    if identity.credential_id is not None:
        bind_session_agent_guard(session, identity.credential_id)


def _preflight(session, identity, body):
    pairs = _preflight_load_targets(session, owner_id=identity.owner_id,
                                    subscription_ids=body.subscription_ids)
    # Copy before role retirement expires/detaches ORM instances.
    targets = tuple(Target(identity.owner_id, account.id, sub.id,
        covering_import_eligibility_code(account, sub, check_missing_credentials=True))
        for account, sub in pairs)
    revision = int(lock_owner_scheduling(session, identity.owner_id).scheduling_revision)
    return targets, revision


def _response(body, window, results, revision, final=None, assessment_error=None):
    rows = [_result_row(item) for item in results]
    attempted = sum(bool(item.provider_event_read_attempted) for item in results)
    ok = sum(row.status == "ok" for row in rows)
    end = None
    readiness = SchedulingReadinessOut(assessment_error=assessment_error or DEADLINE)
    coverage = _fail_closed_coverage_action(window)
    if final is not None:
        readiness = final.readiness
        end = readiness.scheduling_revision
        coverage = CoveringActionOut(
            window=_window_out(window.effective_start, window.effective_end),
            all_requested_covering_ok=final.requested.ok,
            freshness_requested=final.requested.to_dict())
    return CoveringRefreshResponse(
        window_requested=_window_out(window.effective_start, window.effective_end),
        window_effective=_window_out(window.effective_start, window.effective_end),
        window_widened=window.widened, window_widen_reason=window.reason,
        overall_outcome=_derive_overall_outcome(rows, import_attempted=attempted, import_ok=ok),
        action_summary=CoveringActionSummaryOut(requested=len(body.subscription_ids),
            preflight_rejected=sum(row.phase == "preflight" for row in rows),
            import_attempted=attempted, import_ok=ok,
            import_failed=sum(row.status == "failed" for row in rows)),
        results=rows, coverage_action=coverage, scheduling_readiness=readiness,
        scheduling_revision_at_start=revision, scheduling_revision_at_end=end,
        scheduling_revision_bumped=end is not None and end > revision)


def run_bounded_domain(request, body, context, connector, ports):
    """Auth -> telemetry -> ownership -> ordered token/parent -> assessment."""
    identity = _classified_role(connector, CoveringRole.AUTH,
                                lambda db: authenticate(request, db))
    connector.set_authenticated_credential(identity.credential_id)
    if identity.credential_id is not None:
        def telemetry(db):
            _guard(db, identity)
            context.auth_telemetry_admitted = True
            assert_agent_write_still_authorized(db, identity.credential_id)
            db.execute(text("UPDATE agent_credentials SET last_used_at = NOW() "
                            "WHERE id = :id AND revoked_at IS NULL"),
                       {"id": identity.credential_id})
        _classified_role(connector, CoveringRole.TELEMETRY, telemetry)
    try:
        window = effective_covering_pull_window(body.window_start, body.window_end)
        targets, revision = _classified_role(connector, CoveringRole.AUTH,
            lambda db: _preflight(db, identity, body))
    except (CoveringWindowError, CoveringSubscriptionNotEligible) as exc:
        raise ApiError(422, exc.detail, exc.code) from None
    context.ownership_established = True
    results = []
    exhausted = False
    try:
        for target in targets:
            context.budget.check_admission()  # Disconnect is not deadline success.
            if not exhausted:
                try:
                    context.budget.work_remaining()
                except CoveringDeadlineExceeded:
                    exhausted = True
            if exhausted or target.preflight_code:
                results.append(_static_preflight_result(
                    subscription_id=target.subscription_id, window=window,
                    preflight_code=DEADLINE if exhausted else target.preflight_code))
                continue
            def token_read(db):
                _guard(db, identity)
                context.calendar_admitted = True
                return ports.token(db, target, context.budget.work_remaining)
            try:
                token = _classified_role(connector, CoveringRole.TOKEN, token_read)
            except ApiError:
                # The token port must return TokenRejected for a classified
                # refusal. Do not let an unexpected port exception turn a
                # partially completed request into an arbitrary HTTP error.
                raise CoveringRootOutcomeUnknown() from None
            except CoveringDeadlineExceeded:
                # Only begin-before-checkout can escape connector as known expiry.
                exhausted = True
                results.append(_static_preflight_result(subscription_id=target.subscription_id,
                    window=window, preflight_code=DEADLINE))
                continue
            if type(token) is TokenRejected:
                results.append(_static_preflight_result(subscription_id=target.subscription_id,
                    window=window, preflight_code=token.code))
                continue
            if type(token) is not TokenReady or not token.access_token:
                raise CoveringRootOutcomeUnknown()
            now = datetime.now(timezone.utc)
            def apply(db, receipt, adapter):
                _guard(db, identity)
                result = ports.apply(db, target, token, window, receipt, adapter, now,
                                     context.budget.work_remaining)
                if result.commit_unit and identity.credential_id is not None:
                    # Native terminal COMMIT bypasses ORM before_commit.
                    assert_agent_write_still_authorized(db, identity.credential_id)
                return result
            try:
                result, failure = connector.run_target(
                    owner_id=identity.owner_id, account_id=target.account_id,
                    subscription_id=target.subscription_id,
                    locks=lambda db: ports.locks(db, target, context.budget.work_remaining),
                    apply=apply, now=now)
            except CoveringDeadlineExceeded:
                exhausted = True
                results.append(_static_preflight_result(subscription_id=target.subscription_id,
                    window=window, preflight_code=DEADLINE))
                continue
            results.append(result)
            context.completed = list(results)
        final = None
        assessment_error = None
        if not exhausted:
            try:
                context.budget.work_remaining()
                def assess(db):
                    _guard(db, identity)
                    return _assemble_final_assessment(db, owner_id=identity.owner_id,
                        subscription_ids=body.subscription_ids, window=window,
                        horizon_label=body.scheduling_horizon_label,
                        assessment_clock=lambda: datetime.now(timezone.utc))
                final = _classified_role(connector, CoveringRole.ASSESSMENT, assess)
            except CoveringDeadlineExceeded:
                exhausted = True
            except ApiError:
                # The role already supplied known retirement. Never expose
                # exception/provider/SQL details in a public assessment field.
                assessment_error = "CALENDAR_REFRESH_ASSESSMENT_FAILED"
        return _response(body, window, results, revision, final, assessment_error)
    except CoveringRootOutcomeUnknown as exc:
        exc.completed_results = tuple(results)
        raise

