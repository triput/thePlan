# Preparation review — scheduler-native-provider-prep-v3

Jim (Justin), 2026-11-12. PREPARATION ONLY. First vertical increment.

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

## Dex review inputs (hash-verified)

| Input | SHA256 |
| --- | --- |
| Dex-Implementation-and-Checker-Review.md | 0AFFC524A99B0D47F21F1942FB4EF89C5D4E02D289BA8EB0442F3EC59E15F666 |
| Host-Wiring-Supplement.md | 4B76E00E760E3BFAF2D925DE5CD916A922040BF639F1E03F327922166E02D1EB |
| Provider-Trust-and-Wrong-Name-Supplement.md | 1F58FA4A2FA569769965C52F493166B382F517F1575411A1BD09611C8B0859F8 |
| T02-Focused-Crossing-Control-Design.json | 88352EEA19FEC2524A73EED615E2425DA74DFFE6ED55F22A2F10B7E841C554A0 |
| First-Vertical-Production-Contract-Reference.md | C340C47B3D9CDB92D0DBA91506E4916F85233571B90015BBEDABF9CF3820C054 |
| Runner-Host-Report-Contract-Supplement.md | 19A695FC5E02B28CD4943FD6794C1D3487CC3F449395CC92C0A288E2415E5727 |
| Native-Deadline-TLS-Observation-Review.md | 1A485EB29FD095933F0BA45A13B288A149E44FBFCEAFB26029C59C5D5F761069 |
| Incremental-Handback-Order.md | (3AF57EEE… — first vertical priority) |

## Disposition of R1–R4 + supplements

| Finding | Disposition in prep-v3 |
| --- | --- |
| **R1** real peer/TLS/worker + real native case bodies | **ADDRESSED for first vertical.** Peer has bind/accept/handshake/request/response/close_notify/abrupt/stalls + multi Connection:close inventory + retire_owned. NP-V-MS-NONEXPIRED authored; other 26 cases explicit HOLD (not PASS). |
| **R2** checker must NOT echo EXPECTED | **ADDRESSED.** Fake-dependent/extracted controls: suite AST inventory, peer/runner shape, T08 nest/reset+mutation, T02 focused crossing+mutation, T07 names+prior pins, report sink, vertical contract shape. Prior framing/port evidence reused at recorded scope. |
| **R3** launcher unbounded capture | **ADDRESSED (carried from v2).** launch_check uses bounded readers during collection + owned-child/reader retirement + exclusive result gate + lineage to port-fake. |
| **R4** freeze concrete reviewed inputs | **ADDRESSED as pins.** `docs/R4-Reviewed-Input-Pins.json` records exact file hashes + held command citing VERIFICATION-ADMISSION hash. `launch_authorized=false` / `launch_ready=false` remain. No hash-whatever-is-present. |
| **Host-Wiring** DockerOps N06/N07 + wrapper | **ADDRESSED (carried/confirmed).** ProviderDockerOps overrides attach; Invoke-Native-Provider passes --config/--receipt/--docker-config; ExpectedConfigSHA256 is external operator pin (not self_sha256). |
| **Provider-Trust / wrong-name** | **ADDRESSED.** Provider CA under `/tmp/np-provider-tls` (DB `/public-ca` separate). Wrong-name keeps vendor hostname/SNI; `serve_wrong_name_leaf=True` selects wrong-name leaf. Recipe caller contract documents guarded dir + bounded child. |
| **T02 focused crossing** | **ADDRESSED in checker.** Injected 9999+batch2 / 16777215+body2 / reader left+1; mutants fail; scope disclosed. |
| **First vertical contract C340C47B** | **ADDRESSED in runner/auth.** `app.config.Settings` via `fixture_settings`; POST `/api/v1/calendar/covering-refresh` with subscription_ids/window; `i01_asgi_app` + `assessment_binding` immutable lineage; no FixtureByteTransport alias in JoinedTLS claim; measured before/after DB; exact coverage_action/scheduling_readiness booleans; TOKEN ROLLBACK from native terminal wrapper; MS identity vs event routes; finite Connection:close inventory. |
| **Report contract 19A695FC** | **ADDRESSED.** Restore stdout after BoundedOutput capture; flat suite_report_receipt; case_results included; token_rollback_ack allowlisted; truthful executed flags on admitted run path; fake producer/consumer sink control in checker. |

## First vertical confirmation

NP-V-MS-NONEXPIRED uses **Settings + covering-refresh + ASGI** pattern (not private worker dictionary / not `app.core.config.get_settings`).

## Flags

`executed=false`; `launch_authorized=false`; `launch_ready=false`; `prep_is_not_pass=true`; `first_vertical_increment=true`; endpoint unbound; no Slack tip.
