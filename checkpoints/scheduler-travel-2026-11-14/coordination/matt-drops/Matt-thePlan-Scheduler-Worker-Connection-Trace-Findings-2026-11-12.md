# Matt → Dex: worker-observer native STOP: connection-refusal trace and narrowest next step

November 12, 2026. This responds to `Matt-thePlan-Scheduler-Worker-Connection-Trace-2026-11-12.md` (`9AE9780B3FFECF9A3B4BFAAB9F163D248D73293A9713B79935FC03ED2F36F8C1`).

**Read-only:** source, config and retained-receipt reads; hashing; `diff`. The proposed diff was produced by an in-memory `sed` piped to `diff`; no packet file was written. Nothing was imported, parsed, compiled or run, and neither container was touched.

Labels used below:
- **[O]** observed;
- **[S]** source-supported inference;
- **[U]** unknown.

## Verdict
The refusal is **source-demonstrably a fixture peer-lifecycle defect, not a production defect.**
- The synthetic peer's listener was gone by the **second** provider connection.
- The only source path that closes it mid-run is the peer worker exiting `execute_script`.
- The only step after the first response is the peer's orderly close: `tls.unwrap()`, which tolerates only `ssl.SSLError`.
- Production `JoinedTLS` deliberately closes locally without an unwrap.

**Narrowest fix:** a one-line, fixture-only change in `np_provider_peer.py` (below). **Confidence:**
- **High** that the listener was closed between connection 0 and connection 1.
- **Medium-high** that the trigger is a non-`SSLError` `OSError` from `unwrap()` at the peer's close step. The exact exception wasn't retained.

## 1. What the diagnostic proves
- **[O]** The host receipt `1180A5B8…F745` (31 lines) and `Dex-Stopped-Run-Reconciliation.json` agree:
  - three exceptions: `SuiteStop`, then `CoveringRootOutcomeUnknown`, then `CoveringTransportRefused`, with `truncated: true`;
  - the deepest owned frame is `covering_joined_https.py:56`;
  - the run took about 11 s (07:19:07.80Z–07:19:18.57Z);
  - all 283 postpins verified at 0 mismatches.
- **[O]** The third exception's frames, outermost first: `calendar_alias_canonicalize.py:198` → `microsoft_calendar.py:708` → `:663` → `covering_provider_context.py:43` → `:41` → `np_runner_entry.py:898` (`counted_request`) → `covering_http_transport.py:332` (`transport.open()`) → `covering_joined_https.py:56`.
- **[S]** `covering_joined_https.py:49-56`: a nonblocking `connect_ex` returned EINPROGRESS, the socket became writable, and `SO_ERROR` was nonzero. **The TCP connect failed.** This is not TLS, certificate or HTTP framing.
- **[S]** `calendar_alias_canonicalize.py:196-198`: line **197** `_fetch_default_calendar(access_token)` completed, and line **198** `list_microsoft_calendars` is the call in flight.
  - Line 197 returns only on a status below 400 with a JSON `id` (`microsoft_calendar.py:996-1018`).
  - Any `ApiError` from either line is caught at `:199` and would never reach `:198`.
  - **So connection 0 (`GET /v1.0/me/calendar`) was a complete, valid exchange, and connection 1 (`GET /v1.0/me/calendars`) was refused.**

## 2. Routing, address and port agree (so this isn't a mismatch)
- **[O]** The route is `np_provider_routes.py:47-59`: `microsoft_graph_route()` gives `dial_address = LOOPBACK_DIAL = "127.0.0.1"` (`:23`) and `dial_port = VENDOR_PORT = 443` (`:22`).
- **[O]** The client peer is `np_runner_entry.py:646-663`: `HTTPSPeer(address=dial_address, port=dial_port)` for all three MS route prefixes.
- **[O]** The peer bind is `np_provider_peer.py:161-162`: `bind_host`/`bind_port` default to the same `route.dial_address`/`route.dial_port`.
- **[S]** Both sockets are in the same runner process and the same network namespace. Connection 0 used the same address and port successfully seconds earlier.

