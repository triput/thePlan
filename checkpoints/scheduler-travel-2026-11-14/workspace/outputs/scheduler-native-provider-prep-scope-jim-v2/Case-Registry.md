# Canonical Case Registry — native provider prep scope jim-v2

Documents only. Successor to jim-v1. Preserves immutable v1 TIP on-disk 531BFBDE267872AFA3DC58C0294ECFE3270F01650D5DA52D5D1F900A5A45C130 / tip_sha256 2ED4F5DC6E97B54DAF6F06D51DD47975B7D3861241F453CEC4CBB54625958BDA / Proposal 126AC17B31B14C3D2AF5864ABB9830666A42F6C7A2F453F152521AF52431555C.

| Flag | Value |
| --- | --- |
| executed | false |
| launch_authorized | false |
| implementation_authorized | false |
| prep_is_not_pass | true |
| endpoint | unbound |

Planning inventory authority: Transport-Completion-Audit-Current.json SHA256 476BA8245705BB2FDAC2F892CB65DCDACA5C7B86A742ADD7A1C8CDA01B0852CA (76 entries; supersedes v1-cited 57D56C6E… after framing-fake-v4 audit refresh). All **76** planning IDs retained.

---

## A. Exact native executable STOP inventory (canonical count = 27)

One STOP unit per row. Shared multi-oracle allowed only where named oracles are independently enforced with immediate check + STOP on mismatch. No orphan IDs. No glob-only rows. No missing MALFORMED/TRUNCATED/OTHER/PARTIAL variants.

| # | Case ID | Planning ID(s) covered | Stimulus (first guard / input channel) | Primary oracle(s) |
| --- | --- | --- | --- | --- |
| 1 | NP-V-MS-NONEXPIRED | (vertical composition; not a T06 success) | Nonexpired MS seed; get_valid_access_token | No OAuth request; TOKEN ROLLBACK ack; identity/event/assessment measured separately |
| 2 | NP-V-MS-REFRESH | T06-SUCCESS-MICROSOFT | Explicitly expired MS token + synthetic MS client/secret/redirect/tenant | Owning MS refresh through default JoinedTLS; TOKEN COMMIT; persistence |
| 3 | NP-V-MS-TOKEN-THEN-IMPORT-FAIL | (terminal separation) | After TOKEN COMMIT, force known event-import failure | Refreshed tokens remain; parent import rollback/result + assessment separate |
| 4 | NP-V-MS-INVALID | T06-INVALID-GRANT-MICROSOFT | Synthetic MS invalid_grant response on owning refresh | TokenRejected after unchanged-unit rollback |
| 5 | NP-V-GOOGLE-REFRESH | T06-SUCCESS-GOOGLE | Explicitly expired Google token + synthetic Google settings | Owning Google refresh; TOKEN COMMIT; not MS proof |
| 6 | NP-V-GOOGLE-INVALID | T06-INVALID-GRANT-GOOGLE | Synthetic Google invalid_grant on owning refresh | TokenRejected path; not MS proof |
| 7 | NP-T06-BEFORE-SEND | T06-BEFORE-SEND | Pre-send refusal/stop stimulus | No token mutation claim |
| 8 | NP-T06-MALFORMED-ACK | T06-MALFORMED-ACK | After-send malformed OAuth ack body | UNKNOWN remap; no known failure from parser class alone |
| 9 | NP-T06-TRUNCATED-ACK | T06-TRUNCATED-ACK | After-send truncated OAuth ack | UNKNOWN; local tokens retained as observed |
| 10 | NP-T06-OTHER | T06-OTHER-ERROR | Non-invalid_grant OAuth error body | UNKNOWN branch as sourced |
| 11 | NP-T06-PARTIAL | T06-PARTIAL-SEND | OAuth partial send mid-body | UNKNOWN; no replay |
| 12 | NP-T06-LOST | T06-LOST-ACK | Lost ack after send | UNKNOWN; disposable DB state retained |
| 13 | NP-T03-VALID | T03-VALID | verify-full CA+hostname via JoinedTLS to vendor SAN leaf | Handshake + useful app data success |
| 14 | NP-T03-WRONG-CA | T03-WRONG-CA | Distinct wrong trust material | Refuse before useful application data |
| 15 | NP-T03-WRONG-NAME | T03-WRONG-NAME | Mismatched SAN | Refuse |
| 16 | NP-T03-HANDSHAKE-STALL | T03-HANDSHAKE-STALL | Peer stall pre-handshake completion; production 210/240 clocks | First guard = deadline; real elapsed |
| 17 | NP-T03-TCP-REFUSAL | T03-TCP-REFUSAL | Numeric dial to closed port | Typed connect failure; no fake empty receive |
| 18 | NP-T04-HEADER-STALL | T04-HEADER-STALL | Peer stall in header phase; production clocks | First guard = header-phase deadline |
| 19 | NP-T04-BODY-STALL | T04-BODY-STALL | Peer stall in body phase; production clocks | First guard = body-phase deadline |
| 20 | NP-T04-PARTIAL-SEND | T04-PARTIAL-SEND | Partial request send observed | Joined retirement; no retry |
| 21 | NP-T04-DEADLINE | T04-DEADLINE | Explicit app deadline classification | Distinct from supervisor kill |
| 22 | NP-T04-DISCONNECT | T04-DISCONNECT | **ASGI/request-disconnect** signal + joined worker/provider retirement | UNKNOWN/sanitized path; **not** abrupt provider EOF (see NP-T05-ABRUPT / T04 vs T05) |
| 23 | NP-T05-ORDERLY-CLOSE | T05 orderly/close-delimited + short-CL completeness requal | Valid JSON prefix + **short Content-Length** + **orderly TLS close_notify** | HTTP completeness guard observed; SSL abrupt-EOF must not mask it |
| 24 | NP-T05-ABRUPT-TRUNCATION | T05 abrupt truncation | Abrupt TLS truncate **without** close_notify | Classified distinctly from malformed JSON/chunk/header and from ASGI disconnect |
| 25 | NP-T07-OWNED-SOCKET | T07 owned socket/reader retirement (socket claims) | Real owned peer/reader under JoinedTLS | Independent response/transport close provenance on real sockets |
| 26 | NP-T07-BOTH-AFTER-FAILURE | T07-BOTH-CLOSE-AFTER-PRIMARY-FAILURE | Primary failure then both-close branch | Combined both-close-after-failure observed (overlay gap) |
| 27 | NP-T08-OWNERSHIP | T08-FOREIGN-THREAD + T08-FOREIGN-CLOSE + T08-REUSE (+ owner-retirement) | One owned peer lifecycle; four named oracles | foreign-check, foreign-close, reuse-forbid, owner-retirement — each checked immediately; STOP on mismatch |

