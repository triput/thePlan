# Matt → Dex: T04 BODY-STALL addendum (items 1–4; source-only)

November 13, 2026. This responds to `Matt-thePlan-Scheduler-T04-Body-Stall-Design-Addendum-2026-11-13.md` (`CE778F137A9E59D030E6463868D3F55A082FED6DC3F8C8AB50D0B162A72D5A27`) and your review `T04-Design-Peer-Reconciliation-2026-11-13.md` (`FC8A470E1918A6FDFA9CAAC46CDE4C87EE08B839BC5FDECCDF97B3514BD09D23`). It amends my `D71FC4D9` for BODY-STALL only.

**Method:** source reading and document authoring only. No imports, AST, compilation, tests, edits or execution, and no subagents.
- **Labels:** [F] fact at the cited line; [I] inference; [U] unproved.
- **Every outcome below is a candidate oracle for a future run.** None is observed.
- **Baseline unchanged:** `F682D755`. New source files cited here:
  - `covering_refresh.py` `0605E983F728D99D90BD50CCB85A6FC71509FCFBC0ADF50B7C2E3280E3603E5E`;
  - `covering_refresh_failure.py` `DCDF16ACF79F05D2EEB54CE1D4E6F4ED23F0D136E15571B444050EAD8B931920`.
  
  The other hashes are as in `D71FC4D9`.
- **Accepted:**
  - the 50 ms poll is a per-call selector bound, not a scheduling guarantee;
  - no epsilon in success;
  - the 235 s peer limit runs from the peer's own start;
  - PARTIAL-SEND is deferred and unproved, with no new abort operation and the TOKEN mapping untraced;
  - no D1 import.

## 1. Finite timing predicate (common monotonic basis)
**All clocks are the same process's `time.monotonic`.**
- The peer worker runs in the runner process and uses `monotonic` (`np_provider_peer.py` l.504) [F].
- The ingress budget uses `clock=monotonic` (`covering_ingress.py` l.35/43; runner `build_i01_asgi_app(..., clock=monotonic)`, refresh l.1497–1500) [F].

**Measured instants. Each is recorded by the fixture; none is mutated:**

| Symbol | Source | Status |
|---|---|---|
| `P0`, `P_dl` | peer start and peer deadline = `monotonic()` at `execute_script` + 235 (l.504). Today `deadline` is a local. **R-PEER-1** would store it in `life` | proposed |
| `B0`, `W`, `R` | `W = budget._work_deadline` (= B0+210, budget l.24), `R = budget._request_deadline` (= B0+240, l.23), read from the captured ingress budget (`captured_contexts[0].budget`, the refresh pattern at l.1527–1531). A read only; the private attributes are disclosed | [F] for the attributes; the read is proposed |
| `S_in` | peer `stall_body` entry (R-PEER-1) | proposed |
| `X_t`, `X_cls` | client exception time and class, recorded by the runner's `counted_request` wrapper **before** any caller conversion, the same pattern MS-INVALID uses at l.2078–2090. The wrapper re-raises unchanged, so product behavior and public disclosure are unchanged | [F] pattern |
| `T_resp` | runner instant right after `client.post` returns | proposed |
| `T_ret` | runner instant just before `_retire_selected_peer_then_observe` | proposed |
| `S_out`, `S_why` | peer stall exit time and reason ∈ {`retired`, `deadline`} (R-PEER-1) | proposed |

**Success requires every one of these strict inequalities on measured values:**
- **(a)** `P0 < B0`. The peer starts before the POST: `peer.start_background` precedes it (refresh l.1440).
- **(b)** `W < P_dl`. The peer outlives the measured work deadline; otherwise STOP before any classification.
- **(c)** `S_in < W`. The stall is entered before the deadline.
- **(d)** `W ≤ X_t`. The original client deadline fires no earlier than the guard. `_remaining` raises only when `deadline − clock() ≤ 0`, so `X_t ≥ W` follows from source (budget l.48–52) [F].
- **(e)** `X_t < T_resp < T_ret < S_out < P_dl`.
- **(f)** `S_why == "retired"`.
- **(g)** `X_cls == ("exception", "CoveringDeadlineExceeded", "app.services.covering_request_budget")`, recorded exactly once, at the event exchange (inventory position 3).

