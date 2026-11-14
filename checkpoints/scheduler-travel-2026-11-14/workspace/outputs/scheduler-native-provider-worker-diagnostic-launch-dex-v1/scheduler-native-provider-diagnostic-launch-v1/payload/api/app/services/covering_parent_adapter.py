"""Admission policy for a covering-only PostgreSQL parent adapter."""

from __future__ import annotations

import socket
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, ExitStack, contextmanager
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from sqlalchemy.orm import Session

from app.services.covering_request_budget import (
    CoveringDeadlineExceeded,
    CoveringRequestBudget,
)
from app.services.covering_target_transaction import (
    CoveringFailureAdmissionExpired,
    CoveringRootOutcomeUnknown,
    RootOutcome,
)


class CoveringTerminalNotDispatched(Exception):
    """The deadline expired before the driver attempted to send the command."""


class RootCommand(Enum):
    COMMIT = b"COMMIT"
    ROLLBACK = b"ROLLBACK"


@dataclass(frozen=True, eq=False)
class RootOperation:
    root: object
    sequence: int
    command: RootCommand


@dataclass(frozen=True)
class NativeTerminalResult:
    operation: RootOperation
    command_sent: bool
    command_tag: bytes
    drained: bool
    idle: bool


class ParentDriver(Protocol):
    """Native port for one captured root, driver and joined worker."""

    def finish(
        self, operation: RootOperation, *, remaining: Callable[[], float]
    ) -> NativeTerminalResult:
        """Use the live budget before dispatch and on every native wait."""
        ...

    def cut_off_frontend(self) -> bool:
        """Prevent new PostgreSQL writes before unwinding or driver close."""
        ...

    def retire(self) -> bool:
        """Release only the captured driver, without reconnect or reset SQL."""
        ...


def cut_off_socket_writes(owned_socket: socket.socket) -> bool:
    """Cut off writes on the exact live socket held by the native port."""
    try:
        owned_socket.shutdown(socket.SHUT_WR)
    except OSError:
        return False
    return True


