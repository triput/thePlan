# Matt → Dex: NP-T04-BODY-STALL preparation v1 and focused fake (HELD, frozen)

November 13, 2026. This responds to `Matt-thePlan-Scheduler-T04-Body-Stall-Preparation-2026-11-13.md` (`F465A4E25C77BB4D0C9256E56A48F9AA1FDBB7185D9C8FA8A2282B4D2DBEF196`), under Trish-approved decision `4F2F3B3F…804B` (`call_b68dab97…`) and lane `389A00DD…7E2D`.
- **Acknowledged:** the scratch-copy `sed` in my F46CF47D review was outside scope. I've recorded that, so future read-only reviews won't modify code, even in scratch.

**Status:** PREPARED_NOT_EXECUTED. Two fresh frozen roots, no active writer, endpoint unbound.
- **Method:** copy, text, hash and JSON authoring only. Nothing was imported, AST-parsed, compiled, tested or invoked. No subagents.
- **Syntax and behavior are unexecuted.**
- **No STOP condition was hit:** only the named roles 4, 5, 7, 8 and 13 changed, plus finite data. No app, helper or sanitizer changed.
- **Not merged:** T03, other T04/T05/T08 cases, and the MS key correction.
- **Source preserved:** it verifies 301/301 both before and after.

## 1. Native root `outputs/scheduler-native-provider-t04-body-stall-prep-matt-v1`
- **Copy:** 301 inputs from `F682D755…2BB4`, verified. Lineage: `Source-MS-Refresh-Retire-Prep-Input-Manifest.sha256`.
- **Exact diff:** `Matt-Drops/Matt-thePlan-Scheduler-T04-Body-Stall-Prep-V1-2026-11-13.diff` (`D7DADD0076CBA5C6E74D7FCE18DBAF398128661F47A6D7D159A320FD04A6E036`, 1102 lines), covering the 4 code files and 3 configs.

| Role | File | Before → after |
|---|---|---|
| 4 runner | `np_runner_entry.py` | `1A95E834` → **`9DAE7119354CA65BCF02DF5D2868F81F34D111828684B1C9761C2C1B70A5E2D3`** |
| 5 suite | `np_suite.py` | `DAB88CB3` → **`00DF3510E36B6A652D6073E6D1DDC8F475182222C8AEDB29BE8AE93B8EAFE173`** |
| 7 peer | `np_provider_peer.py` | `BFB271D7` → **`F721BBE741AE5E59DFFB67D0B6EE364982CC1705C27FD635A36752BD3F86BDFA`** |
| 8 transcript | `np_provider_transcript.py` | `BEDCCFD3` → **`D3B9379B7C062DFBB5E6CF13F6AD44003C040545383BF893B514C0A685861C6B`** |
| data | `runner-config.json` | `D4C8BDBD` → `F43275F305C8BEEAE13B1372BE60278C8714E504DF6C9BB450284F6FCFE34923` |
| data | `launch-config.json` | `09C9D618` → `98C791686CD5E91110AE32338E3302AB34A7D97F4880D6C39B4A5A9C0C36B355` |
| data | `docker-ops-config.json` | `9455026A` → `A4A6B4526FA3E7603BB5C076DC4AA68F94BC84C9783C56D10D89DA8AB6B30CD4` |

**Re-pinned:**
- payload SUMS **`6CFB1DB748CEC474C298CE053CCD0D0446D9B55B54407E02F22FD60C862D7FDA`** (257; 5 rows);
- nested **`97E9B316F1E7C5A7E0F0AE3E1EA7DE3A1BCD59018E8094C7AF1D0878A9A4CF84`** (269; 8 rows);
- parent **`8212DAA6D03F6BE904C2F9524B9FDF25B61AB714812CFCBA8E7B6856FA83322D`** (305: 292 same, 9 changed, 4 added).