**Canonical native case count = 27.**

ID spelling freeze: always NP-T06-MALFORMED-ACK / NP-T06-TRUNCATED-ACK (with -ACK); always NP-T06-OTHER / NP-T06-PARTIAL (these were orphaned from v1 24/25 registry). Never emit NP-T06-MALFORMED / NP-T06-TRUNCATED without -ACK, and never omit OTHER/PARTIAL from the executable list.

---

## B. Bounded pure-control-flow witness cases (4) — HOLD→CF, not JoinedTLS proof

Exact executed D2/route rows do **not** supply named userinfo / fragment / control-character / purpose-wrong witnesses. Do not claim REUSE from HTTPSPeer guard presence. Include these as bounded pure-control-flow witnesses in fixture preparation (refuse-before-send; no native TLS claim):

| # | Case ID | Planning ID | Disposition |
| --- | --- | --- | --- |
| CF1 | NP-T01-USERINFO-CF | T01-ORIGIN-USERINFO | HOLD→CF-WITNESS |
| CF2 | NP-T01-FRAGMENT-CF | T01-ORIGIN-FRAGMENT | HOLD→CF-WITNESS |
| CF3 | NP-T01-CONTROL-CHAR-CF | T01-ORIGIN-CONTROL-CHAR | HOLD→CF-WITNESS |
| CF4 | NP-T01-PURPOSE-WRONG-CF | T01-PURPOSE-WRONG | HOLD→CF-WITNESS |

Total predeclared fixture STOP units if CF batch included = **31** (27 native + 4 CF). CF may ship as its own separately authorized short launch; still part of the exact registry.

---

## C. Exact requirement → case / reused-control / HOLD map (all 76)

Legend: NATIVE = covered by a §A case; CF-WITNESS = §B; REUSE = cite exact executed control + source lineage; HOLD = waits on port/assembly/other packet; GAP = retained obligation needing focused witness (not waived by post-beta label); COMPOSE = observe on vertical without family closure claim.

### T01 (18)

