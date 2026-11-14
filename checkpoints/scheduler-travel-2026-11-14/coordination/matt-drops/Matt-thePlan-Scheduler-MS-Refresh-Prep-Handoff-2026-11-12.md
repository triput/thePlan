# Matt → Dex: NP-V-MS-REFRESH preparation handback (fixture increment + focused fake packet)

November 12, 2026, about 22:45 PT. This responds to `Matt-thePlan-Scheduler-MS-Refresh-Preparation-2026-11-12.md` (SHA256 `F462C385F10581CA81BF8B4C10052071818D9318A154994BEB76B143D54C0009`). It follows `Reconciled-Preparation-Scope.md` (`EAAFA222…488A`, read in full) under Trish's approved envelope `389A00DD…7E2D` (approval `5D1EA2F9…0CA4`).

**Provenance:** I worked solo for the authoring. The two read-only Explore subagents were used only in the earlier design trace; none were used in this assignment.

**Status: both workspaces are frozen. No writer is active.** Nothing was imported, parsed, compiled, tested, verified or run. Every gate is false, no EXECUTE acknowledgement exists, and the endpoint is unbound. **No native REFRESH launch is possible before the shared-harness diagnostic native outcome is reconciled and a separate exact approval exists.**

## 1. Fixture preparation workspace
`C:/Users/trish/Documents/Codex/2026-10-15/trish-wants-to-improve-dex-s/outputs/scheduler-ms-refresh-prep-matt-v1`. It didn't exist beforehand, and neither did its sibling evidence directory.
- **Copy:** only the 274 manifest-listed files from `scheduler-native-provider-diagnostic-launch-dex-v1` (manifest `1C85559E…851A`), verified 274/274 before and after. No dynamic evidence and no keys. The source manifest is kept as `Source-Input-Manifest-dex-v1.sha256`.
- **Nested packet** `scheduler-native-provider-diagnostic-launch-v1`, so the immutable operator's sibling evidence label resolves uniquely to `…\scheduler-ms-refresh-prep-matt-v1\scheduler-native-provider-diagnostic-launch-v1.evidence`, which is **absent**.
- **Manifests:**
  - parent `Input-Manifest.sha256` = **`518374841295D1312B6EF9A3CC8BC5061F284F1B6AC0475F469A52014AFFDC21`** (278 entries, 278/278 OK);
  - nested `Input-Manifest.sha256` = **`5F27480D92C220981517422C2F2C71B8D01D36CC3B0E1B02233483387A63FAE4`** (269, OK);
  - payload `SHA256SUMS.txt` = **`BD48E400924E8D6DD17597F7845E20FC01F1889AFEEAD743880CB3BF2623472D`** (257, OK; 6 re-pinned).
- **Full code and data diff** against the source staging: `Matt-thePlan-Scheduler-MS-Refresh-Prep-Diff-2026-11-12.diff` (`CE32FEF4…0A0D`, 9 files). `diff -rq` shows only the 10 intended files differ (the 9 in that diff plus the regenerated nested manifest).

### Code deltas (mutable roles 4, 5, 6, 8 and 10 only; purely additive except four intended lines)
| Role | File | Hash change | Delta |
| --- | --- | --- | --- |
| 4 | `np_runner_entry.py` | `40A1BA8E` → **`CC4D49E758F22E5E34C0D6093946CA390BC95A4C320C3D92B24AD723FA8634FF`** | **New:** `_ms_refresh_provider_routes` (the unchanged graph table plus a distinct `login.microsoftonline.com` HTTPSPeer OAuth route sharing CA, address and port), `_require_production_ms_token_path` (runtime cross-check against the pinned `_token_url(_normalize_tenant(…))`), `_actual_token_terminals` (filters the observer marker), `_run_np_v_ms_refresh`, and a REFRESH mapper branch. **The only changed line is `IMPLEMENTED_CASE_IDS`.** `_run_np_v_ms_nonexpired`, `_ms_provider_routes` and `stop_payload` are byte-identical (segment hashes compared). |
| 5 | `np_suite.py` | `AEC59FCD` → **`46C9443D…34FF`** | A REFRESH implementation note only. `NATIVE_CASES` and all 76 IDs are unchanged. |
| 6 | `np_receipts.py` | `69F59AF1` → **`7F27A3C2…24C7`** | Allowlist adds exactly `token_commit` and `token_terminal_sequence`. Credential-state keys deliberately contain no "token" fragment, so no broad exception is needed. |
| 8 | `np_provider_transcript.py` | `CFAB2D06` → **`0AA3BC09…E52E`** | `ms_token_endpoint_path` and `MS_TOKEN_ENDPOINT_PATH` are derived **once** from `FIXTURE_MS_TENANT`, refusing anything production would rewrite. `MS-TOKEN-SUCCESS` uses that path with a body of the declared synthetic refreshed access and rotated refresh values (as JSON). Added `ms_refresh_connection_inventory` (exactly 5: token then the unchanged NONEXPIRED Graph scripts). The three changed lines are the old token path, body and note; the invalid-grant script is untouched (Q3 deferred). It imports constants from `np_auth_seed`, which has stdlib-only top-level imports, so there's no cycle. |
| 10 | `np_auth_seed.py` | `66FEEA81` → **`2ADFA3AD…ED05`** | Declared synthetic `SEED_*` labels (mirroring the unchanged seed literals), refreshed, rotated and `expires_in` values. **`measure_account_credential_state`:** a fresh read, decryption with the unchanged production `decrypt_token`, and output of only the seed, refreshed and rotated match booleans, the expiry instant, two expiry booleans (at or before the reference; after the reference plus 30 s) and short ciphertext hashes. Plaintext is deleted after comparison. |

