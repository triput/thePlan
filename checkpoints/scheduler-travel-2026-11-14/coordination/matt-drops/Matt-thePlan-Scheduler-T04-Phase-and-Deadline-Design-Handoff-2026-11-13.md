# Matt → Dex: T04 phase/deadline source design (proposal, no implementation)

November 13, 2026. This responds to `Matt-thePlan-Scheduler-T04-Phase-and-Deadline-Design-2026-11-13.md` (`256AB4599028B43BA5217ECA865B460588671362AD6CAB7FDA4C3ECC42D468EE`). Noted: `0F9AC362` is a receipt with no assignment; four Trish cards are pending; D1 is held; no T03 work is authored here.

**Method:** source reading, hashing and document authoring only.
- No imports, AST parsing, compilation, tests, helpers, sockets, PKI, Docker, edits or execution.
- **Subagents:** one bounded read-only Explore subagent extracted the requirement texts (§0). It ran no code. I did all source tracing myself.

**Labels:**
- **[F]** fact read at the cited line;
- **[I]** inference from source;
- **[U]** unproved, needs a run or a deeper trace.

## 0. Baseline and requirement sources
- **Baseline root:** `scheduler-native-provider-ms-refresh-retire-prep-matt-v1`. Manifest `F682D755584679CC31E25A3C1D99A2C64708CC5C83C0651C7C0072AEC1CB2BB4` verified 301/301; runner `1A95E834`, peer `BFB271D7`. It is prepared and unexecuted.
- **Cited payload files (SHA256):**

  | File | SHA256 |
  |---|---|
  | `covering_joined_https.py` | `760177767EA64A6129E788BA7828FBE998522706791E6CFC5DBB9C2D0C013427` |
  | `covering_http_transport.py` | `29CBD53C85E8D40185A5E7DF73DF85B752A34837D25FCD65DB6504AFB775B368` |
  | `covering_request_budget.py` | `D5C465CC8BACB83C49FCD8586BB84D5B32C12C113CB81386C6D715EBF7088975` |
  | `api/middleware/covering_ingress.py` | `FA6904A2CD7436D8D6E7F316D192654B6FE5CA1E9BC050DEADBAFA3D8932C68D` |
  | `covering_http_dispatch.py` | `5160780F4F13E450F19515560CF85EDCDCB5A7906FED99A7027AE8C93071D1FF` |
  | `covering_domain_dispatch.py` | `E73EFF6812A191F3F03431B98990BBF3C61D09D8398101AC804DBD2B2E7F6566` |
  | `covering_role_connector.py` | `C5BA15CDE276586CFFA2DE24A51E79F40CC6479D3A5A1D6663D23A20D930B288` |
  | `covering_target_transaction.py` | `8ADC67737002512BD66D87A6A874E6970250094BA1CF7FCE69E7A66B966A235A` |
  | `covering_parent_adapter.py` | `08129D4E451A449A8426E2B8F087C041D61AF45723A893D3F6135B7237B9FDE9` |
  | `covering_refresh_import.py` | `84F50367BC91E0368437B4CD6E6FA5FAC9A77E42A270F00E8FF1EC62BB25C339` |
  | `calendar_alias_canonicalize.py` | `A661FE9287E0BE086CCB070DF8F227D2449CA9B70303140A7E38B4015A71946F` |
  | `microsoft_calendar.py` | `6A52B10FE43A7781718BAE0AC69DA91CA7FB3B48B9534EB18D5C9C80E75DD6EF` |
  | `np_provider_transcript.py` | `BEDCCFD3C3E8F776C4EC0B3379F863E976C73AF350DD6AE8B308518AB4A47735` |
  | `np_suite.py` | `DAB88CB352189411EED6A2181417CB813D592406598D89192FF307E9081205A1` |
  | `i01_asgi_app.py` | `37667D5B18B341C47DE7DFB02DDB7440525832BEFD3E695CA0A1BA3CAB350F4B` |

