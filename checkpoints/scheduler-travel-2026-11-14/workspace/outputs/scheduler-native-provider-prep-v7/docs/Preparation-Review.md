# Preparation review — scheduler-native-provider-prep-v7

Jim (Justin), 2026-11-12. PREPARATION ONLY. First-vertical successor from tipped prep-v6.

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

## Dex formal v5 review 25899558… disposition

| # | Item | Disposition | Evidence |
| --- | --- | --- | --- |
| F1 | AST byte-alias inventory + 4 controls | FIXED | `_assert_no_byte_transport_references` + `byte_alias_reference_control_ids`; docs OK; import/ctor/install refuse |
| F2 | Actual read-footprint/assembly/outer pins under ACYCLIC root | FIXED | 234-file manifest byte verify; wrapper VERIFICATION pins OUTER+manifest; OUTER does not back-pin VERIFICATION |
| F3 | Label shape vs behavioral honestly | FIXED | `control_kind` / `native_behavioral_proof=false` / `fake_may_advance_before_native_pki=true` |
| N1 | Budget via counter.remaining.__self__/work_remaining | FIXED | Retained from prep-v6 runner observation |
| N2 | Primary on LOWER str-sorted ID | FIXED | Retained Alias-Subset-Safe-Seed auth seed |
| N3 | Actual PKI caller authored (invoke held) | FIXED | `invoke_bounded_provider_pki_recipe` + generate-once call site authored; invoke held under prep |
| N4 | Retirement flag BEFORE call (one-attempt) | FIXED | Retained `retirement_attempted` before `retire_owned` |

## Host-Entry supplement 6C8795B7… / host-glue-patch-v1

| Item | Disposition | Evidence |
| --- | --- | --- |
| host-glue | FIXED | `ReceiptRelay` + `admit_host_helper_import` + one-time `bind_record`; immutable `docker_transport` unchanged `7F7EA820…`; seam controls in checker |

## Checker-reference-patch-v2 686D06C5… / 30883786…

| Item | Disposition | Evidence |
| --- | --- | --- |
| checker-v2 | FIXED | AST guard + 4 controls adapted into named checker; report fakes `admit_isolated_import_bootstrap` / `prepare_provider_pki_private_dir` / generate-once; pins regenerated |

## Dex v6 new-source findings A8096174…

| Item | Disposition | Evidence |
| --- | --- | --- |
| PKI call site connected before peer | FIXED | `admit_provider_pki_generated_once` called from `main` after launch_ready gate; requires `GENERATED` before suite/peer; prep does not invoke |
| Late overflow after reader join | FIXED | Final overflow gate after joins/EOF before GENERATED; preserves primary; fake `PKI-LATE-DRAIN-OVERFLOW` controls |

## Authority / fold hashes (verified)

| Document | SHA256 |
| --- | --- |
| Dex-Review-and-Revision.md (formal v5) | 258995585A0011B22ED2C13805F0F1E00063764659FDF0F92DA6344473F724F0 |
| Host-Entry-and-Receipt-Binding-Supplement.md | 6C8795B7C35D2A15A4D34509C6E27F8A964DD61BE52F7DC6DC8E424943436628 |
| checker-v2 candidate check_native_provider.py | 686D06C5A6C9DE16E2EEC8578FF1C9DA8CD8AFF0A03435F6C6BA11C835FC8E07 |
| checker-v2 Proposed-Reference-Guard-and-Report-Fakes.diff | 308837867E2B0CE68CCE52284AAB7D770673ADCF49ADC96034CFF4190E3D00CD |
| host-glue candidate np_supervisor.py | 52205ED13872838FA0D1D67AA798F937949305850100822903697B7CC4D7F386 |
| host-glue Proposed-Host-Import-and-Receipt-Relay.diff | 616C396E94BDFE6E34964C03487E62ED2386B422C5FD11127103BEA3F0855C72 |
| Dex-New-Source-Findings.md (v6) | A80961743D8CC5AC272E00EE0DC5B28FE0A7E92F05C3B3B1FF41C917ADF5D763 |

## Confirmations

- primary alias on LOWER str-sorted subscription ID (carry-forward)
- budget proof via transport.counter.remaining (carry-forward)
- PKI generate-once call site authored; generate/invoke held under prep
- late-overflow gate after reader join authored; fake late-drain controls present
- AST byte-alias docs-safe; assembly 234-byte pins; acyclic OUTER via wrapper root
- production guard / membership / role / enabled / zero OAuth / mapped measurements / final assessment retained

## Intentional HOLD

- Other 26 native cases + 4 CF witnesses: HOLD_EXPLICIT_NOT_PASS
- Provider PKI generation/invocation: authored, not executed under prep
- Fake/native launch: `launch_authorized=false` / `launch_ready=false`
- Actual sanitizer/host failure-path native verification
- Numeric suite/runner bounds pending launch card

## Flags

`executed=false`; `launch_authorized=false`; `launch_ready=false`; `prep_is_not_pass=true`; first_vertical_increment=true; endpoint unbound; no Slack tip; no imports/compile/invoke performed.
