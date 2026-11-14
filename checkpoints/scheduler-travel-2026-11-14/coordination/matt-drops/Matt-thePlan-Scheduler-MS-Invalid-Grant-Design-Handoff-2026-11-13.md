# Matt → Dex: NP-V-MS-INVALID (T06-INVALID-GRANT-MICROSOFT) native fixture design

November 13, 2026. This responds to `Matt-thePlan-Scheduler-MS-Invalid-Grant-Design-2026-11-13.md` (`57DA3EF58BA36808EB7D1FDF4FBB1284485CF921F032D1F1A4C694FB6FC3B573`), under lane `389A00DD…7E2D`.

**Method:** offline design by ordinary read-only text and hash review of the frozen v3 payload (parent `B773B95E…E59B`, nested `4E190C4F…`, payload `D03EA0D6…`).
- Nothing was imported, parsed, compiled, tested or run, and no source or packet was modified.
- No subagents were used.
- The two pending fake packets were left alone.

**Bottom line:**
- The production contract already gives a narrow, exactly-typed path.
- One existing fixture defect must be fixed: the invalid-grant script's token path.
- **No Trish decision is needed.** I recommend the narrow preparation plan in §6.

## 1. Exact call path (frozen v3 payload, source pins)
| step | file (SHA256) | anchor |
|---|---|---|
| public POST `COVERING_PATH` → `run_bounded_domain` | `covering_domain_dispatch.py` `E73EFF68…6566` | l.165–267 |
| TOKEN role: `_classified_role(connector, CoveringRole.TOKEN, token_read)` → `ports.token` | same | l.201–205 |
| token port: eligibility → `covering_provider_transport(transport)` → `_refresh_provider_access_token` | `covering_domain_adapters.py` `BA82577E…A53C` | l.30–61 |
| MS dispatch → `microsoft_calendar.get_valid_access_token` | `covering_refresh_import.py` `84F50367…C339` | `_refresh_provider_access_token` |
| expired (`expires <= now+30s`) → `refresh_access_token(config, decrypt(refresh))` | `microsoft_calendar.py` `6A52B10F…6DD6EF` | l.1236–1269 (refresh POST l.1256) |
| `calendar_client(timeout=30).post(_token_url(tenant), data=…)` | same | l.294–305 |
| covering client resolves the purpose from the route table (exactly one) → `CoveringHTTP.request(..., purpose="oauth")` | `covering_provider_context.py` `65529CBC…48D2` | l.29–52 |
| JoinedTLS open/send → `_GuardedHTTPResponse.begin` → framing gate → read loop → `_admit_fixed_length_complete` → `json.loads` → object check → **OAuth error classification** | `covering_http_transport.py` `29CBD53C…B368` | l.326–360 |
| `CoveringReauthorizationRequired` class | `covering_transport_policy.py` `5F48FD7E…8B88` | l.152 |
| native terminal hook: ROLLBACK requires `command_sent`, `drained`, `idle` and an exact command tag | `covering_native_orm_factory.py` `C37B6DBB…7FE2` | l.339–345 |
| `TokenRejected` → `_static_preflight_result(preflight_code=…)`; `continue` (no `run_target`) | `covering_domain_dispatch.py` | l.218–221 |
| `_static_preflight_result` / `_result_row` / `_derive_overall_outcome` | `covering_refresh.py` `0605E983…3E5E` | l.433–460 / l.134–149 / l.152–165 |
| `run_target` (IMPORT unit), never reached for this target | `covering_role_connector.py` `C5BA15CD…B288` | l.152 |

**Admission versus every other OAuth failure** (`covering_http_transport.py` l.352–379; `purpose == "oauth"`):
- **Typed rejection:** only a **complete, admitted** response does it. That means it passes the header gate and the fixed-length completeness gate, decodes as a JSON **object**, and has `status == 400` **and** `decoded.get("error") == "invalid_grant"`. The client then raises `CoveringReauthorizationRequired` (l.358), which is re-raised unchanged by the `except CoveringReauthorizationRequired` clause (l.368–371).
- **Everything else becomes `CoveringRootOutcomeUnknown`:**
  - any other ≥400 status or error value (l.354–357);
  - **after `transport.sent`**: malformed JSON (`JSONDecodeError`), non-object JSON (`CoveringTransportRefused`), truncated or short-CL body (`IncompleteRead`), framing defects, or a transport EOF or reset (l.372–377, via `except BaseException`; no replay).
  - **Before send:** the original exception propagates (l.378–379).