**There is no upper bound of the form `X_t ≤ W + ε`.** The lateness of `X_t` past `W` is recorded as data only (poll and scheduling latency) and is bounded by (e) through the measured `P_dl`.
- **Peer deadline STOPs:** any `S_why == "deadline"`, or a missing instant.
- **Supervisor kill:** if the 600 s runner kill fires, no receipt exists, which is a STOP.
- **Margin disclosure:** `P_dl − W = 25 − (B0 − P0)`. If setup between peer start and the POST exceeds 25 s, (b) fails closed. Choosing 240, the maximum allowed by l.502, would give 30 s. That's part of the Q-D limit decision.

## 2. Corrected allotments (BODY-STALL; DISCONNECT row corrected)
**Origins:** runner start `T_r`; peer start `P0`; budget start `B0`.
- **Source-derived maxima:**
  - PKI ≤ 45 (30 + 5 + two 5 s), before `P0`;
  - peer life ≤ 235 from `P0`;
  - request ≤ 240 from `B0`;
  - the cleanup allowance ≤ 30 is **inside** the 240 (budget l.60–62), not added to it;
  - retirement join ≤ 5 after `T_ret`.
- **Not separately bounded by its own clock:** DB provisioning, the seed, before/after measurement sessions, app construction, response serialization and container work. These are bounded only by the runner's 600 s and the suite's 900 s.
- **BODY-STALL maximum from `T_r`:**
  - `≤ 45 (PKI) + (B0 − T_r − 45, unbounded setup) + 240 (B0 → response) + 5 (join)`, plus post-response measurement;
  - the peer window overlaps `[P0, P_dl] ⊇ [B0, T_ret]`, so it is not additive.
  - **Clock-bounded subtotal: 290 s, plus unbounded setup and measurement, within the 600 s runner.**
- **BODY-STALL typical estimate (not a bound):** about 230–260 s. That's PKI (typically under 45) + about 210 + small cleanup + under 1 s join + setup.
- **DISCONNECT (corrected; not this increment):**
  - before the checkpoint: PKI ≤ 45 + setup;
  - checkpoint wait ≤ the peer's remaining life (≤ 235 from `P0`), with an unreached checkpoint giving a peer deadline STOP;
  - after the disconnect: cleanup ≤ 30 (within 240 from `B0`) + join ≤ 5;
  - **clock-bounded maximum: 45 + 235 + 5 = 285** (the cleanup overlaps the peer window);
  - **floor even with an immediate checkpoint: ≥ 45 + cleanup used + join, plus setup.** My earlier "about 60 s" is withdrawn.
- **Exclusions, unchanged:** startup, outer, file, hash, receipt and OS latency; no separate outer timeout; the inherited CLI kill has no wait or daemon-cancellation guarantee. The 32-command / 1 MiB caps are unchanged.

## 3. DEADLINE scope (mandatory retention)
- **The ingress witness is an in-process ASGI driver.** It is not a bound HTTP endpoint and not a provider-transport deadline. The withheld-body 504 (`covering_ingress.py` l.48, l.61–62) witnesses **only** the pre-dispatch boundary.
- **The shared-budget post-ownership DEADLINE obligation stays open,** and its evidence is **mandatory** from BODY-STALL's native result:
  - target 1 converted by the event pull;
  - acknowledged rollback under the cleanup budget;
  - target 2's static `CALENDAR_REFRESH_DEADLINE_EXCEEDED` admission refusal (`covering_domain_dispatch.py` l.190–199);
  - no assessment (l.248–259).
  
  **Neither witness alone closes T04-DEADLINE,** and choosing the easier boundary is not a substitution.

## 4. BODY-STALL exact candidate inventory
**Lineage:** the NONEXPIRED vertical, with two subscriptions in the declared order `cal-ms-default` then `cal-np-other`, and no OAuth.
- **Peer script:** exactly 3 connections.
  - Indices 0–1 are the unchanged NONEXPIRED identity scripts.
  - **Index 2** is `GET /v1.0/me/calendars/cal-ms-default/calendarView` with the **exact query** declared. That is the production params `startDateTime`/`endDateTime` (`_iso_z` of the effective window), plus `$top` if the caller sets it (`microsoft_calendar.py` l.817–825; URL l.122; query append `covering_http_transport.py` l.307–311) [F]. The literal string is derived at authoring from the seeded window, so `query_verified` becomes true.
  - It sends the head only, with a valid `Content-Length` greater than 0, then `stall_body` with R-PEER-1.

**Candidate oracles. Any deviation is a STOP:**

