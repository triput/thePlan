"""Module map for the W2b Update Schedule pipeline.

Flow: ``replan`` → ``candidates`` → ``ups`` → ``dependencies`` → ``placement``
with ``horizon`` bounds and ``busy_map`` for immovable intervals.

Candidate set: incomplete tasks with remaining duration > 0; **exclude
effective ``manual`` as well as ``bundle``** from auto-placement
(``effective_schedule_style``: task → project → epic → user default).
Manual/pinned blocks for those tasks remain OK. ADR-006 / DEF-014.

**Future:** a dedicated compose worker service could run ``run_replan`` outside
the API process (same DB contract, poll ``schedule_runs``). v1 uses an
in-process async thread per ADR-006; no second container yet.
"""
