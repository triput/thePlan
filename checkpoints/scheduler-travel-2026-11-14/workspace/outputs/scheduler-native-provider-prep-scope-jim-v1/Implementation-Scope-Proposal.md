# Native synthetic-provider packet — implementation-scope proposal (documents only)

Jim → Dex, 2026-11-11. Coding-perspective scope freeze for the next native synthetic HTTPS provider packet. **Proposal only.**

| Flag | Value |
| --- | --- |
| `executed` | `false` |
| `launch_authorized` | `false` |
| `implementation_authorized` | `false` |
| `prep_is_not_pass` | `true` |
| endpoint | unbound |
| Slack tip from this seat | none |

Assignment pin: `Jim-Native-Provider-Preparation-Scope-Assignment.md` SHA256 `6800E75B876D549CD1468B8E6B93D2F04EF36C986AC650D45C5A0EDB7F728113` (verified match).

Framing-fake-v4 and port one-shot cards remain with Trish — **unexecuted**. Do not treat those packets as PASS. This proposal does not authorize merge, source edits, fixture authoring, PKI, sockets, Docker, providers/credentials, installation/build, or endpoint binding.

---

## 0. Hash-pinned inputs

| Artifact | SHA256 |
| --- | --- |
| Scheduler-Consolidated-Plan-Current.md | `1B9FD4FE207844BFBF13C1BA22AE1167175BF2D1098C566217520E5FFAD6294E` |
| Next-Native-Provider-Slice-Seams-and-Gaps.md | `9EA98B204C42F827914192697C0E421AAAF6E1E87DA9164B4077E7ABE1BDAE74` |
| Native-OAuth-Owning-Terminal-Evidence-Seams.md | `C331BDACD0FF1435673CD9B393752A7A3AE41A75229B1422BFE1EC7F9CC609CA` |
| Native-OAuth-Owning-Terminal-Source-Pins.json | `2CBBD0B6CB50CABE680732FF3E6F88C7AC5FFDDB2B9FBF2D0D08DD9EB9634AE8` |
| Transport-Deadline-Suite-Budget-Review.md | `2DC649FAC1CA87E5F04AFFFE65DF74F178B7524E2C0A9616920B2A79818696D4` |
| Transport-Completion-Audit-Current.json | `57D56C6E581893401FA3EB10848FDEE360FBBFFAD630CD4EE46E73D89F43D086` |
| Transport-Property-Evidence-Reuse-Overlay.json | `D27CA2442CEDAF6EB045C50BE6F2A9C205EA00A8EC6DB595832F583910CCA57A` |
| T01-Route-Property-Evidence-Reuse.json | `5CD74FD03464C016466B525C14CE3AC92E8B58A460602F406D94E5106275C5A3` |
| Retirement-Statement-Lineage-Reuse.json | `EF213E03F7D37705C8954BFA2F7912E73303B08C2B6E80D30C736F3CDA580FE3` |
| Scheduler-Private-Beta-Finish-Line-Working.md | `80FE8308B4D06B0D8F2D50067DBCDFB1336077E917510929946B33075A2D75EC` |
| Header-Compatibility-Decision-For-Review.md | `AEAE53432BDCCA6BB805E7EC5B4A2F7AA37370B2C358F5E7D8738A165F81A1D0` |
| Trish-Header-Policy-Approval.json | `1C932F1A569AD55DF9B86C8994946B052B5BCDDB21676B848EC7ACBF98464059` |

### 0.1 Eight OAuth owning-terminal source pins (retained)

| Path (under Codex outputs) | SHA256 |
| --- | --- |
| scheduler-route-fake-v1/.../google_calendar.py | `8A33597198FEFBC8D5E6671D56FE4118091F89255A6F46A8589117127318231F` |
| scheduler-route-fake-v1/.../microsoft_calendar.py | `6A52B10FE43A7781718BAE0AC69DA91CA7FB3B48B9534EB18D5C9C80E75DD6EF` |
| scheduler-route-fake-v1/.../covering_refresh_import.py | `84F50367BC91E0368437B4CD6E6FA5FAC9A77E42A270F00E8FF1EC62BB25C339` |
| scheduler-route-fake-v1/.../covering_domain_adapters.py | `BA82577E8CF4B27D4EDD5A1B9D31B35E87990A381B83E22D4DB2A4D89352A53C` |
| scheduler-route-fake-v1/.../covering_domain_dispatch.py | `E73EFF6812A191F3F03431B98990BBF3C61D09D8398101AC804DBD2B2E7F6566` |
| scheduler-route-fake-v1/.../covering_native_orm_factory.py | `C37B6DBB005DEF83033312594EE92F8BF180A70F470B4FD2BCCA78F3EFFE7229` |
| scheduler-route-fake-v1/.../covering_role_connector.py | `C5BA15CDE276586CFFA2DE24A51E79F40CC6479D3A5A1D6663D23A20D930B288` |
| scheduler-native-i01-i02-v4/.../i01_auth_seed.py | `F66B4FE3D13F47122754835D3AF45EE6770D45B4D7250D35B013F026C4CC4371` |

### 0.2 Exact current source bases cited by seams / policy

