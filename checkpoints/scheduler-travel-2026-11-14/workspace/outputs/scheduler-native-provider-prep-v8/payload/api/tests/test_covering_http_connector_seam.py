"""HTTP-to-real-connector seam; synthetic orchestration/ports, not release wiring."""
from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.services.covering_role_connector import CoveringRoleConnector, ParentBinding, SessionBinding, RoleCompletion, CoveringRole
from app.services.covering_request_budget import CoveringRequestBudget
from app.services.covering_parent_adapter import NativeTerminalResult
from app.services.covering_target_transaction import CoveringRootOutcomeUnknown
from app.services.covering_refresh_failure import CoveringFailurePersistResult
import app.services.covering_target_transaction as transaction_module
from support.covering_refresh_asgi_harness import (
    COVERING_PATH, HarnessIdentityStore, FakeCoveringOrchestrator,
    covering_refresh_asgi_client, mint_signed_session_cookie, refresh_body,
)


class Bridge:
    """Test adapter replaces only orchestration; actual connector policy runs.

    Auth stays in the accepted fake-identity HTTP harness. Budget starts at this
    adapter, NOT ASGI entry. Response assessment/revisions remain synthetic.
    """
    def __init__(self, *, failure_index=None, parent_unknown=False, recorder_unknown=False):
        self.failure_index = failure_index
        self.parent_unknown = parent_unknown
        self.recorder_unknown = recorder_unknown
        self.events = []
        self.completed = []
        self.unknown = None
        self.connector = None
        self.now = datetime(2026, 11, 9, tzinfo=timezone.utc)

    def session(self, role, target, remaining):
        remaining()
        self.events.append((role.value + '_checkout', target))
        identity = object()
        def close(deadline):
            deadline()
            self.events.append((role.value + '_close', target))
            return RoleCompletion(identity, not (role is CoveringRole.RECORDER and self.recorder_unknown), True, True)
        def quarantine():
            self.events.append((role.value + '_quarantine', target))
        return SessionBinding(object(), identity, close, quarantine)

    def parent(self, target, remaining):
        remaining()
        self.events.append(('parent_checkout', target))
        root = object()
        bridge = self
        class Driver:
            def finish(self, operation, *, remaining):
                remaining()
                assert operation.root is root
                bridge.events.append((operation.command.value.decode(), target))
                if bridge.parent_unknown:
                    raise RuntimeError('synthetic lost acknowledgment; do not expose this text')
                return NativeTerminalResult(operation, True, operation.command.value, True, True)
            def cut_off_frontend(self):
                bridge.events.append(('parent_cutoff', target))
                return True
            def retire(self):
                bridge.events.append(('parent_retire', target))
                return True
        driver = Driver()
        return ParentBinding(object(), driver, root, driver)

    @contextmanager
    def locks(self, target):
        self.events.append(('locks_enter', target))
        try:
            yield SimpleNamespace(owner_id=target[0], account_id=target[1], subscription_id=target[2])
        finally:
            self.events.append(('locks_exit', target))

    def record(self, session, *, attempt, now, cause):
        target = (attempt.owner_id, attempt.account_id, attempt.subscription_id)
        self.events.append(('record', target))
        return CoveringFailurePersistResult(attempt.subscription_id, True, False, None, False, None, cause)

    def __call__(self, db, *, settings, owner_id, body, **kwargs):
        self.connector = CoveringRoleConnector(budget=CoveringRequestBudget(lambda: 0.0),
                                               parent_factory=self.parent, session_factory=self.session)
        account_id = uuid4()
        try:
            for index, sub_id in enumerate(body.subscription_ids):
                target = (owner_id, account_id, sub_id)
                with self.connector.session_scope(CoveringRole.TOKEN):
                    pass
                failed = index == self.failure_index
                imported = SimpleNamespace(subscription_id=sub_id, outcome='failed' if failed else 'ok',
                    commit_unit=not failed, rollback_required=failed, needs_failure_unit=failed,
                    cause='synthetic_provider_failure' if failed else None,
                    attempt=SimpleNamespace(owner_id=owner_id, account_id=account_id, subscription_id=sub_id) if failed else None)
                result, recorder = self.connector.run_target(owner_id=owner_id, account_id=account_id,
                    subscription_id=sub_id, locks=self.locks(target), apply=lambda *args: imported, now=self.now)
                self.completed.append((result, recorder))
            with self.connector.session_scope(CoveringRole.ASSESSMENT):
                pass
        except CoveringRootOutcomeUnknown as exc:
            self.unknown = exc
            raise
        # Deliberately synthetic response construction; this packet proves the
        # dispatch/transaction-to-HTTP seam, not the production orchestrator.
        mode = 'partial_two' if self.failure_index == 1 else 'success'
        response = FakeCoveringOrchestrator(mode=mode)(db, settings=settings, owner_id=owner_id, body=body)
        assert [r.status for r in response.results] == [r.outcome for r, _ in self.completed]
        return response


