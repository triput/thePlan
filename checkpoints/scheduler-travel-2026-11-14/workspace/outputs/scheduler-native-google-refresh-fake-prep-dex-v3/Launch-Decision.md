# NP-V-GOOGLE-REFRESH: focused fake verification preparation v2 (HELD)

Matt, November 13, 2026. This is for Dex `CEBD83C3…6570`, with the in-task feedback `55B75EA0` (primary seed) and `F04CEFCA` (revision/busy). It's the companion to the native root `scheduler-native-google-refresh-prep-matt-v2` (parent `EFC70542…F35D`).
- **v1** (`…-fake-prep-matt-v1`, manifest `F6D75998`) **is preserved untouched as partial work.** It has no primary or calendarList controls.

**No execution is authorized.** Nothing here has been imported, parsed, compiled or run. Both admissions have `launch_authorized=false`, and no PASS is claimed.

## Roles and pins
- **Immutable, byte-identical:** wrapper `AE84E632`, outer `7DCA32E2`, launcher `D22C37E3`.
- **New:**
  - checker `25275E6C…DAAF0`;
  - EXPECTED `60C4A464…CEE1`;
  - OUTER `F29AE7C8…C05B`;
  - VERIFICATION `F2BE4173…4B92` (34 packet pins and 10 partial runtime pins).

## Controls: 14 top-level, 66 nested
1. **SUBJECT-PINS** (1): 28 subjects, including unchanged production `google_calendar` `8A335971`, `export_baseline` `39EB4E58`, `covering_refresh_window` `7E39381B`, `calendar_alias_canonicalize` `A661FE92`, `scheduling_revision` `4A3CBAA0` and `np_auth_seed` `66FEEA81`.
2. **RUNTIME-PROVENANCE** (4, partial).
3. **DIFF-REDERIVATION** (4).
4. **PRESERVED-OUTSIDE-CHANGE** (3):
   - the runner adds exactly 21 units and changes only `IMPLEMENTED_CASE_IDS` and the mapper;
   - 7 reused helpers are byte-identical;
   - the transcript adds 11 units, and the suite changes only its note.
5. **TRANSCRIPT-SCRIPTS** (6, actual units in a **registered** ModuleType, plus the actual peer serializer):
   - the token body and framing;
   - the busy event;
   - the events path and query;
   - **calendarList with exactly one primary entry and the exact `maxResults=250` query**;
   - the **4-exchange** ordered inventory;
   - the peer's exact-query semantics.
6. **ROUTES-AND-QUERY** (5):
   - exact oauth, exact identity, and the event prefix (identity and events share one API peer);
   - the calendarList query mirrors production `list_google_calendars`;
   - the exact events literal;
   - offset normalization;
   - the events params mirror.
7. **CREDENTIAL-MEASUREMENT** (5): unchanged from v1.
8. **EVENT-MEASUREMENT** (2): unchanged from v1.
9. **IDENTITY-AND-OWNER-MEASUREMENT** (3):
   - typed, sorted subscription rows, refusing a missing row;
   - the owner revision plus a busy count and 16-hex digest: deterministic, changing with the intervals, and not leaking timestamps;
   - the runner alias literal equals production `GOOGLE_PRIMARY_ALIAS`, and the `immovable_busy_signature(db, owner_id)` signature matches.
10. **PARENT-OBSERVER** (3).
11. **CASE-WIRING** (12, structural; the case body is not executed). Adds to v1:
    - **primary planted in setup only:** exactly the two assignments, before `setup.commit()`, with no other role, external-ID or enabled writes;
    - **exact revision and identity guards:** revision and busy, unrelated owner, only the primary row rewritten, the before-state rows, unrelated subscriptions, `preflight_effects`, and the canonical wire order;
    - the updated 4-exchange peer guard.
12. **RECEIPT-RETENTION** (2): now also covers the new helper keys.
13. **CONFIG-AND-IMMUTABLES** (6): v2 root, gates false; the payload delta is 4 rows, the nested delta 7; immutables now include the canonicalizer and `scheduling_revision`.
14. **ACTUAL-SOURCE-MUTANTS** (10):
    - the v1 eight;
    - **`calendar_list_primary_flag_dropped`** (behavioral);
    - **`revision_equality_dropped`** (structural).
    
    Every anchor is unique.

## Not proved
- Execution of `_run_np_v_google_refresh`.
- Production refresh, alias canonicalization, import, revision bumps, coverage and assessment.
- The 4-exchange order, `preflight_effects`, and the TOKEN and PARENT sequences, which are source-derived inferences.
- Native TLS and timing, and any T06 requirement.

## Limits
135 s nominal. Capture is 64 KiB per stream and the result 256 KiB. No temporary files. Runtime provenance is partial.

## Future command
`Future-Command-HELD.ps1.txt`. **Not authorized.**
