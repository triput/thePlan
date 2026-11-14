"""Unbound production HTTP-to-connector boundary.

No release binding is installed here. Domain orchestration and transports must
be reviewed together before binding; a callable is not evidence of safety.
"""
from dataclasses import dataclass
from functools import partial
from typing import Callable

import anyio

from app.api.errors import ApiError
from app.api.middleware.covering_ingress import CONTEXT_KEY
from app.services.covering_request_budget import (
    CoveringDeadlineExceeded, CoveringBudgetStopped,
)
from app.services.covering_role_connector import CoveringRoleConnector
from app.services.covering_target_transaction import CoveringRootOutcomeUnknown
from app.services.covering_domain_dispatch import CoveringDomainPorts, run_bounded_domain


@dataclass(frozen=True)
class CoveringReleaseBinding:
    parent_factory: Callable
    session_factory: Callable
    domain_ports: CoveringDomainPorts


def _worker(binding, request, body, context):
    context.budget.work_remaining()
    from app.services.covering_release_plan import CoveringReleasePlan
    if type(binding) is CoveringReleasePlan:
        binding = binding.for_request(context.budget)
    connector = CoveringRoleConnector(
        budget=context.budget,
        parent_factory=binding.parent_factory,
        session_factory=binding.session_factory,
    )
    return run_bounded_domain(request, body, context, connector, binding.domain_ports)


async def dispatch_covering_http(request, body):
    context = request.scope.get("state", {}).get(CONTEXT_KEY)
    if context is None:
        # No legacy fallback if middleware assembly is incomplete.
        raise RuntimeError("covering ingress context missing")
    binding = getattr(request.app.state, "covering_release_binding", None)
    from app.services.covering_release_plan import CoveringReleasePlan
    if (type(binding) is not CoveringReleasePlan and
            (type(binding) is not CoveringReleaseBinding
             or type(binding.domain_ports) is not CoveringDomainPorts)):
        # Accepted by Trish: distinct unbound response, not outcome uncertainty.
        raise ApiError(503, "Calendar refresh is not configured.",
                       "CALENDAR_REFRESH_NOT_CONFIGURED")
    try:
        # One joined owner, including cancellation. Transport ports must honor
        # live budget callbacks; this is not a detached timeout worker.
        with anyio.CancelScope(shield=True):
            return await anyio.to_thread.run_sync(
                partial(_worker, binding, request, body, context),
                abandon_on_cancel=False,
            )
    except CoveringDeadlineExceeded:
        if not context.ownership_established and not context.calendar_admitted:
            raise ApiError(504, "Calendar refresh deadline exceeded.",
                           "CALENDAR_REFRESH_DEADLINE_EXCEEDED") from None
        # Post-ownership expiry must have been converted to typed rows inside
        # dispatch. Escaping it is unclassified, never an invented known result.
        raise ApiError(503, "Calendar refresh outcome is unknown. Do not retry automatically.",
                       "CALENDAR_REFRESH_OUTCOME_UNKNOWN") from None
    except (CoveringRootOutcomeUnknown, CoveringBudgetStopped):
        raise ApiError(503, "Calendar refresh outcome is unknown. Do not retry automatically.",
                       "CALENDAR_REFRESH_OUTCOME_UNKNOWN") from None

