"""Read a typed root result on an admitted covering PostgreSQL driver."""

from __future__ import annotations

from collections.abc import Callable
from selectors import EVENT_READ, EVENT_WRITE, DefaultSelector
from threading import get_ident

from psycopg import generators, pq
from psycopg.abc import PQGen
from psycopg.pq.abc import PGconn

from app.services.covering_parent_adapter import (
    CoveringTerminalNotDispatched,
    NativeTerminalResult,
    RootCommand,
    RootOperation,
)
from app.services.covering_request_budget import CoveringDeadlineExceeded
from app.services.covering_target_transaction import CoveringRootOutcomeUnknown


def exchange_root_terminal(
    pgconn: PGconn, *, captured_root: object, operation: RootOperation,
    remaining: Callable[[], float],
    mark_dispatch: Callable[[], None],
) -> PQGen[NativeTerminalResult]:
    """Run inside the port's joined owner and deadline for an already drained root."""
    if operation.root is not captured_root:
        raise CoveringRootOutcomeUnknown()

    command = operation.command
    if command is RootCommand.COMMIT:
        allowed = (pq.TransactionStatus.INTRANS,)
    elif command is RootCommand.ROLLBACK:
        allowed = (pq.TransactionStatus.INTRANS, pq.TransactionStatus.INERROR)
    else:
        raise CoveringRootOutcomeUnknown()
    if (
        pgconn.status != pq.ConnStatus.OK
        or pgconn.nonblocking != 1
        or pgconn.pipeline_status != pq.PipelineStatus.OFF
        or pgconn.transaction_status not in allowed
        or pgconn.is_busy()
    ):
        raise CoveringRootOutcomeUnknown()

    remaining()
    mark_dispatch()
    pgconn.send_query(command.value)
    results = yield from generators.execute(pgconn)
    if (
        len(results) != 1
        or results[0].status != pq.ExecStatus.COMMAND_OK
        or results[0].command_status != command.value
        or pgconn.status != pq.ConnStatus.OK
        or pgconn.transaction_status != pq.TransactionStatus.IDLE
        or pgconn.is_busy()
    ):
        raise CoveringRootOutcomeUnknown()
    return NativeTerminalResult(
        operation=operation,
        command_sent=True,
        command_tag=command.value,
        drained=True,
        idle=True,
    )

class JoinedParentDriver:
    """Drive one nonblocking PostgreSQL root on its owning worker."""

    def __init__(
        self,
        pgconn: PGconn,
        *,
        root: object,
        cutoff: Callable[[], bool],
        retire_local: Callable[[], bool],
    ) -> None:
        self._pgconn = pgconn
        self._root = root
        self._cutoff = cutoff
        self._retire_local = retire_local
        self._owner = get_ident()
        self._busy = False
        self._closed_to_work = False

    def finish(
        self, operation: RootOperation, *, remaining: Callable[[], float]
    ) -> NativeTerminalResult:
        if get_ident() != self._owner or self._busy or self._closed_to_work:
            raise CoveringRootOutcomeUnknown()
        dispatched = False

        def mark_dispatch() -> None:
            nonlocal dispatched
            # A send call can fail after libpq accepted bytes.
            dispatched = True

        self._busy = True
        exchange = exchange_root_terminal(
            self._pgconn, captured_root=self._root, operation=operation,
            remaining=remaining, mark_dispatch=mark_dispatch,
        )
        try:
            return self._drive(exchange, remaining)
        except CoveringDeadlineExceeded:
            if not dispatched:
                raise CoveringTerminalNotDispatched() from None
            raise CoveringRootOutcomeUnknown() from None
        finally:
            exchange.close()
            self._busy = False

    def _drive(
        self,
        exchange: PQGen[NativeTerminalResult],
        remaining: Callable[[], float],
    ) -> NativeTerminalResult:
        fileno = self._pgconn.socket
        try:
            mask = next(exchange)
            with DefaultSelector() as selector:
                while True:
                    if (
                        mask not in (EVENT_READ, EVENT_WRITE, EVENT_READ | EVENT_WRITE)
                        or self._pgconn.socket != fileno
                    ):
                        raise CoveringRootOutcomeUnknown()
                    selector.register(fileno, mask)
                    try:
                        ready = selector.select(remaining())
                    finally:
                        selector.unregister(fileno)
                    if ready:
                        remaining()
                        mask = exchange.send(ready[0][1])
        except StopIteration as completed:
            return completed.value

    def cut_off_frontend(self) -> bool:
        self._closed_to_work = True
        return get_ident() == self._owner and not self._busy and self._cutoff() is True

    def retire(self) -> bool:
        self._closed_to_work = True
        return get_ident() == self._owner and not self._busy and self._retire_local() is True
