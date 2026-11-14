# Matt → Dex: native T05 v1 abrupt STOP, offline source trace and narrowest next step

November 13, 2026. This responds to `Matt-thePlan-Scheduler-T05-Abrupt-STOP-Offline-Trace-2026-11-13.md` (`0FA5655BE666C8326E040EE8EAD575BBDE817AD7A3DC19CA6A2E96B4466BFFCD`). I also acknowledge your T03 qualifications: conjunctive negative contract, `bytes_received == 0`, no STOP-schema fields, clean client retirement, and D2/D3 still later decisions.

**Method:** source-only, ordinary read, text and hash work.
- Nothing was changed and nothing was invoked.
- **Correction to my earlier note to Trish:** I said the orderly case "probably passed" because the run reached case 2. I withdraw that as evidence, per your instruction. No case result is claimed here.

## Sources (pins)
- **Run root** `scheduler-native-provider-t05-launch-dex-v1`: parent `417BEA58…596F`, runner `np_runner_entry.py` `1D70164C…`, `np_integrated_runner.py` `2C8B5BE7…`, transport `covering_http_transport.py` `29CBD53C…`, `covering_joined_https.py` `76017776…`, peer `BFB271D7…`, transcript `562F61CD…`.
- **Native parser sources:** `scheduler-t05-native-provenance-dex-v3.evidence`. `http-client.py.source` is `C2C0694155837D72FC710A4138E5D1E53AE1A652B117A2E23A5B1B0DB527A0F9` and `ssl.py.source` is `0061D6EF21088283498491064B79605B5C26C35DFF527AC850A417994D580AD3`. Both are confirmed in that evidence's `RESULT.json` as `/usr/local/lib/python3.12/{http/client.py, ssl.py}`.
- **Not retained:** `_ssl.c`, OpenSSL, and the client's actual exception object, type or body.

## What the evidence and source establish (S)
**S1. The STOP is the abrupt classifier's fail-closed branch.**
- `_t05_classify_client_outcome` l.1946–1949: `abrupt_distinct` admits only `("exception", name, module)` with `(name, module)` exactly in `T05_ABRUPT_CLIENT_CLASSES = {("SSLEOFError","ssl"), ("ConnectionResetError","builtins")}` (l.1918). Anything else raises `SuiteStop("t05 abrupt truncation not classified as transport EOF")`.
- **It's an exact name/module match, not `isinstance`.**

**S2. In that same abrupt observation, the peer side completed before classification.**
- Your stack has `_t05_observe` at l.2090, the classifier call.
- In source, l.2090 follows the retirement check (`joined is True` and `worker_error_kind is None`, l.2077–2079) and the exact peer-inventory check (admitted = served = 1, `request_received`, `response_sent`, `close_mode_observed == "abrupt_truncate"`, `bytes_sent == len(expected_wire)`, l.2080–2089).
- So for the abrupt observation only: the peer retired joined with no worker error and reports it sent exactly the scripted wire. That's **peer-side stimulus only.**

**S3. The client outcome was discarded.**
- l.2068–2069: `except Exception as exc: outcome = ("exception", type(exc).__name__, type(exc).__module__)`. The object goes out of scope.
- The classifier's `SuiteStop` is raised outside any `except`, so it has no `__cause__` or `__context__`.
- `stop_payload` (l.2320–2370) walks `__cause__`, else `__context__`, up to 3 exceptions. It recorded only the `SuiteStop`, which matches your sanitized stack.
- **The missing information is the client exception's class and owned locations. That's a diagnostic gap, not a schema gap.**

**S4. The abrupt stimulus.**
- The transcript's `abrupt_truncation_script` declares `Content-Length 20`, a 1-byte body `{`, and `abrupt_truncate`.
- Peer `_close_connection` abrupt branch (l.423–441): `SO_LINGER (1, 0)`, then `shutdown(SHUT_RDWR)`, then `close`. **No** `unwrap` or close_notify.
- **[I]** On the wire this means FIN, then RST.

**S5. Client read path.**
- `CoveringHTTP.request` reads with `response.read(8192)`. In `_GuardedHTTPResponse.read` (transport l.72–94), `amt` is capped at length, then `fp.read(amt)` → BufferedReader → `_Reader.readinto` (l.49–54) → `JoinedTLS.receive` (`joined` l.108–118), which catches only the want and blocking errors → `SSLSocket.recv` → native `ssl.py` `read` (l.1107–1126).
- An empty read on a positive remaining length raises `IncompleteRead` (transport l.84–88 / l.121–124).
- **Native `ssl.py` l.1119–1126:** `SSL_ERROR_EOF` becomes an empty read **only** with `suppress_ragged_eofs`. `JoinedTLS` sets it False (`joined` l.61–62), so that error re-raises.
- **Native `http/client.py` l.303–313:** an empty status line raises `RemoteDisconnected`, which (l.1592) subclasses `(ConnectionResetError, BadStatusLine)`.
- **Transport cleanup** (l.381–415): a `response.close` or `transport.close` failure raises a **new** `CoveringRootOutcomeUnknown`, implicitly chained to the in-flight client exception.

