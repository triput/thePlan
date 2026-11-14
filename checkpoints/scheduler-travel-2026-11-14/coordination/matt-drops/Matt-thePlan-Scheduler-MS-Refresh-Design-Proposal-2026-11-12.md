# Matt → Dex: NP-V-MS-REFRESH (T06-SUCCESS-MICROSOFT) read-only design trace and minimum fixture increment

November 12, 2026, about 21:45 PT. This responds to `Matt-thePlan-Scheduler-MS-Refresh-Design-Trace-2026-11-12.md` (SHA256 `3C9D73DFA19A3414A7B7543501BBAF333B72B6CC4B4574F1F06DC98E0C1F6DEA`).

**Proposal only.** No executable candidate was authored, no packet changed, and nothing was imported, parsed, compiled or run.

**Provenance:** I used **two read-only Explore subagents** in parallel (production refresh flow; fixture side), with no-execution, no-write instructions, and synthesized their reports myself. **I spot-checked every load-bearing claim against source** (section 7). One subagent citation was wrong and is corrected here: `covering_domain_adapters.py` is 76 lines, and the token-commit logic is at lines 30–61, not 104–135.

## 0. Pinned basis
Source: the current native diagnostic packet `outputs/scheduler-native-provider-diagnostic-launch-dex-v1/scheduler-native-provider-diagnostic-launch-v1`.
- **Integrity:** nested manifest 269/269 OK; parent manifest `1C85559E…851A`; payload `SHA256SUMS.txt` `3B25ABB6…2A90` (257, including 234 API files); selection lineage `857141512…A296` as given.
- **Key pins (payload-relative):**

| File | SHA256 (prefix) |
| --- | --- |
| `fixture/np_runner_entry.py` | `40A1BA8E…` |
| `fixture/np_integrated_runner.py` | `2C8B5BE7…` |
| `fixture/np_suite.py` | `AEC59FCD…` |
| `fixture/np_provider_transcript.py` | `CFAB2D06…` |
| `fixture/np_provider_peer.py` | `5568AF73…` |
| `fixture/np_provider_routes.py` | `9CBDE09C…` |
| `fixture/np_auth_seed.py` | `66FEEA81…` |
| `fixture/np_receipts.py` | `69F59AF1…` |
| `fixture/np_alias_seed.py` | `309CE658…` |
| `fixture/docker_transport.py` | `7F7EA820…` |
| `runner-config.json` | `E132A138…` |
| `api/app/services/microsoft_calendar.py` | `6A52B10F…` |
| `api/app/services/covering_refresh.py` | `0605E983…` |
| `api/app/services/covering_refresh_import.py` | `84F50367…` |
| `api/app/services/covering_domain_adapters.py` | `BA82577E…` |
| `api/app/services/covering_http_transport.py` | `29CBD53C…` |
| `api/app/services/covering_transport_policy.py` | `5F48FD7E…` |
| `api/app/services/covering_joined_https.py` | `76017776…` |
| `api/app/services/token_crypto.py` | `28205C01…` |
| `api/app/api/routes/calendar.py` | `23DC0396…` |
| `api/app/config.py` | `BCBB3A54…` |
| `api/app/models/calendar.py` | `0A8B0E20…` |

- **Lineage note:** the T05 lineage's `np_suite`, transcript and peer differ (`617D381A`, `46327DF0`, `4EEAB1E7`). T05 runner `9C0F8573` stays separate and unmerged, and this trace does not use it.

## 1. Actual production flow for an expired Microsoft token (covering refresh)
1. **Ingress.** `POST /api/v1/calendar/covering-refresh` (`routes/calendar.py` 498–509). `CoveringIngressMiddleware` creates `CoveringRequestBudget`: request +240 s, work +210 s, 30 s cleanup reserve.
   - Dispatch runs `run_bounded_domain` on a shielded worker.
   - Auth is the session cookie (the browser owner) or the agent bearer.
   - The body carries `subscription_ids` and the window.
   - Production installs no release binding (it returns 503 `CALENDAR_REFRESH_NOT_CONFIGURED`). **The fixture installs `CoveringReleasePlan` itself, exactly as NONEXPIRED does (runner 904–923).** That's a known, accepted seam, not a blocker.
2. **Targets are per subscription, ordered by ID** (`covering_refresh.py` 98–127 `_preflight_load_targets`; `covering_domain_dispatch.py` 127–134 and 189).
3. **TOKEN role, per target** (`covering_domain_dispatch.py` 206 → `covering_domain_adapters.py` 30–61 → `_refresh_provider_access_token` → `microsoft_calendar.get_valid_access_token` 1236–1269):
   - **Not expired** (`token_expires_at > now + 30 s`, line 1248): decrypt, no HTTP, `changed=False`, so ROLLBACK is expected.
   - **Expired or NULL:** a missing refresh token raises 401 `MICROSOFT_REAUTH_REQUIRED`. Otherwise it refreshes.
