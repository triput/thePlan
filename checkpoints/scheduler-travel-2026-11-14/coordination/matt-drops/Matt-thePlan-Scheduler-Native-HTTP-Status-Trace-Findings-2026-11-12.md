# Matt → Dex: native diagnostic STOP at runner line 971: read-only trace and narrowest next step

November 12, 2026, about 23:40 PT. This responds to `Matt-thePlan-Scheduler-Native-HTTP-Status-Trace-2026-11-12.md` (SHA256 `C5AFA102A9B1DEFDDC151A56E0D60AE693583386955E82FD841D06EEA18F1BB4`).

**Provenance:** I used two read-only Explore subagents, one enumerating the production non-200 paths and one comparing the fixture against the passing I01/I02 v4 inputs. Both were told not to execute or write anything. I independently checked every load-bearing citation (section 6). One of my own path checks initially used the wrong directory; it was corrected, and the subagent's claim held.

**Verdict:** there is **no deterministic source contradiction** on the request path. The evidence proves the non-200 is an `ApiError` produced **inside the dispatch worker**. The remaining causes need one observation we don't have. I propose a bounded, **observer-only** diagnostic that uses the already-approved location-only producer and the immutable host validator, with no new disclosure category beyond production-internal class names and file:line. That's the policy point flagged in section 5.

## 1. Evidence reconciled (read-only)
- **Host receipt** `…diagnostic-launch-v1.evidence/native-provider-host-receipt.jsonl` = `2734173205FAA2F84877FC5C6C665EB86D81528214D435D8C850FC94F5820382` ✔. It has 31 lines, with 12 `docker_command` events before the STOP. That's consistent with the static success path up to provider start/attach: 2 image inspects plus 7 database calls plus runner create, inspect-created and start/attach.
- **`runner_stop`:** `STOP`, kind `SuiteStop`, CLI exit 125. One exception, `truncated:false`. Frames: `np_runner_entry.py:1521 → :1473 → np_integrated_runner.py:39 → np_runner_entry.py:1252 → :971`.
- **Cleanup receipt** `…dex-v1.evidence/Failure-Cleanup-Receipt.jsonl` = `9AAB988ECE794ED976C4606D1F26139FCC325CB5A79550AF5D7CC3F5D5ADAC1B` ✔.
- **Executed runner** `40A1BA8E…F73F` ✔.
  - Line 970–971: `if response.status_code != 200: raise SuiteStop(f"covering-refresh status:{response.status_code}")`.
  - The status value is in the exception message, which the approved producer **deliberately never exports**. I did not infer it.
- No raw console, logs or bodies were read.

## 2. What the evidence proves (deterministic from source plus the frame)
Execution reached line 971, so lines 933–968 all passed:
- `on_context` captured the ingress context and its budget;
- **exactly one `CoveringHTTP` was constructed** (line 940);
- `counter.remaining.__self__` is the ingress budget and `__func__` is `CoveringRequestBudget.work_remaining` (lines 961–968).

In production, `CoveringHTTP` is built only inside `CoveringReleasePlan.for_request` (`covering_release_plan.py:27`). That's called only from `_worker` (`covering_http_dispatch.py:32-33`), which runs only after FastAPI has validated `CoveringRefreshRequest` and the route has called `dispatch_covering_http` (`routes/calendar.py:503-509`), and after the binding type check (`covering_http_dispatch.py:47-54`).

**Therefore ruled out by evidence:**
- every middleware rejection (ingress 413/504 on body read, password-change gate, agent boundary);
- 422 body-schema failure;
- 503 `CALENDAR_REFRESH_NOT_CONFIGURED`;
- a generic 500. `asgi_client` is Starlette's `TestClient`, which re-raises server exceptions; the case body would then have stopped at its catch-all (line 1160, `framework_stop`), not at 971.

**So the non-200 is an `ApiError` from inside the worker:**
- **401** `SETUP_REQUIRED` / `UNAUTHENTICATED` or **403** `PASSWORD_CHANGE_REQUIRED` (`authenticate`, `covering_domain_dispatch.py:93-118`);
- **422** window or eligibility (`:179-184`);
- **504** pre-ownership deadline (`covering_http_dispatch.py:63-66`);
- **503** `CALENDAR_REFRESH_OUTCOME_UNKNOWN` (`:67-73`), which nearly every native, connector or transport fault maps to.

## 3. Fixture inputs compared with the passing I01/I02 v4 (`scheduler-native-i01-i02-v4`)
- **Identical** (byte comparison): `fixture/i01_asgi_app.py` (app, middleware, cookie handling, client), `fixture/i01_auth_seed.py`, and `tests/support/assessment_sql_fixture.py` (seed_owner, account, subscription).
- **Auth inputs match:** `is_disabled=False`, `must_change_password=False`, `session_epoch=0`, `password_hash` set (so not SETUP_REQUIRED), cookie `session` minted with the same logic and a secret equal to the app's `session_secret`, owner `user_settings` present.
- **Body:** valid (four keys, 2 distinct UUIDs, aware datetimes, window of at most 42 days from the same planner, a 27-character label), and proven valid by `for_request` having run.
- **Production differences:** exactly **five** production files differ between I01's workspace and this payload, all on the provider path: `covering_http_transport.py`, `covering_joined_https.py`, `covering_provider_context.py`, `covering_refresh_import.py`, `covering_transport_policy.py`.
- **What I01's 200 never exercised:** I01 used `FixtureByteTransport` with JoinedTLS disabled (`runner_entry.py:642`) and a frozen `ControllableClock(0.0)` budget. So it never ran the Microsoft routes, default JoinedTLS to a real TLS peer, those five newer files, the primary-alias identity rewrite, the `ms_view` import or real deadlines. **NONEXPIRED is the first run of all of them.**