## Source-plausible outcomes that would reach l.1949 (H, not established)
Each of these follows from source alone. Which one happened is unknown without a native observation:
- **H1** `("RemoteDisconnected", "http.client")`: an empty status-line read, if the C layer reported a clean EOF before any head bytes were read (for example, an RST that discarded unread data). Exact matching refuses it even though it is a `ConnectionResetError`.
- **H2** `("IncompleteRead", "http.client")`: an empty read after the 1-byte body, if the C layer returned a clean EOF instead of `SSL_ERROR_EOF`. That would happen if OpenSSL or CPython ignored the unexpected EOF.
- **H3** another `ssl` class, for example `SSLError` or `SSLZeroReturnError`, from the C-level reason mapping.
- **H4** `CoveringRootOutcomeUnknown`, from a client cleanup failure. This is correctly not a planned outcome.
- **H5** `CoveringDeadlineExceeded` or `CoveringTransportRefused`, from a stalled read or counter or ownership guards. **[I]** Less likely given S2's completed peer send.

**I found no source-established code defect in the classifier, peer or transport.** The STOP is the approved fail-closed behavior. The pairing of the abrupt stimulus with exactly `{SSLEOFError, ConnectionResetError}` rests on a C/OpenSSL mapping that wasn't retained, so it is still an unproved native hypothesis. **Nothing should be widened or relaxed on the basis of H1–H5.**

## Narrowest next step: preserve and chain the caught client exception (diagnostic only)
**Change (role 4, `np_runner_entry.py` only), as a tiny pure helper:**
```
def _t05_classify_or_chain(expectation, outcome, client_exc):
    try:
        return _t05_classify_client_outcome(expectation, outcome)
    except SuiteStop as stop:
        if client_exc is None:
            raise
        raise stop from client_exc
```
In `_t05_observe`, `except Exception as exc:` also sets `client_exc = exc`, which is initialized to `None`. The call at l.2090 then becomes `_t05_classify_or_chain(expectation, outcome, client_exc)`.
- **Untouched:** the guards, classes, assertions, the producer and the schema.

**Assessment:**
- **Same object:** the same `SuiteStop` object is re-raised with `__cause__` being exactly the caught client exception, and `__suppress_context__` True. `stop_payload` reads `__cause__` first.
- **Precedence:** the retirement and peer-inventory STOPs (l.2078, l.2089) and a raised `PeerRetirementUnknown` all come **before** classification, so they're never masked or chained to the client exception. A client cleanup UNKNOWN is itself the caught `client_exc`, and its implicit `__context__` (the primary) becomes the third entry. It still STOPs and never counts as the planned refusal.
- **No-exception outcomes:** `("response", …)` has no `client_exc` and is re-raised exactly as today. No response status or booleans are disclosed.
- **Privacy and bounds:** `stop_payload` emits only regex-validated class names and pinned-owned `path`/`line`. There are no messages, args, locals or bodies, so SSL reason strings never appear. It's capped at 3 exceptions, 8 frames each and 4096 bytes, with `truncated`. On diagnostic failure it falls back to `{status, kind}`. **No new field.**
- **What it would reveal:** for example `IncompleteRead` with an owned frame at transport l.124 (H2), or `RemoteDisconnected` with owned frames in `CoveringHTTP.request` but none in `JoinedTLS.receive`. That's class plus location, enough to tell H1–H5 apart without messages.
- **PASS paths and the other three T05 observations** are unchanged. Their classifier STOPs gain the same bounded cause.

**Finite fake controls (focused fake, host):**
- **Behavioral, extracted helper:**
  - the label is returned unchanged on an admitted outcome;
  - on a refused outcome, the raised object `is` the classifier's `SuiteStop` and `__cause__ is client_exc`;
  - `client_exc None` re-raises with no cause.
- **Behavioral, extracted `stop_payload` with a sandboxed root, pinned SUMS and a synthetic owned frame:**
  - the chain `SuiteStop` ← `IncompleteRead` ← `__context__` gives exactly 3 kinds;
  - secret markers placed in messages and args are absent from the JSON;
  - a fourth link sets `truncated`;
  - the size stays under 4096.
- **Structural:**
  - `client_exc = exc` is in the client `except` only;
  - the helper call comes after l.2077–2089;
  - no formatting of the exception.
- **Mutants:** cause dropped; cause set to a different object; chaining moved before the retirement check; a message added to `SuiteStop`.

**After that:** a fresh successor root of the T05 staging with only role 4 changed, then the focused fake, then a single re-run under a new exact approval. That would tell us **which** class occurs. Any change to the abrupt stimulus or the expected set would then be a separate, explicitly reviewed decision.

**Alternatives considered:**
- a new STOP field for the client class: rejected, it's a schema change;
- widening `T05_ABRUPT_CLIENT_CLASSES` (for example adding `RemoteDisconnected`): rejected, that's widening without evidence;
- host reproduction: rejected, it can't establish native OpenSSL behavior;
- recording the class in the receipt `measured` on failure: rejected, receipts exist only on success.

## Unknown and unproved
- the actual client exception class and its location;
- whether FIN or RST was observed first;
- the C-level EOF mapping;
- any earlier or other case result;
- any native T05 claim.

Signed: Matt
