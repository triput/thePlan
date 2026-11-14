"""Domain policy checks: real dispatcher; synthetic role/DB/provider ports.

These do not replace Jim's independent HTTP/auth parity or native proofs.
"""
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone, timedelta
from threading import Event
from types import SimpleNamespace
from uuid import UUID

import pytest
from app.api.errors import ApiError
from app.api.middleware.covering_ingress import CoveringRequestContext
from app.services import covering_domain_dispatch as domain
from app.services.covering_request_budget import CoveringRequestBudget
from app.services.covering_role_admission import CoveringRole
from app.services.covering_target_transaction import CoveringRootOutcomeUnknown
from app.schemas.calendar import CoveringRefreshRequest

OWNER, ACCOUNT, FIRST, SECOND = [UUID(int=i) for i in range(1,5)]


class Clock:
    value = 0
    def __call__(self):
        return self.value


class Connector:
    def __init__(self, budget):
        self.budget, self.events = budget, []
        self.session = SimpleNamespace(info={})
    def set_authenticated_credential(self, credential):
        self.credential = credential
    @contextmanager
    def session_scope(self, role):
        self.budget.work_remaining()
        self.events.append(("open", role))
        try:
            yield self.session
        finally:
            self.events.append(("retire", role))


def prepared(monkeypatch):
    clock = Clock()
    context = CoveringRequestContext(CoveringRequestBudget(clock), Event())
    connector = Connector(context.budget)
    now = datetime(2026,11,9,tzinfo=timezone.utc)
    body = CoveringRefreshRequest(subscription_ids=[SECOND,FIRST],
        window_start=now, window_end=now+timedelta(days=1))
    request = SimpleNamespace(state=SimpleNamespace(), session={}, headers={}, method="POST")
    targets = tuple(domain.Target(OWNER,ACCOUNT,s,None) for s in (FIRST,SECOND))
    monkeypatch.setattr(domain, "authenticate",
                        lambda request, db: domain.Identity(OWNER,None))
    monkeypatch.setattr(domain, "_preflight", lambda db, identity, body: (targets,7))
    tokens = []
    def token(db, target, remaining):
        tokens.append(target.subscription_id)
        return domain.TokenReady("synthetic-only")
    ports = domain.CoveringDomainPorts(token, None, None)
    return clock, context, connector, body, request, tokens, ports


def test_ordered_known_deadline_preserves_completed_and_unadmitted(monkeypatch):
    clock, ctx, connector, body, request, tokens, ports = prepared(monkeypatch)
    def target_run(**kw):
        window=domain.effective_covering_pull_window(body.window_start,body.window_end)
        result=replace(domain._static_preflight_result(subscription_id=FIRST,
            window=window,preflight_code="unused"), outcome="ok",preflight_code=None,
            provider_event_read_attempted=True)
        clock.value=210
        return result,None
    connector.run_target=target_run
    response=domain.run_bounded_domain(request,body,ctx,connector,ports)
    assert [r.subscription_id for r in response.results]==[FIRST,SECOND]
    assert [r.status for r in response.results]==["ok","preflight_rejected"]
    assert response.results[1].preflight_code==domain.DEADLINE
    assert tokens==[FIRST]
    assert response.action_summary.import_attempted==1
    assert response.overall_outcome=="partial"
    assert not any(role is CoveringRole.ASSESSMENT for op,role in connector.events)


def test_unknown_stops_second_target_and_assessment(monkeypatch):
    _,ctx,connector,body,request,tokens,ports=prepared(monkeypatch)
    def unknown(**kw):
        raise CoveringRootOutcomeUnknown()
    connector.run_target=unknown
    with pytest.raises(CoveringRootOutcomeUnknown):
        domain.run_bounded_domain(request,body,ctx,connector,ports)
    assert tokens==[FIRST]
    assert not any(role is CoveringRole.ASSESSMENT for op,role in connector.events)


def test_ownership_refusal_admits_no_token_or_target(monkeypatch):
    _,ctx,connector,body,request,tokens,ports=prepared(monkeypatch)
    def denied(*args):
        raise domain.CoveringSubscriptionNotEligible()
    monkeypatch.setattr(domain,"_preflight",denied)
    with pytest.raises(ApiError) as caught:
        domain.run_bounded_domain(request,body,ctx,connector,ports)
    assert caught.value.status_code==422
    assert tokens==[] and not ctx.ownership_established
    assert connector.events[-1]==("retire",CoveringRole.AUTH)


def test_password_cookie_precedes_bearer_resolution(monkeypatch):
    user=SimpleNamespace(is_disabled=False,must_change_password=True)
    request=SimpleNamespace()
    monkeypatch.setattr(domain.deps,"_parse_session_user_id",lambda request:OWNER)
    monkeypatch.setattr(domain.deps,"session_epoch_matches",lambda request,user:True)
    monkeypatch.setattr(domain.deps,"_resolve_agent_user",
                        lambda *a,**kw:pytest.fail("Bearer reached before password gate"))
    session=SimpleNamespace(get=lambda *args:user)
    with pytest.raises(ApiError) as caught:
        domain.authenticate(request,session)
    assert caught.value.content["code"]=="PASSWORD_CHANGE_REQUIRED"