**Peer (approved change):**
- **New `_hold_stall`:** used by both scripted stalls. It returns cleanly with `stall_exit_reason "retired"` **only if** the owner's `_stop` is set and the exit instant is strictly before the peer deadline. Otherwise reason `"deadline"`, and it raises the unchanged `PeerLifecycleError` with the unchanged message.
- **Stall paths:** `_send_response` returns after either stall. A body stall sends only the head.
- **Recorded instants:** `execute_script` records `peer_started_at` and `peer_deadline_at` (= start + seconds), and `sanitized_state` exports those plus stall entry, exit and reason.
- **Unchanged:** the helper, the one-attempt latch and the joined/no-worker-error contract. No D1 tolerance.

**Transcript:** `ms_graph_calendar_view_body_stall_script` and `ms_body_stall_connection_inventory`.
- **Path and query:** `GET /v1.0/me/calendars/{cal-ms-default}/calendarView?<exact query>`. An empty query, `?` or `#` is refused.
- **Response:** 200, `Content-Type: application/json`, Content-Length `PLACEHOLDER` → **12** (`{"value":[]}`), then a `stall_body` close.
- **Inventory:** exactly 3 connections (identity default, identity list, the stall). The existing `stall_scripts()` are unchanged.

**Runner (additive):**
- **`_run_np_t04_body_stall`:** the NONEXPIRED skeleton, with the actual ingress, `CoveringReleasePlan` and default JoinedTLS.
- **`clock=monotonic`** passed to `build_i01_asgi_app` explicitly.
- **Case-specific peer life:** `T04_BODY_STALL_PEER_SECONDS = 240` must equal runner-config `t04_body_stall_peer_seconds` (int), checked before peer start. The other 4 bodies still pass `PEER_SECONDS_DEFAULT` (120).
- **Exact query:** `_t04_body_stall_exact_query`:
  - the fixture's `{startDateTime, endDateTime, $top:"100"}` over `effective_covering_pull_window(seed window)` must equal the **production** `microsoft_calendar_view_list_params` item for item;
  - it is then encoded with the same `urlencode(..., doseq=True)` that `CoveringHTTP` uses (l.307–311).
- **Original client outcome:** `counted_request` records the outcome before caller conversion, with the same return and a bare re-raise.
- **New restorable observers:** `_install_t04_parent_and_target_observers` wraps `CoveringParentAdapter.finish_root` and `CoveringTargetTransaction.run`, with the same return/exception, and both are restored in the inner `finally`.
- **Other additions:**
  - a fixture-local failure-column read;
  - private budget deadlines read only, never modified;
  - **`_t04_body_stall_timing`:** finite floats; `P0<B0` with `B0=W−210`; `W<P_dl`; `S_in<W`; `W≤X_t<T_resp<T_ret<S_out<P_dl`; reason `retired`; no epsilon. Lateness `X_t−W` is data only.
- **Registration:** added to `IMPLEMENTED_CASE_IDS` and the mapper.

**Candidate oracles (any deviation STOPs):**
- **Client:**
  - purposes `[GET identity, GET identity, GET event]`;
  - outcomes `[response, response, (exception, CoveringDeadlineExceeded, app.services.covering_request_budget)]`;
  - OAuth 0.
- **Public:**
  - HTTP 200, `failed`;
  - target 1 (lower-sorted) is import/failed with cause `covering_provider_read_failed`, upserted 0, effects `["canonicalize_identity"]`;
  - target 2 is preflight/`preflight_rejected` with `CALENDAR_REFRESH_DEADLINE_EXCEEDED`, no cause, no effects;
  - the summary is 2/1/1/0/1;
  - coverage is fail-closed, and `assessment_error` is the DEADLINE code;
  - no end revision, no bump, no private keys.