| Role | Path | SHA256 |
| --- | --- | --- |
| Release plan (JoinedTLS default) | route-fake candidate `covering_release_plan.py` | `0265969CD230D42747CDB722D73FF2C8748144324B5B930E5EB940E97DC2B826` |
| Alias canonicalize | route-fake candidate `calendar_alias_canonicalize.py` | `A661FE9287E0BE086CCB070DF8F227D2449CA9B70303140A7E38B4015A71946F` |
| Microsoft calendar | route-fake candidate `microsoft_calendar.py` | `6A52B10FE43A7781718BAE0AC69DA91CA7FB3B48B9534EB18D5C9C80E75DD6EF` |
| JoinedTLS (route / T07 baseline) | route-fake candidate `covering_joined_https.py` | `2E6A4ABB0E9658747C07A06F17D4359987C926DDD3CFDC0FE098984922A6A29B` |
| JoinedTLS (framing-v2/v4 prospective EOF option) | framing-ack-fake-v4 candidate `covering_joined_https.py` | `760177767EA64A6129E788BA7828FBE998522706791E6CFC5DBB9C2D0C013427` |
| Covering HTTP (framing candidate) | framing-ack-fake-v4 candidate `covering_http_transport.py` | `29CBD53C85E8D40185A5E7DF73DF85B752A34837D25FCD65DB6504AFB775B368` |
| Request budget (210/240/30) | route-fake / T07 / I01 `covering_request_budget.py` | `D5C465CC8BACB83C49FCD8586BB84D5B32C12C113CB81386C6D715EBF7088975` |
| I01 alias injector (byte-fake lineage; do not reuse for JoinedTLS proof) | I01 `i01_covering_http_alias.py` | `F90182C0BE5C3024B40782178120262F5D940794CF4C6A99BAE21DD655440EAD` |
| I01 suite | I01 `i01_i02_suite.py` | `B3986FB351493C85DD4BE53137D3A1C93978A4567C0E02692819CCEEC54ACFA8` |
| I01 PKI recipe pattern | I01 `prepare-c06-runner-tls.sh` | `F1868F913BFBA3841331B397242566938DAF7C2047CACDD5031611B62D60E6DA` |
| I01 supervisor | I01 `supervisor.py` | `A72721BD1E092863B89C77F1FE4C98243759AF9764F9CB8BB31B6402FEBC40DB` |
| I01 integrated runner | I01 `integrated_runner.py` | `E77B3D09AA1907527516118659032C2352807DAFB8F3FBE419A44915ABCAB35A` |
| I01 runner entry | I01 `runner_entry.py` | `2A4602CCDFA68787697ED4FD472B3BEA41FD9FC31F8F808C409339140C81FA3E` |

Final assembled application source for the native packet is **not** frozen here. It must be the post-reconcile merge of authorized routing + framing + TLS-EOF option + port correction, with exact hashes on the later preparation/launch cards. Prospective JoinedTLS EOF bytes `76017776…` remain candidate-only until framing/port results are reconciled and Trish authorizes assembly.

---

## 1. Prospective files, roles, lineage, case↔evidence table

### 1.1 Packet root (prospective)

`outputs/scheduler-native-provider-v1/` (name frozen at preparation; not created by this proposal).

### 1.2 Exact prospective fixture / recipe / case / runner / supervisor files

| Path under packet `payload/` | Executable role |
| --- | --- |
| `fixture/np_supervisor.py` | Suite supervisor: serial batch admission, STOP on fail/mismatch/timeout/unexpected UNKNOWN, success-only exact-ID cleanup authority, no automatic failure cleanup. Lineage pattern: I01 `supervisor.py` `A72721BD…`. |
| `fixture/np_integrated_runner.py` | Runner process: owns disposable DB+runner containers, mounts, capture caps, peer/PKI child lifecycle. Lineage: I01 `integrated_runner.py` `E77B3D09…`. |
| `fixture/np_runner_entry.py` | In-runner entry: imports suite, binds disposable settings, exits with typed receipt. Lineage: I01 `runner_entry.py` `2A4602CC…`. |
| `fixture/np_suite.py` | Finite case inventory + serial batch schedule (see §1.4 / §5). Not a 76-run Cartesian matrix. |
| `fixture/np_receipts.py` | Oracles: peer accept/handshake/request counts, terminal identities, assessment deltas, sanitized booleans/hashes. No token plaintext / secrets / raw provider bodies in public receipts. |
| `fixture/np_provider_peer.py` | Synthetic HTTPS peer: TLS accept, finite transcript, orderly `close_notify` vs abrupt truncation, failure-stage counters. Fixture-only; not production. |
| `fixture/np_provider_transcript.py` | Finite Host/path/method exchange script (OAuth + identity + event). Ordered; no unreviewed continuation. |
| `fixture/np_provider_routes.py` | Reviewed `HTTPSPeer` table: vendor hostname/port unchanged; numeric loopback dial; fixture CA path; purpose-distinct prefixes. |
| `fixture/np_auth_seed.py` | Disposable account seed: nonexpired vs explicitly expired tokens; synthetic Google and Microsoft OAuth settings/tenant. Does not read ambient client-secrets. |
| `fixture/np_alias_seed.py` | Seeds supported Microsoft `primary` alias situation so live identity evidence + canonicalization to reviewed explicit calendar ID are observable (not “three routes ⇒ three calls”). |
| `fixture/prepare-np-provider-tls.sh` | Fixture-only CA + leaf SANs for vendor hostnames under runner-owned trust namespace; private keys in container tmpfs only. Pattern: I01 `prepare-c06-runner-tls.sh` `F1868F91…` — **new SANs required** (`native-fixture.invalid` leaf cannot verify `graph.microsoft.com` / `login.microsoftonline.com`). |
| `fixture/prepare-np-db-tls.sh` | DB TLS bootstrap reuse of I01 postgres TLS pattern (separate trust from provider). |
| `launch-config.json` / `runner-config.json` | Exact commands, hashes, suite/runner/command/capture limits (frozen only on later launch card). |
| `workspace/apps/api/...` | Final assembled application tree (read-only mount). **Not authored in this proposal.** |

