# NP-V-GOOGLE-REFRESH: focused fake verification preparation v1 (HELD)

Matt, November 13, 2026. This is for Dex `CEBD83C3…6570` (Google-first). It's the companion to the native root `scheduler-native-google-refresh-prep-matt-v1` (parent `06703C09…6F35`).

**No execution is authorized.** Nothing here has been imported, parsed, compiled or run. Both admissions have `launch_authorized=false`, and no PASS is claimed.

## Roles and pins
- **Immutable, byte-identical:** wrapper `AE84E632`, outer `7DCA32E2`, launcher `D22C37E3`.
- **New:**
  - checker `972C6196…00D0`;
  - EXPECTED `F163D9B3…4915`;
  - OUTER `8075731A…4305`;
  - VERIFICATION `7287F336…4B09` (32 packet pins and 10 partial runtime pins: interpreter, DLL, json ×3, `urllib/parse.py`, `datetime.py`, `dataclasses.py`, `ast.py`, `typing.py`).

## Controls: 13 top-level, 57 nested
1. **SUBJECT-PINS** (1): 26 raw subject pins, including unchanged production `google_calendar.py` `8A335971`, `export_baseline.py` `39EB4E58`, `covering_refresh_window.py` `7E39381B` and `np_auth_seed.py` `66FEEA81`.
2. **RUNTIME-PROVENANCE** (4, partial): the json trio, plus a disclosure of the unpinned modules.
3. **DIFF-REDERIVATION** (4): runner (3 hunks), transcript, suite and the CRLF runner-config.
4. **PRESERVED-OUTSIDE-CHANGE** (3):
   - the runner adds exactly 15 units and changes only `IMPLEMENTED_CASE_IDS` and the mapper;
   - 7 reused helpers are byte-identical;
   - the transcript adds 9 units, and the suite changes only its notes.
5. **TRANSCRIPT-SCRIPTS** (5, behavioral; actual units in a **registered** `np_provider_transcript` ModuleType, plus the actual peer serializer):
   - token body keys and values, and the Content-Length framing;
   - the busy-event shape, refusing non-Z or unordered instants;
   - the events path `quote(id, safe='')` and the exact query, refusing empty, `?` and `#`;
   - the 3-exchange ordered inventory, refusing 1 or 3 calendars;
   - the peer's exact-query semantics are present.
6. **ROUTES-AND-QUERY** (4, behavioral; actual production `_iso_z`, then `google_mirror_datetime_token`, then `_ensure_aware_utc`, plus the whole registered window module):
   - routes are only `/token` (oauth) and the events prefix (event), with no identity route;
   - the exact literal query, keeping microseconds;
   - a +02:00 input normalizes to the same literal;
   - the params AST mirrors production `list_calendar_events`.
7. **CREDENTIAL-MEASUREMENT** (5, behavioral; named ORM and token_crypto fakes):
   - the seed state;
   - the refreshed and rotated fields are each independent;
   - a naive expiry is read as UTC, plus the absent and missing-account cases;
   - no plaintext or ciphertext is emitted;
   - the seed literals equal `np_auth_seed`.
8. **EVENT-MEASUREMENT** (2): the account filter and sort, and UTC normalization and flags, in the same form as the expected list.
9. **PARENT-OBSERVER** (3): the same return, the same exception object, installed and then restored to the identical function.
10. **CASE-WIRING** (10, structural; the case body is **not** executed):
    - the mapping;
    - oracle names equal the suite (and the receipt observation carries only `owning_google_refresh`);
    - production ingress with `clock=monotonic` and default JoinedTLS;
    - exactly one helper retirement plus one guarded cleanup retirement;
    - literal sequences and summary;
    - seed kwargs and attributes match the signature;
    - free names resolve;
    - exact unrelated, semantic-credential and event guards;
    - the exact peer-inventory guard;
    - observers restored in the `finally` around the POST.
11. **RECEIPT-RETENTION** (2): every emitted key passes the actual `_forbidden_key`. The actual `redact_mapping` keeps `token_terminal`, and drops `token_terminal_sequence` and `token_commit_not_ms_proof`, as disclosed.
12. **CONFIG-AND-IMMUTABLES** (6):
    - runner-config and launch-config (gates false, truthful note);
    - the docker 7-path rename;
    - a 4-row payload delta and a 7-row nested delta;
    - all 234 API files, plus the peer, seed, sanitizer and helpers, immutable.
13. **ACTUAL-SOURCE-MUTANTS** (8):
    - **behavioral:** `refresh_token_omitted`, `query_param_changed`, `rotated_compared_to_access`, `parent_exception_swallowed`, `event_sort_dropped`;
    - **structural:** `token_key_unallowlisted`, `second_retirement`, `unrelated_events_check_dropped`.
    
    Every anchor is unique in its whole candidate text.

## Not proved
- Execution of `_run_np_v_google_refresh`.
- Production refresh, persistence, import mapping, coverage and final assessment.
- CoveringHTTP's `urlencode` wire form.
- The TOKEN and PARENT sequences, `upserted=1` and the provenance, which are source-derived inferences.
- Native TLS and timing, and any T06 requirement.

## Limits
- 135 s nominal (120 + 5 + two 5 s).
- Capture is 64 KiB per stream and the result 256 KiB.
- No temporary files.
- Runtime provenance is partial.

## Future command
`Future-Command-HELD.ps1.txt`. **Not authorized.**
