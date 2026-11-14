# BODY-STALL fixture design decision

Recommendation: approve one bounded BODY-STALL fixture design, then prepare its packet under the existing authoring lane. No execution is requested.

The present fixture cannot witness the production deadline: its peer exits at120seconds, before the210second work guard, and records an error even when the runner intentionally retires the stall. Matt's designD71FC4D9/addendum265F3EB4 and Dex source/reviewFC8A470E/1C9BE5E1 support the diagnosis.

Approve a clean, explicitly recorded retired exit only when the owning runner sets the stop event during a scripted header/body stall. A peer deadline still raises and fails the case. Preserve no-worker-error and joined-retirement checks; no T03 negative-TLS tolerance is imported. Record peer start/deadline, stall entry/exit and exit reason, with finite typed numbers/enums only. No new exception messages, public status fields, credentials or raw payloads.

For the new NP-T04-BODY-STALL case only, propose a240second peer allowance, within the peer's existing1..240 source limit, instead of the earlier235 proposal. This is future configuration/design approval, not permission to invoke240seconds. Existing cases retain120seconds. The future exact launch card must disclose240peer/5join and actual runner/suite/PKI/capture limits. Production210work/240request/30cleanup clocks and600second plan validity remain unchanged.

Preparation scope stays within named roles4runner,5suite,7peer,8transcript,13checker and associated finite data; reuse roles14–16 unchanged where possible. No application, host Docker helper, sanitizer or PKI behavior change. Preserve all predecessors and failures. Prepare exact source diffs, manifests and a separately held fake-verification packet; return commands/hashes. No imports, parsing, compilation, tests, helper invocation, certificate generation, sockets, Docker, database, installation or native run.

Exact intended stimulus: two normal identity exchanges then first event GET on cal-ms-default/calendarView with exact seed-derived query. Send valid headers/positiveContent-Length and withhold body. Real monotonic clock required. Original client must raise CoveringDeadlineExceeded; publicHTTP200 failed first import row/covering_provider_read_failed and second deadline-preflight row; zero later provider/target admission and no assessment. Require known parent rollback, explicit recorder persisted-or-known-cleanup-refusal disposition, unchanged credentials/no minted coverage, bounded joined peer without error.

Measured success predicate: same-process monotonic P0<B0; W=B0+210<P_dl=P0+240; stall entry<W; W<=client_exception_time<response_time<retirement_call<stall_exit<P_dl; exit retired. Any missing value, peer deadline exit, wrong client/public/native outcome, unexpectedUNKNOWN, unjoined resource or failed inequality STOPs. Selector50ms polling is not a wall-time guarantee. PKI45, work210/request240/cleanup30 and join5 are nominal phase allowances with OS/process exclusions; setup/measurement remain within outer600runner/900suite supervision. No undefined epsilon.

This increment does not close the five-case T04 family. HEADER-STALL, actual ASGI DISCONNECT, pre-dispatch ingress DEADLINE and native client PARTIAL-SEND gaps remain separately retained. The post-ownership deadline result is mandatory; it is not replaced by a simpler ingress504.

The three prior T05fake/MSrefreshfake/T03D1 decisions remain independent. One-shot invalid-grant authority is consumed. Endpoint stays unbound; every execution and state-changing failure cleanup keeps its gate.

Signed: Dex