New native peer/PKI/case/supervisor roles are **outside** the current 3-file / 4-fake-role authoring lane and require Trish’s later source-preparation card (§6).

### 1.3 Existing base-image / runner / source lineage (reuse, not rewrite)

| Component | Reuse claim | Boundary |
| --- | --- | --- |
| I01/I02 v4 database image + bootstrap | Two-container disposable pattern, postgres TLS, exact-ID success cleanup | Passed containers already disposed; cannot reuse live IDs. New launch creates fresh containers. |
| I01/I02 v4 runner image + runtime pins | Python 3.12.16 / psycopg 3.2.13 / SQLAlchemy 2.0.51 pattern | Historical `runner_seconds=600` / `suite_seconds=900` are **not** authority for this suite (§5). |
| CoveringReleasePlan.for_request → CoveringHTTP → default JoinedTLS | **Real production transport construction** | Do **not** invent a new injection seam. Do **not** wrap release-plan alias with `FixtureByteTransport` for JoinedTLS claims. Preserve I01 byte-fake proof separately. |
| Native assessment / owner-lock / ingress / dispatch / connector | I01/I02 v4 evidence at recorded scope | Final assembled source must re-pin; changed transport files are not covered by old snapshot alone. |
| Route-fake owning MS/Google path classification | T01 property-matched reuse | Pre-transport / fake control-flow; not native TLS. |
| T02 admission counters | Property-matched reuse at T02 scope | Data-overrun gaps for items/bytes remain; native composition observes shared counters, does not re-prove every equality witness. |
| T05 host-fake characterization + framing candidate (when authorized) | Framing control flow | Byte fakes ≠ orderly/abrupt TLS. |
| T07 retirement statement region | Logical cleanup provenance reuse | Real owned socket/worker retirement still required natively for socket claims. |
| DB TLS N06/N07 / I01-C06 | PostgreSQL ack path | **Not** provider HTTPS teardown proof. |

### 1.4 Genuine necessary production / source seams (and what is **not** needed)

| Seam | Decision |
| --- | --- |
| JoinedTLS factory | **None new.** Release plan already supplies real JoinedTLS by default. Leave alias unwrapped. |
| Provider routes | Supply reviewed loopback `HTTPSPeer` entries only (fixture configuration), not a new production dialer. |
| Auth / OAuth settings | Fixture seed of synthetic client/secret/redirect/tenant; no ambient secrets file. |
| Alias → canonical calendar ID | Seed + observe via existing `calendar_alias_canonicalize` / `account_needs_live_identity_evidence` behavior. |
| Token terminal | Existing native TOKEN hook (COMMIT if changed / ROLLBACK otherwise). Observe; do not redesign. |
| TLS EOF option (`suppress_ragged_eofs=False`) | Prospective covering-only change already designed; lands only via authorized framing/final assembly — **not** this proposal. |
| Port-zero policy | Separate packet; not this proposal. |

### 1.5 Finite case ↔ requirement / evidence table

All **76** accepted planning IDs remain retained. This table maps each ID to **property-matched disposition** for the native provider packet. It is **not** 76 automatic new runs.

Legend: `REUSE` = prior verified component evidence at recorded scope; `NATIVE` = real JoinedTLS/socket/timing/terminal witness in this packet; `COMPOSE` = observe on vertical path without claiming full family closure; `HOLD` = waits on framing/port/final assembly reconcile before claiming; `GAP` = retained obligation still needing a focused witness (may be native or later fake).

#### T01 (18) — route / origin / path

