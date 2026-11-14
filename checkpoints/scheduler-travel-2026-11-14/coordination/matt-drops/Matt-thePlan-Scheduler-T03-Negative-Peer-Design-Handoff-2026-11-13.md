# Matt → Dex: T03 five-requirement source-only design (VALID, WRONG-CA, WRONG-NAME, HANDSHAKE-STALL, TCP-REFUSAL)

November 13, 2026. This responds to `Matt-thePlan-Scheduler-T03-Negative-Peer-Design-2026-11-13.md` (`F7FE1018EB90BC54A3F6C43A09E82947BC6343D1FCDB559EBEE831BF50BBF6BC`).

**Method:** ordinary read-only text and hash review.
- No source or packet was edited, and nothing was invoked. No subagents.
- Labels used throughout: **[S]** observed source fact, **[I]** inference, **[N]** unproved native behavior.

## Baselines (read only)
- **T05 staging `scheduler-native-provider-t05-launch-dex-v1`** (manifest `417BEA58…`, runner `1D70164C`, peer `BFB271D7`). Fixture files: routes `9CBDE09C…11EA`, PKI script `591855FF…E205`, suite `9AED74EE…`. Application files: `covering_joined_https` `76017776…3427`, `covering_request_budget` `D5C465CC…8975`, `covering_transport_policy` `5F48FD7E…8B88`, `covering_http_transport` `29CBD53C…B368`.
- **Shared source cross-read from `scheduler-native-provider-ms-invalid-prep-matt-v2`** (`6144365E`). Its routes, PKI and application bytes are identical.
- **Queued readiness** `0A0510EF…E8FB`: its four findings are confirmed below, with two additions (A1, A2).

**Declarations [S] (suite `9AED74EE` l.151–184):**
- `NP-T03-VALID` → `handshake_and_useful_app_data`;
- `NP-T03-WRONG-CA` → `refuse_before_useful_application_data`;
- `NP-T03-WRONG-NAME` → `refuse`;
- `NP-T03-HANDSHAKE-STALL` (B3) → `first_guard_deadline_real_elapsed`;
- `NP-T03-TCP-REFUSAL` → `typed_connect_failure_no_fake_empty_receive`.

All five IDs are retained, and no family closure is claimed.

## Source facts
**F1 [S] Client.** `JoinedTLS.open` (`covering_joined_https` l.40–90):
- dials `(peer.address, peer.port)` (l.48);
- connect failure is the typed `CoveringTransportRefused("connect refused")`, at l.52 for immediate errno or l.56 for async `SO_ERROR`;
- context: `create_default_context(cafile=peer.ca_file)`, `check_hostname=True`, `CERT_REQUIRED`, `server_hostname=peer.hostname`, `suppress_ragged_eofs=False` (l.58–62);
- the handshake loop polls `self.check()` → `remaining()` (l.63–72, `ready` l.35);
- any failure closes the transport and re-raises the original (l.73–90);
- `send` is never reached before `open` returns, so `sent` stays False.

**F2 [S] Remapping.** In `CoveringHTTP.request` (`covering_http_transport` l.371–379), a non-OAuth purpose (`event`) propagates the original exception unchanged. Only OAuth after `sent` is remapped to UNKNOWN.

**F3 [S] Budget.** In `CoveringRequestBudget` (l.19–52), the work deadline is start + 210 and the request deadline is start + 240. `work_remaining` raises `CoveringDeadlineExceeded` (l.48–52). With the T05-style construction `ProviderCounter(…, budget.work_remaining)`, **the first guard to fire inside a stalled handshake is the 210 s work deadline**. The 240 s request guard can't fire first through direct transport. **[I]** Proving the 240 s guard would need ASGI-ingress composition, which is out of scope here.

**F4 [S] Trust stimuli.**
- `*_route(wrong_ca=True)` swaps only the client `ca_path` to `wrong-ca.crt`, a distinct self-signed root (PKI l.40–43). The hostname, SNI, port and verify flags are unchanged.
- `wrong_name=True` sets only `serve_wrong_name_leaf`. The peer then serves `wrong-name.crt` (SAN `wrong-name.fixture.invalid`), **signed by the same fixture CA** (PKI l.57–67; peer `_select_cert_paths` l.210–214).
- **Each varies exactly one trust dimension.**

**F5 [S] Peer handshake.**
- `_handshake` (peer l.284–309) catches only `SSLWantRead`/`SSLWantWriteError`.
- Any other exception escapes through `_run_one_connection`'s `finally` (l.448–498) to the worker. The worker records `_error` plus the note `worker_error:<Class>` (l.531–537), and `retire_owned` returns that as `worker_error_kind`.
- **The inventory row is appended only on success** (l.510–516), so a failed handshake leaves `exchange_inventory == []`.
- `phase_entered` stays `"accepted"` (set l.276) until the handshake completes (l.303–304).

