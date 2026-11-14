"""Covering-only composition of role leases and the native parent adapter.

Factories are explicit injected ports, never SessionLocal fallbacks. They must
own partial-checkout quarantine on failure and enforce the supplied live budget
at every blocking operation. No endpoint or factory is installed here.
"""
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from app.services.covering_parent_adapter import CoveringParentAdapter, ParentDriver
from app.services.covering_request_budget import CoveringRequestBudget
from app.services.covering_role_admission import (
    CoveringRole, CoveringRoleAdmission, CoveringRoleRefused,
)
from app.services.covering_target_transaction import (
    CoveringRootOutcomeUnknown, CoveringTargetTransaction,
)


@dataclass(frozen=True)
class RoleCompletion:
    identity: object
    outcome_known: bool
    locks_exited: bool
    retired: bool


@dataclass(frozen=True)
class SessionBinding:
    session: object
    identity: object
    # Observe terminal evidence and retire exactly this driver. This callback
    # must never retry a terminal command that the recorder already sent.
    close_known: Callable[[Callable[[], float]], RoleCompletion]
    quarantine: Callable[[], None]


@dataclass(frozen=True)
class ParentBinding:
    session: object
    identity: object
    root: object
    driver: ParentDriver


class _RoleParent(CoveringParentAdapter):
    def __init__(self, *, admission, lease, identity, locks_exited, **kwargs):
        super().__init__(**kwargs)
        self._admission = admission
        self._lease = lease
        self._identity = identity
        self._locks_exited = locks_exited
        self._lease_completed = False

    def _unknown(self):
        self._admission.stop()
        return super()._unknown()

    def retire_parent(self):
        if not self._locks_exited() or self._lease_completed:
            self._unknown()
            return False
        if not super().retire_parent():
            return False
        try:
            self._admission.complete(
                self._lease, driver_identity=self._identity,
                outcome_known=self.acknowledged_outcome is not None,
                locks_exited=True, retired=True,
            )
        except Exception:
            self._unknown()
            raise CoveringRootOutcomeUnknown() from None
        self._lease_completed = True
        return True


class CoveringRoleConnector:
    """One request's joined worker; use the ASGI-created budget unchanged."""

    def __init__(self, *, budget: CoveringRequestBudget, parent_factory, session_factory):
        self.budget = budget
        self._admission = CoveringRoleAdmission(budget)
        self._parent_factory = parent_factory
        self._session_factory = session_factory
        self._credential_id = None
        self._identity_set = False

    def set_authenticated_credential(self, credential_id):
        if self._identity_set:
            self._admission.stop()
            raise CoveringRootOutcomeUnknown()
        self._identity_set = True
        self._credential_id = credential_id

    def _stamp(self, session):
        if self._credential_id is not None:
            from app.services.agent_auth_context import bind_session_agent_guard
            bind_session_agent_guard(session, self._credential_id)

    def _begin(self, role, target=None):
        try:
            return self._admission.begin(role, target=target)
        except CoveringRoleRefused:
            raise CoveringRootOutcomeUnknown() from None

    @contextmanager
    def session_scope(self, role: CoveringRole) -> Iterator[object]:
        """Ordinary roles only. Recorder entry is private to the parent permit."""
        if role not in (CoveringRole.AUTH, CoveringRole.TELEMETRY,
                        CoveringRole.TOKEN, CoveringRole.ASSESSMENT):
            self._admission.stop()
            raise CoveringRootOutcomeUnknown()
        with self._session_scope(role, None, self.budget.work_remaining) as session:
            yield session

    @contextmanager
    def _session_scope(self, role, target, remaining):
        # Expiry before begin is a known admission refusal, with zero checkout.
        lease = self._begin(role, target)
        binding = None
        try:
            binding = self._session_factory(role, target, remaining)
            self._admission.bind(lease, binding.identity)
            self._stamp(binding.session)
            yield binding.session
            if role is CoveringRole.RECORDER:
                completion = binding.close_known(remaining)
            else:
                # Ordinary role retirement also consumes the shared cleanup
                # reserve; it must remain possible after the work cutoff.
                with self.budget.cleanup():
                    completion = binding.close_known(self.budget.cleanup_remaining)
            if type(completion) is not RoleCompletion:
                raise CoveringRootOutcomeUnknown()
            self._admission.complete(
                lease, driver_identity=completion.identity,
                outcome_known=completion.outcome_known,
                locks_exited=completion.locks_exited, retired=completion.retired,
            )
        except BaseException:
            # Stop admission before calling any transport teardown port.
            self._admission.stop()
            if binding is not None:
                try:
                    binding.quarantine()
                except BaseException:
                    pass  # Keep stopped; never attempt a second teardown.
            raise CoveringRootOutcomeUnknown() from None

    def run_target(self, *, owner_id, account_id, subscription_id, locks, apply, now):
        """Apply receives (session, lock receipt, adapter) for native flush hooks.

Parent factory receives the exact target tuple and the live work budget.
Recorder factory is reached only through this parent's consumed permit.
"""
        target = (owner_id, account_id, subscription_id)
        lease = self._begin(CoveringRole.PARENT, target)
        binding = None
        adapter = None
        exited = False

        @contextmanager
        def tracked_locks():
            nonlocal exited
            scope = locks(binding.session) if callable(locks) else locks
            with scope as receipt:
                yield receipt
            exited = True  # Only normal completion proves lock-scope exit.

        def failure_session(remaining):
            return self._session_scope(CoveringRole.RECORDER, target, remaining)

        try:
            binding = self._parent_factory(target, self.budget.work_remaining)
            self._admission.bind(lease, binding.identity)
            self._stamp(binding.session)
            adapter = _RoleParent(
                admission=self._admission, lease=lease, identity=binding.identity,
                locks_exited=lambda: exited, root=binding.root, driver=binding.driver,
                budget=self.budget, failure_session=failure_session,
            )
            with adapter.target_scope():
                bind_parent = getattr(binding.driver, "bind_parent", None)
                if bind_parent is not None:
                    bind_parent(adapter)
                return CoveringTargetTransaction(adapter).run(
                    owner_id=owner_id, account_id=account_id,
                    subscription_id=subscription_id, locks=tracked_locks(),
                    apply=lambda receipt: apply(binding.session, receipt, adapter), now=now,
                )
        except BaseException as exc:
            self._admission.stop()
            # target_scope already owns abort once adapter construction succeeds.
            if adapter is None and binding is not None:
                try:
                    if binding.driver.cut_off_frontend() is True:
                        binding.driver.retire()
                except BaseException:
                    pass
            if isinstance(exc, CoveringRootOutcomeUnknown):
                raise  # Retain a previously acknowledged parent's result.
            raise CoveringRootOutcomeUnknown() from None
