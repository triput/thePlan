# Preparation review — scheduler-native-provider-t05-closure-prep-jim-v1

Jim (Justin), 2026-11-12. PREPARATION ONLY. Fresh successor from native-ready-prep-v1 implementing NP-T05-ORDERLY-CLOSE + NP-T05-ABRUPT-TRUNCATION fixture bodies and focused fake-check. Zero execution. Dex interrupt on peer/EOF pairing folded.

## Authority

| Document | SHA256 |
| --- | --- |
| Reconciled-Authoring-Scope-For-Approval.md | 389A00DD444C610A93877362A574A1C93543F916F119D2D2FF71BA167FBF7E2D |
| Trish-Preparation-Approval.json | 5D1EA2F973FE110D35B65E4172821F014E74A8F2A65BCBB4AB8EE22458F80CA4 |
| Dex-Reconciliation.md (candidate-v2 QUALIFIED ACCEPT) | BA194960F6B96B1D9DD95F4434EC8C94AB1F7C65E1238761DA7B4DF17DCDF0BB |
| Native-Deadline-TLS-Observation-Review.md (§6 TLS EOF) | 1A485EB29FD095933F0BA45A13B288A149E44FBFCEAFB26029C59C5D5F761069 |
| Held candidate-v2 TIP | 34BBC408549BA80F54A9DB189C11A37377484B1424FF33F5190836C3224BC440 |
| Held native-ready TIP on-disk | A321FB198A69FBA4864C14D1CE474D49E68DF887F087EF0673DAA588CDB3FF57 |
| Held prep-v9 TIP on-disk | 6585E768FA64E455052368F75E47795ECC99708DC4EDCFBF6D33CD3B5A25F188 |

Same approved **16-role** authoring lane. No new preparation card. Held packets untouched.

## Per-observation FIXED evidence

| # | Observation | Disposition | Evidence |
| --- | --- | --- | --- |
| 1 | Complete close-delimited JSON accepted after orderly close_notify | FIXED (authored) | Transcript `T05-ORDERLY-CLOSE-DELIMITED-COMPLETE` uses `Content-Length:OMIT` (true close-delimited; no auto-CL). Runner `_run_np_t05_orderly_close` obs (a) requires peer orderly stimulus **and** production `clean_eof` under `suppress_ragged_eofs=False`, then httpx accept. Peer `orderly_close_notify_attempted` alone insufficient. |
| 2 | Valid JSON prefix shorter than Content-Length refused after orderly close_notify | FIXED (authored) | Transcript `T05-ORDERLY-SHORT-CL-VALID-JSON` (CL=20, body `{}`). Obs (b) requires orderly stimulus + production `clean_eof` + refuse (`CoveringTransportRefused` / `IncompleteRead` / UNKNOWN-wrapped primary). |
| 3 | Abrupt TLS truncation without close_notify classified separately | FIXED (authored) | Transcript `T05-ABRUPT-TRUNCATION` + peer `abrupt_truncate`. Runner requires abrupt stimulus + production `abrupt_ssl_error` and/or incomplete/refuse chain; rejects success, malformed-JSON-only, and records `asgi_disconnect=false`. |

## Dex interrupt constraints folded

1. Peer sets `close_mode_observed` before unwrap and may swallow `ssl.SSLError` → records attempt/unwrap_ok separately; `peer_stimulus_not_sole_orderly_eof_proof` note.
2. Production receive observer classifies `clean_eof` vs `abrupt_ssl_error` under preserved `suppress_ragged_eofs=False`.
3. Do **not** require successful two-way server unwrap as sole proof — JoinedTLS.close remains local-only (§6).
4. No extra case/policy/launch gate; launch batch stays `NP-V-MS-NONEXPIRED` only.

## Flags

executed=false; launch_authorized=false; launch_ready=false; prep_is_not_pass=true; endpoint unbound; no invoke; Slack tip=false.

## Policy / contract surfaces (not invented)

1. **Close-delimited spelling:** prior script used CL:2 while labeled close-delimited — corrected to `Content-Length:OMIT` stripped by peer, matching covering transport policy “Neither CL nor TE for close-delimited”.
2. **T05 body path:** authored as production `CoveringHTTP`→default `JoinedTLS` Google event exchanges (framing/TLS), not the full covering-refresh ASGI vertical used by NP-V-MS-NONEXPIRED. Still vendor hostname + verify-full + numeric loopback; no transport_factory injection.
3. **Short-CL refuse class:** may be `IncompleteRead`, `CoveringTransportRefused("incomplete fixed-length…")`, or UNKNOWN-wrapped primary — fixture accepts those refuse classes; does not invent a new public exception type.

## HOLDs / gaps

- Other 24 native + 4 CF case bodies: HOLD_EXPLICIT_NOT_PASS (76 planning IDs retained)
- T05 bodies authored but **not** in launch batch; not waiting on Trish for this prep freeze
- fake-v1 PASS prerequisite UNFULFILLED; candidate-v2 / native-ready / prep-v9 / fake-v1 untouched
- Provider PKI / native launch / focused fake invoke unauthorized under this prep
- Image presence / port 443 bind unverified (no live probe)