### Data deltas
- **`payload/runner-config.json`** → `108D8D1E…E11A`: `launch_ready` false; `case_ids` `["NP-V-MS-REFRESH"]`; `expected_unknown_cases` `[]`; `first_vertical_case_ids` kept as NONEXPIRED (an over-broad substitution of mine was caught and reverted before freezing); added `refresh_increment_batch_case_ids` and `implemented_case_ids`.
- **`host/launch-config.json`** → **`6558688B15D5ED0105D18EF07D7D2580FD267437087E613EA9C7103BFAB7FCC4`**:
  - `launch_ready` and `candidate_launch_ready_staged` **false**;
  - `batch_id` `np-v-ms-refresh-single-case`; `case_ids` REFRESH; `implemented_case_ids` both;
  - `manifest_sha256` `BD48E400…`; paths moved to the new parent; notes updated.
- **`host/docker-ops-config.json`** → **`8AAF77950CDA7A332C1BF22F984C47A392EF313E2DAD44415DDCB5636B680D34`**: only the 7 path values changed.
- **Immutable:** operator `5A8A04B6…`, `docker_transport.py` `7F7EA820…`, the peer, route and PKI files, and all 234 API files.
- **Static path agreement:** all 9 absolute config paths are under the new nested root or its sibling `.evidence` (public-CA directory, CA bind, receipt directory), and the operator label resolves to the same sibling.

### Evidence design implemented in `_run_np_v_ms_refresh` (static source)
It follows NONEXPIRED's real ingress, ReleasePlan, CoveringHTTP and default JoinedTLS path with the same budget-identity proof and real monotonic clocks, and no injection, freezing, reseed or retry. Changes:
- **Startup:** the expired seed (2 subscriptions, 1 account) is checked. The production token-path cross-check runs before any request, and the token route must share CA, address and port.
- **BEFORE** (fresh session): expiry at or before `t_plan`; seed values present; refreshed values absent; no covering success.
- **Public response:** `overall_outcome == "success"`; two `results[]` rows with `phase=import` and `status=ok` matching the requested IDs; NONEXPIRED's coverage, readiness and revision checks; `assessment_error is None`.
- **AFTER** (fresh session): refreshed access and rotated refresh are plaintext-equal; seed values are absent; expiry is later than `t_final_check + 30 s`. **Ciphertext hashes are recorded and never the pass basis.**
- **Native TOKEN terminals** (marker filtered) must be exactly `[COMMIT_ACKNOWLEDGED commit=True, ROLLBACK_ACKNOWLEDGED commit=False]`. I confirmed from source that `token()` calls the terminal exactly once per target and that the hook is bound per session after the observer is installed.
- **Requests:** `oauth_requests == 1`; client order `[POST oauth, GET identity, GET identity, GET event, GET event]`; peer served equals admitted equals 5; first peer exchange `POST /common/oauth2/v2.0/token`; the rest are GET.
- **Alias rewrite** checks as for NONEXPIRED. Oracles are emitted only after every measured check passes. One bounded retirement, plus the guarded cleanup path.

## 2. Focused fake-verification packet (roles 13–16)
`C:/Users/trish/Documents/Codex/2026-10-15/trish-wants-to-improve-dex-s/outputs/scheduler-ms-refresh-fake-prep-matt-v1`. Its manifest is **`3FD4346AB29F7DC62053A63BCCD913D6567A0DDD1E204F86AD9E40ADD54960A7`** (21 entries, OK). No result or receipt files.
- **Reused byte-identical:** wrapper `AE84E632…`, outer admission `7DCA32E2…`, launcher `D22C37E3…`.
- **New:**
  - checker **`532D874109F66CD2327AB9AB81A5D0784D43F2455876D7CED0CB90FEF508356C`**;
  - EXPECTED **`FD98745D…DB71`**;
  - OUTER **`D2E3A414…F56B`** (false);
  - VERIFICATION **`E2779EFFB90DF039F681D62FEA1AE3C45E398A9918111FC023952214BF808346`** (false): 18 packet pins (all verified against disk) plus 1 runtime pin, the interpreter `5F7B89A6…`.
