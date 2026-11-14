# Matt → Dex: NP-V-GOOGLE-REFRESH preparation v2 and focused fake (HELD, frozen)

November 13, 2026. This responds to `Matt-thePlan-Scheduler-Google-First-Vertical-Preparation-2026-11-13.md` (`CEBD83C31757CFF3B567C400920ADA37AAE334F3F2BEC4EFA1ABC864AE5A6570`). It also incorporates your in-task feedback:
- `3E5590C4…61E2`: source pointers;
- `55B75EA0…26C1`: primary seed;
- `F04CEFCA…B82`: revision/busy.

**Status:** PREPARED_NOT_EXECUTED. Two fresh frozen v2 roots, no active writer, endpoint unbound.
- **Method:** copy, text, hash and JSON authoring. Nothing was imported, parsed, compiled, tested or invoked. No DB, Docker, PKI or sockets.
- **Subagent:** one bounded read-only source trace (no file writes, no code copies). Its findings are labeled FACT or INFERENCE below.
- **Unexecuted:** syntax and behavior.

## 0. v1 preserved as partial (not handed back as final)
I froze `scheduler-native-google-refresh-prep-matt-v1` (parent `06703C09…6F35`, 305) and `…-fake-prep-matt-v1` (`F6D75998…6748`, 35) **before** I read 55B75EA0 and F04CEFCA.
- **What v1 lacks:** it has the token refresh and two informational imports only. There is no primary row, no calendarList and no revision/busy check.
- **Handling:** both roots are untouched, and both re-verified at freeze time. Per the never-repair rule, v2 is a fresh pair of roots.
- **My miss:** CEBD83C3 itself already asked for the primary row and the before/after busy change. I should have caught that from the assignment.

## 1. Native root `outputs/scheduler-native-google-refresh-prep-matt-v2`
- **Source:** `scheduler-native-ms-nonexpired-retirement-launch-matt-v2`, `C62FDA91…F2BA`, re-verified 301/301.
  - Manifest-listed inputs only; no evidence copied.
  - Runner `A2C32A20`, peer `17EA148E`.
- **Parent:** `Input-Manifest.sha256` = **`EFC705425F839D4FCC7C04FCEA2840A22FA3262B40B9F270F8951B868E42F35D`** (305: the 301 inputs, plus the README, Freeze, HELD command and source-manifest copy). Verified OK.
- **Exact diff:** `Matt-thePlan-Scheduler-Google-Refresh-Prep-V2-2026-11-13.diff` = `71D669D5CC83B35905A98FAB805CA2767E1EFA8673F879F70463EA1D5E0F27D9` (1197 lines, 24 hunks, 8 files).

| Role | File | Before → after |
|---|---|---|
| 4 runner | `np_runner_entry.py` | `A2C32A20` → **`8EFE8D5BCEA73D5936E4C0B094F5710B1BA7A7F9244A6E4BCD052CAA8A4BF774`** |
| 5 suite | `np_suite.py` (note only) | `AEC59FCD` → **`E028812B852C73A1183D609803A450AB41B42CCDE44B4DEE4441EEDB21EA7D1A`** |
| 8 transcript | `np_provider_transcript.py` | `CFAB2D06` → **`79025EC55B3EFED65D610494753401F65818068B97DA76ACD626ED183C94B513`** |
| data | `runner-config.json` (CRLF) | `8668F156` → `95278DF6B3756F39B5D45CF24C96B3435B20394D3A951FAD95DE5FB76095E7ED` |
| data | `launch-config.json` (CRLF, 102 CR) | `03A131BC` → `B9413B449E744B5C82AEDEBB46D92EDD6B5704049846F6E9C1E20929AA12FBAA` |
| data | `docker-ops-config.json` (7-path rename) | `5E6CEDCB` → `6A497DFC81EB84B790DB494FFE54007F0AF0EE0CB081BEFA056279BD492E40A8` |
| manifest | payload `SHA256SUMS.txt` (257; 4 rows) | `C058ECCE` → `4A5550D466B08ED6C264A1B17B10F15326A3E755C0DA079D93BB9CF5BDEE4E68` |
| manifest | nested `Input-Manifest.sha256` (269; 7 rows) | `DA1D9A15` → `FE1B77FA0D257E52B3909E4599E486665C9CF293F271613008EB70F0124A48C9` |

