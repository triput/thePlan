# T05-SHORT-LENGTH-INVALID-JSON combined witness: focused fake preparation (HELD)

Matt, November 13, 2026. This is for assignment `Matt-thePlan-Scheduler-T05-Combined-Witness-Preparation-2026-11-13.md` (`6B6662CE…3547`), under lane `389A00DD…7E2D` (role 13 checker; roles 14–16 unchanged). It closes the gap that `scheduler-investigation/Transport-Completion-Audit-Current.json` records at `T05-SHORT-LENGTH-INVALID-JSON` and `direct_combined_witness_gap` as a **finite host-fake witness only**.

**No execution is authorized.** Nothing here has been imported, parsed, compiled or run. Both admissions have `launch_authorized=false`. No PASS is claimed.

## Important source finding: the refusal layer
The current code refuses a short fixed-length body **inside the guarded read**, not at `_admit_fixed_length_complete`:
- `covering_http_transport.py:80-94`: `_GuardedHTTPResponse.read(amt)` clamps `amt` to `length`. When `fp.read` returns `b""` with `length > 0`, it raises **`http.client.IncompleteRead(b"", remaining)`** (`:84-88`).
- `CoveringHTTP.request` collects with `response.read(8192)` (`:343-348`), so a short body raises during collection. `_admit_fixed_length_complete(response)` (`:349`, defined at `:269-273`) and `json.loads` (`:350`) are never reached.
- **Consequences:**
  - On this path the refusal type is `IncompleteRead`, an `http.client.HTTPException`, and not `CoveringTransportRefused`.
  - The completion gate is a second, redundant layer.
  - Removing only the gate call is an **equivalent mutant** here; it cannot make invalid JSON reach the decoder.
- The witness therefore asserts the actual refusal class and site, tests the gate layer separately, and uses layered mutants. It does not count an equivalent mutant as a detection.

## Roles and pins
- **Reused byte-identical:** wrapper `Invoke-Fake.ps1` `AE84E632…FEB7`, outer `verify_admission.py` `7DCA32E2…18FB`, launcher `launch_check.py` `D22C37E3…BD07`. No helper changes were needed.
- **New:**
  - checker **`CBC7DC4CFD14C64DF30E75AD342981E6B478DD14DEF99D9587168051840680BF`**;
  - EXPECTED **`F98EA54B7E24C9D905B643700CF79C9BED57D3FC8DBA4B31654B68A915F8EB13`**;
  - OUTER **`F37D661FB61C0FFA6B19CC4F1E260A52C09D4468501B078CD84E987062260993`**;
  - VERIFICATION **`1973BB780D78461C5433E6B7799D509B588C1A6216465CB02C692FD11B3289AD`**.
- **Subjects:** byte copies from `scheduler-native-provider-peer-close-launch-dex-v1` payload, all LF, with a CRLF-pair-safe predicate:
  - `covering_http_transport.py` `29CBD53C…B368`;
  - `covering_transport_policy.py` `5F48FD7E…8B88`;
  - `covering_joined_https.py` `76017776…3427`;
  - `payload-SHA256SUMS.txt` `5F94DD7D…CCD6`. The checker verifies the three subject rows against it.
- **Runtime pins** (10 files; the wrapper verifies each by absolute path):
  - `python.exe` `5F7B89A6`, `python311.dll` `0817A2A6`;
  - `Lib/http/client.py` `3A752927` (it matches the transport docstring);
  - `Lib/json/__init__.py` `FEB17670`, `decoder.py` `B719FBCF`, `scanner.py` `9841566F`;
  - `Lib/email/feedparser.py` `A3A309A2`, `parser.py` `D8DF38F1`;
  - `Lib/socket.py` `5AD9B530`, `Lib/ssl.py` `8A1E202A`.
  - The checker also re-hashes the loaded modules' `__file__` at runtime.
  - **Partial scope:** `_socket.pyd`, `_ssl.pyd`, the OpenSSL DLLs and the rest of the stdlib are not locked.

## Fake surface
- **Actual source, executed whole:** `covering_transport_policy.py` and `covering_http_transport.py`, inside an exact `sys.modules` sandbox that is restored after each scenario.
- **Fakes, installed only for imports that aren't under test:**
  - `app` and `app.services` (packages);
  - `covering_request_budget` (`CoveringDeadlineExceeded`);
  - `covering_joined_https` (a `JoinedTLS` placeholder; `covering_joined_https.py` itself is read structurally only);
  - `covering_target_transaction` (`CoveringRootOutcomeUnknown`);
  - `httpx` (Request and Response recorders).
- **Actual stdlib:** the host `http.client` parser through the actual `_GuardedHTTPResponse`, `_SocketView` and `_Reader`; the actual `json.loads` through a spy that delegates to it and records calls, inputs and the raised objects.
- **Actual policy objects:** `ProviderCounter`, `ProviderLimits` (`approved_provider_limits`) and `HTTPSPeer`, through `CoveringHTTP.request`.
- **Transport:** an injected byte-buffer transport with the `JoinedTLS` `open`/`send`/`receive`/`close`/`sent` interface.
- **Never used:** socket, SSL or TLS constructors. Importing `http.client` loads `socket` (and `ssl` inside a module-level `try`); this is disclosed and recorded.
- **Data:** all bytes are synthetic, with a synthetic Bearer token.

