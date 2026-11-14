# Actual subscription coverage measurement: unexecuted source contribution

The frozen v3 measurement helper reads covering_generation, covering_window_start/end and last_covering_success_at. None is mapped on the selected CalendarSubscription. Its getattr defaults consequently produce None and false even after a real successful refresh. This guarantees the after-state assertion cannot establish the intended transition.

This candidate changes only measure_subscription_coverage_state in the named mutable np_auth_seed role. It reads the actual coverage_window_start/end, coverage_success_at, coverage_active_generation and coverage_success_generation fields, without silent missing-attribute defaults. It preserves subscription ID and aggregate boolean keys consumed by the first body. Row evidence now uses actual model field names. Outside-function source is unchanged; original file and raw hashes are retained in Preparation-Receipt.json.

Source facts: payload/api/app/models/calendar.py defines the mapped fields; tests/support/assessment_sql_fixture.py:mark_covering_fresh writes those same fields. Their application bytes are not edited. This is source review, not database observation or verification PASS.

Jim should reconcile the patch in his fresh successor, update exact receipt/checker expectations and source pins, and add a meaningful extracted-helper control with fake rows exposing only actual mapped attributes. Require before null/false, after actual timestamp/window/generations and true; reject a mutant reading the invented old attribute. No dynamic import, compilation, check, database, socket or native operation was performed. No run authority is included.

Keep the distinction: a non-null success timestamp alone is a measurement, not a replacement for the production freshness predicate. The real response/final assessment and coherent generation/window evidence remain required. Do not weaken those assertions.

Also preserve bootstrap guard intent when adapting the passed runner: its old blanket JoinedTLS refusal was correct for a byte-fixture suite but cannot be copied into the new real-JoinedTLS claim. Admit only the bounded synthetic provider path through the existing reviewed route/CA/dial policy, while retaining ambient application/session/provider refusal and selected runtime/environment isolation.