- **Unchanged:** `np_auth_seed` `66FEEA81`, routes `9CBDE09C`, peer `17EA148E`, sanitizer `69F59AF1`, PKI, all 234 API files, the operator and the helpers. No role 10/11 helper was needed: the primary planting is inline in setup.
- **Gates:** host `launch_ready` false, staged false, runner-config false, both `launch_authorized` false. The note is truthful and the paths point at the own root.

### Functional case as authored
1. **Seed:**
   - `fixture_settings()` and a fresh plan, with the window re-derived from the plan (600 s validity; expiry STOP);
   - schema setup once;
   - an expired Google account with encrypted synthetic tokens and two inverted planted subscriptions, plus an unrelated non-expired Google owner (1 subscription).
2. **Primary planting (setup only, before `setup.commit()`):**
   - the first str-sorted requested row gets `role=primary` and `external_calendar_id="primary"`, checked equal to production `GOOGLE_PRIMARY_ALIAS`;
   - the second row stays enabled and informational with its stable id;
   - the canonical `np-google-canonical-primary` is checked as unoccupied across both owners;
   - the seeded map is rewritten truthfully.
   
   The shared seed helper is unchanged, because it always seeds informational rows.
3. **Finite inventory (4 exchanges, all `Connection: close`, orderly close):**

   | # | Request | Purpose | Body |
   |---|---|---|---|
   | 1 | POST `oauth2.googleapis.com/token` | oauth | refreshed access, rotated refresh, `expires_in` 3600 |
   | 2 | GET `/calendar/v3/users/me/calendarList?maxResults=250` | identity | one page; exactly one `primary:true` entry = canonical id, plus the informational id |
   | 3 | GET `/calendar/v3/calendars/np-google-canonical-primary/events?<exact>` | event | one confirmed, opaque, timed busy event (window +1h to +2h) |
   | 4 | GET `/calendar/v3/calendars/<informational id>/events?<exact>` | event | one busy event (+3h to +4h) |

   - Routes: exact oauth `/token`, exact identity calendarList, and the event prefix. One peer serves both hostnames.
   - Query: production `_iso_z` over the production window. The calendarList params mirror `list_google_calendars`.
4. **Public assertions:**
   - 200 success;
   - 2 rows, each import/ok with `upserted` 1;
   - `preflight_effects` is `["canonicalize_identity"]` on target 1 and `[]` on target 2;
   - action summary 2/0/2/2/0;
   - all requested covering ok, freshness ok, `scheduling_ready`, `freshness_all` ok, `assessment_error` None;
   - no banned private keys.
5. **Native assertions:**
   - oauth == 1, with purposes POST oauth, GET identity, GET event, GET event, and 4 responses;
   - TOKEN `[COMMIT_ACKNOWLEDGED, ROLLBACK_ACKNOWLEDGED]` and the observer marker;
   - PARENT `[COMMIT, COMMIT]`;
   - CoveringReleasePlan with the ingress-budget identity and default JoinedTLS.
6. **Before/after (separate native read sessions):**
   - **credentials:** semantic decrypt shows refreshed and rotated, seed false, expiry > now+30 s;
   - **subscriptions:** before is alias plus primary, and informational. After, only the primary row is rewritten to canonical; role and enabled are unchanged.
   - **events:** exactly the 2 declared rows (canonical and informational calendar ids, UTC bounds, opaque, `provider_explicit`, not cancelled or pending, no block);
   - **coverage:** all success;
   - **owner (per F04CEFCA):**
     - `UserSettings.scheduling_revision` after > before;
     - the production `immovable_busy_signature` digest changes and its count rises;
     - public `scheduling_revision_at_start` equals the persisted before revision;
     - `scheduling_revision_at_end`, `scheduling_readiness.scheduling_revision` and the persisted after revision are all equal;
     - `scheduling_revision_bumped` is true.
   - **unrelated owner:** credential, coverage, events, subscriptions, revision and busy signature all unchanged.