## Controls (11 top-level, 40 nested predicates, in order)
1. **SUBJECT-PINS**
2. **SOURCE-LINEAGE** (3): the transport, policy and joined rows in the pinned payload manifest equal the subject pins.
3. **RUNTIME-PROVENANCE** (7): the six loaded-module pins, plus the transitive `socket`/`ssl`/`_ssl`/`_json` loading, recorded as disclosure.
4. **STRUCTURE** (4):
   - in the `request` try: read loop, then the gate call, then `decoded=json.loads(body)` immediately after;
   - exactly one guarded-read `IncompleteRead` raise;
   - the default factory is `JoinedTLS`;
   - `JoinedTLS.close` calls `self.sock.close` and never `unwrap` (an AST check of the calls, not the comment text).
5. **SHORT-VALID-JSON** (CL 20, body `{"value":[]}`, 4 predicates): exact `IncompleteRead(partial=b"", expected=8)` raised at `<subject:covering_http_transport.py>` `read`; json calls 0; gate calls 0; cleanup and counters.
6. **SHORT-INVALID-JSON-COMBINED** (CL 5, body `{`, 4 predicates): **the missing witness**. The same refusal, with `expected=4`; json calls 0; gate calls 0; cleanup and counters.
7. **COMPLETE-INVALID-JSON** (CL 1, body `{`, 4 predicates):
   - the gate admits (1 call), and runs before json;
   - json is called exactly once with `b"{"`;
   - the **exact** `json.JSONDecodeError` object raised in `json/decoder.py` (pos 1) propagates unchanged;
   - it's asserted *not* to be an `HTTPException` or `CoveringTransportRefused`.
8. **COMPLETE-VALID-JSON** (CL 12, 4 predicates): a typed Response recorder (200, request echo); exact body bytes with Content-Length 12; log exactly `[gate, json, transport_close]`; items 0.
9. **LAYER-INDEPENDENCE** (2):
   - with the read guard bypassed, the gate alone raises `CoveringTransportRefused("incomplete fixed-length body refused")` at `_admit_fixed_length_complete` with json 0;
   - with only the gate call removed, the read still refuses (equivalent; not a detection).
10. **INVENTORY-REJECTION** (4): the nested-inventory comparator rejects a dropped, reordered or padded case and accepts the exact inventory. `run_checks` uses the same comparator.
11. **ACTUAL-SOURCE-MUTANTS** (3). Each is detected only by its targeted oracle's first failing predicate:
    - `both_layers_bypassed` (read guard and gate call removed) → "combined witness: decoder invoked";
    - `condition_inverted_under_read_bypass` (`remaining > 0` → `< 0`) → "gate layer: decoder invoked";
    - `condition_weakened_under_read_bypass` (`> 0` → `> 4`) → "gate layer: decoder invoked".
    - Any anchor, extraction, import or cleanup failure fails the checker as "unrelated".

**Common cleanup and counters** (every scenario): the transport is opened once and closed once; the wire starts `GET /v1.0/me/calendars HTTP/1.1`; `counter.bytes` equals the total response bytes; the identity page count is 1.

## Self-review fixes before freezing (my bugs, caught by tracing CPython 3.11)
- **Read-guard bypass mutation:** it removes the inner `self._close_conn()` together with the `raise`. `HTTPResponse._close_conn()` sets `fp=None` then calls `fp.close()`, so two consecutive calls would fail on `None` for an unrelated reason.
- **Local-close structure check:** it uses AST calls, because the method's comment contains "unwrap".
- **Anchors:** each was read statically as unique in the transport text (the read guard's 20-space indent differs from `readinto`'s 16).

## Not proved, remaining gaps
- **Native TLS closure:** a fake byte EOF does not distinguish orderly from abrupt native TLS closure.
- **Captured-native parser:** its behavior (interim and trailer caps differ) is not tested; only the host parser is.
- **Still open at their actual layers:**
  - the native close-delimited positive;
  - the short-length orderly negative natively;
  - the abrupt-close distinction;
  - the rest of the T05 family.
- **No full T05 or family closure.**
- **Compatibility policy:** the framing compatibility policy stays a REVIEW CANDIDATE (unchanged).

## Limits (inherited launcher)
- **Timing:** one checker child; 120 s, plus at most one 5 s kill/wait, plus two 5 s reader joins: 135 s nominal, with no separate outer timeout. Startup, file and OS latency are excluded.
- **Capture:** 64 KiB per stream; 256 KiB for the result.
- **Success** requires exit 0, no output, clean joined EOF readers and the exact inventory.
- **Exclusive evidence** goes under `packet/verify/`; a failure stops and preserves, with no retry.

## Future command
`Future-Command-HELD.ps1.txt` (admission `1973BB78…`). The wrapper refuses while the flags are false.
