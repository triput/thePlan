# Preparation review — scheduler-native-provider-prep-v1

Jim (Justin coding lead), 2026-11-12. PREPARATION ONLY.

## Authority

| Artifact | SHA256 |
| --- | --- |
| Reconciled-Authoring-Scope-For-Approval.md | 389A00DD444C610A93877362A574A1C93543F916F119D2D2FF71BA167FBF7E2D |
| Trish-Preparation-Approval.json | 5D1EA2F973FE110D35B65E4172821F014E74A8F2A65BCBB4AB8EE22458F80CA4 |
| Final-Assembly-Proposed-Source-Selection.json | 857141512AADF6F90F1CA8F92547A777E3D5FE943671495512FA18CEA7CBA296 |
| jim-v2 TIP-FREEZE.json (immutable baseline) | 1D88A97FCD60BF65B95414044CEA3D90FCD110848C05B67E54DAC0BDA8C575F4 |
| jim-v2 Implementation-Scope-Proposal.md | F89B990CA1EA4FB89DD58756136F8972EF9AFAE00AE6150C9FD54EF936C9784B |
| jim-v2 Case-Registry.md | BBFEF33312A4E532BCC0FD49BACAA40641C26F955F5862FD3192641621F15F05 |

## Assembly

- Base: `scheduler-framing-ack-fake-v4/packet/candidate`
- Sole override: `scheduler-port-zero-fake-v1/.../covering_transport_policy.py` = 5F48FD7ED50C57A6A47ADA20138678BB3C112A2A69D1C234A47580E6CD068B88
- 234 files; every selected source re-hashed before copy; destination re-hashed
- Manifest: `docs/Assembly-Selected-Source-Manifest.json`
- Diff: `docs/Assembly-Selected-Source-Diff.json`
- Not new application editing. Port unverified; copy ≠ run authority.

## Qualifications carried

- 27 native STOP + 4 CF witnesses; 76 planning IDs mapped; no silent omission
- NP-T05-ORDERLY-CLOSE dual named observations (complete accept + short-CL refuse) after orderly close_notify; abrupt distinct
- T02 overrun + T08 nested/reset gaps explicit; focused fake witnesses named
- T07 observations named individually
- Fresh planning / 600s validity / clocks 210/240/30
- Unchanged-isolation :443 first; host Docker only; no new privileges
- Retirement: owned peer/PKI/reader may be implemented; invocation/fault authority later; failed-container separately gated; unjoined → UNKNOWN

## Flags

executed=false; launch_authorized=false; implementation beyond prep=false; prep_is_not_pass=true; endpoint=unbound; no Slack tip.
