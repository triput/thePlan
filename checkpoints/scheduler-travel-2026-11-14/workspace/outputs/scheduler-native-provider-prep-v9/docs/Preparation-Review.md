# Preparation review — scheduler-native-provider-prep-v9

Jim (Justin), 2026-11-12. PREPARATION ONLY. Fresh successor from tipped prep-v8 (immutable).

## Authority (unchanged)

| Document | SHA256 |
| --- | --- |
| Reconciled-Authoring-Scope-For-Approval.md | 389A00DD444C610A93877362A574A1C93543F916F119D2D2FF71BA167FBF7E2D |
| Trish-Preparation-Approval.json | 5D1EA2F973FE110D35B65E4172821F014E74A8F2A65BCBB4AB8EE22458F80CA4 |

## Immutable tipped predecessors

| Packet | TIP on-disk SHA256 |
| --- | --- |
| Frozen tipped prep-v7 | B99657509593AB385BA67D9F2AB0287D89E0D37F07B42EA87668300B07CBA149 |
| Frozen tipped prep-v8 | AF3EAA400FC16D0335DB329B8A5B286FE0900791B6B851F5997E4E19D15E168C |

## Dex v7 review D3B6FAD3… disposition

| # | Item | Disposition | Evidence |
| --- | --- | --- | --- |
| R1 | Admission pins for five checker-read fixtures + finite np_*.py inventory | FIXED | VERIFICATION packet pins + REVIEWED_NP_FIXTURE_PY_PINS |
| R2 | Late-drain controls must exercise actual candidate gate | FIXED | AST-extracted post-join overflow/primary-refusal; gate-deletion mutation |

## Dex Fake-Launcher-Retirement-Supplement 30FEEDFF… disposition

| Item | Disposition | Evidence |
| --- | --- | --- |
| Partial reader-setup retirement / EOF+no-error / exclusive failure receipt / one-attempt / 135s limits | FIXED | OwnedCheckSession retire_once; separate_outer_timeout=false |

## Dex launcher receipt-patch D8D77976… / candidate D22C37… disposition

| Item | Disposition | Evidence |
| --- | --- | --- |
| Failure receipt refuses RECEIPT only (not RESULT) | FIXED | `_write_failure_receipt` gates on RECEIPT.is_file() only; main preflight still refuses either |
| Zero observed stdout/stderr required before PASS | FIXED | `unexpected check stdout or stderr` after clean EOF |

## Intentional HOLD

- Other 26 native cases + 4 CF witnesses: HOLD_EXPLICIT_NOT_PASS
- Provider PKI generation/invocation held; fake/native launch unauthorized
- Partial runtime inventory: interpreter only

## Flags

executed=false; launch_authorized=false; launch_ready=false; prep_is_not_pass=true; endpoint unbound; no invoke.