| Planning ID | Disposition | Exact case / control / HOLD |
| --- | --- | --- |
| T01-ORIGIN-FOREIGN-HOST | REUSE | D2 control CTRL-CONT-FOREIGN-BEFORE-SEND — result 2FB80F2C50BBC1302EA71728EC899EAD665660D69B6CE970FF13D10791BF3CCD, receipt 9E11B3A1F91186AEA945B4FF828B63A732A8A99228DEB765AA08C4E50FBAB91D; observation: origin/route refuse before send; 0/0. Scope: D2 fake path-admission, not native TLS. |
| T01-ORIGIN-FOREIGN-PORT | HOLD | Port-zero packet prepared, **unexecuted/unapproved**. No native claim. |
| T01-ORIGIN-USERINFO | CF-WITNESS | NP-T01-USERINFO-CF — no named executed D2/route userinfo row; do not invent REUSE. |
| T01-ORIGIN-FRAGMENT | CF-WITNESS | NP-T01-FRAGMENT-CF — same. |
| T01-ORIGIN-CONTROL-CHAR | CF-WITNESS | NP-T01-CONTROL-CHAR-CF — same. |
| T01-PURPOSE-WRONG | CF-WITNESS | NP-T01-PURPOSE-WRONG-CF — route overlay 
eusable_route_controls: []. |
| T01-PURPOSE-AMBIGUOUS | REUSE | Route control ROUTE-EQUAL-PATH-CONFLICT in T01-Route-Property-Evidence-Reuse.json 5CD74FD03464C016466B525C14CE3AC92E8B58A460602F406D94E5106275C5A3 — REFUSE before send; identity=0 event=0 sends=0. |
| T01-CONTINUATION-REDIRECT | REUSE | D2 control CTRL-CONT-REDIRECT-3XX — same D2 result/receipt hashes as FOREIGN-BEFORE-SEND; observation: 1 open/send original; 0 follow-ups; redirect refused. |
| T01-CONTINUATION-GOOGLE-PAGE-TOKEN | REUSE | Route controls ROUTE-GOOGLE-LIST, ROUTE-GOOGLE-EVENT in 5CD74FD0… (and D2 CTRL-CONT-G-PAGE-TOKEN at D2 scope). |
| T01-CONTINUATION-MS-NEXTLINK | REUSE | Route controls ROUTE-MS-LIST-CONTINUATION-ABS, ROUTE-MS-LIST-CONTINUATION-ROOT, ROUTE-MS-EVENT-CONTINUATION in 5CD74FD0… (and D2 CTRL-CONT-MS-NEXTLINK). |
| T01-PATH-POSITIVE-EXACT | REUSE+COMPOSE | Route ROUTE-MS-LIST, ROUTE-MS-DEFAULT, ROUTE-MS-EVENT-OVERLAP in 5CD74FD0…; vertical COMPOSE observes actual MS default→list→calendarView counts on JoinedTLS. |
| T01-PATH-POSITIVE-CHILD | REUSE | Route child/descendant controls in 5CD74FD0… at recorded route-fake scope. |
| T01-PATH-PREFIX-BOUNDARY | REUSE | D2 CTRL-NEG-PREFIX-BOUNDARY in result 2FB80F2C…. |
| T01-PATH-DOT-SEGMENT | REUSE | D2 CTRL-NEG-RAW-DOT / CTRL-NEG-NEST-DOT in 2FB80F2C…. |
| T01-PATH-ENCODED-DOT | REUSE | D2 encoded-dot negatives in 2FB80F2C… at D2 scope. |
| T01-PATH-ENCODED-SEP | REUSE | D2 CTRL-NEG-ENC-SLASH-PCT2F-UPPER / LOWER / nest variants in 2FB80F2C…. |
| T01-PATH-ENCODED-ID-GOOGLE | REUSE | D2/route Google ID positives in 2FB80F2C… / 5CD74FD0…. |
| T01-PATH-ENCODED-ID-MICROSOFT | REUSE+COMPOSE | Route MS encoded ID controls in 5CD74FD0…; vertical uses encoded reviewed calendar ID on real JoinedTLS. |

### T02 (12)