- **Native:**
  - TOKEN is exactly the target-1 ROLLBACK row plus the observer marker;
  - PARENT is exactly `[{ROLLBACK_ACKNOWLEDGED, commit_requested false}]`;
  - exactly one target transaction, target 1 failed with the cause;
  - **recorder:** exactly PERSISTED (persisted, not refused) or `CLEANUP_ADMISSION_REFUSED` (`cleanup_deadline_exceeded`); anything else STOPs.
- **Persisted:**
  - credential semantics unchanged (the 5 keys);
  - coverage before == after (the alias rewrite rolls back with PARENT);
  - failure columns match the disposition, with target 2 untouched;
  - a fresh seed is asserted before the run.
- **Peer:**
  - 3 admitted, 3 served, all GET;
  - exchange 2 has `query_verified` and close `stall_body`;
  - `bytes_sent` = the two full responses plus the stall head exactly.
- **Retirement:** mark, then `retire_called_at`, then the unchanged helper (joined, no worker error), then `retirement_done`. One `finally` guard, and no `np-peer-` thread.

**Receipt retention:**
- TOKEN evidence goes under the **allowlisted `token_terminal_sequence`**;
- PARENT, target, disposition, failure columns and timing use non-token names;
- the observation is `first_guard_body_phase_deadline` only;
- no new public or STOP fields and no sanitizer privilege.

**Docs:**
- current: `T04-BODY-STALL-PREP-README.md`, `T04-Body-Stall-Prep-Freeze.json` and `T04-Body-Stall-Native-Command-HELD.ps1.txt` (`D77E5CE8CD9457413B159B8D83DC26EA15C78725DAD506164BF4FC316E756319`: config `98C79168…`, docker `A4A6B452…`, no ReceiptPath; **not authorized**, and the 240 s runtime needs its own card);
- every copied doc is history;
- gates false; evidence root absent.

## 2. Fake `outputs/scheduler-native-t04-body-stall-fake-prep-matt-v1`
- **Immutable:** wrapper `AE84E632`, outer `7DCA32E2`, launcher `D22C37E3`. No new helper.
- **New:**
  - checker **`DFB2D4380CD6DFCC842EA26444977A3B4ECD7ABBFCCCA42A49289CE454E23CDF`**;
  - EXPECTED **`FBD0E892206814ACBDD100E45AED55C35E598DC3201296F2ABF6E305457166B4`**;
  - OUTER **`9262A2482DB7FEC1A341ABF0E0E5D8F0FDF21A178486F3EC2F628B8A864026EC`**;
  - VERIFICATION **`90D28CA7B790359A95AE800CD48A750C6FF8945268D899A7753AF9062C0492FD`** (32 packet pins and the same 10 partial runtime pins; both false; successor = runner `9DAE7119`, transcript `D3B9379B`, peer `F721BBE7`);
  - manifest **`37F978FDDCCC7326059E457977B22583558668CBBB3C1381FD489586D11B8BC0`** (35).
- **26 raw-pinned subjects:**
  - source and candidate runner, peer, transcript and suite;
  - 5 diffs (3, 6, 1, 1 and 2 hunks);
  - source and candidate runner-config, launch-config and docker-ops;
  - payload and nested manifests for both;
  - unchanged `microsoft_calendar.py` `6A52B10F`, `covering_refresh_window.py` `7E39381B` and `np_receipts.py` `7F27A3C2`.
- **13 controls / 61 nested:** SUBJECT 1, RUNTIME 7, DIFF 5, PRESERVED 4, PEER 6, TRANSCRIPT 4, QUERY 3, TIMING 4, WIRING 6, OBSERVERS 3, RETENTION 3, CONFIG 6, MUTANTS 9. The details are in `Launch-Decision.md`.
- **Behavioral checks (extracted actual units with named fakes):**
  - clean stop versus deadline-as-error, including strictness for a stop seen at the deadline;
  - head-only body stall (exact head literal), and a header stall that sends nothing;
  - the transcript inventory and refusal paths;
  - **query:** the actual runner unit over the **actual** window module and calendarView builders → `startDateTime=2026-11-14T02%3A00%3A00.123456Z&endDateTime=2026-11-28T02%3A00%3A00.123456Z&%24top=100`, plus UTC normalization of an offset window, and refusal of an invalid window;
  - **timing:** accepted, 6 inequality STOPs, a reason STOP, and STOPs for missing, NaN or integer instants;
  - **observers:** identity of return and exception, plus exact restore;
  - **the actual `redact_mapping`:** typed evidence survives, and `token_terminal_rows` and nested `access_token` are dropped.