- **Cleanup override:** if `response.close()` or `transport.close()` raises in the `finally`, a **new** `CoveringRootOutcomeUnknown` replaces even the typed rejection (l.381–415). That is a STOP, never expected behavior.
- **No account writes before the rejection:** the typed exception escapes `client.post` inside `refresh_access_token`. It never reaches the `status_code >= 400` → `ApiError(502)` branch (l.306) and never reaches `_validated_oauth_token_fields` or any `account.*` assignment or flush (l.1257–1268).
- **Adapter mapping:** the adapter catches **only** `CoveringReauthorizationRequired` and maps it to `changed=False`, `TokenRejected("CALENDAR_ACCOUNT_DISCONNECTED")` (`PREFLIGHT_ACCOUNT_DISCONNECTED`, `covering_refresh_import.py` l.89). It then requires `terminal(commit=False) is RootOutcome.ROLLBACK_ACKNOWLEDGED`; anything else raises UNKNOWN (adapter l.50–60).
- **No new policy:** nothing here widens the classification or the expected-UNKNOWN set.

**Note:** the same public code can come from `covering_import_eligibility_code` (adapter l.39–42) without any OAuth exchange. **So the public code alone is not proof**; see §3.

## 2. Minimal fixture-role diff plan (lane 389A00DD, existing roles only; 234 API files immutable)
- **New root:** a fresh successor copied from the frozen v3 root, for example `scheduler-native-provider-ms-invalid-prep-matt-v1`. Native T05 v1–v3 stay frozen.
- **Role 8 `np_provider_transcript.py`**
  - **Required fix:** `ms_token_invalid_grant_script()` today expects `path="/oauth2/v2.0/token"`. Production `_token_url` builds `/{tenant}/oauth2/v2.0/token`, and the peer enforces exact path equality (`np_provider_peer.py` l.342–346: "exact transcript path mismatch"). As written, the native run would fail at the peer, producing a post-send transport UNKNOWN, not the invalid_grant path.
    - Change it to `path=MS_TOKEN_ENDPOINT_PATH`, exactly as `ms_token_success_script` does.
    - Keep status 400, `Content-Type: application/json`, body `{"error":"invalid_grant"}` (25 bytes; the auto path appends `Content-Length: 25`), and `close_mode="orderly_close_notify"`.
  - **Add** `ms_invalid_grant_connection_inventory() -> (ms_token_invalid_grant_script(),)` plus a constant `MS_INVALID_GRANT_EXCHANGE_COUNT = 1`.
  - **Not changed:** the Google invalid-grant script's path. That belongs to NP-V-GOOGLE-INVALID and is flagged only.
- **Role 4 `np_runner_entry.py`**
  - Add `"NP-V-MS-INVALID"` to `IMPLEMENTED_CASE_IDS` and a mapper branch.
  - **Add the body `_run_np_v_ms_invalid()`**, modelled on `_run_np_v_ms_refresh` (l.1259–1822) and reusing its unchanged helpers: `_ms_refresh_provider_routes`, `_require_production_ms_token_path`, `_install_token_terminal_observer`, `_actual_token_terminals`, `CoveringReleasePlan` install, `capturing_init`.
  - **Observer changes:**
    - `counted_request` must **record the exception class name and module, then re-raise the same object** (observation only; no behavior change);
    - add a counting wrapper on `CoveringRoleConnector.run_target`, restored in `finally`, to observe that IMPORT is never entered for this target.
  - **No new helper files.**
- **Role 5 `np_suite.py`**
  - Add a `CASE_IMPLEMENTATION_NOTES` entry only.
  - **The declaration is unchanged:** case `NP-V-MS-INVALID`, planning `("T06-INVALID-GRANT-MICROSOFT",)`, oracle `token_rejected_after_unchanged_unit_rollback`.
  - All 31 declarations and 76 planning IDs are preserved.
- **Roles unchanged:** role 10 `np_auth_seed.py`, peer role 7 (`BFB271D7`) and receipts. The seed already has `seed_token_plan(provider="microsoft", expired=True)`, the `SEED_MS_*` plaintext constants and `measure_account_credential_state`.
- **Data:** in `runner-config.json`, set `case_ids` to `["NP-V-MS-INVALID"]` and `expected_unknown_cases` to `[]`. The launch-config gets the batch id `np-v-ms-invalid` and the payload or manifest re-pins. Gates stay false.
- **Seed:**
  - `seed_browser_owner_with_subscriptions(subscription_count=1, provider="microsoft", expired=True, mark_covering_fresh_at_seed=False)`.
  - No primary alias is needed, because there are no Graph calls.
  - Expiry is at or before `t_plan`, so `get_valid_access_token` takes the refresh branch.
  - **Why one subscription:** with two subscriptions on one account, the rolled-back token stays expired and the second target would issue a second OAuth POST.