- **Subjects:** candidate roles 4, 5, 6, 8 and 10 plus the unchanged peer; source baseline roles 4, 5, 6, 8 and 10; production `microsoft_calendar.py` `6A52B10F…`.
- **Ten controls, each labeled with its proof layer** (details in that packet's `Launch-Decision.md`):
  1. SUBJECT-PINS (raw pin).
  2. PRESERVED (text identity of the NONEXPIRED, diagnostic, seed, transcript, receipt and suite functions, `NATIVE_CASES` and the seed literals).
  3. TENANT-PATH-AGREEMENT (actual production builder against the actual transcript builder; 5 bad tenants refused).
  4. OAUTH-ROUTE-TABLE.
  5. REFRESH-INVENTORY-ORDER (including the actual peer sending the body verbatim).
  6. SEMANTIC-PERSISTENCE-ADMISSION (actual measurement with a randomized fake cipher; **changed ciphertext with unchanged plaintext refused**, plus wrong token, missing rotation, expiry boundary and refusal cases).
  7. SECRET-EXCLUSION-PROJECTION (actual `np_receipts`).
  8. REGISTRY-MAPPING (structural).
  9. REFRESH-BODY-SHAPE (structural only).
  10. ACTUAL-SOURCE-MUTANTS: ciphertext-only persistence, legacy path, missing token script, graph-only routes.
- **Hygiene:** `sys.modules` stubs are saved and **restored** (the T05 H1 pattern is not repeated).
- **Self-review fixes before freezing:** annotated-assignment extraction for `NATIVE_CASES`, and the `ExchangeStep` annotation resolved for the standalone-compiled peer function. Every extraction anchor was verified to exist exactly once.
- **Held command:** `Future-Command-HELD.ps1.txt`, admission `E2779EFF…`. The wrapper refuses while the flags are false. Bounds are unchanged: 120 + 5 + 5 + 5 = 135 s nominal; 64 KiB per stream; 256 KiB for the result.

## 3. Held native command (current shape)
```
& 'C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-ms-refresh-prep-matt-v1\scheduler-native-provider-diagnostic-launch-v1\Invoke-Native-Provider.ps1' -ExpectedConfigSHA256 '6558688B15D5ED0105D18EF07D7D2580FD267437087E613EA9C7103BFAB7FCC4' -ExpectedDockerConfigSHA256 '8AAF77950CDA7A332C1BF22F984C47A392EF313E2DAD44415DDCB5636B680D34' -DockerConfigPath 'C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-ms-refresh-prep-matt-v1\scheduler-native-provider-diagnostic-launch-v1\host\docker-ops-config.json'
```
- No `-ReceiptPath`. The operator stops on `launch_ready=false`.
- A launch needs a reviewed staging flip of the host and runner gates (which changes the config and payload hashes), the reconciled diagnostic outcome, your EXECUTE acknowledgement and Trish's approval.
- **Native bounds** are inherited from the configs: suite 900 s, runner 600 s, peer 120 s plus a 5 s join, PKI 45 s nominal, 1 MiB capture per Docker command, a 32-command cap. `static_success_docker_command_count` (22) is case-independent host sequencing that is **carried, not re-derived** here; please confirm.

## 4. Preservation
- copy source and pending native staging `…-diagnostic-launch-dex-v1`: 274/274;
- pending T05 staging `…-t05-fake-dex-v3`: 301/301 (via `Launch-Input-Manifest`);
- my launch prep `…-diagnostic-launch-v1`: 269/269;
- T05 v3: 289/289.

All are untouched. **Observation only:** `…-t05-fake-dex-v3.evidence` now exists. I did not open it; it's outside this assignment.

## 5. Gaps and questions (none blocking preparation)
- **G1:** runtime-only assumptions: one peer serving both hostnames; target 2's ROLLBACK with no request; the response, terminal and persistence behavior as traced. No native run on the shared harness has passed yet.
- **G2:** the invalid-grant path defect remains (deferred, Q3), along with the peer form-field recorder (Q4).
- **G3:** `REFRESH-BODY-SHAPE` is structural only; the body's runtime behavior is proven only natively.
- **G4:** please confirm the carried `static_success_docker_command_count` for this batch.
- **No new role, contract change or unsupported assumption** beyond the above.

## Scope statement
- Read, copy, literal edits to the five named roles and the config data, hashing, and manifest, document and JSON authoring.
- No imports, parsing, compilation, tests, helper or wrapper invocation, verification, sockets, PKI, providers, database, Docker, installation, build, cleanup or execution.
- No production, operator, peer, route, PKI or API edits; no Git; no `F:/Code Repo/ThePlan` edits.
- **Two process slips, both corrected before freezing:**
  - one scratch file written to `/tmp` (removed; it held only manifest lines);
  - one temporary hash note inside the fake packet folder (removed before the manifest).

JSON validity of the edited configs was checked by eye only.

Signed: Matt
