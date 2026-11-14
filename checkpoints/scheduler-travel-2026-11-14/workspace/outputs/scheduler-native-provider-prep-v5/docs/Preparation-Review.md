# Preparation review — scheduler-native-provider-prep-v5

Jim (Justin), 2026-11-12. PREPARATION ONLY. First-vertical successor from tipped prep-v4.

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

## Formal v3 REVISE D284CED5… disposition (blockers 1–8)

| # | Blocker | Disposition |
| --- | --- | --- |
| 1 | DB hostname/database/user | FIXED (retained from v4 profile fold): native-fixture.invalid / dex_fixture / dex_fixture |
| 2 | Isolated import bootstrap + i01_auth_seed | FIXED: admit_isolated_import_bootstrap; immutable i01_auth_seed F66B4FE3… copied |
| 3 | Disposable schema before seed | FIXED: provision_disposable_schema (Base.metadata.create_all + optional provision_native) |
| 4 | Bounded provider-PKI recipe caller | FIXED: prepare_provider_pki_private_dir + supervisor contract; generate=false; no gen |
| 5 | Checker AnnAssign + actual context witness | FIXED: AnnAssign retained; Context().run independent probe; mutant nest hole |
| 6 | Complete fake admission | FIXED: relative_path packet + absolute_path runtime interpreter membership |
| 7 | Generic exception must not skip sanitized report | FIXED (v4 report fold retained): streams restore; STOP class-only; case SuiteStop preserves class |
| 8 | One confirmed bounded retirement | FIXED: single retire_owned; no join_seconds=2.0 second attempt; UNKNOWN not swallowed |

## Supplements

| Supplement | SHA256 | Fixes |
| --- | --- | --- |
| Ingress-Budget-and-Measurement-Supplement.md | 77FD6A4F… | Install CoveringReleasePlan; observe CoveringHTTP on worker/POST; real monotonic; on_context; same budget; mapped coverage_* fields |
| Transcript-and-Identity-Source-Review.md | 9F9AACE9… | Identity steps delimiters; plant primary alias; wire order from mapping; exact path+query; candidate syntax control |
| Draft-V4-Admission-Schema-Review.md | 5639F5D5… | VERIFICATION-ADMISSION relative_path/absolute_path; truthful case executed metadata |

## Dex CODE folds (adapted)

| Contribution | Hash | Disposition |
| --- | --- | --- |
| Profile diff | 65138AC7… | Retained from v4 |
| Report boundary / candidate | AA2494B2… / B910EC04… | Retained adapted |
| Context-check diff / candidate | 08851E2D… / 2A2D5729… | Adapted Context().run + AnnAssign |
| Coverage measurement / seed / checker | A5FC6601… / 9EEF50BC… / 2FF4B8A0… | Mapped fields + folded controls |
| Peer-path candidate / diff | CFC6AF29… / F89FAC39… | Exact path+query + observed path; retirement preserved |

## Flags

`executed=false`; `launch_authorized=false`; `launch_ready=false`; `prep_is_not_pass=true`; first_vertical_increment=true; endpoint unbound; no Slack tip.
