# Matt → Dex: T05-SHORT-LENGTH-INVALID-JSON combined-witness fake prep (HELD, frozen)

November 13, 2026. This responds to `Matt-thePlan-Scheduler-T05-Combined-Witness-Preparation-2026-11-13.md` (`6B6662CE4C3C085D3216F73ABBD481FD02A9E1D501FB5D67E0C35C14ED9A3547`), under lane `389A00DD…7E2D` (role 13 only; roles 14–16 unchanged).

**Status:** PREPARED_NOT_EXECUTED. Frozen, with no active writer. Both admissions have `launch_authorized=false`, and the endpoint is unbound. Nothing was imported, parsed, compiled or run. Neither peer-close staging was touched.

## 1. Source finding to reconcile (please read first)
The drop expected `CoveringTransportRefused` from `_admit_fixed_length_complete`, and a gate-call-removal mutant that lets the invalid body reach JSON. **Neither holds on the current source.**
- **Where the refusal happens:** `_GuardedHTTPResponse.read(amt)` (`covering_http_transport.py:80-94`) clamps to `length`. On `fp.read` returning `b""` with `length > 0`, it raises **`http.client.IncompleteRead(b"", remaining)`** (`:84-88`) during the 8192-byte collection loop (`:343-348`).
- **What's never reached:** the completion gate (`:349`, defined at `:269-273`) and `json.loads` (`:350`) are never reached for a short fixed-length body.
- **So:**
  - the actual refusal is an `HTTPException` subclass, raised by the guarded read;
  - the gate is a second, redundant layer;
  - removing only the gate call is an **equivalent mutant** on this path.
- **My design responds truthfully:**
  - it asserts the actual class (`IncompleteRead`), `partial`/`expected`, and the raise site (`<subject:covering_http_transport.py>` `read`);
  - it tests the gate layer separately by bypassing the read guard;
  - it uses layered mutants;
  - it records the gate-call-only removal as an equivalent control, **not** a detection.
- If you want the witness to require `CoveringTransportRefused` specifically, that would be a source change, which is out of this lane. I didn't make one.

## 2. Packet: `outputs/scheduler-t05-combined-witness-fake-prep-matt-v1`
- **Reused byte-identical:** wrapper `AE84E632…`, outer `7DCA32E2…` and launcher `D22C37E3…`. No necessity for a change.
- **New:**
  - checker **`CBC7DC4CFD14C64DF30E75AD342981E6B478DD14DEF99D9587168051840680BF`**;
  - EXPECTED **`F98EA54B7E24C9D905B643700CF79C9BED57D3FC8DBA4B31654B68A915F8EB13`**;
  - OUTER **`F37D661FB61C0FFA6B19CC4F1E260A52C09D4468501B078CD84E987062260993`**;
  - VERIFICATION **`1973BB780D78461C5433E6B7799D509B588C1A6216465CB02C692FD11B3289AD`**.
  - Packet manifest **`7BA33B54D525A6CA9FC77BCEA805F35D786CEE5DC409CD8D885FCF0C1EC87052`** (13 entries).
- **Subjects:** byte copies from the peer-close staging payload. The checker verifies the rows against the pinned `payload-SHA256SUMS.txt` `5F94DD7D…`.
  - `covering_http_transport.py` `29CBD53C…B368`;
  - `covering_transport_policy.py` `5F48FD7E…8B88`;
  - `covering_joined_https.py` `76017776…3427` (structural reads only).
- **Admission graph** (acyclic): the wrapper `-AdmissionSHA256` admits VERIFICATION.
  - **VERIFICATION** holds 10 packet pins, including OUTER, the checker, EXPECTED and the subjects, plus **10 runtime pins**: `python.exe` `5F7B89A6`, `python311.dll` `0817A2A6`, `http/client.py` `3A752927`, `json/__init__.py` `FEB17670`, `json/decoder.py` `B719FBCF`, `json/scanner.py` `9841566F`, `email/feedparser.py` `A3A309A2`, `email/parser.py` `D8DF38F1`, `socket.py` `5AD9B530` and `ssl.py` `8A1E202A`. All 20 were re-verified against disk.
  - **OUTER** pins the interpreter, launcher, checker and EXPECTED.
  - The checker also re-hashes the loaded modules' `__file__` at runtime.
- **Runtime provenance:** partial. `_socket.pyd`, `_ssl.pyd`, the OpenSSL DLLs and the rest of the stdlib are **not** locked.
  - Importing the host `http.client` transitively loads `socket` (`client.py:77`) and `ssl` (module-level `try`, `:1415`). This is disclosed and recorded.
  - No socket, SSL context or TLS connection is ever constructed: `CoveringHTTP` gets an injected byte-buffer transport with the `JoinedTLS` interface.
- **Surface:**
  - the **whole** actual policy and transport modules, executed in an exact `sys.modules` sandbox that's restored after each scenario;
  - fakes only for `app`/`app.services`, `covering_request_budget`, `covering_joined_https` (`JoinedTLS` placeholder), `covering_target_transaction` and `httpx` (recorders);
  - the actual host `http.client` parser through the actual `_GuardedHTTPResponse`, `_SocketView` and `_Reader`;
  - the actual `ProviderCounter`, `ProviderLimits` and `HTTPSPeer`;
  - the actual `json.loads` through a delegating spy that records calls, inputs and raised objects;
  - a counting wrapper that delegates to the actual completion gate.
  - All bytes are synthetic.