| ID | Disposition | Evidence basis |
| --- | --- | --- |
| T01-ORIGIN-FOREIGN-HOST | REUSE+HOLD | Pre-send refusal; D2/route scope. Native not required for pure path spelling. |
| T01-ORIGIN-FOREIGN-PORT | HOLD | Port-zero packet prepared, unexecuted. Not native TLS. |
| T01-ORIGIN-USERINFO | REUSE | Pre-send / D2 scope. |
| T01-ORIGIN-FRAGMENT | REUSE | Pre-send / D2 scope. |
| T01-ORIGIN-CONTROL-CHAR | REUSE | Pre-send / D2 scope. |
| T01-PURPOSE-WRONG | REUSE | Route/D2. |
| T01-PURPOSE-AMBIGUOUS | REUSE | `ROUTE-EQUAL-PATH-CONFLICT` refuse-before-send. |
| T01-CONTINUATION-REDIRECT | REUSE+GAP | Foreign 3xx / no follow-up needs exchange-count witness; may be fake or native COMPOSE. |
| T01-CONTINUATION-GOOGLE-PAGE-TOKEN | REUSE | Route-fake owning pagination. |
| T01-CONTINUATION-MS-NEXTLINK | REUSE | Route-fake MS continuation. |
| T01-PATH-POSITIVE-EXACT | REUSE+COMPOSE | Route positives; vertical observes actual MS default→list→calendarView counts. |
| T01-PATH-POSITIVE-CHILD | REUSE | Event descendant vs identity descendant policy. |
| T01-PATH-PREFIX-BOUNDARY | REUSE | D2 scope. |
| T01-PATH-DOT-SEGMENT | REUSE | D2 scope. |
| T01-PATH-ENCODED-DOT | REUSE | D2 scope. |
| T01-PATH-ENCODED-SEP | REUSE | D2 scope. |
| T01-PATH-ENCODED-ID-GOOGLE | REUSE | D2/route. |
| T01-PATH-ENCODED-ID-MICROSOFT | REUSE+COMPOSE | Vertical uses encoded reviewed calendar ID on real JoinedTLS. |

#### T02 (12) — cumulative limits

| ID | Disposition | Evidence basis |
| --- | --- | --- |
| T02-*-BOUNDARY / OVERFLOW (pages) | REUSE | T02 fake admission. |
| T02-ITEMS-OVERFLOW | GAP | Overlay: direct data-overrun not established by N−1 + new admission alone. |
| T02-BYTES-OVERFLOW | GAP | Same. |
| T02-EQUALITY-WITNESS-* | REUSE | Counter equality at T02 scope. |
| Shared-counter composition on native vertical | COMPOSE | Observe counters on NP-V* success path; do not re-run all 12. |

#### T03 (5) — verify-full TLS / connect — **all NATIVE**

| ID | Native case | Obligation |
| --- | --- | --- |
| T03-VALID | NP-T03-VALID | verify-full CA+hostname success on vendor SAN leaf via JoinedTLS. |
| T03-WRONG-CA | NP-T03-WRONG-CA | Distinct wrong trust material; refuse before useful application data. |
| T03-WRONG-NAME | NP-T03-WRONG-NAME | Mismatched SAN; refuse. |
| T03-HANDSHAKE-STALL | NP-T03-HANDSHAKE-STALL | Real elapsed stall to production work/request expiry; first guard = deadline. |
| T03-TCP-REFUSAL | NP-T03-TCP-REFUSAL | Numeric dial to closed port; typed connect failure; no fake empty receive. |

#### T04 (5) — timing / partial / disconnect — **all NATIVE**

| ID | Native case | Obligation |
| --- | --- | --- |
| T04-HEADER-STALL | NP-T04-HEADER-STALL | Full production budget; first guard = header-phase deadline. |
| T04-BODY-STALL | NP-T04-BODY-STALL | Full production budget; first guard = body-phase deadline. |
| T04-PARTIAL-SEND | NP-T04-PARTIAL-SEND | Partial send observed; joined retirement; no retry. |
| T04-DEADLINE | NP-T04-DEADLINE | Explicit deadline classification distinct from supervisor kill. |
| T04-DISCONNECT | NP-T04-DISCONNECT | Peer disconnect mid-exchange; UNKNOWN/sanitized path as required. |

#### T05 (13) — framing

| ID | Disposition | Evidence basis |
| --- | --- | --- |
| Valid complete CL / chunked / encoding / JSON classes | HOLD→REUSE | Framing-fake-v4 unexecuted; after PASS, reuse byte-fake control flow. |
| Incomplete / duplicate CL / TE+CL / malformed header | HOLD→REUSE | Same; policy `AEAE5343…` approved. |
| Orderly close-delimited vs abrupt truncation | **NATIVE** | NP-T05-ORDERLY-CLOSE + NP-T05-ABRUPT-TRUNCATION. Byte fakes cannot close this. Header policy requires native TLS distinction. |

#### T06 (10) — OAuth ack / owning refresh — **NATIVE owning paths**

| ID | Native case | Obligation |
| --- | --- | --- |
| T06-BEFORE-SEND | NP-T06-BEFORE-SEND | Pre-send refusal/stop; no token mutation claim. |
| T06-MALFORMED-ACK | NP-T06-MALFORMED-ACK | After-send UNKNOWN remap; no known failure from parser class alone. |
| T06-TRUNCATED-ACK | NP-T06-TRUNCATED-ACK | Truncated ack → UNKNOWN; local tokens retained as observed. |
| T06-INVALID-GRANT-GOOGLE | NP-V-GOOGLE-INVALID | Owning Google refresh; TokenRejected after unchanged-unit rollback. |
| T06-INVALID-GRANT-MICROSOFT | NP-V-MS-INVALID | Owning Microsoft refresh + synthetic MS config/tenant. |
| T06-OTHER-ERROR | NP-T06-OTHER | Non-invalid_grant OAuth error → UNKNOWN branch as sourced. |
| T06-SUCCESS-GOOGLE | NP-V-GOOGLE-REFRESH | Expired seed; real Google refresh; TOKEN COMMIT; persistence. |
| T06-SUCCESS-MICROSOFT | NP-V-MS-REFRESH | Expired seed; real MS refresh; TOKEN COMMIT; persistence. |
| T06-PARTIAL-SEND | NP-T06-PARTIAL | OAuth partial send; UNKNOWN; no replay. |
| T06-LOST-ACK | NP-T06-LOST | Lost ack after send; UNKNOWN; disposable DB state retained. |