def test_malformed_bearer_never_falls_back_to_cookie(monkeypatch):
    request=SimpleNamespace()
    monkeypatch.setattr(domain.deps,"_parse_session_user_id",lambda request:None)
    monkeypatch.setattr(domain.deps,"is_setup_required",lambda db:False)
    monkeypatch.setattr(domain.deps,"request_has_bearer",lambda request:True)
    monkeypatch.setattr(domain.deps,"extract_bearer_token",lambda request:"")
    def refused(request,db,token,*,touch):
        assert token==""
        raise ApiError(401,"Not authenticated","UNAUTHENTICATED")
    monkeypatch.setattr(domain.deps,"_resolve_agent_user",refused)
    monkeypatch.setattr(domain.deps,"_resolve_browser_user",
                        lambda *args:pytest.fail("cookie fallback"))
    with pytest.raises(ApiError) as caught:
        domain.authenticate(request,object())
    assert caught.value.status_code==401


def test_known_auth_refusal_retires_role_before_raising():
    connector=Connector(CoveringRequestBudget())
    def denied(db):
        raise ApiError(401,"Not authenticated","UNAUTHENTICATED")
    with pytest.raises(ApiError):
        domain._classified_role(connector,CoveringRole.AUTH,denied)
    assert connector.events==[("open",CoveringRole.AUTH),("retire",CoveringRole.AUTH)]


def test_valid_agent_telemetry_after_auth_retirement(monkeypatch):
    clock,ctx,connector,body,request,tokens,ports=prepared(monkeypatch)
    credential=UUID(int=99)
    monkeypatch.setattr(domain,"authenticate",lambda req,db:domain.Identity(OWNER,credential))
    monkeypatch.setattr(domain,"assert_agent_write_still_authorized",lambda db,c:None)
    def execute(*args):
        assert connector.events[:3]==[("open",CoveringRole.AUTH),
            ("retire",CoveringRole.AUTH),("open",CoveringRole.TELEMETRY)]
        clock.value=210
    connector.session.execute=execute
    from app.services.covering_request_budget import CoveringDeadlineExceeded
    with pytest.raises(CoveringDeadlineExceeded):
        domain.run_bounded_domain(request,body,ctx,connector,ports)
    assert ctx.auth_telemetry_admitted and not ctx.calendar_admitted
    assert not ctx.ownership_established and tokens==[]


def test_auth_refusal_has_no_telemetry_or_ownership(monkeypatch):
    _,ctx,connector,body,request,tokens,ports=prepared(monkeypatch)
    def denied(request,db):
        raise ApiError(401,"Not authenticated","UNAUTHENTICATED")
    monkeypatch.setattr(domain,"authenticate",denied)
    with pytest.raises(ApiError):
        domain.run_bounded_domain(request,body,ctx,connector,ports)
    assert connector.events==[("open",CoveringRole.AUTH),("retire",CoveringRole.AUTH)]
    assert not ctx.auth_telemetry_admitted and not ctx.ownership_established
    assert tokens==[]


def test_expiry_after_ownership_marks_every_target_unadmitted(monkeypatch):
    clock,ctx,connector,body,request,tokens,ports=prepared(monkeypatch)
    def preflight(db,identity,body):
        clock.value=210
        return tuple(domain.Target(OWNER,ACCOUNT,s,None) for s in (FIRST,SECOND)),7
    monkeypatch.setattr(domain,"_preflight",preflight)
    result=domain.run_bounded_domain(request,body,ctx,connector,ports)
    assert ctx.ownership_established and tokens==[]
    assert [r.subscription_id for r in result.results]==[FIRST,SECOND]
    assert all(r.preflight_code==domain.DEADLINE for r in result.results)
    assert result.action_summary.import_attempted==0


def test_known_assessment_error_is_sanitized_after_retirement(monkeypatch):
    _,ctx,connector,body,request,tokens,ports=prepared(monkeypatch)
    window=domain.effective_covering_pull_window(body.window_start,body.window_end)
    connector.run_target=lambda **kw:(domain._static_preflight_result(
        subscription_id=kw["subscription_id"],window=window,preflight_code="synthetic"),None)
    def failed(**kwargs):
        raise ApiError(503,"secret-provider-detail","INTERNAL_FAKE")
    monkeypatch.setattr(domain,"_assemble_final_assessment",lambda *args,**kwargs:failed(**kwargs))
    result=domain.run_bounded_domain(request,body,ctx,connector,ports)
    assert result.scheduling_readiness.assessment_error=="CALENDAR_REFRESH_ASSESSMENT_FAILED"
    assert connector.events[-1]==("retire",CoveringRole.ASSESSMENT)
    assert "secret-provider-detail" not in result.model_dump_json()