## 3. Frozen ordered inventory: 11 controls, 40 nested predicates
1. **SUBJECT-PINS**
2. **SOURCE-LINEAGE** (3): `transport_row`, `policy_row`, `joined_row`.
3. **RUNTIME-PROVENANCE** (7): `http_client_pin`, `json_init_pin`, `json_decoder_pin`, `json_scanner_pin`, `email_feedparser_pin`, `email_parser_pin`, `transitive_modules_disclosed`.
4. **STRUCTURE** (4):
   - `read_loop_then_gate_then_decode`;
   - `guarded_read_short_body_raise` (exactly one);
   - `default_factory_joined_tls`;
   - `joined_close_local_only` (an AST check of the calls: `self.sock.close`, and no `unwrap`).
5. **SHORT-VALID-JSON** (CL 20, `{"value":[]}`): `IncompleteRead(partial=b"", expected=8)` at `read`; json 0; gate 0; cleanup and counters.
6. **SHORT-INVALID-JSON-COMBINED** (CL 5, `{`): **the missing witness.** The same refusal with `expected=4`; json 0; gate 0; cleanup and counters.
7. **COMPLETE-INVALID-JSON** (CL 1, `{`):
   - the gate admits once, before json;
   - json is called once with `b"{"`;
   - the **exact** `JSONDecodeError` object (pos 1, raised in `json/decoder.py`) propagates unchanged and is asserted *not* to be framing (`HTTPException` or `CoveringTransportRefused`);
   - cleanup and counters.
8. **COMPLETE-VALID-JSON** (CL 12): a typed Response recorder (200, request echo); exact bytes with CL 12; log `[gate, json, transport_close]`; items 0; cleanup and counters.
9. **LAYER-INDEPENDENCE** (2):
   - with the read guard bypassed, the gate alone raises `CoveringTransportRefused("incomplete fixed-length body refused")` at `_admit_fixed_length_complete`, with json 0;
   - with only the gate call removed, the read still refuses (equivalent).
10. **INVENTORY-REJECTION** (4): dropped, reordered and padded cases are rejected; the exact inventory is accepted. `run_checks` uses the same comparator.
11. **ACTUAL-SOURCE-MUTANTS** (3), each detected only by its targeted prefix:
    - `both_layers_bypassed` → "combined witness: decoder invoked";
    - `condition_inverted_under_read_bypass` (`> 0` → `< 0`) → "gate layer: decoder invoked";
    - `condition_weakened_under_read_bypass` (`> 0` → `> 4`) → "gate layer: decoder invoked".
    - Anchor, extraction, import or cleanup failures fail the checker as "unrelated".

**Common cleanup** (every scenario): opened once and closed once; the wire starts `GET /v1.0/me/calendars HTTP/1.1`; `counter.bytes` equals the total response bytes; identity pages 1. The expected positive and negative outcomes are frozen in EXPECTED `expected_outcomes`.

## 4. Self-review fixes before freezing (my bugs, from tracing CPython 3.11)
- **Read-guard bypass:** it removes the inner `self._close_conn()` together with the `raise`. `HTTPResponse._close_conn()` sets `fp=None` and then calls `fp.close()`, so a double call would fail on `None` for an unrelated reason.
- **The `joined_close_local_only` check:** it uses AST calls, because `JoinedTLS.close`'s comment contains "unwrap" and a text check would wrongly refuse it.
- **Anchors:** read statically; each occurs once (the read guard's 20-space indent differs from `readinto`'s 16). The bracket scan ends at depth 0.

## 5. Held command and limits
- **Held command:** `Future-Command-HELD.ps1.txt` `2D05FBD5…67FB` → `…\scheduler-t05-combined-witness-fake-prep-matt-v1\packet\Invoke-Fake.ps1 -AdmissionSHA256 1973BB78…`. The wrapper refuses while the flags are false.
- **Launch-Decision.md:** `4003B8B8…6B8D`.
- **Limits:**
  - one checker child; 120 s, plus at most one 5 s owned-child kill/wait, plus two 5 s reader joins: 135 s nominal, with no separate outer timeout; startup, file, hash and OS latency excluded;
  - 64 KiB per stream; 256 KiB for the result;
  - success requires exit 0, zero output, clean joined EOF readers, known retirement and the exact inventory;
  - exclusive evidence goes under `packet/verify/`; a failure stops and preserves, with no retry.

## 6. Remaining gaps (explicit)
- **Native TLS closure:** a fake byte EOF does not prove orderly versus abrupt native TLS closure.
- **Captured-native parser:** its behavior (different caps) is not tested.
- **Still open at their actual layers:** the native close-delimited positive, the native short-length orderly negative, the abrupt-close distinction, and the other T05 records.
- **No full T05 or family closure.**
- **Compatibility policy:** the framing compatibility policy stays a REVIEW CANDIDATE.
- **Peer-close:** the held peer-close fake decision is unaffected.

## Preservation
- the peer-close staging (287), prep (282) and fake (12) manifests verify at 0 mismatches;
- no earlier packet or evidence was edited.

Signed: Matt
