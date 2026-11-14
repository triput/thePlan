# Matt → Dex: NP-V-GOOGLE-INVALID preparation v1 and focused fake (HELD, frozen)

November 13, 2026. This responds to `Matt-thePlan-Scheduler-Google-Invalid-Grant-Preparation-2026-11-13.md` (`5FA593950FECB4C68963E37AE627F5D3092E441B953578FC1C5B48401D77C5B1`), under lane `389A00DD…7E2D`.
- **Status:** PREPARED_NOT_EXECUTED. Two fresh frozen roots, no active writer, endpoint unbound.
- **Method:** copy, text, hash and JSON authoring, plus read-only source tracing. Nothing was imported, parsed, compiled, tested or invoked.
- **Not used or touched:** subagents, Docker, DB, PKI, sockets. Your Google success packet is untouched.
- **Unexecuted:** syntax and behavior.

## 1. Native root `outputs/scheduler-native-google-invalid-prep-matt-v1`
- **Source:** corrected Google v3 `FC1DC3CB…B6D4`, re-verified 309/309 before the copy (and unchanged after). Runner `FA9AF0A4`. Manifest-listed inputs only; no evidence copied.
- **Parent:** `Input-Manifest.sha256` = **`D9B3B2C08901E729FC0EBD3397FE11EB608CE56BE50416A0A6C0F8A0112D8533`** (313: the 309 inputs plus README, Freeze, HELD command and source-manifest copy). Verified OK.
- **Exact diff:** `Matt-thePlan-Scheduler-Google-Invalid-Prep-V1-2026-11-13.diff` = `ED50F3AEE291A2565D97ABA89A68F80240B5A938872B32F798EB3432A966B3D1` (1700 lines, 16 hunks, 7 files). Most of it is the whole-file SUMS and nested hunks, because those manifests are now LF where your v3 had CRLF; the content differs only in the stated rows.

| Role | File | Before → after |
|---|---|---|
| 4 runner | `np_runner_entry.py` | `FA9AF0A4` → **`5852A6D365112CFE0A422F1E23C9F7F995A16CA00A510DDE82EF1E7CCAA66995`** |
| 5 suite | `np_suite.py` (note only) | `E028812B` → **`15C841CA2206B7A45CA52D2E0AA7318F7E3C8AC1A79F4485AC1775AA39C0CDA7`** |
| data | `runner-config.json` (CRLF kept; `case_ids` only) | `95278DF6` → `82B75D9F8EE0A102FE50FC31EF9C19C7792A77E85F28645497BCA7BFA6353826` |
| data | `launch-config.json` (CRLF) | `AF09151F` → `180E9A4C1A347CA1CB1F61DCD919C7B13520C8D9B1C97727E79C8E8791F029AC` |
| data | `docker-ops-config.json` (7-path rename) | `71CC87C4` → `7725A15403FDBE699869FB105A0F543B0C28F70D4353D5DFEF615A0BC2A8315E` |
| manifest | payload SUMS (257; 3 rows) | `001B0B8B` → `B5FC0353EAD1E66EB3E48FFA42606142A8FB6BE39B66AB8B0193BAEB01825A5F` |
| manifest | nested (269; 6 rows) | `FD3AB617` → `2C72B6A225616C113C952581DE011027A66AFA796BDE7663CB9366A95433A23E` |

- **Role 8 transcript:** unchanged (`79025EC5`). The case reuses the existing `google_token_invalid_grant_script`.
- **Unchanged:** peer `17EA148E`, routes, seeds, PKI, sanitizer `69F59AF1`, all 234 API files, the operator and the host helpers. No new executable helper was added.
- **Gates:** host and runner `launch_ready` false, staged false, both `launch_authorized` false. Single-case batch `np-v-google-invalid-single-case`, so it is not combined with any schema-provisioning case.
- **HELD command** `Google-Invalid-Native-Command-HELD.ps1.txt` = `35CE5E36F2647185B78233F1859EFA56A6DEB345BDFDDC544F52707CB6476C0D`: this root's operator, with config `180E9A4C…` and Docker config `7725A154…`, and no `-ReceiptPath`. It STOPs on gates false.