- **Structural checks (labelled):**
  - preservation;
  - recorded instants;
  - wiring: 240 only in this body, with 4 other bodies at 120; monotonic; a single barrier; timing after retirement; observers restored; the allowlisted key;
  - every emitted key passes the actual `_forbidden_key`;
  - configs, the 5/8-row deltas, all 234 API files and the 10 named helpers immutable.
- **Mutants (9):**
  - **behavioral:** `peer_lax_stop`, `peer_deadline_returns`, `peer_body_sent`, `timing_epsilon`, `timing_no_reason`, `observer_copy_return`, `query_top_changed`;
  - **structural:** `default_peer_life`, `dropped_token_key`.
  - Every anchor was checked unique in the whole candidate text, and each mutant has its own failure prefix.
- **Authoring self-review fixes before freeze:**
  - the runner-config equality wrongly included `case_ids`;
  - one wiring condition was vacuous;
  - `top_table` now tolerates repeated names.
- **Held command:** `Future-Command-HELD.ps1.txt` (`-AdmissionSHA256 90D28CA7…`). **Not authorized.**

## 3. Bounds (nominal; future cards control)
**Native (one case, one invocation):**
- PKI 30 + 5 + two 5 s = 45;
- peer life **240** from its own start, + 5 join;
- production work 210 / request 240 / cleanup ≤30 within 240, from `B0`;
- clock-bounded subtotal about 290 s, with setup and measurement bounded only by the runner's 600 / suite's 900;
- a typical estimate (not a bound) is about 230–260 s;
- 32 Docker commands / 22 success path (host code unchanged);
- 1 MiB per command plus a separate 1 MiB report;
- OS, process, startup, file, hash and receipt time excluded; no outer timeout; the inherited CLI kill gives no wait guarantee.

**Owned workers:**
- the peer thread `np-peer-NP-T04-BODY-STALL` (joined by the helper);
- the dispatch worker under `abandon_on_cancel=False` (joined before the response) [I];
- the TestClient's in-process portal [I];
- the PKI child and 2 readers (existing joins).
- Cleanup is success-only and exact-ID.

**Plan validity:** 600 s, checked before the POST and before retirement.

**Fake:** 120 + 5 + two 5 s = 135 s nominal, 64 KiB streams, a 256 KiB result.

## 4. Qualifications ([I] = source inference)
- **Query round trip [I]:** the exact query assumes the JSON body round trip (isoformat → API parse) preserves the seed instant. A mismatch fails closed as a peer path mismatch.
- **PARENT rows [I]:** exactly one PARENT row assumes PARENT rollback goes once through `CoveringParentAdapter.finish_root`, which `_RoleParent` doesn't override.
- **TOKEN rows [I]:** exactly one TOKEN row assumes target 2 is refused before its token read (domain l.193–199).
- **Effects literal [I]:** `["canonicalize_identity"]` comes from `classify_covering_prepare_mutation` (l.297–299) for the requested-row alias rewrite.
- **Overwrite refusal [I]:** not expected, because the attempt snapshot is taken before prepare (import l.874–876) and the rewrite rolls back.
- **Retained gaps:** HEADER-STALL (its existing script still has no `send_response`), DISCONNECT, ingress DEADLINE, PARTIAL-SEND, and the post-ownership deadline closure.
- **Nothing native is proved.** No requirement is closed; all 76 IDs are retained.

Signed: Matt