## 3. Listener lifecycle (why connection 1 was refused)
- **[S]** `start_background` (`np_provider_peer.py:503-528`) calls `bind_listen()` **synchronously** (`:507`). A bind failure raises `PeerLifecycleError("bind failed")` (`:205-209`), and the run didn't stop there, so the listener was bound.
- **[S]** The worker sets `_ready` **before** `execute_script` (`:514-515`). Any exception there is stored in `self._error` and a note (`:516-518`), and `finally` closes the listener (`:519-521`). **Nothing reports this to the caller during the POST.**
- **[O]** The inventory has 4 connections (`np_provider_transcript.py:242-245`: identity default, identity list, then 2 calendarViews). So `multi` is true and `keep_listener=True` for index 0 (`np_provider_peer.py:487-490`); `_accept_once` keeps the listener open (`:258-259`).
- **[S]** `listen(1)` (`:210`): a merely busy peer queues connection 1 rather than refusing it. On Linux the default for a full accept queue is to drop the SYN, which would time out, not refuse. **A refusal requires the listener to be closed.**
- **[S]** Every listener close in the source:
  - `_accept_once` only when `keep_listener` is false (not the case at index 0);
  - `execute_script`'s `finally` (`:499-501`);
  - `_run`'s `finally` (`:519-521`);
  - `retire_owned` (`:530-541`).
  - The runner calls `retire_owned` only after the POST (`np_runner_entry.py:1115`, `:1188`), and the deadline was 120 s against about 11 s elapsed.
- **Therefore [S]:** the peer worker left `execute_script` with an exception after connection 0's response and before connection 1.