def request(bridge, monkeypatch, *, stale=False):
    monkeypatch.setattr(transaction_module, 'record_covering_refresh_failure_in_session', bridge.record)
    store = HarnessIdentityStore()
    user = store.add_browser_user(session_epoch=3)
    ids = [uuid4(), uuid4()]
    with covering_refresh_asgi_client(store=store, orchestrator=bridge) as harness:
        harness.client.cookies.set('session', mint_signed_session_cookie(user_id=user.id, session_epoch=2 if stale else 3))
        response = harness.client.post(COVERING_PATH, json=refresh_body(ids))
    return response, ids


def names(bridge):
    return [name for name, _ in bridge.events]


def test_integrated_http_two_known_commits(monkeypatch):
    bridge = Bridge()
    response, ids = request(bridge, monkeypatch)
    assert response.status_code == 200, response.text
    assert response.json()['overall_outcome'] == 'success'
    assert [str(r.subscription_id) for r, _ in bridge.completed] == [str(x) for x in ids]
    assert names(bridge) == ['token_checkout','token_close','parent_checkout','locks_enter','COMMIT','locks_exit','parent_retire'] * 2 + ['assessment_checkout','assessment_close']


def test_integrated_http_known_failure_records_after_retirement(monkeypatch):
    bridge = Bridge(failure_index=1)
    response, ids = request(bridge, monkeypatch)
    assert response.status_code == 200, response.text
    assert response.json()['overall_outcome'] == 'partial'
    assert bridge.completed[1][1].persisted
    assert names(bridge) == ['token_checkout','token_close','parent_checkout','locks_enter','COMMIT','locks_exit','parent_retire',
        'token_checkout','token_close','parent_checkout','locks_enter','ROLLBACK','locks_exit','parent_retire','recorder_checkout','record','recorder_close','assessment_checkout','assessment_close']


def test_integrated_http_parent_unknown_stops_second_target(monkeypatch):
    bridge = Bridge(parent_unknown=True)
    response, ids = request(bridge, monkeypatch)
    assert response.status_code == 503, response.text
    assert response.json()['code'] == 'CALENDAR_REFRESH_OUTCOME_UNKNOWN'
    assert 'synthetic' not in response.text
    assert names(bridge).count('parent_checkout') == 1
    assert names(bridge).count('COMMIT') == 1
    assert names(bridge).count('parent_cutoff') == 1
    assert names(bridge).count('parent_retire') == 1
    assert 'recorder_checkout' not in names(bridge) and 'assessment_checkout' not in names(bridge)
    assert bridge.completed == []


def test_integrated_http_recorder_unknown_preserves_parent_ack(monkeypatch):
    bridge = Bridge(failure_index=0, recorder_unknown=True)
    response, ids = request(bridge, monkeypatch)
    assert response.status_code == 503, response.text
    assert response.json()['code'] == 'CALENDAR_REFRESH_OUTCOME_UNKNOWN'
    assert bridge.unknown.parent_acknowledgment is not None
    assert bridge.unknown.parent_acknowledgment[1].subscription_id == ids[0]
    assert names(bridge).count('parent_checkout') == 1
    assert names(bridge).count('ROLLBACK') == 1
    assert names(bridge).count('record') == 1
    assert names(bridge).count('recorder_quarantine') == 1
    assert 'assessment_checkout' not in names(bridge)


def test_integrated_http_auth_refusal_never_creates_connector(monkeypatch):
    bridge = Bridge()
    response, ids = request(bridge, monkeypatch, stale=True)
    assert response.status_code == 401
    assert response.json()['code'] == 'UNAUTHENTICATED'
    assert bridge.connector is None and bridge.events == []