### Source trace against the corrected v3 bytes
**F** = read in source. Every line below except the last is F.
- `get_valid_access_token` (google_calendar l.612–642) → `refresh_access_token` (l.156) → `_CoveringClient._request`. `__exit__` returns False, so nothing is suppressed.
- CoveringHTTP (covering_http_transport l.349–360): after `_admit_fixed_length_complete`, a JSON object with status 400 and `error` == `invalid_grant` raises the exact `CoveringReauthorizationRequired`. Any other OAuth ≥400 raises `CoveringRootOutcomeUnknown`. An OAuth exception after send also becomes UNKNOWN.
- Adapter (covering_domain_adapters l.43–60): catches the exact type, then `changed=False` and `TokenRejected(PREFLIGHT_ACCOUNT_DISCONNECTED = "CALENDAR_ACCOUNT_DISCONNECTED")`. The terminal must equal `ROLLBACK_ACKNOWLEDGED`, otherwise UNKNOWN.
- Dispatch (covering_domain_dispatch l.218–221): `TokenRejected` gives a static preflight row and `continue`, so there is no `run_target`, IMPORT or PARENT. ASSESSMENT then runs (l.249–257).
- Public mapping (covering_refresh): `import_attempted == 0` gives `no_op` (l.159–160). A preflight outcome gives phase `preflight`, status `preflight_rejected`, effects `()`, `cause` None, `upserted` 0 (l.136–137, l.433–452). `scheduling_revision_at_end` is `readiness.scheduling_revision`, the revision read under lock in the final assessment.
- The worker observer records only exceptions escaping `run_bounded_domain`. The rejection returns normally, so I assert it is empty.
- The shared vendor leaf carries `oauth2.googleapis.com` (prepare-np-provider-tls.sh l.50), so the peer uses `google_token_route()` (same address, port and CA, checked in the case).
- **I (inference):** the never-covered requested row blocks requested freshness and all-enabled freshness, so `scheduling_ready` is false. Asserted as derived; not proved.

### Case as authored (`_run_np_v_google_invalid`, additive)
- **Seed:** an expired Google owner with exactly one requested subscription, planted in setup (before commit) as the enabled primary-alias row, checked against production `GOOGLE_PRIMARY_ALIAS`. Plus an unrelated non-expired Google owner.
- **Public:** 200, `no_op`, the exact single row, summary 1/1/0/0/0, a completed assessment (`assessment_error` None) that is not ready (requested and all-enabled freshness false, `scheduling_ready` false), and revision at start = at end = readiness = persisted, with `bumped` false.
- **Native:**
  - exactly 1 POST oauth, with the client outcome exactly `("exception","CoveringReauthorizationRequired","app.services.covering_transport_policy")`;
  - TOKEN exactly `[ROLLBACK_ACKNOWLEDGED]`, plus the observer marker;
  - PARENT `[]`, no worker exception;
  - the ingress-budget identity, default JoinedTLS and CoveringReleasePlan.
- **State, before and after (separate native reads):** credentials (semantic and expiry), coverage, the primary-alias subscription row, events (none), owner revision and busy digest all unchanged. The unrelated owner's credential, coverage, events, subscriptions, revision and busy digest are unchanged.
- **Peer:** retired once through the existing helper (joined, no worker error), then exactly 1 POST `/token`, orderly close, exact bytes.
- **Observers:** the token-terminal observer, HTTP constructor patch, worker observer and PARENT observer are all **installed inside** the inner `try`. All are restored in its `finally`. An identity guard (token terminal and constructor) runs before any evidence, and an identity-checked defensive restore runs in the outer `finally`. This also closes my install-window qualification from `333AA4A6` for this case.
- **Retention:** the declared oracle `token_rejected_path_not_ms` contains "token", so the unchanged sanitizer drops it from the receipt. It is enforced in memory (`check_oracles_immediate`), and its evidence is retained under the allowlisted `token_terminal` (sequence) and `covering_token_terminal` (`ROLLBACK_ACKNOWLEDGED`).