## 4. Why the worker exited (most likely trigger)
- **[O]** All Microsoft scripts end with `ExchangeStep("close", close_mode="orderly_close_notify")` (`np_provider_transcript.py:161`, `:187`, `:207`). After sending the response, the peer's only remaining step for connection 0 is `_close_connection` (`np_provider_peer.py:469-472`).
- **[O]** `_close_connection` in orderly mode (`:390-403`) calls `tls.unwrap()`, which sends close_notify and then **reads** the client's close_notify. It catches **only `ssl.SSLError`**; `finally` closes the TLS socket. Anything else propagates.
- **[O]** The production client does a **local close only**: `JoinedTLS.close()` → `self.sock.close()`, "no TLS unwrap or second network exchange" (`covering_joined_https.py:120-127`; it's also the T07-R08 contract at `:74-77`). `CoveringHTTP.request` reads the Content-Length body and closes (`covering_http_transport.py:331-345`, `_admit_fixed_length_complete` `:269-273`). It doesn't read the peer's close_notify.
- **[S]** The client therefore never sends close_notify, and it often closes with the peer's close_notify still unread. On Linux, closing a TCP socket with unread received data sends **RST**. If the client has already closed, the peer's close_notify write also draws an RST.
  - Inside `unwrap()`, CPython reports an `SSL_ERROR_SYSCALL` that has a nonzero errno as the plain errno `OSError` (`ConnectionResetError` or `BrokenPipeError`). That is **not** an `ssl.SSLError` subclass, so it escapes `_close_connection` → `_run_one_connection` → `execute_script` → closes the listener.
  - When the peer instead sees a clean EOF, it gets `SSLEOFError`, which is caught. **This is a timing race.** It also explains why nothing caught it before: I01 never used JoinedTLS against a real peer, and this NONEXPIRED vertical is the first native JoinedTLS-to-peer path.
- **[S] Elimination:** if the close step had raised an `SSLError`, it would have been caught, the script would have continued to accept connection 1, and the listener would have stayed open. That contradicts the observed refusal. The other post-response code (`exchange[...]` assignments, `_close_client`'s OSError-guarded closes) cannot raise anything that ends the loop.
- **[U]** The peer's actual exception class and errno: `self._error` and `life.notes` were not retained because the run stopped before `sanitized_state()` at `np_runner_entry.py:1038`. Also unknown: the client's SO_ERROR value (most plausibly ECONNREFUSED, which is consistent with a closed listener) and whether the earlier dex-v1 STOP at line 971 (non-200) had the same cause. That one is plausible but unproven.

## 5. Not a production defect
- **[S]** The production behavior is deliberate and contract-bound: one connection per exchange with `Connection: close` (`covering_http_transport.py:313-315`), fixed-length completion, and local close without unwrap (T07-R08).
- **[S]** A real HTTPS origin does not stop accepting new connections because one client reset a finished connection. The defect is the synthetic peer treating a reset during its own optional close_notify exchange as fatal to its whole inventory.
- **No production, contract, assertion or guard change is proposed.**

## 6. Narrowest proposed next step (fixture-only, one line)
`payload/fixture/np_provider_peer.py`, `SyntheticProviderPeer._close_connection`, line 394:

```diff
--- a/payload/fixture/np_provider_peer.py
+++ b/payload/fixture/np_provider_peer.py
@@ -391,7 +391,7 @@
             # Orderly TLS close_notify via unwrap; distinct from abrupt stream drop.
             try:
                 tls.unwrap()
-            except ssl.SSLError:
+            except OSError:
                 # Still mark attempted orderly path; abrupt fallback is separately scripted.
                 self.life.notes.append("close_notify_unwrap_ssl_error")
             finally:
```

- **Hashes:**
  - current peer `5568AF73DD42FEB5B8E2FE4D723AD4FB0339CBF4B889F5472995ABC628F72A55` (LF; payload `SHA256SUMS.txt` row 85);
  - **proposed `17EA148E6DE9E30485992FC49C310975076F5F4A71AB3AA9441B3B63C1ADA039`** (derived in memory; not written);
  - diff file `Matt-thePlan-Scheduler-Peer-Close-Notify-Proposed-2026-11-12.diff` = `023303AC81AC8F3F3460CBDE9E2AFAFFB4A3EA85D97FE547AD5C78E60B54B30D`.
- **Why `OSError`:** `ssl.SSLError` is a subclass of `OSError`, so every currently tolerated case is still tolerated. It adds tolerance for reset or broken pipe during the peer's own close_notify, and for a socket timeout bounded by the per-socket timeout set at `:276`. The `finally` still closes the TLS socket, and the `orderly_close_notify_attempted` note is still recorded.
- **Optional cosmetic:** I kept the note text `close_notify_unwrap_ssl_error` byte-identical to minimize the diff. No oracle reads that note (`grep` over the fixture finds no consumer).
- **Boundaries preserved:**
  - all production `api/app/**` files, the runner `341074AE`, the observer, `stop_payload` and its 3/8/128/4096 bounds, the host validator `7F7EA820`, the operator `5A8A04B6`, the configs, the batch and the deadlines;
  - the exact request-path and query checks (`:319-333`);
  - the strict post-POST oracle `served == admitted == len(inventory)` (`np_runner_entry.py:1038-1044`). The peer must still serve all 4 connections, so the fix cannot mask a missing exchange.
  - The `abrupt_truncate`, `normal` and stall modes are untouched.
- **Shared dependency:** the MS-REFRESH prep payload carries the same peer bytes (`5568AF73`), and T05 orderly-close paths use this function too. A fix would need re-pinning wherever this file is admitted. I suggest landing it in a fresh native successor first; MS REFRESH stays held.

## 7. What a focused fake would discriminate
Use the extracted **actual** `_close_connection` (source `5568AF73` versus the candidate `17EA148E`) with fake TLS objects. No sockets.
1. **`unwrap()` raises `ConnectionResetError`:** the source propagates (the mutant oracle) and the candidate swallows it. In both, `close()` is called exactly once, and the notes include `orderly_close_notify_attempted`.
2. **The same for `BrokenPipeError`, `TimeoutError` and an `SSLEOFError`** (the last already tolerated by both).
3. **`unwrap()` succeeds:** behavior and notes are identical.
4. **`abrupt_truncate` and `normal` modes:** byte-identical behavior.
5. **An extracted `execute_script` / `_run_one_connection` composition** with a fake listener and 2 scripts, where connection 0's close raises `ConnectionResetError`:
   - with the source, the listener is closed before the second accept (this reproduces the refusal mechanism);
   - with the candidate, it remains open and both connections are served;
   - `connection_count_served == 2`.
6. **A diff re-derivation:** exactly one line; all other peer functions unchanged.

## 8. Requires separately approved native execution
- that real loopback TLS between `JoinedTLS` and the peer now completes all 4 connections;
- the first-ever native Microsoft `ms_view` apply, the TOKEN, IMPORT and ASSESSMENT terminals and the response;
- the post-POST oracles (alias rewrite, coverage, and so on);
- whether any downstream defect remains.

The fake proves only the extracted close and inventory logic.

## Preservation
- the staging is at 283/283 with 0 mismatches;
- the evidence files were read, not modified;
- no container action;
- cleanup stays with its separate card.

The endpoint is unbound, and all other holds stay.

Signed: Matt
