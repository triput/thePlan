"""Concrete covering token/lock/apply adapters. Construction does not bind."""
from app.models import CalendarAccount, CalendarSubscription
from app.services.covering_domain_dispatch import CoveringDomainPorts, TokenReady, TokenRejected
from app.services.covering_refresh_import import (
    _refresh_provider_access_token, covering_import_eligibility_code,
    import_covering_subscription_cache,
)
from app.services.covering_refresh_locks import covering_unit_locks
from app.services.covering_provider_context import covering_provider_transport
from app.services.covering_target_transaction import CoveringRootOutcomeUnknown, RootOutcome
from app.services.agent_auth_context import resolve_session_agent_credential
from app.services.agent_credentials import assert_agent_write_still_authorized
from app.services.covering_transport_policy import CoveringReauthorizationRequired
from app.services.covering_refresh_import import PREFLIGHT_ACCOUNT_DISCONNECTED


def make_domain_ports(*, settings, transport):
    def locks(db,target,remaining):
        return covering_unit_locks(db,owner_id=target.owner_id,account_id=target.account_id,
            subscription_id=target.subscription_id,remaining=remaining)

    def pair(db,target):
        account=db.query(CalendarAccount).filter(CalendarAccount.id==target.account_id).populate_existing().one()
        sub=db.query(CalendarSubscription).filter(CalendarSubscription.id==target.subscription_id).populate_existing().one_or_none()
        if account.owner_id!=target.owner_id or (sub is not None and
                (sub.owner_id!=target.owner_id or sub.calendar_account_id!=target.account_id)):
            raise CoveringRootOutcomeUnknown()
        return account,sub

    def token(db,target,remaining):
        if transport.counter.stopped:
            return TokenRejected("CALENDAR_REFRESH_PROVIDER_LIMIT_EXCEEDED")
        terminal=db.info.get("covering_token_terminal")
        if not callable(terminal):
            raise CoveringRootOutcomeUnknown()
        with locks(db,target,remaining):
            remaining()
            account,sub=pair(db,target)
            code=covering_import_eligibility_code(account,sub,check_missing_credentials=True)
            if code is not None:
                result=TokenRejected(code)
                changed=False
            else:
                before=(account.access_token_enc,account.refresh_token_enc,account.token_expires_at)
                try:
                    with covering_provider_transport(transport):
                        access=_refresh_provider_access_token(db,settings=settings,account=account)
                    changed=before!=(account.access_token_enc,account.refresh_token_enc,account.token_expires_at)
                    result=TokenReady(access)
                except CoveringReauthorizationRequired:
                    changed=False
                    result=TokenRejected(PREFLIGHT_ACCOUNT_DISCONNECTED)
            credential=resolve_session_agent_credential(db)
            if changed and credential is not None:
                assert_agent_write_still_authorized(db,credential)
            # Native factory owns this hook: exact terminal evidence, no duplicate
            # terminal from close_known, and no ordinary ORM commit fallback.
            expected=RootOutcome.COMMIT_ACKNOWLEDGED if changed else RootOutcome.ROLLBACK_ACKNOWLEDGED
            if terminal(commit=changed,remaining=remaining) is not expected:
                raise CoveringRootOutcomeUnknown()
        return result

    def apply(db,target,token,window,receipt,adapter,now,remaining):
        if db.info.get("covering_native_flush_bound") is not adapter:
            raise CoveringRootOutcomeUnknown()
        remaining()
        account,sub=pair(db,target)
        if sub is None:
            raise CoveringRootOutcomeUnknown()
        with covering_provider_transport(transport):
            return import_covering_subscription_cache(db,settings=settings,account=account,
                subscription=sub,access_token=token.access_token,
                window_start=window.effective_start,window_end=window.effective_end,
                lock_receipt=receipt,now=now)
    return CoveringDomainPorts(token,locks,apply)