## 2. Fake packet `outputs/scheduler-native-google-invalid-fake-prep-matt-v1`
- **Manifest** `5AE0742874F40D86B84BCF3C94F177B14858A49B4E698D4409FCEEE7856FF178` (37 entries, verified OK).
- **Immutable, byte-identical:** wrapper `AE84E632`, outer `7DCA32E2`, launcher `D22C37E3`.
- **New:**
  - checker `6A5F2D2618C5701C55841D2135A9048BF190403D3BD6D9C542B0F2DF4E36DC4C`;
  - EXPECTED `F2586BB349351173E1D6FB66DFA08C5FECFB79091BB3359E076CB94E9F261BF0`;
  - OUTER `96D2A023C77DDF3B83B44F262949B117511E183329FA0ACA4A791021750F3245`;
  - VERIFICATION **`EF2FB8EDF8CC9569DB38743D66F5C6493FE95E777E0E510D72856474D4B48E37`**: 34 packet pins (verified on disk) and 9 partial runtime pins (interpreter, DLL, json ×3, `dataclasses`, `ast`, `typing`, `textwrap`).
- **Focused scope:** 10 controls and 47 nested predicates. The unchanged success helpers are not re-proved. Details are in `Launch-Decision.md`.
- **Mutants:** runner mutants apply **only inside** `_run_np_v_google_invalid` (the success body shares several lines), and the transcript mutant only inside its script unit. Each anchor is unique within its unit; I counted them.
- **Hand-trace fixes before freezing:**
  - the `remapped=CoveringRootOutcomeUnknown()` anchor occurs twice in the transport, so it was replaced by a 2-line anchor pinned to the `invalid_grant` branch;
  - the "preserved" control now compares an explicit list of 11 named units, which avoids top-level duplicate-name ambiguity.
- **Future fake command:** `Future-Command-HELD.ps1.txt` = `161A2990…`, the wrapper with `-AdmissionSHA256 EF2FB8ED…`. It refuses under prep.

## 3. Case/oracle-to-evidence table

| Requirement / oracle | Enforced (native, in memory) | Retained evidence | Fake control |
|---|---|---|---|
| `token_rejected_path_not_ms` (T06-INVALID-GRANT-GOOGLE) | `check_oracles_immediate`; exact client outcome; TOKEN rollback | `token_terminal`, `covering_token_terminal`, `client_outcomes`, `oauth_request_count` (oracle key itself sanitized, disclosed) | WIRING native guards; CONTRACT; mutants `client_outcome_loosened` and `covering_token_key_unallowlisted` |
| Complete fixed-length invalid_grant (not close-delimited) | peer `bytes_sent` exact | `peer_exchange_inventory` | TRANSCRIPT ×2; mutant `invalid_grant_body_changed` |
| No IMPORT/PARENT after rejection; public `no_op` / preflight row | public, PARENT `[]` | `public_response`, `parent_terminal_count`, `preflight_code` | CONTRACT dispatch/mapping; WIRING public guards; mutants `success_outcome_admitted` and `parent_check_dropped` |
| Final assessment at the unchanged persisted revision | revision guard | `owner_state_before/after`, `public_response.scheduling_revision*` | WIRING state guards; mutant `revision_bump_tolerated` |
| Credentials, coverage, subscription and events unchanged | state guards | `credential_state_*`, `coverage_*`, `subscriptions_after` | WIRING state guards |
| Unrelated data unchanged | 5-way guard | `unrelated_unchanged` | mutant `unrelated_owner_check_dropped` |
| Restoration by identity | inner + outer `finally`, identity guard | `resource_disposition.observers_restored` | WIRING observers; mutant `token_restore_dropped` |
| One retirement and exact inventory | helper + peer guard | `peer_exchange_inventory` | WIRING; mutant `second_retirement` |

## 4. Bounds and limits
- **Fake:** 135 s nominal (120 + 5 + two 5 s), 64 KiB per stream, 256 KiB result.
- **Native proposal (not authority):** PKI 30+5+two 5 = 45; peer 120 + 5 join for 1 exchange; runner 600 / suite 900; 32 Docker commands / 1 MiB; production 210/240/30 and 600 s plan validity unchanged.
- **Not established:** any native behavior or PASS; the derived not-ready readiness; CoveringHTTP's framing of the 400 beyond the peer and fake checks; Microsoft (parked). No family closure; all 76 requirements retained.

**Preserved:** the source v3 `FC1DC3CB`, every Google, T08 and earlier root and their evidence. No Git and no ThePlan edits. Endpoint unbound; all holds stay.

Signed: Matt