| Planning ID | Disposition | Exact case / control / HOLD |
| --- | --- | --- |
| T02-EVENT-PAGES-BOUNDARY | REUSE | Prior T02 fake admission at recorded T02 scope (overlay D27CA2442CEDAF6EB045C50BE6F2A9C205EA00A8EC6DB595832F583910CCA57A). |
| T02-EVENT-PAGES-OVERFLOW | REUSE | Same T02 scope. |
| T02-IDENTITY-PAGES-BOUNDARY | REUSE | Same. |
| T02-IDENTITY-PAGES-OVERFLOW | REUSE | Same. |
| T02-ITEMS-BOUNDARY | REUSE | Same. |
| T02-ITEMS-OVERFLOW | GAP | Overlay: direct data-overrun not established by N−1 + new admission alone. **Not waived** by post-beta label. Framing host-fake EXCESS-ITEM-BYTE (result 3905A070…) is host-fake refuse observation only — does **not** close native/T02 full goal. |
| T02-BYTES-BOUNDARY | REUSE | T02 scope. |
| T02-BYTES-OVERFLOW | GAP | Same as items overrun — retained. |
| T02-EQUALITY-WITNESS-EVENT-PAGES | REUSE | Counter equality at T02 scope. |
| T02-EQUALITY-WITNESS-IDENTITY-PAGES | REUSE | Same. |
| T02-EQUALITY-WITNESS-ITEMS | REUSE | Same. |
| T02-EQUALITY-WITNESS-BYTES | REUSE | Same. |
| (composition note) | COMPOSE | Observe shared counters on NP-V-* success path; do not re-run all 12. |

### T03 (5) — all NATIVE

| Planning ID | Native case |
| --- | --- |
| T03-VALID | NP-T03-VALID |
| T03-WRONG-CA | NP-T03-WRONG-CA |
| T03-WRONG-NAME | NP-T03-WRONG-NAME |
| T03-HANDSHAKE-STALL | NP-T03-HANDSHAKE-STALL |
| T03-TCP-REFUSAL | NP-T03-TCP-REFUSAL |

### T04 (5) — all NATIVE

| Planning ID | Native case | Stimulus note |
| --- | --- | --- |
| T04-HEADER-STALL | NP-T04-HEADER-STALL | Header-phase stall |
| T04-BODY-STALL | NP-T04-BODY-STALL | Body-phase stall |
| T04-PARTIAL-SEND | NP-T04-PARTIAL-SEND | Partial send |
| T04-DEADLINE | NP-T04-DEADLINE | App deadline ≠ supervisor kill |
| T04-DISCONNECT | NP-T04-DISCONNECT | ASGI/request-disconnect + joined retirement; **≠** provider abrupt EOF |

### T05 (13)

| Planning ID | Disposition | Exact lineage |
| --- | --- | --- |
| T05-VALID-COMPLETE-CONTENT-LENGTH | REUSE (host-fake) | Framing-fake-v4 PASS 73/73 — result 3905A070AE06EF2EA6B31C8A8D1407A6F58E46B549E1118FF3928C00866ECBA3, receipt 166BB080CCCD19B80F88703BA3CC16B46142DAEF3904BDAF5D7AA9CF3254E6E6, reconciliation E9BCFB2D91A4C6E52657DF719F749B0FE8E21959D9CBEDB074516CB729C50E18. **Not native proof.** |
| T05-VALID-COMPLETE-CHUNKED | REUSE (host-fake) | Same framing run / same hashes. |
| T05-SHORT-LENGTH-VALID-JSON | REUSE (host-fake) + NATIVE requal share | Host-fake REUSE from framing run; native requal observation shares with NP-T05-ORDERLY-CLOSE when same exact observation proves short-CL completeness under orderly TLS close. |
| T05-SHORT-LENGTH-INVALID-JSON | REUSE (host-fake) | Framing run; keep distinct from abrupt TLS. |
| T05-CHUNK-EOF | REUSE (host-fake) | Framing run; distinct stimulus/oracle from abrupt TLS. |
| T05-DUPLICATE-CONTENT-LENGTH | REUSE (host-fake) | Framing run + header policy AEAE5343… / approval 1C932F1A…. |
| T05-CONFLICTING-CONTENT-LENGTH | REUSE (host-fake) | Same. |
| T05-TE-CHUNKED-PLUS-CL | REUSE (host-fake) | Same. |
| T05-TE-NONEXACT-PLUS-CL | REUSE (host-fake) | Same. |
| T05-MALFORMED-HEADER | REUSE (host-fake) | Framing run; distinct from abrupt TLS. |
| T05-MALFORMED-JSON | REUSE (host-fake) | Framing run; distinct from abrupt TLS. |
| T05-NONOBJECT | REUSE (host-fake) | Framing run. |
| T05-ENCODING | REUSE (host-fake) | Framing run. |
| (L4 orderly vs abrupt) | NATIVE | NP-T05-ORDERLY-CLOSE, NP-T05-ABRUPT-TRUNCATION — byte fakes cannot close. |
| EXCESS-ITEM-BYTE (framing control) | host-fake observation | observed_outcome=PASS; yte_excess_outcome=OBSERVED_REFUSE / item_excess_outcome=OBSERVED_REFUSE; exception CoveringTransportRefused. Scope: host-fake only. |
| PRIMARY-BOTH-CLOSES (framing control) | host-fake observation | OBSERVED_UNKNOWN; 	hree_roles_present=true; FakeResponseCloseError + FakeTransportCloseError. Scope: host-fake; does not replace NP-T07-BOTH-AFTER-FAILURE native. |

