"""Module map for the W2b Update Schedule pipeline.

Flow: ``replan`` → ``candidates`` → ``ups`` → ``dependencies`` → ``placement``
with ``horizon`` bounds and ``busy_map`` for immovable intervals.

Candidate set: incomplete tasks with remaining duration > 0; **exclude
effective ``manual`` as well as ``bundle``** from auto-placement
(``effective_schedule_style``: task → project → epic → user default).
Manual/pinned blocks for those tasks remain OK. ADR-006 / DEF-014.

**Compose worker (W2c):** the ``scheduler`` service runs
``python -m app.scheduler.worker --poll``. It claims ``schedule_runs`` rows
with ``status=running`` (Postgres advisory lock) and calls ``run_replan``.
The API inserts the row and returns 202. Default ``SCHEDULE_DISPATCH=external``
does not execute in the API. ``SCHEDULE_DISPATCH=thread`` is the residual
in-process bridge for a process with no scheduler — do not combine it with
the scheduler service on the same database. Desktop sidecar / bare uvicorn
need this poller (or the thread bridge) or Update Schedule stays ``running``
until the 15-minute stale reclaim.
"""