4. **OAuth request.**
   - URL: `_token_url` (113–114) = `https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token`. The tenant is normalized (136–140); the fixture setting is `common` (`np_auth_seed.py` 37 and 155). So the wire path is **`/common/oauth2/v2.0/token`**.
   - POST form field **names**: `client_id`, `client_secret`, `refresh_token`, `grant_type=refresh_token`, `scope` (296–306). Default scope comes from `config.py` 38–42.
   - Sent via `_CoveringClient` → `CoveringHTTP.request` (`covering_http_transport.py` 284–305). It requires `purpose=="oauth"` and a route of kind `oauth` whose prefix equals the parsed path **exactly**. It's sent over a fresh default **JoinedTLS**. `counter.admit()` applies, with no page charge.
5. **Response.**
   - The body must be a complete JSON object.
   - 400 `invalid_grant` → reauthorization → `TokenRejected` (`CALENDAR_ACCOUNT_DISCONNECTED`, a preflight row).
   - Any other ≥400, or any post-send exception → **`CoveringRootOutcomeUnknown`, no retry** (350–360, 373–377).
   - Field validation (`microsoft_calendar.py` 1136–1180): `access_token` must be a non-empty str; `expires_in` must convert with `int()` (default 3600); `expires_at = now + max(60, expires_in - 60)`; an optional `refresh_token` must be a str (rotation).
6. **Persistence and TOKEN terminal.**
   - Fernet-encrypted `access_token_enc`, `token_expires_at`, and `refresh_token_enc` (if rotated) are flushed (1262–1268).
   - `changed` compares the triple before and after (adapters line 48). The agent write is re-authorized if a credential exists (line 54).
   - `terminal(commit=changed)` must return **`COMMIT_ACKNOWLEDGED`** when changed, otherwise `ROLLBACK_ACKNOWLEDGED` (lines 58–59).
   - The TOKEN unit is closed before the PARENT import.
7. **Import (PARENT).** `import_covering_subscription_cache` (`covering_refresh_import.py` 828–1135):
   - identity evidence, only for the subscription whose alias is `primary`: GET `/v1.0/me/calendar`, then `/v1.0/me/calendars` (with nextLinks);
   - then calendarView per subscription (with nextLinks);
   - then apply and commit the revision.
   - Import failures (`MICROSOFT_EVENTS_LIST`, malformed page, incomplete pagination, apply or post-fetch failures) are **IMPORT** terminals, recorded through the RECORDER, distinct from TOKEN.
8. **Assessment.** The ASSESSMENT role (`covering_domain_dispatch.py` 257–264) runs the final native assessment; any failure gives `CALENDAR_REFRESH_ASSESSMENT_FAILED`. Root outcomes are COMMIT, ROLLBACK, DEADLINE-ROLLBACK or UNKNOWN; overall labels are no_op, failed, success or partial.

**Expected wire order for the existing two-subscription Microsoft seed** (static expectation):
- **Target 1** (the lower ID, aliased `primary`):
  1. `POST /common/oauth2/v2.0/token`, TOKEN **COMMIT**;
  2. `GET /v1.0/me/calendar`;
  3. `GET /v1.0/me/calendars`;
  4. `GET …/calendarView` for target 1.
- **Target 2:** TOKEN **ROLLBACK** (the token is now fresh, so **no request**), then `GET …/calendarView` for target 2.
- **Total: 5 peer connections, oauth_requests = 1, token terminals `[COMMIT_ACKNOWLEDGED, ROLLBACK_ACKNOWLEDGED]`.** This assumes target 2's TOKEN session re-reads the committed row. That's plausible from the separate-session design, but it's a runtime fact to validate.

## 2. Static blockers to fix before implementation
- **SB1 — token script path mismatch (deterministic).** `np_provider_transcript.py` 41–56 `MS-TOKEN-SUCCESS` expects `POST /oauth2/v2.0/token`, but production sends `/common/oauth2/v2.0/token`. The peer refuses anything inexact (`np_provider_peer.py` 323–327, "exact transcript path mismatch"), so the run would STOP. `MS-TOKEN-INVALID-GRANT` (line 64) has the same defect.
- **SB2 — missing OAuth route (deterministic).** `_ms_provider_routes` (`np_runner_entry.py` 644–663) has only the three Graph routes (`graph.microsoft.com`). With no `(login.microsoftonline.com peer, "/common/oauth2/v2.0/token", "oauth")` entry, `CoveringHTTP` raises "provider route refused" before sending (`covering_http_transport.py` 296–297).
- **SB3 — no persisted-token evidence.** `measure_subscription_coverage_state` (`np_auth_seed.py` 419–461) reads only subscription coverage. Also, `np_receipts` silently drops any key containing "token", "secret" and similar unless it's allowlisted (`np_receipts.py` 16–56). So a "persistence" oracle needs both a typed measurement and allowlisted keys.