- **Exchange order (exactly 1):**
  1. POST `MS_TOKEN_ENDPOINT_PATH` on `login.microsoftonline.com`.
  2. The peer sends the complete 400 `invalid_grant` response, then an orderly close_notify.
  - No Graph GET follows. The final ASSESSMENT is DB-only.

## 3. Required evidence (separately observed; each is a STOP on mismatch)
1. **Completed response:** the peer state shows admitted = served = 1, request received, response sent, `bytes_sent == len(_http_response_bytes(step))`, close mode `orderly_close_notify`, retirement joined with no worker error, and a single `exchange_inventory` row POST at the production path. **This is the peer-side stimulus only.**
2. **Typed token rejection (client side):** the recorded outcome of the one `purpose == "oauth"` request is exactly the class `CoveringReauthorizationRequired` from module `app.services.covering_transport_policy`. That class is only raised after the completeness gate and a decoded 400 `invalid_grant` object. `oauth_requests == 1`, the client inventory is `[("POST", "oauth")]`, and there are no other requests.
3. **Native TOKEN rollback acknowledged:** `_actual_token_terminals(...)` is exactly `[{"terminal": "ROLLBACK_ACKNOWLEDGED", "commit_requested": False}]`. Any COMMIT, extra row or missing row STOPs. The hook itself requires `command_sent`, `drained`, `idle` and the exact tag.
4. **Unchanged semantic persisted credential:** two fresh native setup sessions (before and after), separate from the request, each call `measure_account_credential_state`.
   - **Before:** seed access and refresh match `True`; refreshed and rotated match `False`; expiry at or before the reference.
   - **After:** **identical booleans**, and **`expiry` string equal to before**.
   - Ciphertext `sha16` equality is supplementary only and never the basis.
5. **Public result** (the actual contract, from source):
   - HTTP 200;
   - `results` has exactly one row: `{subscription_id: seeded, phase: "preflight", status: "preflight_rejected", preflight_code: "CALENDAR_ACCOUNT_DISCONNECTED", preflight_effects: [], cause: null, upserted: 0}`;
   - `action_summary`: `requested 1`, `preflight_rejected 1`, `import_attempted 0`, `import_ok 0`, `import_failed 0`;
   - `overall_outcome == "no_op"` (`_derive_overall_outcome`: `import_attempted == 0`);
   - no private keys.
   - **Recorded, not asserted:** `coverage_action` and `scheduling_readiness`. Their exact values come from `_assemble_final_assessment` over the seed, and I won't invent them; preparation can derive them from source before freezing any oracle.
6. **IMPORT:**
   - **Not begun.** Dispatch `continue`s after `TokenRejected` (l.218–221), so `connector.run_target` is never called.
   - **Evidence:** the `run_target` observer count is 0, there are no Graph exchanges, and `measure_subscription_coverage_state` before equals after.
   - No IMPORT terminal is claimed, either refused or rolled back.

**Not used as outcome proof:**
- ciphertext inequality;
- `transport.sent`;
- the authored peer 400;
- an HTTP label;
- the public preflight code alone. (It needs items 2, 3 and 4 together.)

## 4. Fake prerequisites (one focused fake; same host-parser / extraction style as T05 fake v3)
**Original-vs-candidate checks**
- the transcript diff is the path fix plus the inventory function only;
- the default serializer regression is byte-identical for every other catalog script;
- the 400 invalid_grant wire is exact: `HTTP/1.1 400 OK\r\nContent-Type: application/json\r\nContent-Length: 25\r\nConnection: close\r\n\r\n{"error":"invalid_grant"}`. The reason phrase is the fixture's fixed "OK", which `http.client` ignores; this is disclosed.

**Host parser over the actual transport and policy**
- **Positive:** a complete 400 `{"error":"invalid_grant"}` raises `CoveringReauthorizationRequired`, with gate 1, json 1 and transport closed once.
- **Negatives, each giving `CoveringRootOutcomeUnknown` with sent=True:**
  - 400 with `error: invalid_request`;
  - 401 with invalid_grant;
  - 400 with non-object JSON `["invalid_grant"]`;
  - malformed `{"error":`;
  - short Content-Length (truncated);
  - an injected transport EOF after send;
  - a close failure after invalid_grant, which gives a new UNKNOWN that replaces the typed rejection.