Do **not** treat Google success as Microsoft proof (distinct callers/config/validation).

#### T07 (8) — retirement

| ID | Disposition | Evidence basis |
| --- | --- | --- |
| RESPONSE/TRANSPORT/BOTH close after success/failure (6) | REUSE+NATIVE | Fake provenance `C5431778…` / lineage reuse for logical cleanup; **plus** NP-T07-OWNED-SOCKET for real peer/reader retirement. |
| T07-BOTH-CLOSE-AFTER-PRIMARY-FAILURE | GAP→NATIVE | Overlay: missing explicit combined branch — include NP-T07-BOTH-AFTER-FAILURE. |
| T07-OPEN-CLOSE / T07-SETBLOCKING | REUSE+NATIVE | Fake control flow reusable; native confirms real socket open/close/blocking under JoinedTLS. |

#### T08 (5) — context / thread ownership

| ID | Disposition | Evidence basis |
| --- | --- | --- |
| T08-NESTED / T08-RESET | REUSE or focused unit | ContextVar nesting/reset; may remain non-TLS if property is pure context. |
| T08-FOREIGN-THREAD | NATIVE | NP-T08-FOREIGN-THREAD — real thread identity, not fake owner IDs. |
| T08-FOREIGN-CLOSE | NATIVE | NP-T08-FOREIGN-CLOSE. |
| T08-REUSE | NATIVE | NP-T08-REUSE — forbid cross-request socket reuse claims without real ownership proof. |

### 1.6 Finite native executable case count (proposed)

**24 native executable cases** (serial), not 76:

Vertical / OAuth / assessment (9): `NP-V-MS-NONEXPIRED`, `NP-V-MS-REFRESH`, `NP-V-MS-TOKEN-THEN-IMPORT-FAIL`, `NP-V-MS-INVALID`, `NP-V-GOOGLE-REFRESH`, `NP-V-GOOGLE-INVALID`, `NP-T06-BEFORE-SEND`, `NP-T06-TRUNCATED` (covers truncated+malformed family with one malformed sibling if oracle-distinct — see note), `NP-T06-LOST`.

TLS trust/connect (5): `NP-T03-VALID`, `WRONG-CA`, `WRONG-NAME`, `HANDSHAKE-STALL`, `TCP-REFUSAL`.

Timing (5): `NP-T04-HEADER-STALL`, `BODY-STALL`, `PARTIAL-SEND`, `DEADLINE`, `DISCONNECT`.

Framing TLS closure (2): `NP-T05-ORDERLY-CLOSE`, `NP-T05-ABRUPT-TRUNCATION`.

Retirement / thread (3): `NP-T07-OWNED-SOCKET`, `NP-T07-BOTH-AFTER-FAILURE`, `NP-T08-OWNERSHIP` (bundles FOREIGN-THREAD/CLOSE/REUSE observations under one owned peer lifecycle with distinct oracles — **or** split to 3 if Dex requires separate STOP units; recommendation: one batch with three named oracles, still three planning IDs).

**Note on T06-MALFORMED vs TRUNCATED:** retain both planning IDs; if oracles are distinct, keep two cases (`NP-T06-MALFORMED`, `NP-T06-TRUNCATED`) raising native count to **25**. Prefer 25 if receipt fields differ. Default freeze: **25 cases** (split malformed/truncated; split T08 into one ownership case with three oracle sections counted as one STOP unit only if Dex accepts; otherwise 27). **Jim recommendation: freeze 25** — malformed and truncated separate; T08 as one multi-oracle case `NP-T08-OWNERSHIP` covering three IDs without claiming Cartesian expansion.

Remaining planning IDs: REUSE/HOLD/GAP as tabled — **inventory preserved, not re-executed**.

---

## 2. Coherent native vertical demonstration

### 2.1 Composition (required)

One synthetic **Microsoft** target drives the primary vertical:

1. Production in-process HTTP ingress → dispatch → role connector (I01 pattern).
2. `CoveringReleasePlan.for_request` constructs CoveringHTTP with **default JoinedTLS** (alias **unwrapped**).
3. Reviewed `HTTPSPeer` routes: vendor URL host/port unchanged; dial `127.0.0.1:443`; `server_hostname` = vendor hostname; `ca_file` = fixture CA; CERT_REQUIRED / verify-full.
4. Synthetic provider TLS peer serves finite transcript (OAuth / me / default calendar / list / calendarView as seeded).
5. Native ORM token + event-import units with real TOKEN terminal acknowledgments.
6. Final persisted assessment inputs **change** as a consequence of observed coverage — not a preseeded success bit or seed revision alone.