**F6 [S] Stall.** `close_mode == "stall_pre_handshake"` sets `phase_entered` and `close_mode_observed` to `"stall_pre_handshake"`. It holds the accepted TCP socket without TLS until the peer deadline **or the stop event**, then **always** raises `PeerLifecycleError("handshake stall held to deadline")` (l.286–293). A correct stall therefore *always* ends with `worker_error_kind = "PeerLifecycleError"`. `execute_script` caps the peer at 240 s (l.502).

**F7 [S] Missing material.** Missing server certificate material raises `PeerLifecycleError` from `_build_server_context` (l.80–81) in phase `"accepted"`, which is the same phase as a TLS refusal.

**F8 [S] TCP route.**
- `tcp_refusal_route` has `url_port 443` but `dial_port 9`, with the comment "actual closed port chosen at launch card" (routes l.104–116).
- `bind_listen` refuses that purpose (peer l.218–219).

## Additions to the queued findings
**A1 [S] The TCP-refusal route can't be expressed through production `HTTPSPeer`.**
- `HTTPSPeer` has one `port` field, used both by `check_url` (`(443 if u.port is None else u.port) == self.port`, policy l.187) and for the dial (F1 l.48).
- A peer with `port=9` refuses a vendor URL without a port as "provider origin refused", **before any connect**. A peer with `port=443` never dials 9.
- **Consequence:** a real T03-TCP-REFUSAL must put the *same* closed port in the URL **and** in `HTTPSPeer.port` (for example `https://graph.microsoft.com:<p>/v1.0/...`), built in the case body.
- `tcp_refusal_route()` as written must not be used. I propose leaving its bytes untouched (it's a shared pinned file) and documenting it as a placeholder.

**A2 [S]+[I] Peer error class alone can't separate a planned refusal from a fixture fault.**
- F7 shows a material fault raises `PeerLifecycleError` in the same `"accepted"` phase.
- A corrupt PEM would raise `ssl.SSLError` from `load_cert_chain`, again in that phase.
- **The disambiguator is the client side:** a fixture fault never yields a client certificate-verification failure. **[I]** The client would instead see an EOF or reset.

## Proposed observation contract (narrow, case-specific; no global tolerance)
**Positive cases stay unchanged.** T03-VALID uses the existing `_t05_observe` / `_retire_selected_peer_then_observe` admission: joined, `worker_error_kind is None`, post-join snapshot.

**New pure helper in role 4 (runner):** `_retire_negative_peer_then_observe(peer, *, allowed_worker_errors, expected_phase)`.
- Exactly one call to the unchanged `retire_owned(5.0)`, with `retirement_attempted` set before the call by the caller.
- `PeerRetirementUnknown` and any other exception propagate as the same object.
- **Requirements:**
  - `joined is True`;
  - `worker_error_kind` is **in** the case's frozen finite set; `None` is a STOP;
  - then, from `sanitized_state()`: `accepted is True`, `handshake_complete is False`, `request_received is False`, `response_sent is False`, `bytes_sent == 0`, `exchange_inventory == []`, and `phase_entered == expected_phase`;
  - exactly one `worker_error:` note equal to the returned kind.
- Anything else STOPs.
- **Retained STOP evidence stays class and phase only.** No exception messages or reasons are added to receipts or diagnostics.

**Per case:**
| case | client outcome (finite, else STOP) | peer helper args |
|---|---|---|
| WRONG-CA | `("exception", "SSLCertVerificationError", "ssl")` raised through `JoinedTLS.open` l.66, request never sent | `expected_phase="accepted"`, allowed `{SSLError, SSLEOFError, ConnectionResetError}` **[N] hypothesis** |
| WRONG-NAME | the same client class | the same peer args |
| HANDSHAKE-STALL | `("exception", "CoveringDeadlineExceeded", "app.services.covering_request_budget")`, with real elapsed time since budget start ≥ 210 s and < 240 s | `expected_phase="stall_pre_handshake"`, allowed `{PeerLifecycleError}`, plus `close_mode_observed == "stall_pre_handshake"` |
| TCP-REFUSAL | `("exception", "CoveringTransportRefused", "app.services.covering_transport_policy")`, innermost owned frame `covering_joined_https.open` at line 52 or 56 (location only) | no peer |

**The useful-application-data boundary is evidenced on both sides:**
- **peer:** `request_received` and `response_sent` False, `bytes_sent` 0;
- **client:** the exception escapes `open`, so `send` and `receive` were never reached (F1, F2).
- **Optional client observer:** a class-level counting wrapper on `JoinedTLS.send` and `receive`, restored in `finally`, would show 0 calls directly. It delegates to the real methods (not a fake transport). Tradeoff: it adds observer surface, and the peer-side and location evidence may already suffice. I recommend not adding it unless you want a direct client-side count.

**Fake controls (host, behavior on the extracted helper with a named fake peer):**
- planned error in the right phase passes;
- `None` → STOP;
- a class outside the set (for example `PeerLifecycleError` for WRONG-CA, or `FileNotFoundError`) → STOP;
- a phase advanced (`request_received` True) → STOP;
- a non-empty inventory → STOP;
- the stall phase mismatched → STOP;
- unjoined `PeerRetirementUnknown` → the same object;
- exactly one attempt on every path;
- client-classifier cases for each finite tuple, and every other tuple STOPs.

**Mutants:**
- **behavioral:** allowed set widened to any class; `None` admitted; phase check dropped;
- **structural:** WRONG-CA uses a wrong-name route, or vice versa; the TCP case's URL port differs from `HTTPSPeer.port`; the stall peer is under 210 s.

**What the host fake can't prove:** the real SSL classes, the alert behavior or the timing.

## Exact case groups and bounds (current 600 s runner / 900 s suite unchanged)
**B2a (recommended next): VALID, WRONG-CA, WRONG-NAME.**
- Three sequential owned peers at 120 + 5 s nominal each: 375 s ≤ 600. The real handshakes take seconds.
- `expected_unknown []`, serial and stop-first.
- No new limit.

**B2b: TCP-REFUSAL.**
- No peer. It needs one **launch-time port-ownership action** (decision D3).
- **Recommended strategy:** inside the existing loopback-only namespace (`run_suite` requires `/sys/class/net == {"lo"}`), the case body binds an owned TCP socket to `127.0.0.1:0` **without `listen()`**. It reads the assigned port, uses it as both URL and `HTTPSPeer` port, holds the socket bound through the request, and closes it in `finally`.
- **Why:** holding the bind prevents any other binder (no TOCTOU), and a bound-but-not-listening port refuses connects. **[N]** Linux sending RST/`ECONNREFUSED` for a bound-but-not-listening port is to be confirmed natively.
- **Alternatives:**
  - port 9 as written: no guarantee it's closed, and it's rejected;
  - listen then close (TOCTOU race): rejected;
  - an ephemeral probe connect: rejected, because it probes.
- It can join B2a once D3 is approved. I keep it separate so each approval stays narrow.

**B3: HANDSHAKE-STALL, alone.**
- It needs a **case-specific peer allotment of 240 s** (the `execute_script` maximum) so the peer is still stalling when the 210 s work guard fires. The current disclosed `peer_seconds` is 120, and `PEER_SECONDS_DEFAULT = 120` is in the runner.
- **Nominal timing:** about 210 s client time, plus a 0.05 s poll, plus a 5 s join (the stop event ends the stall within 0.05 s), plus PKI and setup. That fits a single-case batch under 600/900.
- **Feasibility conflict:** combining the stall with B2a would give a nominal allotment of 375 + 245 = 620 s, over 600. Keep it separate.
- **No clock changes:** none to the 210/240/30 clocks, no grace, no retry.
- **Exclusions:** startup, file, hash and OS latency, and Docker CLI kill-without-wait, as with existing cards.

## Retained finite evidence versus native-only
- **Finite and retainable now:** F1–F8, A1–A2 by source reading. A future focused fake can cover the helper and classifier behavior, the route construction, the URL/peer port equality, and the barrier order.
- **Native-only [N]:**
  - the actual client and peer exception classes under OpenSSL/TLS 1.3;
  - that the refusal happens before any application byte on the wire;
  - the real `connect_ex` errno path (l.52 versus l.56);
  - `ECONNREFUSED` for a bound-but-not-listening port;
  - the real 210 s elapsed time;
  - peer retirement timing.
- **Allowed peer class sets are fail-closed hypotheses.** Any different native class STOPs, as an honest UNKNOWN. Widening needs an explicit review, never silent.

## Role-level source changes (next implementation; existing named roles only)
- **Role 4 runner:**
  - five case bodies and mapper and implemented IDs;
  - `_retire_negative_peer_then_observe`;
  - the finite T03 client-outcome constants;
  - the TCP owned-port block in its case body.
- **Role 5 suite:** implementation notes only. Declarations unchanged.
- **Role 8 transcript:** a T03-VALID GET script (complete fixed-length `{}`); WRONG-CA and WRONG-NAME reuse the same request script. The existing `stall_pre_handshake` script is reused.
- **Data:** per-batch runner-config. For B3, `peer_seconds` 240 (decision D2).
- **No changes:** peer (role 7), routes, PKI script and the application stay byte-identical. That keeps the existing fake and T05 evidence valid. No new helper file, no production policy change, no exception widening.

## Minimum decisions genuinely needed
- **D1:** accept the frozen peer-side allowed class set for WRONG-CA/WRONG-NAME as a fail-closed hypothesis, `{SSLError, SSLEOFError, ConnectionResetError}`, refined only by explicit review after first native observation. The alternative is recording the class only, which I don't recommend because it can't STOP on a fixture fault.
- **D2:** a later limit review for a B3-only 240 s peer allotment. Not approved now.
- **D3:** the B2b launch-time owned bound-not-listening port strategy. Not approved now.

## Recommended next bounded implementation scope
Prepare **B2a only** (VALID, WRONG-CA, WRONG-NAME) as a fresh successor of the T05 staging lineage, with its focused fake.
- Role 4 helper, bodies and constants; role 8 VALID script; role 5 notes; B2a runner-config.
- Gate it on D1.
- Leave B2b and B3 as separate later preparations after D3 and D2.

Signed: Matt
