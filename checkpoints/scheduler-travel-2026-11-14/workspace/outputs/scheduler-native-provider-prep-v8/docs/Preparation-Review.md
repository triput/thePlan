# Preparation review — scheduler-native-provider-prep-v8

Jim (Justin), 2026-11-12. PREPARATION ONLY. First-vertical successor from tipped prep-v7.

## Authority (unchanged)

| Document | SHA256 |
| --- | --- |
| Reconciled-Authoring-Scope-For-Approval.md | 389A00DD444C610A93877362A574A1C93543F916F119D2D2FF71BA167FBF7E2D |
| Trish-Preparation-Approval.json | 5D1EA2F973FE110D35B65E4172821F014E74A8F2A65BCBB4AB8EE22458F80CA4 |

## Immutable tipped predecessors

| Packet | TIP on-disk SHA256 |
| --- | --- |
| Frozen tipped prep-v1 | 0AA4C08197E897F8A91A23945D882854FED44528E476AF04506D245B2EDB211D |
| Frozen tipped prep-v2 | 9C49E0B84B36F7B53FADC79490FCEF3AB2CE093FA6F6B6A8E16F40243BEDD38D |
| Frozen tipped prep-v3 | 06C46CB3547C70247021885D463D9F642FE580534577919B964A56F745DC11A4 |
| Frozen tipped prep-v4 | FC27FF88427A3EC0705547D2ACBF1A183F230F6B2AAA75A3582993D83C31A896 |
| Frozen tipped prep-v5 | 49F16773BE3730B55F161EC65E422098BEE60F3752A93B917B5F8301D84B2EA1 |
| Frozen tipped prep-v6 | 205CAE8DEA237EDDCA2AF7AD63F61FCF03B2DF666BBBDD969B5D7D19A7E3A647 |
| Frozen tipped prep-v7 | B99657509593AB385BA67D9F2AB0287D89E0D37F07B42EA87668300B07CBA149 |

## Dex v7 review D3B6FAD3… disposition

| # | Item | Disposition | Evidence |
| --- | --- | --- | --- |
| R1 | Admission pins for five checker-read fixtures + finite np_*.py inventory | FIXED | VERIFICATION packet pins bootstrap/prepare-tls/np_alias_seed/np_integrated_runner/np_provider_routes; `REVIEWED_NP_FIXTURE_PY_PINS` refuses glob drift |
| R2 | Late-drain controls must exercise actual candidate gate | FIXED | AST-extracted post-join overflow/primary-refusal from `invoke_bounded_provider_pki_recipe`; gate-deletion mutation must admit GENERATED |

## Dex Fake-Launcher-Retirement-Supplement 30FEEDFF… disposition

| Item | Disposition | Evidence |
| --- | --- | --- |
| Partial reader-setup retirement after Popen | FIXED | `OwnedCheckSession` wraps construction/start; setup errors call `retire_once` |
| Success requires clean EOF + no reader_error | FIXED | refuses reader_error / incomplete saw_eof before result admission |
| Exclusive failure/disposition receipt | FIXED | `_write_failure_receipt` O_EXCL; no overwrite of prior evidence |
| One-attempt kill/wait/join bookkeeping | FIXED | `retirement_attempted` gate; unresolved → UNKNOWN; primary preserved |
| Truthful limits freeze | FIXED | 120s collection + 5s kill/wait + two 5s joins = 135s; `separate_outer_timeout=false` |

## Accepted carry-forward (no regress)

PKI call site + post-join overflow authored; AST byte-alias; host relay/import; 234-file assembly + acyclic OUTER; N1–N4 / F1–F3 / host-glue / checker-v2.

## Intentional HOLD

- Other 26 native cases + 4 CF witnesses: HOLD_EXPLICIT_NOT_PASS
- Provider PKI generation/invocation: authored, not executed under prep
- Fake/native launch: `launch_authorized=false` / `launch_ready=false`
- Actual sanitizer/host failure-path native verification
- Numeric suite/runner bounds pending launch card
- Partial runtime inventory: interpreter only

## Flags

`executed=false`; `launch_authorized=false`; `launch_ready=false`; `prep_is_not_pass=true`; first_vertical_increment=true; endpoint unbound; no Slack tip; no imports/compile/invoke performed.

Key role SHA256:
- check_native_provider.py 48E60C427BAF14170F869056BB1983E785AA397BC8621A3382EE14C5C7F51664
- launch_check.py F096D9C24664FDA31514769303160DACFE770E214100857C35542B99DE988FEB