class CoveringParentAdapter:
    """Resolve one root and admit at most one distinct failure checkout."""

    def __init__(
        self,
        *,
        root: object,
        driver: ParentDriver,
        budget: CoveringRequestBudget,
        failure_session: Callable[[Callable[[], float]], AbstractContextManager[Session]],
    ) -> None:
        self._root = root
        self._driver = driver
        self._budget = budget
        self._cleanup_stack = ExitStack()
        self._cleanup_started = False
        self._active = False
        self._entered = False
        self._failure_session = failure_session
        self._sequence = 0
        self._flush_armed = False
        self._flush_operation: RootOperation | None = None
        self._acknowledged: RootOutcome | None = None
        self._finished = False
        self._retired = False
        self._retirement_attempted = False
        self._failure_used = False
        self._stopped = False
        self._cut_off = False

    @contextmanager
    def target_scope(self) -> Iterator[CoveringParentAdapter]:
        """Own the budget scope across the importer, root, retirement and recorder."""
        if self._entered:
            raise RuntimeError("covering parent scope already used")
        self._entered = self._active = True
        try:
            with self._cleanup_stack:
                try:
                    yield self
                    if not self._retired:
                        raise CoveringRootOutcomeUnknown()
                except BaseException:
                    self.abort()
                    raise
        finally:
            self._active = False

    def _require_active(self) -> None:
        if not self._active:
            raise RuntimeError("covering parent scope is not active")

    def _begin_cleanup(self) -> None:
        if not self._cleanup_started:
            self._cleanup_stack.enter_context(self._budget.cleanup())
            self._cleanup_started = True

    @property
    def acknowledged_outcome(self) -> RootOutcome | None:
        return self._acknowledged

    def _operation(self, command: RootCommand) -> RootOperation:
        self._sequence += 1
        return RootOperation(self._root, self._sequence, command)

    def _unknown(self) -> RootOutcome:
        if not self._stopped:
            self._stopped = True
            try:
                self._budget.stop()
            finally:
                if not self._retired:
                    try:
                        self._cut_off = self._driver.cut_off_frontend() is True
                    except Exception:
                        self._cut_off = False
        return RootOutcome.UNKNOWN

    def _acknowledge(
        self, operation: RootOperation, result: NativeTerminalResult
    ) -> RootOutcome:
        if (
            type(result) is not NativeTerminalResult
            or result.operation is not operation
            or result.command_sent is not True
            or result.command_tag != operation.command.value
            or result.drained is not True
            or result.idle is not True
        ):
            return self._unknown()
        self._acknowledged = (
            RootOutcome.COMMIT_ACKNOWLEDGED
            if operation.command is RootCommand.COMMIT
            else RootOutcome.ROLLBACK_ACKNOWLEDGED
        )
        return self._acknowledged

    def arm_flush_rollback(self) -> None:
        """Arm the exact root before importer apply begins."""
        self._require_active()
        if self._flush_armed or self._flush_operation or self._finished or self._stopped:
            raise RuntimeError("covering flush rollback cannot be armed")
        self._flush_armed = True

    def begin_flush_rollback(
        self, root: object, *, known_error_drained: bool, savepoint_active: bool
    ) -> RootOperation:
        """Admit only the ORM rollback of this root after a drained SQL error."""
        self._require_active()
        if (
            not self._flush_armed or self._finished or self._stopped
            or root is not self._root or not known_error_drained or savepoint_active
        ):
            self._unknown()
            raise CoveringRootOutcomeUnknown()
        self._flush_armed = False
        try:
            self._begin_cleanup()
            self._budget.cleanup_remaining()
        except Exception:
            self._unknown()
            raise CoveringRootOutcomeUnknown() from None
        self._flush_operation = self._operation(RootCommand.ROLLBACK)
        return self._flush_operation

    def flush_rollback_remaining(self, operation: RootOperation) -> float:
        self._require_active()
        if self._stopped or operation is not self._flush_operation or self._acknowledged is not None:
            self._unknown()
            raise CoveringRootOutcomeUnknown()
        return self._budget.cleanup_remaining()

    def observe_flush_rollback(self, result: NativeTerminalResult) -> None:
        """Capture the automatic rollback before returning to the ORM."""
        self._require_active()
        operation = self._flush_operation
        if self._stopped or self._finished or operation is None or self._acknowledged is not None:
            self._unknown()
            raise CoveringRootOutcomeUnknown()
        if self._acknowledge(operation, result) is RootOutcome.UNKNOWN:
            raise CoveringRootOutcomeUnknown()

    def finish_root(self, *, commit: bool) -> RootOutcome:
        self._require_active()
        if self._stopped or self._finished:
            return self._unknown()
        self._finished = True
        self._flush_armed = False
        if self._flush_operation is not None:
            if not commit and self._acknowledged is RootOutcome.ROLLBACK_ACKNOWLEDGED:
                return self._acknowledged
            return self._unknown()
        command = RootCommand.COMMIT if commit else RootCommand.ROLLBACK
        operation = self._operation(command)
        try:
            remaining = self._budget.work_remaining
            if command is RootCommand.ROLLBACK:
                self._begin_cleanup()
                remaining = self._budget.cleanup_remaining
            result = self._driver.finish(operation, remaining=remaining)
        except CoveringTerminalNotDispatched:
            if command is not RootCommand.COMMIT:
                return self._unknown()
            return self._rollback_expired_commit()
        except Exception:
            return self._unknown()
        return self._acknowledge(operation, result)

    def _rollback_expired_commit(self) -> RootOutcome:
        """Resolve the active root when COMMIT never reached the send boundary."""
        operation = self._operation(RootCommand.ROLLBACK)
        try:
            self._begin_cleanup()
            result = self._driver.finish(operation, remaining=self._budget.cleanup_remaining)
        except Exception:
            return self._unknown()
        if self._acknowledge(operation, result) is RootOutcome.ROLLBACK_ACKNOWLEDGED:
            return RootOutcome.COMMIT_DEADLINE_ROLLBACK_ACKNOWLEDGED
        return RootOutcome.UNKNOWN

    def _retire_once(self) -> bool:
        if not self._retirement_attempted:
            self._retirement_attempted = True
            try:
                self._retired = self._driver.retire() is True
            except Exception:
                self._retired = False
        return self._retired

    def retire_parent(self) -> bool:
        self._require_active()
        if self._stopped or not self._finished or self._acknowledged is None:
            self._unknown()
            return False
        # COMMIT also needs bounded local retirement. Keep that charge in the
        # same request cleanup allowance used by rollback and the recorder.
        try:
            self._begin_cleanup()
            self._budget.cleanup_remaining()
        except Exception:
            self._unknown()
            return False
        if not self._retire_once():
            self._unknown()
        return self._retired

    def abort(self) -> bool:
        """Latch UNKNOWN before local close; quarantine if cutoff fails."""
        self._unknown()
        if self._cut_off:
            self._retire_once()
        return self._retired

    @contextmanager
    def open_failure_session(self) -> Iterator[Session]:
        self._require_active()
        if (
            self._stopped or not self._retired or self._failure_used
            or self._acknowledged is not RootOutcome.ROLLBACK_ACKNOWLEDGED
        ):
            raise CoveringRootOutcomeUnknown()
        self._failure_used = True
        try:
            self._budget.cleanup_remaining()
        except CoveringDeadlineExceeded:
            # This check is before the only checkout call.
            raise CoveringFailureAdmissionExpired() from None
        with self._failure_session(self._budget.cleanup_remaining) as session:
            yield session