| Layer | Exact expectation | Basis |
|---|---|---|
| Client inventory | `[(GET,identity),(GET,identity),(GET,event)]`; OAuth 0 | NONEXPIRED order [F]; stall at index 2 [design] |
| Client outcomes | `[response, response, ("exception","CoveringDeadlineExceeded","app.services.covering_request_budget")]` | guard [F]; recorded pre-conversion [F pattern] |
| Peer | admitted = served = 3; no 4th accept; exchanges 0–1 complete with orderly close; exchange 2: `request_received` True, `response_sent` True, phase `stall_body`, `bytes_sent` = len(head + CRLFCRLF), `S_why == retired` | `np_provider_peer.py` l.367–377 [F] + R-PEER-1 |
| Public | HTTP 200; `overall_outcome == "failed"` (attempted 1, ok 0: `covering_refresh.py` l.159–162) | [F] |
| Row 1 (cal-ms-default) | `phase "import"`, `status "failed"`, `cause "covering_provider_read_failed"`, `upserted 0` (`_result_row` l.134–148; cause l.133/648–655 in import) | [F] |
| Row 1 `preflight_effects` | exactly `prepared.preflight_effects` (import failed-result block l.985–997) for the planted seed; **the literal value is derived at authoring**, not guessed | [F source], value [U] |
| Row 2 (cal-np-other) | `phase "preflight"`, `status "preflight_rejected"`, `preflight_code "CALENDAR_REFRESH_DEADLINE_EXCEEDED"`, `cause` None, effects `[]` (`_static_preflight_result` l.433–447) | [F] |
| Action summary | requested 2, preflight_rejected 1, import_attempted 1, import_ok 0, import_failed 1 (`covering_domain_dispatch.py` l.156–159) | [F] |
| Coverage / readiness | `_fail_closed_coverage_action` (`all_requested_covering_ok` False: `covering_refresh.py` l.462–474); readiness `assessment_error == "CALENDAR_REFRESH_DEADLINE_EXCEEDED"`; `scheduling_revision_at_end` None; bumped False (dispatch l.141–146, l.161–162) | [F] |
| Native TOKEN | one `ROLLBACK_ACKNOWLEDGED`, `token_rollback_ack` True, `commit_requested` False, for target 1 only; target 2 is refused before token read (l.193–199) | [I]; observer as NONEXPIRED |
| Native PARENT | `finish_root(commit=False)` → ROLLBACK under `cleanup_remaining` (`covering_parent_adapter.py` l.232–236) = `ROLLBACK_ACKNOWLEDGED`, else UNKNOWN (`covering_target_transaction.py` l.132–133) | [F path], [U native] |
| Failure recorder | **exactly one of:** (i) persisted through `_commit_failure` → `_write_failure_state(cause="covering_provider_read_failed")` (`covering_refresh_failure.py` l.325); or (ii) `refuse_reason "cleanup_deadline_exceeded"` (`covering_target_transaction.py` l.147–156). **An overwrite refusal (`covering_refresh_failure.py` l.274) is a STOP for this fresh seed.** The disposition is reported, not chosen | [F] |
| Persisted state | credential semantics unchanged; no coverage success minted for either subscription; for (i), target 1's failure fields carry the cause, otherwise unchanged; target 2 unchanged | [I] |
| Timing | §1 (a)–(g) | measured |
| Retirement | `retirement_attempted` mark → unchanged `_retire_selected_peer_then_observe` (joined True, `worker_error_kind` None); no `np-peer-` thread; exact-ID container cleanup on success only | [F] helper |

**STOP, always:**
- any 503 UNKNOWN or other public status;
- any other client exception class, or a second exception;
- any assessment;
- a TOKEN terminal for target 2;
- PARENT not acknowledged;
- any peer worker error or `deadline` exit;
- an unjoined worker;
- a missing instant;
- any inequality failing.

**Unproved until run:** the native terminal timing, the recorder disposition, `X_t − W`, and every row value.

## Minimal increment (unchanged recommendation)
- **R-PEER-1:** clean `retired` exit on `_stop` in the stall loop, keeping deadline-as-error; record `P_dl`, `S_in`, `S_out`, `S_why`.
- **R-TRANSCRIPT:** the 3-connection BODY-STALL script with the exact event path and query.
- **R-RUNNER:** the BODY-STALL body with the instants above.

These need a decision on the new operation, plus the Q-D (235/240) limit card for you to bring to Trish. HEADER-STALL and DISCONNECT follow at separately reviewed scope. PARTIAL-SEND is deferred and unproved. No requirement is closed; all 76 IDs are retained. Endpoint unbound; all holds stay.

Signed: Matt
