"""Request-local role admission; no connection creation or endpoint binding.

This internal seam serializes checkout attempts. A native adapter must supply
the exact opaque driver identity and classified retirement evidence; this
module cannot establish those facts itself or authorize a failure recorder.
"""

from dataclasses import dataclass
from enum import Enum
from threading import get_ident

from app.services.covering_request_budget import CoveringRequestBudget


class CoveringRoleRefused(Exception):
    """Admission stopped because role ownership could not be established."""


class CoveringRole(Enum):
    AUTH = "auth"
    TELEMETRY = "telemetry"
    TOKEN = "token"
    PARENT = "parent"
    RECORDER = "recorder"
    ASSESSMENT = "assessment"


@dataclass(frozen=True, eq=False)
class RoleLease:
    role: CoveringRole
    target: object | None
    sequence: int


class CoveringRoleAdmission:
    """One joined owner, one in-flight checkout, no reuse across roles.

Create on the joined worker with the budget created at ASGI entry. Keep a
lease active through checkout, native work, lock exit, and local retirement.
An unclassified checkout failure must stop, not cancel, the lease.
"""

    def __init__(self, budget: CoveringRequestBudget) -> None:
        self._budget = budget
        self._owner = get_ident()
        self._active: RoleLease | None = None
        self._driver: object | None = None
        # Retain opaque identities for this request to prevent identity reuse.
        self._seen: list[object] = []
        self._sequence = 0
        self._stopped = False

    def stop(self) -> None:
        """Close admission before the native owner quarantines its transport."""
        self._stopped = True
        self._budget.stop()

    def _refuse(self) -> None:
        self.stop()
        raise CoveringRoleRefused()

    def _owner_check(self) -> None:
        if self._stopped or get_ident() != self._owner:
            self._refuse()

    def _lease_check(self, lease: RoleLease) -> None:
        self._owner_check()
        if lease is not self._active:
            self._refuse()

    def begin(self, role: CoveringRole, *, target: object | None = None) -> RoleLease:
        """Reserve before calling any factory; deadline refusal opens nothing.

The caller still owns role order, target authorization, and the parent's
one-use recorder permit. A RECORDER lease alone grants none of these.
"""
        self._owner_check()
        self._budget.check_admission()
        if self._active is not None or type(role) is not CoveringRole:
            self._refuse()
        if (role in (CoveringRole.PARENT, CoveringRole.RECORDER)) != (target is not None):
            self._refuse()
        if role is CoveringRole.RECORDER:
            self._budget.cleanup_remaining()
        else:
            self._budget.work_remaining()
        self._sequence += 1
        self._active = RoleLease(role, target, self._sequence)
        return self._active

    def bind(self, lease: RoleLease, driver_identity: object) -> None:
        """Bind the exact native identity, not a disposable session wrapper."""
        self._lease_check(lease)
        if (
            driver_identity is None or self._driver is not None
            or any(driver_identity is prior for prior in self._seen)
        ):
            self._refuse()
        self._driver = driver_identity
        self._seen.append(driver_identity)

    def cancel_before_connect(self, lease: RoleLease) -> None:
        """For a proven pre-connect refusal only; never for a connect timeout."""
        self._lease_check(lease)
        if self._driver is not None:
            self._refuse()
        self._active = None

    def complete(
        self, lease: RoleLease, *, driver_identity: object,
        outcome_known: bool, locks_exited: bool, retired: bool,
    ) -> None:
        """Release only after native classification and exact local retirement.

Do not recheck time here: expiry cannot erase an acknowledged outcome or
prevent recording completed retirement. The next admission checks its budget.
"""
        self._lease_check(lease)
        if (
            self._driver is None or driver_identity is not self._driver
            or outcome_known is not True or locks_exited is not True
            or retired is not True
        ):
            self._refuse()
        self._driver = None
        self._active = None
