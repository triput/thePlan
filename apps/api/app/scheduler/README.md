"""Module map for the W2b Update Schedule pipeline.

Flow: ``replan`` → ``collect`` → ``calculate`` → ``apply`` (F3 shared pipeline).
``collect`` loads candidates, deps, busy, and excluded tasks; ``calculate``
proposes blocks + reason facts without persisting; ``apply`` wipes unpinned
horizon blocks, writes blocks, task status, and ``schedule_task_outcomes``
via ``persist_calculation_outcomes`` (input snapshot + fingerprint,
Alembic ``023_schedule_outcome_provenance``). Explanation GETs compare snapshot v2 on read and never replan: duration,
deadline, map/style, dependency edges, pins, project daily cap,
timezone/horizon/workweek, lifecycle, immovable busy, prerequisite state,
and due/soft target. Deferred to W3: priority/UPS and time-map overrides.
Legacy modules: ``candidates``, ``ups``, ``dependencies``, ``placement``,
``horizon``, ``busy_map``.

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