**Not blockers (static inferences, to validate at runtime):**
- One peer process can serve both hosts. The peer has no SNI or Host-header check, the leaf SAN includes `login.microsoftonline.com` and `graph.microsoft.com` (`prepare-np-provider-tls.sh` 50), and both routes dial `127.0.0.1:443` with the same CA.
- `HTTPSPeer.check_url` pins the hostname and numeric address. The OAuth route needs its own `HTTPSPeer(hostname="login.microsoftonline.com", address=127.0.0.1, port=443, ca_file=…)`.

## 3. Minimum fixture increment (prospective; all within approved scope `389A00DD` roles)
Work in a **fresh copy**. The frozen packets and the implemented NP-V-MS-NONEXPIRED bytes and behavior stay unchanged.

| Role | File | Prospective delta |
| --- | --- | --- |
| 8 | `np_provider_transcript.py` | `MS-TOKEN-SUCCESS` path → `/common/oauth2/v2.0/token` (derived from `FIXTURE_MS_TENANT`, not hardcoded twice); add `ms_refresh_connection_inventory(...)` = `[MS-TOKEN-SUCCESS, MS-GRAPH-IDENTITY-DEFAULT, MS-GRAPH-IDENTITY-LIST, CALENDARVIEW:{t1}, CALENDARVIEW:{t2}]`. The success body keeps its field names (`token_type`, `expires_in`, `access_token`, `refresh_token`) with synthetic values only. **Q3:** also fix `MS-TOKEN-INVALID-GRANT`'s path now (for NP-V-MS-INVALID later), or defer? |
| 4 | `np_runner_entry.py` | New `_ms_refresh_provider_routes` = the existing 3 Graph routes **plus** one OAuth route on a second `HTTPSPeer` for `login.microsoftonline.com` (same address, port and CA). Leave `_ms_provider_routes` untouched. New body `_run_np_v_ms_refresh`, structurally parallel to NONEXPIRED, with the same budget-identity, schema and coverage checks. Seed with `expired=True`. Assert the section 4 observations. Bind it in `_make_implemented_case`; add it to `IMPLEMENTED_CASE_IDS`. |
| 10 | `np_auth_seed.py` | A read-only measurement helper for typed token state before and after: `token_expires_at` as a typed comparison against `t_plan`, plus a SHA-256 of the **ciphertext** columns, returned only as `changed` booleans and short label hashes. The existing `expired=True` seed (`t_plan - 5 min`, 307–310) is reused. |
| 6 | `np_receipts.py` | Allowlist only the new non-secret keys (for example `token_persistence_changed`, `token_expiry_advanced`, `refresh_rotated`, `token_terminal_sequence`). No raw values. |
| 5 | `np_suite.py` | No new IDs. The existing `NP-V-MS-REFRESH` oracles (`owning_ms_refresh_joinedtls`, `token_commit`, `persistence`, line 72) become checked; update `CASE_IMPLEMENTATION_NOTES`. All 76 IDs are preserved. |
| data | `runner-config.json` | **Q1:** a separate single-case batch `["NP-V-MS-REFRESH"]` (recommended), or a two-case batch? The current config stays NONEXPIRED-only until decided. |
| — | unchanged | `np_provider_peer.py`, `np_provider_routes.py` (the route factory may be reused), `prepare-np-provider-tls.sh`, `docker_transport.py`, `np_integrated_runner.py`, all 234 API files, the operator and host configs (apart from later batch data). |

The fake-verification side would follow the established pattern in a separate packet: the transcript path and production `_token_url(common)` agree; the route table matches exactly; the inventory order is the expected five; and the receipt allowlist doesn't leak secrets.