Private parser coupling remains disclosed; **no 57-case native repetition** required.

### T06 (10) — all NATIVE owning paths

| Planning ID | Native case |
| --- | --- |
| T06-BEFORE-SEND | NP-T06-BEFORE-SEND |
| T06-MALFORMED-ACK | NP-T06-MALFORMED-ACK |
| T06-TRUNCATED-ACK | NP-T06-TRUNCATED-ACK |
| T06-INVALID-GRANT-GOOGLE | NP-V-GOOGLE-INVALID |
| T06-INVALID-GRANT-MICROSOFT | NP-V-MS-INVALID |
| T06-OTHER-ERROR | NP-T06-OTHER |
| T06-SUCCESS-GOOGLE | NP-V-GOOGLE-REFRESH |
| T06-SUCCESS-MICROSOFT | NP-V-MS-REFRESH |
| T06-PARTIAL-SEND | NP-T06-PARTIAL |
| T06-LOST-ACK | NP-T06-LOST |

### T07 (8)

| Planning ID | Disposition | Mapping |
| --- | --- | --- |
| T07-RESPONSE-CLOSE-AFTER-SUCCESS | REUSE+NATIVE | Fake provenance/lineage reuse EF213E03F7D37705C8954BFA2F7912E73303B08C2B6E80D30C736F3CDA580FE3 for logical cleanup; socket claims via NP-T07-OWNED-SOCKET. |
| T07-RESPONSE-CLOSE-AFTER-PRIMARY-FAILURE | REUSE+NATIVE | Same pattern. |
| T07-TRANSPORT-CLOSE-AFTER-SUCCESS | REUSE+NATIVE | Same. |
| T07-TRANSPORT-CLOSE-AFTER-PRIMARY-FAILURE | REUSE+NATIVE | Same. |
| T07-BOTH-CLOSE-AFTER-SUCCESS | REUSE+NATIVE | Logical reuse + owned socket case. |
| T07-BOTH-CLOSE-AFTER-PRIMARY-FAILURE | GAP→NATIVE | NP-T07-BOTH-AFTER-FAILURE (host-fake PRIMARY-BOTH-CLOSES does not close this). |
| T07-OPEN-CLOSE | REUSE+NATIVE | Fake control flow reusable; native confirms real open/close under JoinedTLS via owned-socket case observations. |
| T07-SETBLOCKING | REUSE+NATIVE | Same. |

### T08 (5)

| Planning ID | Disposition | Mapping |
| --- | --- | --- |
| T08-NESTED | REUSE or focused unit | ContextVar nesting; may remain non-TLS if pure context. |
| T08-RESET | REUSE or focused unit | ContextVar reset; same. |
| T08-FOREIGN-THREAD | NATIVE | Oracle inside NP-T08-OWNERSHIP |
| T08-FOREIGN-CLOSE | NATIVE | Oracle inside NP-T08-OWNERSHIP |
| T08-REUSE | NATIVE | Oracle inside NP-T08-OWNERSHIP |

---

## D. Orphan / spelling reconciliation vs jim-v1

| jim-v1 defect | v2 fix |
| --- | --- |
| T06 table named NP-T06-OTHER / NP-T06-PARTIAL but 24/25 registry omitted them | Both listed as cases #10 and #11 |
| NP-T06-MALFORMED / NP-T06-TRUNCATED vs -ACK mismatch | Frozen as NP-T06-MALFORMED-ACK / NP-T06-TRUNCATED-ACK only |
| Ambiguous 24 vs 25 vs 27 | Canonical native = **27**; CF witnesses = **4** additional |
| Glob-only T02 rows in prose | Expanded to exact 12 IDs above |

No orphan case IDs remain outside §A/§B. No planning ID lacks a disposition row in §C.
