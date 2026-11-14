"""Monotonic request budget for the covering-only connector."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from time import monotonic


class CoveringDeadlineExceeded(Exception):
    """An admission window expired. The caller classifies dispatched work."""


class CoveringBudgetStopped(Exception):
    """The request has stopped admitting work."""


class CoveringRequestBudget:
    """Shared by one request owner from ASGI admission through teardown."""

    def __init__(self, clock: Callable[[], float] = monotonic, *, cancelled: Callable[[], bool] = lambda: False) -> None:
        self._cancelled = cancelled
        self._clock = clock
        started = clock()
        self._request_deadline = started + 240
        self._work_deadline = started + 210
        self._cleanup_left = 30.0
        self._cleanup_deadline: float | None = None
        self._stopped = False

    def stop(self) -> None:
        """Latch the stop before unwinding an unresolved operation."""
        self._stopped = True

    def check_admission(self) -> None:
        if self._cancelled():
            raise CoveringBudgetStopped()

    def work_remaining(self) -> float:
        self.check_admission()
        if self._stopped or self._cleanup_deadline is not None:
            raise CoveringBudgetStopped()
        return self._remaining(self._work_deadline)

    def cleanup_remaining(self) -> float:
        if self._stopped or self._cleanup_deadline is None:
            raise CoveringBudgetStopped()
        return self._remaining(self._cleanup_deadline)

    def _remaining(self, deadline: float) -> float:
        left = deadline - self._clock()
        if not left > 0:
            raise CoveringDeadlineExceeded()
        return left

    @contextmanager
    def cleanup(self) -> Iterator[None]:
        """Charge one serialized, fully classified cleanup scope."""
        if self._stopped or self._cleanup_deadline is not None:
            raise CoveringBudgetStopped()
        started = self._clock()
        self._cleanup_deadline = min(
            self._request_deadline, started + self._cleanup_left
        )
        try:
            self.cleanup_remaining()
            yield
        except BaseException:
            # Handle known role failures inside this scope after retirement.
            # An escaping failure must never reopen ordinary admission.
            self.stop()
            raise
        finally:
            ended = self._clock()
            elapsed = max(0.0, ended - started)
            self._cleanup_left = max(0.0, self._cleanup_left - elapsed)
            # Closing an already resolved scope must not replace its result.
            if ended >= self._cleanup_deadline:
                self.stop()
            self._cleanup_deadline = None
