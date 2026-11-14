# Preparation review — scheduler-native-provider-t05-closure-prep-jim-v2

Jim (Justin), 2026-11-12. PREPARATION ONLY. Fresh same-lane successor from t05-closure-prep-jim-v1 consolidating Dex R1–R5. Zero execution. Held packets untouched. Tip base C902F529… preserved immutable.

## Authority

| Document | SHA256 |
| --- | --- |
| Reconciled-Authoring-Scope-For-Approval.md | 389A00DD444C610A93877362A574A1C93543F916F119D2D2FF71BA167FBF7E2D |
| Trish-Preparation-Approval.json | 5D1EA2F973FE110D35B65E4172821F014E74A8F2A65BCBB4AB8EE22458F80CA4 |
| Dex-Reconciliation.md (candidate-v2 QUALIFIED ACCEPT) | BA194960F6B96B1D9DD95F4434EC8C94AB1F7C65E1238761DA7B4DF17DCDF0BB |
| Native-Deadline-TLS-Observation-Review.md (§6 TLS EOF) | 1A485EB29FD095933F0BA45A13B288A149E44FBFCEAFB26029C59C5D5F761069 |
| Dex-Review-and-Revision.md (t05-closure-prep-v1 REVISE) | (read fully; outputs/scheduler-native-provider-t05-closure-dex-review-v1) |
| Held tip base t05-closure-prep-jim-v1 TIP on-disk | C902F5296D2B76031254213A1A0812CB944062296BD6B5BA13373A29863483EB |
| Held candidate-v2 TIP | 34BBC408549BA80F54A9DB189C11A37377484B1424FF33F5190836C3224BC440 |
| Held native-ready TIP on-disk | A321FB198A69FBA4864C14D1CE474D49E68DF887F087EF0673DAA588CDB3FF57 |
| Held prep-v9 TIP on-disk | 6585E768FA64E455052368F75E47795ECC99708DC4EDCFBF6D33CD3B5A25F188 |

Same approved **16-role** authoring lane. No new preparation card. T05 NOT added to launch batch.

## Dex R1–R5 FIXED

| ID | Disposition | Finite fix |
| --- | --- | --- |
| R1 | FIXED | `_t05_admit_orderly_event_refusal` / abrupt path STOP on `CoveringRootOutcomeUnknown` before unwrap when `expected_unknown=false`; IncompleteRead/CoveringTransportRefused only |
| R2 | FIXED | `_t05_admit_abrupt_truncation` requires measured `abrupt_ssl_error`\|`abrupt_tcp_reset` receive + peer stimulus + distinct framing refuse; rejects generic refuse-alone, deadline, malformed-only, UNKNOWN |
| R3 | FIXED | `_t05_start_owned_peer_or_retire` performs one bounded `retire_owned` on `start_background` failure after partial acquisition; caller finally skips helper-retired peers |
| R4 | FIXED | `_t05_capture_validated_plan` per exchange a/b/abrupt; `assert_plan_still_valid` before/after; no `_iso_now` fallback; failure/expiry STOP; no retries |
| R5 | FIXED | `_report_producer_env` admits fake `bind_runtime_public_ca_hash` + `_provider_pki_typed_success_summary`; T05-CLOSURE-FOCUSED adds 14 extracted actual-helper controls + mutations (no real imports/fs/PKI/sockets) |

## Per-observation FIXED evidence (preserved)

| # | Observation | Disposition | Evidence |
| --- | --- | --- | --- |
| 1 | Complete close-delimited JSON accepted after orderly close_notify | FIXED (authored) | Transcript `Content-Length:OMIT`; production `clean_eof`; peer stimulus ≠ sole proof |
| 2 | Valid JSON prefix shorter than Content-Length refused after orderly close_notify | FIXED (authored) | clean_eof + `_t05_admit_orderly_event_refusal` (no UNKNOWN unwrap) |
| 3 | Abrupt TLS truncation without close_notify classified separately | FIXED (authored) | measured abrupt receive class + stimulus; distinct from malformed/ASGI/deadline/UNKNOWN |

## Dex interrupt constraints folded (preserved)

1. Peer stimulus / attempt notes ≠ sole orderly EOF proof
2. Production receive observer under `suppress_ragged_eofs=False` (clean_eof vs abrupt_ssl_error / abrupt_tcp_reset)
3. JoinedTLS.close remains local-only; unwrap success not sole proof
4. No extra launch gate; launch batch stays `NP-V-MS-NONEXPIRED` only

## Finite extracted control inventory (R5)

```
T05-R1-CLEAN-REFUSAL-ADMITTED
T05-R1-UNKNOWN-REFUSED
T05-R1-UNKNOWN-UNWRAP-MUTATION-HOLE
T05-R2-ABRUPT-MEASURED-ADMITTED
T05-R2-GENERIC-REFUSAL-REFUSED
T05-R2-DEADLINE-REFUSED
T05-R2-UNKNOWN-REFUSED
T05-R2-MEASURED-GUARD-MUTATION-HOLE
T05-R3-PARTIAL-START-ONE-RETIREMENT
T05-R3-UNCONFIRMED-RETIREMENT-STOP
T05-R3-DOUBLE-RETIRE-GUARD-PRESENT
T05-R4-PLAN-CAPTURE-FAILURE-STOP
T05-R4-PLAN-EXPIRY-STOP
T05-R4-NOW-FALLBACK-ABSENT
```

## Flags

executed=false; launch_authorized=false; launch_ready=false; prep_is_not_pass=true; endpoint unbound; no invoke; Slack tip=false.

## Policy / contract surfaces (not invented)

1. **Close-delimited spelling:** `Content-Length:OMIT` stripped by peer
2. **T05 body path:** CoveringHTTP→default JoinedTLS Google event exchanges (framing/TLS), not full covering-refresh ASGI vertical
3. **Short-CL refuse class:** `IncompleteRead` or `CoveringTransportRefused` only — CoveringRootOutcomeUnknown (incl. cleanup-wrapped primary) is STOP under expected_unknown=false
4. **Abrupt evidence:** measured production receive terminal + stimulus required; generic refuse insufficient
5. **Structural vs extracted:** T05-CLOSURE-FOCUSED remains honest that native behavioral proof is unexecuted; extracted controls are fake-scope predicates

## HOLDs / gaps

- Other 24 native + 4 CF case bodies: HOLD_EXPLICIT_NOT_PASS (76 planning IDs retained)
- T05 bodies authored but **not** in launch batch; not waiting on Trish for this prep freeze
- fake-v1 PASS prerequisite UNFULFILLED; candidate-v2 / native-ready / prep-v9 / fake-v1 / tip base v1 untouched
- Provider PKI / native launch / focused fake invoke unauthorized under this prep
- Image presence / port 443 bind unverified (no live probe)