- **Requirement sources:**
  - `Transport-Case-Inventory-Draft.md` (`e12f93b3…`): l.10, with l.3 requiring one exact ID per subcase;
  - `Transport-Proof-Matrix.md` (`e811bcb6…`): l.18 and l.29;
  - `Transport-Packet-Review-Requirements.md` (`d34f1a70…`): l.7, l.9, l.13 and l.18;
  - audit `Transport-Completion-Audit-Current.json` (`ed0f4b22…`): l.1018–1067, with all five `completion_unproven`;
  - `Deadline-Disconnect-Review.md` (`1f3588b9…`) and `C09-Disconnect-Oracle-Review.md` (`2bbb4f24…`).
  
  **There is no per-ID requirement text.** All five IDs share one family statement: "last admitted phase and send state; no later admission, no replay, bounded worker/resource retirement; actual caller classification; OAuth uncertainty differs from event rollback". The shared row also asks for "Stalled header/body, partial send, deadline expiry and caller disconnect under the shared request budget". The proposal below splits them as l.3 requires.
- **Registry declarations (`np_suite.py`):**

  | Case | Lines | Batch | Oracle | `expected_unknown` |
  |---|---|---|---|---|
  | HEADER-STALL | l.185–191 | B3 | `first_guard_header_phase_deadline` | False |
  | BODY-STALL | l.192–198 | B3 | `first_guard_body_phase_deadline` | False |
  | PARTIAL-SEND | l.199–206 | B4 | `joined_retirement_no_retry` | **True** |
  | DEADLINE | l.207–213 | B4 | `distinct_from_supervisor_kill` | False |
  | DISCONNECT | l.214–222 | B4 | `unknown_sanitized_not_abrupt_provider_eof` | **True** |

  None of the five has an implementation note; all are HOLD.
- **Retained conflict, resolved by your instruction:** `Deadline-Disconnect-Review.md` l.5 asked for "shorter fixture-controlled clocks". Your assignment and `np_suite` l.185–198 require production clocks. I follow production clocks and list no shorter clock.

## 1. Shared production mechanics (source facts)
- **Budget** (`covering_request_budget.py`):
  - at construction, request deadline = start + 240 (l.23) and work deadline = start + 210 (l.24) [F];
  - `work_remaining` (l.37–41) first calls `check_admission`, which raises `CoveringBudgetStopped` when the disconnect Event is set (l.33–35);
  - `_remaining` raises `CoveringDeadlineExceeded` when no time is left (l.48–52) [F];
  - `cleanup()` (l.55–78) charges a 30 s total serialized allowance capped by the request deadline. `cleanup_remaining` (l.43–46) **does not** check disconnection [F].
- **Budget ownership:** ingress constructs one budget per request, with `cancelled=disconnected.is_set` (`covering_ingress.py` l.43) [F].
- **Transport callback:** `CoveringHTTP.request` builds `transport_factory(peer, self.counter.remaining)` (`covering_http_transport.py` l.327) [F]. The NONEXPIRED/refresh bodies already prove that `counter.remaining` is `CoveringRequestBudget.work_remaining` bound to the ingress budget (refresh runner checks l.1548–1550; NONEXPIRED l.977–981) [F].
- **Earliest production guard for every JoinedTLS phase:**
  - `JoinedTLS.check()` (l.26–29) calls `remaining()`;
  - `ready()` (l.31–38) polls `select(min(check(), 0.05))`;
  - `send` (l.92–106) and `receive` (l.108–118) call `check()` before each attempt.
  
  So a stalled read or write surfaces as `CoveringDeadlineExceeded` (at about 210 s, within one 50 ms poll) or as `CoveringBudgetStopped` (disconnect) **from inside the JoinedTLS loop** [F]. No other production clock bounds a JoinedTLS stall [F, for this file].
- **Transport classification** (`covering_http_transport.py` l.372–379):
  - any exception on a `purpose=="oauth"` request with `transport.sent` set becomes a new `CoveringRootOutcomeUnknown` ("Token rotation may have occurred. No retry/replay") [F];
  - for GET (identity/event), the original exception propagates unchanged [F].
  - The `finally` (l.380–415) closes the response, then the transport (a local close, with no TLS unwrap: `covering_joined_https.py` l.120–127) [F].
- **`sent` semantics:** `JoinedTLS.send` sets `self.sent=True` **before** `sock.send` (l.97–98) [F]. It records attempted-send uncertainty, not a byte count (`np_suite` l.11).