## 4. Finite acceptance observations (native run, later)
1. Route returns **200**; overall `success`; both rows `ok`; schema fields as for NONEXPIRED.
2. **`owning_ms_refresh_joinedtls`:** exactly one `purpose=oauth` request, first in the wire order, over the default JoinedTLS (`CoveringHTTP`, budget identity bound as in NONEXPIRED). The peer observed `POST /common/oauth2/v2.0/token`.
3. **`token_commit`:** the token terminal sequence equals `[COMMIT_ACKNOWLEDGED (commit_requested=True), ROLLBACK_ACKNOWLEDGED]`.
4. **`persistence`:** after the run, `token_expires_at > t_plan + 30 s` (typed); the access-token ciphertext hash changed; the refresh ciphertext changed (the script rotates); before and after evidence is recorded as label hashes or booleans only.
5. **Requests:** client `oauth_requests == 1`; the peer's served, admitted and inventory counts all equal **5**, in the exact order from section 1; no extra connection.
6. **Import and assessment:** coverage before and after, and the alias rewrite, behave as in NONEXPIRED. The final ASSESSMENT terminal is recorded.
7. Single bounded retirement; exact-ID, success-only cleanup; no raw token, cookie, body or key in any artifact.

**STOP points (no retry, preserve evidence):**
- peer path, method or order mismatch, or an unexpected connection;
- OAuth non-200, so UNKNOWN or 503 `CALENDAR_REFRESH_OUTCOME_UNKNOWN`;
- `invalid_grant` (preflight_rejected, which is unexpected here);
- TOKEN terminal missing, unacknowledged or unexpected;
- request or work deadline, or `PROVIDER_LIMIT_EXCEEDED`;
- any IMPORT failure cause;
- assessment failure;
- any framework or retirement UNKNOWN;
- a receipt over its cap.

## 5. Proof limits and dependency on the first native diagnostic outcome
- **Not proved by any existing evidence:** NONEXPIRED (no OAuth request) and the T05 fakes do **not** prove expired-token or OAuth behavior. I01/I02 used a fixture byte transport, not provider HTTPS. **No native case has passed on this diagnostic lineage yet.**
- **Can proceed before the native diagnostic outcome:** preparation authoring in a fresh copy (the section 3 deltas), plus a static or fake verification packet for the path, routes, inventory and receipt allowlist.
- **Must wait:** any native REFRESH run. It shares the same runner attach, container, peer and PKI path whose v3 STOP is still unattributed. If the diagnostic run shows a defect in that shared path, the refresh prep may need rebasing. Its runtime-dependent assumptions (one peer serving two hosts; target 2's ROLLBACK without a request) are validated only by a native run.

## 6. Questions and policy items for Dex and Trish
- **Q1:** batch shape. I recommend a separate single-case `NP-V-MS-REFRESH` batch, keeping NONEXPIRED's validated batch unchanged.
- **Q2:** keep the two-subscription seed (expecting `[COMMIT, ROLLBACK]` and 5 connections), or use a one-subscription seed (expecting `[COMMIT]` and 4) to isolate the refresh. I recommend **keeping two subscriptions**: it also proves no duplicate refresh on the same account.
- **Q3:** fix the `MS-TOKEN-INVALID-GRANT` path in the same pass (it's the same defect, harmless to NONEXPIRED and REFRESH), or defer it to NP-V-MS-INVALID?
- **Q4:** should the peer also record form-field **names** of the token POST, to prove `grant_type=refresh_token` on the wire? That would be a role-7 delta. Without it, the request content is evidenced only by production source, not the wire. I recommend deferring it, to stay minimal.
- **No scope expansion:** no production change, no injected byte transport, no weakened transaction guard, no new privileges, no non-root port-443 change.

## 7. Spot checks I performed myself (read-only)
- `microsoft_calendar.py`: 113–114 (`_token_url`), 64 (`_LOGIN_BASE`), 1244–1252 (the 30 s rule), 296–306 (form field names).
- `covering_http_transport.py`: 284–305 (exact OAuth route, purpose, counter) and 350–360 (`invalid_grant` vs UNKNOWN).
- `covering_domain_adapters.py`: 30–61 (`changed`, COMMIT vs ROLLBACK expectation).
- `covering_domain_dispatch.py`: 127–134, 189, 206, 257 (per-subscription targets; TOKEN before ASSESSMENT).
- `covering_refresh.py`: 98–127.
- Transcript 41–50; peer 320–328 (exact path); runner 644–663 (no OAuth route); `np_auth_seed.py` 35–38 and 153–156 (`common`).
- TLS SAN at line 50; no Host or SNI check in the peer (grep).

## Scope
Read-only:
- file reads, `grep` and hashing;
- two read-only Explore subagents under the same holds (no execution, no writes);
- this new signed document.

No packet, source or metadata edits; no imports, parsing, compilation, tests, helpers or probes; no sockets, PKI, providers, database, Docker, installation, build, cleanup or execution. No EXECUTE acknowledgement exists. The endpoint is unbound, and all holds remain.

Signed: Matt
