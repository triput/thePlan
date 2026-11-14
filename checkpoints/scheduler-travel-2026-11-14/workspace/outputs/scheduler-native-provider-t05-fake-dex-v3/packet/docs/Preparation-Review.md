# Preparation review — scheduler-native-provider-t05-closure-prep-jim-v3

Jim (Justin), 2026-11-12. PREPARATION ONLY. Fresh same-lane successor from t05-closure-prep-jim-v2 fixing remaining Dex R2 taxonomy boundary. Zero execution. Held packets untouched. Tip base 7CC58CDA… preserved immutable.

## Authority

| Document | SHA256 |
| --- | --- |
| Reconciled-Authoring-Scope-For-Approval.md | 389A00DD444C610A93877362A574A1C93543F916F119D2D2FF71BA167FBF7E2D |
| Trish-Preparation-Approval.json | 5D1EA2F973FE110D35B65E4172821F014E74A8F2A65BCBB4AB8EE22458F80CA4 |
| Dex-Reconciliation.md (candidate-v2 QUALIFIED ACCEPT) | BA194960F6B96B1D9DD95F4434EC8C94AB1F7C65E1238761DA7B4DF17DCDF0BB |
| Native-Deadline-TLS-Observation-Review.md (§6 TLS EOF) | 1A485EB29FD095933F0BA45A13B288A149E44FBFCEAFB26029C59C5D5F761069 |
| Dex-Review-and-Revision.md (t05-closure-prep-v2 REVISE R2) | B5E561BAB6270F2BFA8DE6091F0F3694DE2AC4C39926C870388B82D7D6277B30 |
| Held tip base t05-closure-prep-jim-v2 TIP on-disk | 7CC58CDAF6C6570583D68E94CB842A2810E49AF70F94A9296CBB30237433A638 |
| Held tip base t05-closure-prep-jim-v1 TIP on-disk | C902F5296D2B76031254213A1A0812CB944062296BD6B5BA13373A29863483EB |
| Held candidate-v2 TIP | 34BBC408549BA80F54A9DB189C11A37377484B1424FF33F5190836C3224BC440 |
| Held native-ready TIP on-disk | A321FB198A69FBA4864C14D1CE474D49E68DF887F087EF0673DAA588CDB3FF57 |
| Held prep-v9 TIP on-disk | 6585E768FA64E455052368F75E47795ECC99708DC4EDCFBF6D33CD3B5A25F188 |

Same approved **16-role** authoring lane. No new preparation card. T05 NOT added to launch batch.

## Dex R2 FIXED (remaining boundary from review-v2)

| ID | Disposition | Finite fix |
| --- | --- | --- |
| R2 | FIXED | Observer admits only `abrupt_ssl_eof` (`ssl.SSLEOFError`) and `abrupt_tcp_reset` (`ConnectionResetError`\|`ConnectionAbortedError`). Generic `ssl.SSLError` → `ssl_error_non_eof`; unrelated `OSError`/TimeoutError → `os_error_non_reset`. Admission requires those finite measured classes + stimulus; generic SSL/OSError/timeout/clean_eof/UNKNOWN STOP. Fake controls exercise extracted observer with fake JoinedTLS.receive then actual admission predicate. |

## Dex R1/R3/R4/R5 PRESERVED

| ID | Disposition | Evidence |
| --- | --- | --- |
| R1 | PRESERVED | `_t05_admit_orderly_event_refusal` STOP on CoveringRootOutcomeUnknown before unwrap; IncompleteRead/CoveringTransportRefused only |
| R3 | PRESERVED | `_t05_start_owned_peer_or_retire` one bounded retirement on partial start failure; no double cleanup |
| R4 | PRESERVED | `_t05_capture_validated_plan` per exchange; no now-fallback; expiry/failure STOP |
| R5 | PRESERVED (+ R2 controls expanded) | Report-producer fake deps admitted; T05-CLOSURE-FOCUSED extracted controls now 19 (finite observer taxonomy controls added); no real imports/fs/PKI/sockets |

## Per-observation FIXED evidence (preserved)

| # | Observation | Disposition | Evidence |
| --- | --- | --- | --- |
| 1 | Complete close-delimited JSON accepted after orderly close_notify | FIXED (authored) | Transcript `Content-Length:OMIT`; production `clean_eof`; peer stimulus ≠ sole proof |
| 2 | Valid JSON prefix shorter than Content-Length refused after orderly close_notify | FIXED (authored) | clean_eof + `_t05_admit_orderly_event_refusal` (no UNKNOWN unwrap) |
| 3 | Abrupt TLS truncation without close_notify classified separately | FIXED (authored) | finite abrupt_ssl_eof\|abrupt_tcp_reset + stimulus; distinct from malformed/ASGI/deadline/UNKNOWN/generic SSL/OSError |

## Dex interrupt constraints folded (preserved)

1. Peer stimulus / attempt notes ≠ sole orderly EOF proof
2. Production receive observer under `suppress_ragged_eofs=False` (clean_eof vs abrupt_ssl_eof / abrupt_tcp_reset; non-abrupt generic classes distinct)
3. JoinedTLS.close remains local-only; unwrap success not sole proof
4. No extra launch gate; launch batch stays `NP-V-MS-NONEXPIRED` only
5. No production source changes

## Finite extracted control inventory (R5 / R2 taxonomy)

```
T05-R1-CLEAN-REFUSAL-ADMITTED
T05-R1-UNKNOWN-REFUSED
T05-R1-UNKNOWN-UNWRAP-MUTATION-HOLE
T05-R2-OBSERVER-EOF-ADMITTED
T05-R2-OBSERVER-RESET-ADMITTED
T05-R2-OBSERVER-GENERIC-SSL-REFUSED
T05-R2-OBSERVER-GENERIC-OSERROR-REFUSED
T05-R2-OBSERVER-TIMEOUT-REFUSED
T05-R2-OBSERVER-CLEAN-EOF-REFUSED
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

## HOLDs / gaps

- Other 24 native + 4 CF case bodies: HOLD_EXPLICIT_NOT_PASS (76 planning IDs retained)
- T05 bodies authored but **not** in launch batch; not waiting on Trish for this prep freeze
- fake-v1 PASS prerequisite UNFULFILLED; candidate-v2 / native-ready / prep-v9 / fake-v1 / tip base v1 / tip base v2 untouched
- Provider PKI / native launch / focused fake invoke unauthorized under this prep
- Image presence / port 443 bind unverified (no live probe)