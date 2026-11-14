# Case inventory — I01/I02 fixture prep REVISE2-corrected7

## I01
- I01-C01 — Happy multi-target; hex-safe distinct inverted UUIDs (actual tokens i01c01); production-sorted subscription→calendar script; reversed request_ids via `assert_ordering_request_ids` (already-sorted refuses); T_plan window; success_at=T_plan; token_expiry=T_plan+7d; full scheduling_ready; revision/trust coherence from live response observations; `assert_transport_coverage_observations`
- I01-C02 — Exact wrong-owner 422 CALENDAR_SUBSCRIPTION_NOT_ELIGIBLE; Bearer 200 with auth_telemetry_admitted
- I01-C03 — Count-specific 422: subscription_ids loc + too_short (0) / too_long (21); 503 NOT_CONFIGURED for 1 and 20 unbound
- I01-C04 — Unbound default; 503 CALENDAR_REFRESH_NOT_CONFIGURED
- I01-C05 — Assessment error sanitization via domain-bound `_assemble_final_assessment` replace only
- I01-C06 — Native lost-ack via dual-peer + case-owned tls_ack_gate (I01-C06.*); idempotent stop_gate retirement; `load_c06_gate_receipt` evidence validator
- I01-C06-MAP — Mapping control only (direct CoveringRootOutcomeUnknown); not a substitute for lost-ack observations
- I01-C07A — Oversized ingress >16KiB; 413; worker_entry_count=0 and checkout_count=0
- I01-C07B — Independent ingress vs worker budget object identities via `assert_budget_identity_observations`; exact 200
- I01-C08 — ControllableClock advance after budget construction; pre-ownership 504 DEADLINE_EXCEEDED
- I01-C09 — check_admission hold; actual ASGI http.disconnect; monitor_observed via retained/joined observe thread (`retire_monitor_observation`); `_next_receive_message` accounts every child outcome including late successful peers (explicit refusal), peer errors under primary (secondary), and cancellation-before-selection with already-done failing peer retained as secondary without replacing cancellation; cancellation provenance CoveringBudgetStopped PLUS ApiError 503/UNKNOWN; reject asgi_result.error / missing result; zero post-disconnect outbound; bounded direct ASGI driver; poster/injector/monitor join on every path
- I01-C10 — Distinct planted UUIDs from C01 (token i01c10); production-ordered script; synthetic provider label via `assert_transport_coverage_observations`

## I02
- I02-C01 — Advisory lock contention; admit_mutation success-only commit; retire_mutator failure wake-up; `assert_intended_subscription_diagnostic`; `assert_i02_lock_observations`; `select_i02_primary` promotes only worker *operational* cause over owner generics; worker `factory.close` is cleanup secondary (owner-primary + worker-close preserves owner; worker-primary + observer-close preserves worker); `run_verification_query_with_close` dual-fault primary preservation; cleanup-only still rejects PASS

## Expected UNKNOWN (runner-config)
- N06, N07 (native; unchanged)
- I01-C06

## Lifecycle
- PASS only after successful teardown; cleanup/alias/binding restoration failures fail the attempt
- Teardown SuiteStop does not replace already-captured primary failure
- Gate/injector/poster/monitor-observe: one bounded retirement each; unjoined work stops suite and forbids alias restore

## Corrected5 harness deltas retained (fake-only; authored not executed)
- Launcher reader ownership/outcome accounting (join `is_alive`; UNKNOWN on live/incomplete/error; overflow interrupt; kill/wait secondary evidence; disclosed timeout/retirement limits)
- N14 `SharedTransportScript.take.__globals__` patch visibility + separate class `__module__/sys.modules` identity

## Corrected6 harness deltas retained (fake-only; authored not executed)
- Choice B: disclose Windows ProactorEventLoop internal wakeup sockets (loopback-only; concurrent bound 2; N11 sequential 3 asyncio.run cycles); not literally no sockets (Dex p1794366344 / consolidated p1794366450)
- Any collection interrupt/error (incl. `proc_wait_error` with `capture_stop=None`) requires explicit non-None child-exit confirmation before result validation or `child_exited_normally` (Dex p1794366621)
- Retirement total reconciled to 45s (30+5+2×5); distinct from outer-admission deadline (Dex p1794366987)

## Corrected7 harness deltas (fake-only; authored not executed)
- Primary collection/wait error or unexpected collection interrupt prevents result admission/PASS even when child exit later proves 0 with a valid-looking result file; pe retained as primary; no retry (Dex p1794367441)
- Receipt pins `child_pid` at Popen success plus executable/argv/start timestamp for read-only custody; no process enumeration, retry, fallback, or new cleanup authority (Dex p1794367500)
- Tip message IDs reconciled: p1794366621, p1794366344, p1794366450, p1794366987, p1794367441, p1794367500
