# Preparation review — scheduler-native-provider-prep-v2

Jim (Justin coding lead), 2026-11-12. PREPARATION ONLY. Fresh successor correcting Dex provisional + R1–R4/host-wiring under same authority.

## Authority

| Artifact | SHA256 |
| --- | --- |
| Reconciled-Authoring-Scope-For-Approval.md | 389A00DD444C610A93877362A574A1C93543F916F119D2D2FF71BA167FBF7E2D |
| Trish-Preparation-Approval.json | 5D1EA2F973FE110D35B65E4172821F014E74A8F2A65BCBB4AB8EE22458F80CA4 |
| Final-Assembly-Proposed-Source-Selection.json | 857141512AADF6F90F1CA8F92547A777E3D5FE943671495512FA18CEA7CBA296 |
| jim-v2 TIP-FREEZE.json (immutable baseline) | 1D88A97FCD60BF65B95414044CEA3D90FCD110848C05B67E54DAC0BDA8C575F4 |
| Frozen tipped prep-v1 TIP on-disk (interim scaffolding) | 0AA4C08197E897F8A91A23945D882854FED44528E476AF04506D245B2EDB211D |
| Frozen tipped prep-v1 tip_sha256 (preimage) | 31FC0AD8F8A9700F0B8FC168134AA0973FE5C9207BC68BB2A72AF5A8823B07B7 |

## Dex provisional fixes (R1)

- `np_provider_peer.py` — real socket/TLS lifecycle (bind/accept/handshake/request/response/close_notify/abrupt/stalls + bounded `retire_owned`)
- `np_runner_entry.py` — real registry dispatch; `NP-V-MS-NONEXPIRED` implemented source; remaining cases explicit `CaseBodyHold`; main runs suite when `launch_ready` (no unconditional always-refuse after admission)
- Incomplete cases HOLD — never fabricated PASS

## R2–R4 / host-wiring

- Checker: exact AST registry order; peer/runner shape; T08 nested/reset behavioral controls; port PASS pins; prior framing evidence pins
- Launcher: bounded readers during collection; exclusive receipt; exact result/control gate (port-fake lineage)
- Invoke-Native-Provider: external `-ExpectedConfigSHA256` (no self-hash fixed point); passes config/receipt/docker-config to supervisor
- Supervisor: `ProviderDockerOps` composition overrides N06/N07 attach for NP batches

## Assembly

- Base: `scheduler-framing-ack-fake-v4/packet/candidate`
- Sole override: `covering_transport_policy.py` = 5F48FD7ED50C57A6A47ADA20138678BB3C112A2A69D1C234A47580E6CD068B88
- 234 files re-verified; destination re-hashed
- Port dependency = verified finite host PASS 9/9 (RESULT B8C6353A… / Receipt 61F266A3… / Reconciliation E922DA61…) — not native dial/TLS or full T01

## Observation aids

- `docs/Native-Deadline-TLS-Observation-Review.md` SHA256 1A485EB29FD095933F0BA45A13B288A149E44FBFCEAFB26029C59C5D5F761069
- `docs/Source-Pins-Native-Observation-Review.json`
- `docs/T02-T08-Witness-Matching-20261112.md`

## Flags

executed=false; launch_authorized=false; prep_is_not_pass=true; endpoint=unbound; no Slack tip.
