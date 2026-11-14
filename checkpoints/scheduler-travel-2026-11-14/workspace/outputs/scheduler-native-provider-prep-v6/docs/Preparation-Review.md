# Preparation review — scheduler-native-provider-prep-v6

Jim (Justin), 2026-11-12. PREPARATION ONLY. First-vertical successor from tipped prep-v5.

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

## Formal v4 REVISE CC37D4AD… disposition

| # | Item | Disposition |
| --- | --- | --- |
| 1 | Bootstrap + immutable helper | FIXED (retained/strengthened): admit_isolated_import_bootstrap; i01_auth_seed present |
| 2 | Schema + PKI caller | FIXED: provision_disposable_schema; invoke_bounded_provider_pki_recipe authored (dir/child/group/readers); INVOKING held |
| 3 | Worker + shared ingress budget | FIXED: CoveringReleasePlan.for_request; observe counter.remaining.__self__/__func__ (not invented .budget) |
| 4 | Mapped coverage_* state | FIXED (retained): coverage_* fields + external_calendar_id/role/enabled in measure |
| 5 | Transcript + primary-alias stimulus + target order | FIXED: Alias-Subset-Safe-Seed — primary on LOWER str-sorted ID; cal-np-other on higher; inverted request; identity default+list then calendarViews |
| 6 | Exact peer paths/observations | FIXED (retained): exact path+query; observed_path; newer retirement preserved |
| 7 | Consumable admission/runtime schema | FIXED (retained/strengthened): relative_path packet + absolute_path runtime interpreter membership |
| 8 | One-attempt retirement | FIXED: retirement_attempted guard; sole failure-path when no attempt; no swallow UNKNOWN |

## Authority supplements (hash-verified)

| Document | SHA256 |
| --- | --- |
| Dex-Review-and-Revision.md | CC37D4ADBA657FB3F13EDFA1F4A99A8A48D196368025A564DDE723FD78BCAB14 |
| Alias-Subset-Safe-Seed-Reference.md | 7AA3407D01A9C7DA4006BA721E305CD97D90E6CE8DC2060B5F1812C79DD1AE07 |
| Provisional-V5-Implementation-Observations.md | 1CB895E089B07FFB0B3D35D75DF4042803EC8B3E0DB02285ADFEE401B834F3DF |

## Confirmations

- primary alias on LOWER str-sorted subscription ID
- budget proof via transport.counter.remaining (not .budget)
- PKI caller authored; generate/invoke held
- production guard / membership / role / enabled / zero OAuth / mapped measurements / final assessment retained

## Flags

`executed=false`; `launch_authorized=false`; `launch_ready=false`; `prep_is_not_pass=true`; first_vertical_increment=true; endpoint unbound; no Slack tip.