7. **Retirement:** one retirement through the existing helper. Inventory 4/4: POST, GET, GET, GET, `/token`, calendarList path, `query_verified` on the GETs, orderly close, exact `bytes_sent`; no `np-peer-` thread. There is one guarded cleanup retirement only if none was attempted. Every patch is restored in `finally`.
8. **Evidence:** retained under the unchanged sanitizer:
   - `token_terminal`, as you confirmed;
   - typed revisions, counts and 16-hex digests;
   - no titles, bodies, tokens or ciphertext.

### Source basis (subagent trace; F = read in source, I = inference)
- **F:**
  - `account_needs_live_identity_evidence` (canonicalize l.815–832) triggers on any enabled alias row; role is irrelevant.
  - `list_google_calendars` (google_calendar l.374–399): `maxResults=250` plus `pageToken`.
  - The canonical id is the single `primary`/`isDefaultCalendar` entry; the rewrite affects only the alias row, with role and enabled unchanged.
  - Canonicalization runs inside IMPORT prepare using that target's TOKEN result (no extra TOKEN unit).
  - `classify_covering_prepare_mutation` allows a pure id rewrite (`canonicalize_identity`) and refuses role or enable changes.
  - The events URL uses the canonical id; `preflight_effects` defaults to `[]`.
  - `seed_subscription` hardcodes informational.
  - The busy signature has no role filter.
  - Public `scheduling_revision_at_start`/`_at_end`.
  - `_apply_subscription_full` counts `upserted` per upserted event.
- **I:**
  - target 2 needs no second calendarList, because no enabled alias row remains after T1 commits;
  - TOKEN `[COMMIT, ROLLBACK]`, PARENT `[COMMIT, COMMIT]`;
  - the revision bumps (+2 at T1, +1 at T2); I only assert after > before, not the exact count;
  - `upserted == 1`; `assessment_error` None;
  - `provider_explicit` provenance; one peer serves both hostnames.
  
  If T1 import failed, the rewrite rolls back and T2 would re-fetch calendarList. That is a STOP path, since the inventory is exact.

## 2. Fake packet `outputs/scheduler-native-google-refresh-fake-prep-matt-v2`
- **Manifest** `D626F1C2D9DA9045F68AC19E8B6269FAED82A09A650037ECA04DC7392079931F` (37 entries, verified OK).
- **Immutable, byte-identical:** wrapper `AE84E632`, outer `7DCA32E2`, launcher `D22C37E3`.
- **New:**
  - checker `25275E6CABCA57ECBC575987767C104B44B58F90941EDC37B01804FA835DAAF0`;
  - EXPECTED `60C4A464449AE7CDCD054887889037D24FB3E37B948424DCFB7186E56453CEE1`;
  - OUTER `F29AE7C8E74CF54DF6BEB1ECC66B75081752B347C012E7E50A0B736C75BAC05B`;
  - VERIFICATION **`F2BE4173016FA0C11CFE7E3D5689443D602A8CA61086B8A04FF1833FEF4E4B92`** (34 packet pins and 10 partial runtime pins).
- **Controls:** 14 top-level, 66 nested; listed in `Launch-Decision.md`.
- **Module registration:** dataclasses and all faked module names are registered as owned ModuleTypes before any extracted definition executes. The Sandbox refuses pre-existing names and cleans up only its own entries.
- **Hand-traced against the actual subjects:**
  - `FakeEqColumn.__eq__` for `UserSettings.owner_id == owner_id`;
  - the NamedTuple window module executed whole in a registered module;
  - `list_google_calendars` params is an AnnAssign (matched as such);
  - the multi-line guard expressions are parsed parenthesized;
  - the restore check selects the single `try` whose `finally` restores all three patches.
- **Mutants (10, every anchor unique in its candidate text):**
  - **behavioral:** `refresh_token_omitted`, `query_param_changed`, `rotated_compared_to_access`, `parent_exception_swallowed`, `event_sort_dropped`, `calendar_list_primary_flag_dropped`;
  - **structural:** `token_key_unallowlisted`, `second_retirement`, `unrelated_events_check_dropped`, `revision_equality_dropped`.

## 3. Case/oracle-to-evidence table