- **Before send:** an injected open or send failure propagates unchanged.

**Extracted production units with fakes**
- `get_valid_access_token` with `calendar_client` returning a client that raises `CoveringReauthorizationRequired`: it propagates, **no `account.*` attribute is assigned**, `db.flush` is never called, and the 502 branch is never reached.
- The adapter `token` closure with a fake terminal: it returns `TokenRejected("CALENDAR_ACCOUNT_DISCONNECTED")`, and the terminal is called once with `commit=False`.

**Runner wiring (structural)**
- default JoinedTLS;
- exactly one `_t05_observe`-style peer, retired in `finally` before classification;
- the oracle is checked before the receipt;
- the `counted_request` re-raise preserves object identity;
- the `run_target` wrapper is restored.

**Negative controls** (the classifier or oracle STOPs on each):
- a terminal sequence of COMMIT, or two rows;
- an after-state with refreshed or rotated match `True`, or a changed expiry;
- `oauth_requests == 2`;
- a client class of `CoveringRootOutcomeUnknown` or `ApiError`;
- a public code other than `CALENDAR_ACCOUNT_DISCONNECTED`;
- `import_attempted == 1`, or a `run_target` count of 1;
- a peer exchange count of 2.

**Source mutants** (each detected by its targeted oracle)
- the adapter `except` sets `changed=True` (wrong terminal);
- the adapter `except` is removed (exception escapes);
- the transport condition is weakened to accept any 400;
- the path fix is reverted (the transcript path check catches it);
- `counted_request` swallows the exception.

**Only real native execution with default JoinedTLS can establish:**
- the TLS read of the complete 400 response followed by close_notify;
- the actual PostgreSQL ROLLBACK acknowledgement through `token_terminal`;
- semantic unchanged persistence through a separate native session;
- the actual ASGI public response;
- native peer and worker retirement.

**Never expected:** fixture, retirement or cleanup UNKNOWN. `expected_unknown_cases` stays `[]`.

## 5. Isolated one-case batch and bounds (source-derived, reusing existing isolation)
- **Batch:** `case_ids ["NP-V-MS-INVALID"]`, its own root and runner-config, no sequencing with other batches, no retry.
- **Routing:** reuse `_ms_refresh_provider_routes` (Graph table plus one OAuth route on a distinct `login.microsoftonline.com` HTTPSPeer, same CA, numeric loopback :443, verify-full) and `_require_production_ms_token_path`. Graph routes stay admitted but are never used. Any Graph request is a STOP through the inventory.
- **Bounds:**
  - one owned peer: `peer_seconds` 120 plus 5 s retire join;
  - provider PKI: generation 30 s, reap 5 s, reader join 5 s, total retirement 45 s (unchanged config);
  - `runner_seconds` 600 is the outer hard bound;
  - the request deadlines are unchanged (work 210 s, request 240 s, cleanup 30 s);
  - output cap 1 MiB. Supervisor expiry is UNKNOWN, never PASS.
- **Command:** the same operator shape as the held T05 command with the new root's config hashes and no `-ReceiptPath`. HELD.
- **Dependencies, not claimed as passed:**
  - the peer orderly close relies on the peer-close correction, whose corrected fake v2 is unexecuted;
  - native JoinedTLS, the OAuth route and the native TOKEN terminal path have no native PASS; NP-V-MS-REFRESH has never run natively;
  - the MS-refresh helper fake PASS 10 applies only at its finite helper scope, and its excluded `_run_np_v_ms_nonexpired` claim stays excluded.
  - None of these blocks authoring. They do block any launch.

## 6. Decision
- **No material choice remains open:** the contract fixes the typed class, the terminal, the preflight code and `no_op`.
- **The one-subscription batch is the narrow reading** of "the owning refresh path receiving one complete acknowledgment."
- **Recommendation:** authorize the narrow preparation (§2 roles 4/5/8 plus data) with its focused fake (§4) as the next bounded assignment.

## Not claimed
No native or fake run, no invalid_grant PASS, no Google claims, no IMPORT terminal, and no claim about exact coverage or readiness values. The endpoint is unbound, and all execution holds stay.

Signed: Matt