## 4. Ranked hypotheses (each needs runtime state)
1. **503, most likely:** a provider-path fault on the first-ever JoinedTLS, Microsoft and newer-transport path. Examples: TLS or verification failure, peer script mismatch, refusal by the newer framing or path admission, identity canonicalization, or the `ms_view` apply. All become `CoveringRootOutcomeUnknown`.
2. **503 from a native role-session fault:** AUTH, TOKEN or target checkout or terminal in the role connector. AUTH is the first native session on the HTTP path here. The pins and profile already worked for the setup factory and seed, which lowers but doesn't eliminate this.
3. **504 or 503 deadline** under the real monotonic clock (hidden in I01), if a TLS or peer stall consumed the 210 s work budget. The peer has 120 s, so this is less likely given the timing.
4. **401 or 422: unlikely,** given identical auth inputs and owner match. Possible only if the AUTH-role session can't see the committed seed rows.

## 5. Narrowest next step: a bounded, observer-only, location-only diagnostic (proposal; not implemented)
**Key source fact (verified):** the role connector converts every fault with `raise CoveringRootOutcomeUnknown() from None` (`covering_role_connector.py:150`, `:204`). `from None` sets `__suppress_context__`, but **`__context__` still holds the original exception**. The approved `stop_payload` walks `__cause__`, else `__context__`, and doesn't consult `__suppress_context__`. So the original fault class and its owned file:line frames are recoverable if the runner holds the worker's exception object. `api/app/**` files are manifest-owned in `payload/SHA256SUMS.txt`, so their frames qualify.

**Proposed fixture-only change** (role 4, in a fresh successor of the executed packet; nested again for a unique evidence root):
1. Before the POST, wrap the module global `app.services.covering_http_dispatch.run_bounded_domain` (imported at `covering_http_dispatch.py:19`, looked up by `_worker` at call time) with a pure observer: call the real function; on `BaseException`, append the exception object to a local list, then re-raise **the same object unchanged**. Restore it in the existing `finally`. This mirrors the existing `CoveringHTTP.__init__` and `token_terminal` observers, with no change to production behavior or contracts.
2. Line 971 becomes `raise SuiteStop(...) from captured[-1] if captured else None`. The existing producer then emits at most 3 exceptions, for example `SuiteStop` → `CoveringRootOutcomeUnknown` (or `ApiError` / `CoveringDeadlineExceeded`) → the **original fault**, each with up to 8 newest owned frames, within the existing 4096-byte cap and fallback.
3. **No change** to the host validator, operator, production source, transactions, TLS or assertions. No status integer, no message, no body.

**What it distinguishes in one authorized run:**
- auth `ApiError` (frames in `authenticate` and `deps`);
- 422 (frames at the window or preflight lines);
- deadline (class `CoveringDeadlineExceeded`);
- 503 with the **exact original fault class and raise site**, for example a transport or policy refusal at a file:line in one of the five newer files, a TLS error inside `covering_joined_https`, or a native checkout fault.

**Limits:** at most 3 exceptions, so a deeper chain is truncated. Frames outside owned paths (stdlib, ssl, psycopg) are dropped, so a library-raised error shows only its owned callers. The original class name is sanitized, so exotic names become `Exception`.

**Policy point for Dex and Trish:** this extends the STOP envelope from fixture-only frames to **production-internal exception class names and production file:line frames**. It's the same approved schema and host validator, and still no messages, status, bodies or secrets. But it's a new disclosure scope, so please decide explicitly.

**Cheaper alternative (weaker):** map `response.status_code` and the response's `code` to a finite allowlisted `SuiteStop` subclass name, for example `CoveringStatus503OutcomeUnknown`. That discloses only a bucket, but a 503 bucket wouldn't localize the fault, so it would likely cost a second run. I recommend the observer.

**Process:** a fresh successor; a focused fake packet with extracted-observer controls (re-raise identity, restore, chain shape through the actual producer and host validator, a `from None` context-walk control); Dex review; Trish's one-shot approval. MS REFRESH stays held, since it shares this harness and its rebase depends on the result.

## 6. Citations I checked independently
- `np_runner_entry.py` lines 970–971, 1250–1253, 1471–1474, 1519–1522, 1157–1160;
- `np_integrated_runner.py` line 39;
- `covering_http_dispatch.py` lines 19, 30–73 (ordering, the 503 not-configured gate, `for_request` in `_worker`, the 503/504 mappings);
- `routes/calendar.py` lines 498–509;
- `covering_domain_dispatch.py` lines 75–92 (`_classified_role`) and 165–205 (auth → window → preflight → token order);
- `covering_role_connector.py` lines 142–150 and 190–204 (`from None` conversions);
- `TestClient` import in `i01_asgi_app.py` (lines 14, 523);
- byte identity of the three shared fixture and test files;
- the five-file `app/` difference against I01's `workspace/apps/api/app`.

**Not independently re-verified** (subagent citations, consistent with what I read): the individual 401/403 sub-branches in `deps.py` and `agent_credentials.py`, the native checkout validation details, and the I01 clock and transport line numbers.

## Scope
Read-only:
- source, manifest and retained-receipt reads, hashing and `cmp`/`diff`;
- two read-only subagents;
- signed document authoring.

No imports, parsing, compilation, tests, helpers, Docker, database, PKI, sockets, raw logs or bodies, and no edits to any packet. No EXECUTE acknowledgement exists. The endpoint is unbound, and MS REFRESH stays held.

Signed: Matt
