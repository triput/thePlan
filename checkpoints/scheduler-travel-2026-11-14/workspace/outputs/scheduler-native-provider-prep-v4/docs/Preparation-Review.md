# Preparation review — scheduler-native-provider-prep-v4

Jim (Justin), 2026-11-12. PREPARATION ONLY. First vertical increment successor.

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

## Dex CODE contributions folded (adapted, not blind overwrite)

| Contribution | Declared hash | Disposition |
| --- | --- | --- |
| Report-boundary Review-and-Limits.md | (Dex note) | Adapted into `np_runner_entry.main` / `__main__` |
| Report candidate entry | B910EC04… | Reconciled onto v3→v4 runner (not byte-copied over newer vertical) |
| Report diff | AA2494B2… | Streams restore in finally; machine channel byte-bounded; STOP class-only; executed=true observed; launch_authorized popped |
| Checker contribution | C996C5F2… | 15 controls folded into named checker REPORT-PRODUCER-CONSUMER-SINK; pins reconciled to final v4 runner/host |
| Profile diff | 65138AC7… | Three literals → native-fixture.invalid / dex_fixture / dex_fixture; CA/passfile/client isolation unchanged |
| Profile candidate | 74405B57… | Literals only adapted |

## Prep-v2 formal REVISE `42648CA5…` leftovers addressed in v4

| Blocker | v4 disposition |
| --- | --- |
| ASGI/auth/persisted seed/typed response (C340C47B) | Strengthened: exact coverage_action/scheduling_readiness objects; reject private-worker keys; persisted before/after; trailing-slash event route prefix |
| Machine-output/schema/per-case evidence | Dex report boundary adapted; flat top-level + case_results; console hash-only |
| Bounded peer interruption + exact inventory/trust | retire_owned closes sockets before join; exact request-path match; provider CA under /tmp/np-provider-tls |
| Checker AnnAssign + T08 extract + Dex fold | AnnAssign inventory; AST-extract covering_provider_transport; 15 boundary controls |
| Concrete fake pins/commands | OUTER/VERIFICATION filled with actual hashes; launch_authorized=false; held command cites VERIFICATION hash |
| TIP identity LF/preimage | Fresh atomic LF-only freeze; tip_sha256 preimage on exact bytes; no CRLF→LF reinterpretation |

## First vertical confirmation

NP-V-MS-NONEXPIRED uses **Settings + covering-refresh + ASGI** pattern (not private worker dictionary / not `app.core.config.get_settings`).

## Flags

`executed=false`; `launch_authorized=false`; `launch_ready=false`; `prep_is_not_pass=true`; `first_vertical_increment=true`; endpoint unbound; no Slack tip.