| Requirement / oracle | Enforced (native, in memory) | Retained evidence key | Fake control |
|---|---|---|---|
| `owning_google_refresh` (T06-SUCCESS-GOOGLE) | oauth==1, TOKEN COMMIT, semantic refreshed/rotated persistence, expiry > now+30 s | `observations.owning_google_refresh`, `oauth_request_count`, `token_terminal`, `credential_state_before/after` | TRANSCRIPT token; CREDENTIAL ×5; mutants `refresh_token_omitted` and `rotated_compared_to_access` |
| `token_commit_not_ms_proof` | `check_oracles_immediate` in memory (key not allowlisted, so not retained) | `token_terminal` (Google-only witness) | RETENTION b (disclosed drop) |
| Primary-alias resolution, requested row only | before/after subscription guards; `preflight_effects`; GET identity; peer path[1] | `subscriptions_before/after`, `preflight_effects_by_target_order`, `primary_alias_rewritten_to_canonical`, `wire_calendar_order` | TRANSCRIPT calendarList; QUERY identity route + mirror; IDENTITY ×3; WIRING planting + guards; mutant `calendar_list_primary_flag_dropped` |
| Non-empty import with identity/time/busy | exact event list | `imported_events_after`, `imported_event_count_before` | EVENTS ×2; mutant `event_sort_dropped` |
| Native final assessment at the actual final revision, plus a before/after busy change | revision/busy guard | `owner_state_before/after`, `public_response.scheduling_revision*` | IDENTITY owner; WIRING revision guard; mutant `revision_equality_dropped` |
| Coverage and freshness | public + persisted | `coverage_before/after`, `public_response` | WIRING (structural) |
| Unrelated data unchanged | 6 unrelated comparisons | `unrelated_unchanged` | WIRING guards; mutant `unrelated_events_check_dropped` |
| Exact inventory and single retirement | peer guard; helper | `client_exchange_inventory`, `client_outcomes`, `peer_exchange_inventory` | TRANSCRIPT inventory; WIRING; mutant `second_retirement` |
| Restoration | `finally` | `resource_disposition.observers_restored` | PARENT ×3; WIRING restore; mutant `parent_exception_swallowed` |
| Sanitizer | — | all keys | RETENTION; mutant `token_key_unallowlisted` |

## 4. Commands (HELD, not authorized)
- **Fake:** `& '…\scheduler-native-google-refresh-fake-prep-matt-v2\packet\Invoke-Fake.ps1' -AdmissionSHA256 'F2BE4173016FA0C11CFE7E3D5689443D602A8CA61086B8A04FF1833FEF4E4B92'`. Against `launch_authorized=false` it refuses before any child.
- **Native:** `Google-Refresh-Native-Command-HELD.ps1.txt` (`08A58907A3BE2B45D91BF95D4B63F8BFFDA26429AE294D5350C4889D6FC9A56F`), which runs `Invoke-Native-Provider.ps1 -ExpectedConfigSHA256 B9413B44… -ExpectedDockerConfigSHA256 6A497DFC…`. The operator STOPs on gates false.

## 5. Bounds and limits
- **Fake:** 135 s nominal (120 + 5 + two 5 s), 64 KiB per stream, 256 KiB result.
- **Native proposal (not authority):**
  - PKI 30+5+two 5 = 45;
  - peer 120 + 5 join;
  - 4 exchanges, well within the 120 s peer window;
  - runner 600 and suite 900 unchanged;
  - Docker 32 commands / 1 MiB unchanged.
- **Not established:** any native behavior or PASS; the source-derived inferences in §1; the CoveringHTTP `urlencode` wire form beyond the peer's exact check; recurrence and paging (excluded); planning, Preview/Apply, activation or household readiness. Microsoft-specific work stays parked. No family or full-goal closure is implied, and all 76 original requirements are retained.

## 6. Preservation and holds
- Untouched and re-verified: baseline `C62FDA91`, v1 native `06703C09`, v1 fake `F6D75998`.
- All earlier packets and evidence are preserved.
- No Git, no ThePlan edits, no production source changes.
- Endpoint unbound; all execution and activation holds stay.

Signed: Matt