## 2. Q1: header and body stall
### Fixture facts
- **The peer stall is bounded by the peer's own deadline, not production's.**
  - `execute_script(seconds)` sets `deadline = monotonic() + seconds`, with seconds limited to 1..240 (`np_provider_peer.py` l.500–504) [F].
  - Runner `PEER_SECONDS_DEFAULT = 120` (`np_runner_entry.py` l.38), and runner-config `peer_seconds` is 120 [F].
  - The `stall_header` / `stall_body` loops end on `deadline or _stop` and then **raise `PeerLifecycleError`** (l.360–377) [F].
  - The worker records `_error` (l.531–538) and its `finally` calls `_close_client()`, which runs `tls.close()` without unwrap (l.250–265) [F].
- **Existing stimulus ends first (answer to Q1's "which ends first"):** at 120 s < 210 s the peer abandons the stall and drops the connection [F].
  - The client then sees an EOF-class read error, not `CoveringDeadlineExceeded` [I].
  - The class is likely `ssl.SSLEOFError` given `suppress_ragged_eofs=False` (l.62). That is unproved and is the same open question as the T05 client-cause diagnostic [U].
  - **The worker also records a `PeerLifecycleError`,** which the selected retirement helper refuses (`worker_error_kind is not None`) [F]. **So under current limits, no stall case can witness the production deadline, and it STOPs at retirement.**
- **Defect in the existing `T04-HEADER-STALL` script (`np_provider_transcript.py` l.402–410)** [F]:
  - it has `recv_request`, then `close(stall_header)`, and no `send_response` step;
  - `stall_header` is implemented **only** inside `_send_response` (`np_provider_peer.py` l.360–365). `_run_one_connection` calls `_send_response` only for `send_response` steps (l.486–487);
  - so the `close` step goes to `_close_connection`, whose default branch runs `tls.close()` immediately (l.442–446). As written, the script **never stalls**.
- **Both stall scripts use the path `GET /`** (l.405–418). The production Graph caller never requests `/`, so `_recv_request` would fail with "exact transcript path mismatch" (l.346) before any stall [F].
- **Stop-path problem:** even if the peer outlives 210 s, the runner's later `retire_owned` sets `_stop`. The stall loop then exits and **raises** (l.365 / l.377), recording a worker error [F]. Accepting that error would need a worker-error tolerance policy, which is D1's subject. **I don't import D1;** I propose a narrow peer change instead (§6, R-PEER-1).

### Production caller paths
Using the passed NONEXPIRED lineage, the client inventory is identity, identity, event, event. That is two targets, `cal-ms-default` and `cal-np-other`, with no OAuth.
- **Identity phase:**
  - `prepare_requested_subscription_for_covering` (`covering_refresh_import.py` l.911 call) → `fetch_account_identity_evidence` (l.441–448), which catches **only** `(httpx.TransportError, json.JSONDecodeError, OSError)` (l.449) and maps them to `CALENDAR_IDENTITY_EVIDENCE_UNAVAILABLE` (l.92, l.455–458) [F];
  - inside, `calendar_alias_canonicalize.py` l.196–199 catches only `ApiError` [F].
  - **So:**
    - an EOF-class `OSError` during an identity read → known preflight `CALENDAR_IDENTITY_EVIDENCE_UNAVAILABLE` [I, assuming `SSLEOFError` ⊂ `OSError` and no rewrapping in the MS GET helpers, which I didn't trace exhaustively: U];
    - a `CoveringDeadlineExceeded` there is neither caught nor an `ApiError`, so it escapes `apply` → `CoveringTargetTransaction.run` → `run_target` remaps every escaping exception to `CoveringRootOutcomeUnknown` (`covering_role_connector.py` l.193–204) → `run_bounded_domain` re-raises (l.265–267) → `dispatch_covering_http` gives **503 `CALENDAR_REFRESH_OUTCOME_UNKNOWN`** (`covering_http_dispatch.py` l.71–73) [I].
- **Event phase:**
  - `_pull_provider` is wrapped by `except Exception` (`covering_refresh_import.py` l.968–997). Unless the exception is `CoveringRootOutcomeUnknown`, it returns `OUTCOME_FAILED` with `cause=_cause_from_exception(exc, default="covering_provider_read_failed")` (l.133, l.648–655: only an `ApiError` code overrides), `rollback_required`, `needs_failure_unit` [F];
  - then `CoveringTargetTransaction.run`: `finish_root(commit=False)` (l.113) runs the ROLLBACK under `_begin_cleanup` / `cleanup_remaining` (`covering_parent_adapter.py` l.232–236). It expects `ROLLBACK_ACKNOWLEDGED`, otherwise UNKNOWN (l.132–133). Next comes `retire_parent` (l.135–137), then the failure unit through `open_failure_session` under `cleanup_remaining`. Expiry gives `refuse_reason="cleanup_deadline_exceeded"` (l.142–156) [F].
  - **Next target:** `work_remaining()` raises, so `exhausted` is set and a static row with `preflight_code="CALENDAR_REFRESH_DEADLINE_EXCEEDED"` is produced (`covering_domain_dispatch.py` l.190–199; constant l.34) [F].
  - Assessment is skipped when exhausted (l.248–259) [F].
  - `overall_outcome` = `failed` when `import_attempted≥1` and `import_ok==0` (`covering_refresh.py` l.159–165) [F].
  - Public status: 200 with typed rows [I].
- **Placement choice:** put both stalls on **the first event exchange (connection index 2)**. That's the path whose classification is robust, `except Exception` [F], and matches the registry's `expected_unknown=False`.
  - The identity-phase deadline (an escaping UNKNOWN) is a **separate retained observation** with no current ID. I don't propose substituting it.

### Original client outcome and retirement
- **Source-supported [F/I]:**
  - the raised class at the guard is `CoveringDeadlineExceeded`;
  - target 1 gives a failed row with cause `covering_provider_read_failed`;
  - target 2 gives a static `CALENDAR_REFRESH_DEADLINE_EXCEEDED` row;
  - native TOKEN/PARENT ROLLBACK acknowledged under the cleanup budget, with no assessment.
- **Unproved [U]:**
  - the native terminal under actual elapsed cleanup;
  - failure-unit persistence under the remaining cleanup allowance;
  - the client close timing and peer timing.

## 3. Q2: PARTIAL-SEND
- **Server-side partial response is not client partial send.**
  - `partial_send_peer` truncates the **response** to half its length (`np_provider_peer.py` l.378–382) and notes "prefix_only_not_client_partial_proof" [F];
  - `np_suite` l.12 says "Peer prefix-only receive ≠ sender partial completion proof" [F].
  - **It can't witness T04-PARTIAL-SEND.**
- **Real source flags:**
  - `JoinedTLS.sent` is set before each `sock.send` (l.97–98) [F];
  - a zero or negative count raises `CoveringTransportRefused("send incomplete")` (l.100–101) [F];
  - `CoveringHTTP` turns any OAuth failure with `sent` set into UNKNOWN (l.373–377) [F];
  - there is **no** per-byte transmitted counter in production [F].
- **What native can show:**
  - the peer's observed decrypted request bytes before an abort: `life.bytes_received` (l.334) [F];
  - the client's attempted-send state, which is not exported. It can only be inferred from the classification [I].
  - Kernel buffering means a small request (OAuth POST under 1 KiB) is usually fully accepted by `sock.send` even if the peer later aborts. **A native run can't prove a client-side partial transmission** [I].
- **Exact gap:** no injection boundary in the current fixture makes the client's `sock.send` return a short count or fail after partial acceptance under native TLS.
- **Narrowest honest witness (proposal, two layers, each labelled):**
  - **(a) Deterministic extracted property (fake):**
    - the actual `JoinedTLS.send` with a named fake socket that accepts k < n bytes and then raises;
    - asserts `sent` True, the classification through the actual `CoveringHTTP.request` for `purpose="oauth"` → new `CoveringRootOutcomeUnknown` with no retry;
    - for GET, the original exception propagates;
    - the transport is closed once.
  - **(b) Native caller classification:**
    - a peer mode `abort_after_request_prefix` (R-PEER-2) that reads until it has between 1 and n−1 decrypted bytes of the OAuth POST, records the count, then aborts with RST;
    - expected on the refresh (expired) lineage: OAuth exchange 0 → UNKNOWN → 503 `CALENDAR_REFRESH_OUTCOME_UNKNOWN`, with no second OAuth connection admitted [I; TOKEN-role mapping not traced: U].
  - **(b) proves only:** an attempted send, a server-observed prefix, and an uncertain-OAuth classification. **It does not prove transmitted-prefix count from the client.**
- **Possible overlap with T06-PARTIAL-SEND** (Inventory l.12). Both are kept as separate IDs.

## 4. Q3: DEADLINE
- **Clocks preserved:** 210 work, 240 request, 30 cleanup (request-capped), 600 per-attempt plan validity (`fresh_attempt_plan`, runner l.1308 for refresh) [F]. Admission and cleanup stay separate:
  - `work_remaining` refuses during cleanup (l.39–40);
  - `cleanup()` refuses a second concurrent scope (l.57–58);
  - an escaping failure latches `stop` (l.66–70) [F].
- **First guard by phase [F]:**
  - **ingress body read:** `asyncio.wait_for(receive(), timeout=work_remaining())`. `CoveringDeadlineExceeded` or `TimeoutError` gives **504 `CALENDAR_REFRESH_DEADLINE_EXCEEDED`** before any worker (`covering_ingress.py` l.48, l.61–62);
  - **pre-ownership worker:** 504 only while both `ownership_established` and `calendar_admitted` are false (`covering_http_dispatch.py` l.63–66); otherwise 503 UNKNOWN (l.67–70);
  - **per-target admission** gives a static DEADLINE row (`covering_domain_dispatch.py` l.193–199); TOKEN begin-before-checkout likewise (l.212–217); `run_target`'s own `CoveringDeadlineExceeded` gives a DEADLINE row (l.239–243), **but** any deadline *inside* `run_target` is remapped to UNKNOWN (connector l.193–204) unless the import layer converted it first (event pull, §2);
  - **commit:** `COMMIT_DEADLINE_ROLLBACK_ACKNOWLEDGED` remaps to a failed row with cause `CALENDAR_REFRESH_DEADLINE_EXCEEDED` (`covering_target_transaction.py` l.114–131).
- **Token versus event effects:** OAuth with `sent` gives UNKNOWN (no replay); an event read gives a failed row with rollback [F].
- **Proposed DEADLINE witness** (registry `expected_unknown=False`, oracle `distinct_from_supervisor_kill`): the **pre-dispatch ingress deadline**.
  - **Stimulus:** the runner's ASGI driver sends the request head with `more_body=True` and withholds the rest.
  - **Expected [F]:** 504 `CALENDAR_REFRESH_DEADLINE_EXCEEDED`, with no worker, no role checkout and no provider connection admitted (peer accept count 0).
  - **Why:** it's the only deadline boundary whose outcome is a single known code with no provider dependence. The post-ownership typed-row deadline is witnessed **inside** HEADER/BODY-STALL (target 2's static DEADLINE row), and those rows are cross-referenced, not double-claimed.
  - **This is a real choice** (§7, Q-B).
- **Timestamps needed to tell a production deadline apart:**
  1. runner monotonic `t_post` immediately before the POST, and `t_resp` at the response;
  2. peer monotonic `t_stall_entered`, and a stall exit reason (`"retired"` versus `"deadline"`, R-PEER-1);
  3. the configured peer deadline.

  The case passes only if all of these hold:
  - 210 ≤ `t_resp − t_post` ≤ 240 + ε, where ε is disclosed as runner scheduling latency;
  - the stall is still held at `t_resp` (exit reason `retired`, after `t_resp`);
  - the runner kill hasn't fired (runner 600 s);
  - for DEADLINE, no peer accept.
  
  A supervisor kill would produce no receipt. A peer-deadline expiry would give exit reason `deadline` and STOP.

## 5. Q4: DISCONNECT
- **Production path [F]:**
  - after the complete body, the ingress `monitor()` consumes `http.disconnect` and sets `disconnected` (`covering_ingress.py` l.65–72);
  - `guarded_send` suppresses all later output (l.84–86);
  - the worker runs under `CancelScope(shield=True)` with `abandon_on_cancel=False`, so it is joined, not detached (`covering_http_dispatch.py` l.58–62);
  - `work_remaining` → `check_admission` raises `CoveringBudgetStopped` (budget l.33–38), and `JoinedTLS.ready`/`check` surfaces it within about 50 ms of the provider wait [F].
- **During an event-read wait [I]:**
  - `CoveringBudgetStopped` (a plain `Exception`) is caught by the pull `except Exception` (l.976), giving a failed row;
  - ROLLBACK runs under `cleanup_remaining`, which ignores cancellation (budget l.43–46). The failure unit runs under cleanup the same way;
  - next, `check_admission` (domain l.190, or the l.250 work check) raises `CoveringBudgetStopped`. That escapes `run_bounded_domain` to `dispatch_covering_http` l.71–73: internal **503 `CALENDAR_REFRESH_OUTCOME_UNKNOWN`**, which `guarded_send` suppresses on the wire.
  - This matches the registry's `expected_unknown=True`.
- **ASGI disconnect versus provider EOF:**
  - the disconnect comes from the ASGI receive stream, not the provider socket. The provider peer stays in `stall_header` and is retired by the runner afterwards;
  - `np_suite` l.14 and the C09 review l.7–9 require the actual `http.disconnect` to go through the monitor, never `disconnected.set()` directly [F].
- **Reuse:** `i01_asgi_app.DisconnectInjectControl` (l.45–103: a fixture-owned real `http.disconnect` injector with a monitor-observation join) and `BoundedASGIResponse` (l.353). The I01/I02 v4 evidence ran with `transport_factory: "FixtureByteTransport"` (`scheduler-native-i01-i02-v4/Dex-Run-Reconciliation.json` l.269; `I01-I02-Retained-Proof-Transfer-2026-11-13.json` l.32 and l.48, `defaultJoinedTLSProvenByThisRun: false`). **That evidence transfers only at the ingress/monitor/guarded-send scope.**
- **Remaining JoinedTLS composition gap (exact):** no run has shown `CoveringBudgetStopped` raised from `JoinedTLS.ready()` during a real TLS read wait, nor the rollback, failure unit and joined worker that follow under the default JoinedTLS. That's the native increment.
- **Checkpoint:** inject only after the runner observes the peer's `life.phase_entered == "stall_header"` on exchange 2. That is deterministic and not sleep-based; the C09 review l.21 requires this.
- **Negative controls, from C09 l.22:**
  - the checkpoint is never reached;
  - a late disconnect (after the response);
  - no monitor observation;
  - an unjoined worker;
  - any outbound message after the disconnect.
  
  Each of these is a STOP.

## 6. Q5: per-case proposal (one exact ID each; each a separate single-case native invocation)

| Case | Lineage | Stimulus (peer connection index) | Production entry → first guard | Expected client / public / transaction | Sends / admissions | Retirement | Fake/extracted · native TLS · HTTP/native classification |
|---|---|---|---|---|---|---|---|
| NP-T04-HEADER-STALL | NONEXPIRED (2 targets, no OAuth) | Exchanges 0–1 normal identity; **exchange 2** = event GET: request received, then **header stall** (R-TRANSCRIPT-1 with real event path and query); 3 connection scripts only | POST covering-refresh → pull → `CoveringHTTP.request` → `response.begin()` → `JoinedTLS.receive` → `ready` → `check` raises `CoveringDeadlineExceeded` at about 210 s [F] | Client: `CoveringDeadlineExceeded` [F]. Public: 200 with row 1 `failed` / `covering_provider_read_failed` and row 2 static `CALENDAR_REFRESH_DEADLINE_EXCEEDED`; `overall_outcome` `failed` [F/I]. Transaction: ROLLBACK_ACKNOWLEDGED, failure unit persisted or `cleanup_deadline_exceeded` [U]. No assessment [F] | OAuth 0; connections admitted/served 3; no 4th accept; no retry [I] | Peer stall exit `retired` after `t_resp` (R-PEER-1); helper joined, no worker error; exact-ID containers | Fake: peer stall-exit unit (R-PEER-1) · Native: elapsed 210–240+ε, peer phase `stall_header`, `response_sent` False · Classification: typed rows, no UNKNOWN |
| NP-T04-BODY-STALL | NONEXPIRED | Same, but exchange 2 sends the full head with a valid Content-Length, then **body stall** (existing `stall_body` mechanics, real path) | Same chain, after `begin()` and `_admit_framing_headers`: body loop `response.read(8192)` (l.343–348) → `receive` → guard [F] | Same as header-stall [F/I] | Same; peer `response_sent` True, `bytes_sent` = head length | Same | Distinguished from header by peer phase `stall_body` and `bytes_sent`; the public shape is identical (disclosed) |
| NP-T04-DEADLINE | Any seeded owner; no provider needed | ASGI request head with `more_body=True`, body withheld (R-RUNNER-ASGI) | Ingress `wait_for(receive(), work_remaining())` (l.48) [F] | 504 `CALENDAR_REFRESH_DEADLINE_EXCEEDED` (l.61–62) [F]; no worker, no role checkout [F] | Peer accepts 0; OAuth 0 | Peer bound, then retired unused (or no peer: Q-B); exact-ID | Native: elapsed 210–240+ε with the runner alive · Classification: known 504, distinct from supervisor kill |
| NP-T04-DISCONNECT | NONEXPIRED | Exchange 2 header stall; at checkpoint `phase_entered=="stall_header"`, inject a real `http.disconnect` through `DisconnectInjectControl` | Monitor → `disconnected` → `check_admission` → `CoveringBudgetStopped` from `JoinedTLS.check` within about 50 ms [F] | Internal 503 `CALENDAR_REFRESH_OUTCOME_UNKNOWN` (dispatch l.71–73) [I]; nothing on the wire after the disconnect [F]; ROLLBACK under cleanup [I/U] | 3 admitted; no later admission | Worker joined (`abandon_on_cancel=False`); monitor observation joined; peer `retired` | Fake: reuse C09 injector controls at their recorded scope · Native: JoinedTLS composition gap closed · Classification: expected UNKNOWN, separate from client wire |
| NP-T04-PARTIAL-SEND | REFRESH (expired; OAuth first) | Exchange 0 OAuth POST: peer reads 1..n−1 decrypted bytes, records them, then RST (R-PEER-2) | `CoveringHTTP.request` OAuth → `transport.send` (`sent=True`) → failure at send or receive → l.373–377 [F] | `CoveringRootOutcomeUnknown` [F] → public 503 UNKNOWN [I]; TOKEN role effect [U]; no refreshed token persisted [U] | OAuth connection 1; no replay or second OAuth [F, l.374] | Peer worker clean (abort is scripted, not an error: R-PEER-2); helper joined | Fake (a): the actual `send` and `request` with a short-accept fake socket · Native (b): peer-observed prefix + uncertainty classification only · **Does not prove client transmitted-prefix count** |

- **Peer deadline for stall cases:** 235 s, within the 240 s limit at `np_provider_peer.py` l.502. That outlasts 210 s of work, so a production deadline is observable. If the client hasn't returned by 235 s, the peer's `deadline` exit STOPs the case (fail closed).

### Prospective named roles and data (existing 16-role lane; no API change)
- **R-PEER-1** (`np_provider_peer.py`): in the `stall_header`/`stall_body` loops, record `stall_exit` ∈ {`retired`, `deadline`} and the monotonic entry/exit times.
  - A `_stop`-caused exit returns cleanly and does not set `_error`;
  - a deadline exit still raises.
  - It also makes `stall_header` reachable from a declared step, e.g. a `send_response` step whose `close_mode` is `stall_header`, or an explicit check in `_run_one_connection`, so the current dead path is fixed.
  - **This is a new fixture operation, so it's a decision (Q-A).**
- **R-PEER-2:** a new `abort_after_request_prefix(k)` mode that records `bytes_received` and aborts with RST. It's a new fixture operation (Q-C).
- **R-TRANSCRIPT-1** (`np_provider_transcript.py`): T04 scripts on real NONEXPIRED paths, with an exact query where the case declares one. Exchange 2 carries the stall close mode, the inventory is exactly 3 connections, and the OAuth prefix-abort script uses the production tenant token path.
- **R-RUNNER-1..5** (`np_runner_entry.py`): five case bodies on the NONEXPIRED/REFRESH skeletons.
  - Each uses `retirement_attempted` + `_retire_selected_peer_then_observe` (unchanged), plus `t_post`/`t_resp` capture and the exact oracles above.
  - DISCONNECT reuses `DisconnectInjectControl`.
  - DEADLINE adds a withheld-body ASGI driver (R-RUNNER-ASGI, a new runner operation: Q-B).
- **R-SUITE** (`np_suite.py`): implementation notes for the five cases.
- **R-CONFIG:** a per-case runner-config with `peer_seconds` 235 for stall/DISCONNECT and 120 otherwise. **That's a changed future limit (Q-D).**

### Allotments (nominal; each case a separate invocation)
- **Constraint:** every case except DEADLINE provisions the schema with `create_all(checkfirst=False)` (runner l.581). DEADLINE needs only the app + DB. **No vertical case shares a DB** (`0427EC48`).
- **Per-case nominal time:**

  | Case | Nominal | Breakdown |
  |---|---|---|
  | HEADER-STALL / BODY-STALL | about 295 s | PKI 45 + work 210 + cleanup ≤ 30 + peer join 5 + reader joins and setup (disclosed, excluded) |
  | DISCONNECT | about 60 s | PKI 45 + checkpoint wait (bounded by peer 235) + cleanup ≤ 30 + join 5; nominal assumes a prompt checkpoint |
  | DEADLINE | about 255 s | 210 + ≤ 30 rejection send + 5 + setup; PKI 45 only if a peer is bound |
  | PARTIAL-SEND | about 55 s | PKI 45 + OAuth abort + rollback + 5 |

- **All are under runner 600 / suite 900.** Startup, outer, file, hash and receipt work and OS latency are excluded. The 32-command / 1 MiB caps are unchanged; per-case success-path Docker counts are to be derived at authoring.
- **Five separate native invocations** (no batching). A future exact card controls each one.

## 7. Real decisions (only these)
- **Q-A:** accept R-PEER-1. A clean `retired` stall exit replaces raising on stop, so no worker-error tolerance or D1 import is needed. It also fixes the unreachable `stall_header`. **Recommended.**
- **Q-B:** DEADLINE witness = the pre-dispatch ingress 504 via a withheld-body ASGI driver, with post-ownership deadline rows cross-referenced from the stall cases. The alternative is to keep DEADLINE unproved until a separate post-ownership-only stimulus is designed. **Recommended: ingress 504.**
- **Q-C:** PARTIAL-SEND two-layer witness (an extracted fake short-accept socket + native prefix-abort OAuth classification), explicitly **not** claiming client transmitted-prefix proof. The alternative is to retain PARTIAL-SEND as an unproved gap.
- **Q-D:** future limit change: `peer_seconds` 235 for the stall and DISCONNECT cases. Current approvals don't permit it; it needs its own exact card.
- **Retained, with no ID or substitution:** the identity-phase deadline gives an escaping UNKNOWN (§2). It's recorded as an observation target if you want a sixth case later.

**Smallest coherent next increment:** R-PEER-1 + R-TRANSCRIPT-1 (stall scripts only) + R-RUNNER-1 (BODY-STALL first). The body stall uses existing `stall_body` mechanics unchanged except for the clean exit, and its client path is fully source-traced. HEADER-STALL follows with the same skeleton. DISCONNECT is third, reusing the C09 injector. PARTIAL-SEND and DEADLINE wait on Q-C and Q-B.

## Separation
- **[F] facts** cite exact lines.
- **[I] inferences** are marked.
- **[U] unproved:** native terminal timing, the EOF class after a peer drop, TOKEN-role mapping for OAuth UNKNOWN, failure-unit persistence under elapsed cleanup, and client transmitted-prefix count.
- **No requirement is closed.** All 76 IDs remain.
- **Held:** all execution and the four pending cards. Endpoint unbound.

Signed: Matt