Google appears as **separate owning refresh cases**, not as a second full vertical duplicate of every MS identity/event step.

### 2.2 Distinctions that must remain honest

| Claim | How proved | What must not be claimed |
| --- | --- | --- |
| Nonexpired seed | `NP-V-MS-NONEXPIRED`: `get_valid_access_token` returns prior token; **no** OAuth request; TOKEN **ROLLBACK** acknowledged; identity/event import + assessment measured separately | OAuth success |
| Google owning refresh | `NP-V-GOOGLE-REFRESH`: explicitly expired Google token + synthetic Google settings; real `refresh_access_token` through covering TLS; TOKEN **COMMIT** if changed | MS proof |
| Microsoft owning refresh | `NP-V-MS-REFRESH`: explicitly expired MS token + synthetic MS client/secret/redirect/**tenant**; `_validated_oauth_token_fields`; TOKEN COMMIT | Google proof; ambient secrets |
| Alias canonicalization | Seed `external_calendar_id="primary"` (enabled) so live identity evidence runs; observe canonicalization to reviewed explicit event calendar ID; retain owner/target authorization | “Configured 3 routes ⇒ 3 calls happened” |
| Route configuration | `np_provider_routes.py` purpose-distinct prefixes | Alias behavior |
| Token commit vs parent import rollback | `NP-V-MS-TOKEN-THEN-IMPORT-FAIL`: after TOKEN COMMIT, force known event-import failure; refreshed tokens **remain**; parent import rollback/result + assessment recorded separately | Global rollback of token unit |
| Provider ambiguity vs local tokens | Truncated/lost ack: UNKNOWN; disposable DB may retain old fields; absence of local writes ≠ provider non-rotation | Known reauth from unchanged locals |

### 2.3 Observables (receipt fields — conceptual)

Peer: accept count, handshake success/fail stage, request count by purpose, close mode (`close_notify` | `abrupt` | `stall` | `refuse`).

App: transport factory class name (`JoinedTLS…`, not `FixtureByteTransport`), terminal identity/command for TOKEN and IMPORT, assessment generation/window/pages/hash or boolean deltas, sanitized token-field change booleans.

---

## 3. Missing T01–T08 real transport/worker obligations and reuse

### 3.1 Preserve

- All **76** accepted IDs from `Transport-Completion-Audit-Current.json` `57D56C6E…`.
- Required variants called out in overlays (T02 items/bytes overrun gap; T07 combined both-close-after-failure; T05 orderly vs abrupt; T06 Google≠Microsoft; T08 real threads).
- Property-matched REUSE overlays `D27CA244…`, T01 `5CD74FD0…`, retirement `EF213E03…`.

### 3.2 Real obligations this native packet must actually witness

| Family | Real obligation | Forbidden substitute |
| --- | --- | --- |
| T03 | verify-full, wrong CA/name, handshake stall, TCP refusal on JoinedTLS | Host-fake / FixtureByteTransport |
| T04 | header/body stall, partial send, deadline, disconnect at **production** 210/240/30 | Shortened fake clock; supervisor kill relabeled as app deadline |
| T05 L4 | orderly `close_notify` vs abrupt truncation | Empty fake receive; DB TLS N06/N07 labels |
| T06 | owning Google/Microsoft refresh + native TOKEN terminals + UNKNOWN after-send rules | Low-level POST observation alone; nonexpired seed as refresh |
| T07 | owned peer/PKI/worker/reader retirement on real sockets | Fake close exception provenance alone for socket claims |
| T08 | foreign thread/close/reuse on real ownership | Fake owner IDs |

### 3.3 Avoid

- Redundant Cartesian provider × fault × framing matrix.
- 76 automatic new runs.
- Closing socket/TLS/timing/thread requirements with pure fake witnesses.
- Relabeling I01 byte-fake receipts as JoinedTLS.

### 3.4 Dependency on unexecuted packets

Framing-fake-v4 (73 controls) and port-zero (9 controls) are **with Trish, unexecuted**. Native packet may **compose** after their authorized results are reconciled into final assembled source. Until then: HOLD on framing byte-fake closure and port-origin closure; still design native L4 TLS cases now.

---

## 4. Topology, trust, close modes, failure-stage counters

### 4.1 Declared topology (candidate)

| Element | Value |
| --- | --- |
| URL origin/port | **Unchanged vendor** (`login.microsoftonline.com:443`, `graph.microsoft.com:443`, `oauth2.googleapis.com:443`, `www.googleapis.com:443` as required by case) |
| Dial | Numeric `127.0.0.1:443` inside isolated fixture network namespace |
| TLS | verify-full; `server_hostname` = vendor hostname; fixture CA; CERT_REQUIRED |
| DNS/public | Do not resolve/contact public addresses |
| Listener | One runner-owned loopback:443 TLS peer serving finite transcript |
| DB | Separate container/trust; provider private keys never in DB trust store |

This matches `Synthetic-Provider-Unchanged-Origin-Design.md` source implications (release plan + JoinedTLS numeric dial / hostname verify).

### 4.2 Fixture-only trust / SAN / private-key containment

- New fixture CA under runner-owned namespace (not `native-fixture.invalid` leaf reuse for vendor names).
- Leaf SANs: exact vendor hostnames used by routes under test.
- Private keys: container **tmpfs only**; never in public receipts or DropFolder.
- Wrong-CA / wrong-name cases use **distinct** deliberately incorrect material.
- Public CA/leaf may enter evidence hashes; private key bytes must not.

### 4.3 Orderly vs abrupt + failure-stage counters

| Mode | Peer behavior | Client obligation |
| --- | --- | --- |
| Orderly | Send complete response then TLS `close_notify` within peer lifecycle | No required reciprocal unwrap/second exchange |
| Abrupt | Truncate without `close_notify` | Classified distinctly; with EOF option, not ordinary empty read |
| Stall stages | Counter: `pre_accept` / `pre_handshake` / `post_handshake_pre_headers` / `headers` / `body` / `post_body` | Receipt records actual first guard |
| TCP refusal | No accept | Connect failure stage |

### 4.4 Nonroot :443 bind — **explicit decision gate**

**Fact:** nonroot container bind to :443 remains **unproved**. No root, capability, sysctl, published-port translation, or URL-rewrite fallback is authorized by this proposal.

| Alternative | Description | May claim full vendor-origin composition? |
| --- | --- | --- |
| **A (recommended)** | Disposable container created with an explicitly declared **namespace-local unprivileged-port** setting that permits nonroot :443 **inside that namespace only** | Yes, if bind succeeds and URLs stay unchanged |
| B | Narrow `CAP_NET_BIND_SERVICE` on disposable runner only, justified and reviewed | Yes, if bind succeeds — higher privilege cost |
| C | High-port peer + matching high-port peer.port in routes | **No** — useful TLS/transport proof but **cannot** be labeled unchanged full vendor-client composition |
| D | STOP at bind failure; no fallback | Honest non-PASS |

**Jim recommendation:** Prefer **A**. On bind failure: **STOP** (Alternative D behavior) — do not silently switch to C inside a packet labeled vendor-origin. If Trish rejects namespace port settings, bring Alternative C as a **separately labeled** high-port packet rather than rewriting URLs.

Launch setup must include an explicit bounded bind probe step that fails closed.

---

## 5. Serial batches, timing, limits, retirement, STOP policy

### 5.1 Production timing (where claimed)

From pinned `covering_request_budget.py` `D5C465CC…`:

- Work deadline: start + **210s**
- Request deadline: start + **240s**
- Cumulative cleanup allowance: **30s**

Supervisor timeout ≠ application expiry. Shortened fake clocks / fixed remaining callbacks / outer kill at shortened deadline **cannot** establish 210/240/30.

### 5.2 Full-duration stall arithmetic (source-derived)

Three independent full-expiry witnesses (handshake + header + body stalls) imply **≥ 720s** of configured request windows alone, before setup/teardown/retirement. Inherited I01 `runner_seconds=600` / `suite_seconds=900` are **insufficient** if those three run in one runner window.

### 5.3 Finite serial batches (proposed)

| Batch | Cases | Runner budget (computed floor) | Notes |
| --- | --- | --- | --- |
| B1 Vertical-OAuth | NP-V-* + T06 non-stall (≈11) | **900s** runner / **1200s** suite floor | Mostly short; includes refresh/import/assessment |
| B2 TLS trust | T03 VALID/WRONG-CA/WRONG-NAME/TCP-REFUSAL (4) | **600s** / **900s** | No full 240s stall |
| B3 Full stalls | T03-HANDSHAKE-STALL, T04-HEADER-STALL, T04-BODY-STALL | **900s** runner floor (**3×240s + 180s overhead**) / **1200s** suite | Must not share a 600s runner |
| B4 Timing remainder | T04-PARTIAL-SEND, DEADLINE, DISCONNECT | **900s** / **1200s** | DEADLINE may approach full window — isolate if measured near 240s |
| B5 Closure + retirement + thread | T05 orderly/abrupt, T07×2, T08 | **600s** / **900s** | Real close_notify; owned retirement |

**Suite command admission deadline** (outer): sum of batch suite floors + disclosed margin → proposed **5400s** suite wall for the full native provider suite across batches, **or** five separately authorized one-shot launches (preferred for STOP isolation).

**Jim recommendation:** Prefer **five separately authorized serial one-shot launches** (B1–B5), each with its own exact command/hash/bounds card. Avoid one mega-suite that forces a huge supervisor window and couples unrelated STOP domains.

### 5.4 Computed caps (per launch card; freeze later)

| Cap | Proposed default |
| --- | --- |
| `command_count_cap` | 64 (I01 lineage) unless batch needs less |
| `output_byte_cap` | 1 MiB public capture (I01 lineage) |
| Per-case app request | 240s max when claiming production deadline |
| Shared cleanup | 30s cumulative where claimed |
| Excluded from app-deadline proof | Host Docker I/O, image pull, unrelated OS scheduling latency, file hashing, CLI capture drain — **disclose; do not count as application expiry** |

### 5.5 Retirement and cleanup authority

| Resource | Owner | Success cleanup | Failure cleanup |
| --- | --- | --- | --- |
| Provider peer listener/workers | Runner | Exact-ID stop + join within cleanup allowance | **No automatic**; requires separate approval |
| Fixture PKI tmpfs keys | Runner | Unmount/destroy with container | Leave for forensic read-only if failed |
| DB container | Supervisor | Exact-ID success disposal (I01 pattern) | No automatic |
| Application readers/sockets | JoinedTLS / covering retirement | Independent response/transport close provenance | Observe; no repair/retry |

### 5.6 STOP policy

Failure / mismatch / timeout / unexpected UNKNOWN → **STOP** authorized suite. No retry, no repair, no automatic failure cleanup. New reviewed cases are not retries. Expected UNKNOWNs must be named on the launch card.

Existing passing cleanup / owner-lock / assessment evidence remains reusable **at its recorded scope** (I01/I02 v4).

---

## 6. Trish source-preparation card wording + unresolved decisions

### 6.1 Exact scope wording (proposal text for later card — not an approval ask now)

See also `Trish-source-preparation-card-wording.md` in this packet.

> **Proposed later card title:** Native synthetic-provider fixture preparation (source/fixture authoring only)
>
> **Authorize Jim to author, in a fresh packet copy only,** the prospective files listed in §1.2 of `Implementation-Scope-Proposal.md` (np_supervisor / integrated_runner / runner_entry / suite / receipts / provider_peer / transcript / routes / auth_seed / alias_seed / prepare-np-provider-tls.sh / prepare-np-db-tls.sh and packet configs), reusing I01/I02 v4 container/runner patterns and exact source lineage pins, **without** modifying the approved 3-file covering application lane except by consuming the **already separately authorized** final assembled application tree.
>
> **In scope:** fixture-only synthetic HTTPS peer, fixture CA/SAN recipe (tmpfs private keys), finite case oracles for the frozen 25-case inventory, serial batch configs B1–B5, receipts that observe JoinedTLS (not FixtureByteTransport), native TOKEN vs IMPORT terminal separation, assessment deltas.
>
> **Out of scope / still forbidden by this card alone:** execution/launch; Docker run; PKI generation on shared hosts outside disposable recipe review; real providers/credentials; endpoint binding; port/framing merge; URL rewrite; root/capability/sysctl; ambient secrets; expanding to a 76-run matrix; claiming PASS.
>
> **Dependencies before launch (not before preparation authoring):** reconciled framing-fake-v4 and port-zero authorized results; final assembled application hashes; topology bind decision recorded; separately frozen command/hash/bounds launch packet(s).
>
> Flags remain: `implementation_authorized` only for fixture/packet authoring after Trish signs this card; `launch_authorized=false` until a later launch card; `executed=false`; `prep_is_not_pass=true`.

### 6.2 Unresolved decisions / dependencies (actual)

| ID | Decision / dependency | Owner | Blocks |
| --- | --- | --- | --- |
| D1 | Framing-fake-v4 one-shot authorize → run → reconcile | Trish / Dex | Final assembled `covering_http_transport.py` bytes; T05 REUSE closure |
| D2 | Port-zero one-shot authorize → run → reconcile | Trish / Dex | T01-ORIGIN-FOREIGN-PORT; final policy file lineage |
| D3 | Final assembled application source set + hashes (routing + framing + TLS EOF + port) | Dex / Trish | Native workspace mount pins |
| D4 | Topology :443 nonroot bind alternative A/B/C/D | Trish (consequential) | Launch topology; vendor-origin claim |
| D5 | Approve fixture preparation card (§6.1) | Trish | Any np_* source authoring |
| D6 | Freeze 25 vs split T08 into 3 STOP units | Dex design retain | Suite inventory |
| D7 | Five separate launch cards vs one mega-suite | Dex / Trish | Budget arithmetic |
| D8 | Native launch command/hash/bounds packet(s) | Later freeze | Execution |
| D9 | T02 items/bytes direct overrun witness (fake or native) | Dex | Full T02 closure — not beta-blocking per finish-line if disclosed |
| D10 | Whether MemoryBIO/SSLObject peer vs real socket peer is acceptable for which cases | Dex | Peer mechanism — both must still speak real TLS records to JoinedTLS for T03/T04/T05 L4 |

No approval question is raised by this handback. Concrete proposal is now reviewable.

### 6.3 Authority boundary (restated)

- Dex retains design/integration decisions.
- This packet makes the approved goal **concrete and implementable**.
- Native launch requires a **later separately frozen** command/hash/bounds packet.
- Endpoint unbound; all holds stay.

---

## 7. Handback summary for Dex

- Documents-only implementation-scope proposal complete.
- 76 IDs retained; **25** proposed native executable cases; property-matched REUSE elsewhere.
- No new JoinedTLS injection seam.
- Vertical: real HTTP/dispatch/connector/JoinedTLS + synthetic provider TLS + native token/import + changed assessment; distinctions frozen.
- Topology decision **explicit** (recommend A; stop on bind failure; no silent contract change).
- Budgets computed from 210/240/30; I01 600/900 not reused as authority.
- Framing/port remain unexecuted; prep ≠ pass.

— Jim
