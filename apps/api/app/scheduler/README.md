"""Module map for the W2b Update Schedule pipeline.

Flow: ``replan`` → ``candidates`` → ``ups`` → ``dependencies`` → ``placement``
with ``horizon`` bounds and ``busy_map`` for immovable intervals.

**Future:** a dedicated compose worker service could run ``run_replan`` outside
the API process (same DB contract, poll ``schedule_runs``). v1 uses an
in-process async thread per ADR-006; no second container yet.
"""
