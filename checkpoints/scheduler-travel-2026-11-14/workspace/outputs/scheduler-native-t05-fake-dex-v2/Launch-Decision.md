# Native T05 fixture: focused fake verification preparation v3 (HELD)

Matt, November 13, 2026. This is for assignment `Matt-thePlan-Scheduler-Native-T05-Preparation-2026-11-13.md` (`62E314AB…3B84`), revised under Dex's consolidated v2 review (`8893E242…56F8`). It's the companion to the frozen `scheduler-native-provider-t05-prep-matt-v3` (parent `B773B95E…E59B`). Fake v1 and v2 are preserved unchanged.

**No execution is authorized.** Nothing here has been imported, parsed, compiled or run. Both admissions have `launch_authorized=false`. No PASS is claimed.

## Roles and pins
- **Reused byte-identical:** wrapper `AE84E632`, outer `7DCA32E2`, launcher `D22C37E3`.
- **New in v3:**
  - checker **`991CF4E99E1B422DF044A623ED6807920E04D67D1848E49BF503D56A07776460`**;
  - EXPECTED **`811AC4866B95492DD6C4AE291FBD8F2B3F0D28D3D0659C5E521EDEEA556B4A7B`**;
  - OUTER **`99A66DA71F1A32137617A68D31BA489CABBBA86AFFB788006165281FB3572124`**;
  - VERIFICATION **`06873FB0FDC86D3719636EF14900B344178EF3835B75F482DE7B32381FE260F9`** (28 packet pins and the same 10 runtime pins, all re-verified).
- **Runtime (partial scope, unchanged):** `python.exe`, `python311.dll`, `http/client.py`, `json/__init__`/`decoder`/`scanner`, `email/feedparser`/`parser`, `socket.py`, `ssl.py`. Importing `http.client` loads `socket` and `ssl`, but no socket or SSL object is constructed.

## Client model (Dex B1)
The fake `httpx.Response` defaults to **`AutoLengthHttpxResponse`**. It represents the one relevant httpx 0.28.1 adaptation: when production rebuilds the API response with non-empty bytes content and no Content-Length, `Content-Length: len(content)` is supplied; an explicit one is kept.
- **Finite scope:** it models nothing else of httpx (no case-insensitive mapping, multi-valued headers, decoding or streaming).
- **Every client case now runs under it.** `close_delimited_accepted` asserts that the rebuilt response **has** `Content-Length: 2` while the scripted wire is close-delimited (no CL/TE). This replaces v2's assertion of no CL on a model that never added it.

## Controls (14 top-level, 74 nested, in order)
1. **SUBJECT-PINS** (22 subjects).
2. **RUNTIME-PROVENANCE** (7).
3. **DIFF-REDERIVATION** (5): runner (3 hunks), peer (1), transcript (**5**), suite (**3**), runner-config (1). All are cumulative from the frozen MS-merge NONEXPIRED source to the v3 candidate.
4. **PRESERVED-OUTSIDE-CHANGE** (4): exact top-level partitions.
   - **Runner:** adds `T05_SCRIPTED_WIRE_FRAMINGS` and `_t05_scripted_wire_framing`.
   - **Transcript:** adds `orderly_fixed_length_complete_script` and the changed `finite_script_catalog`.
   - **Suite:** `NATIVE_CASES` and `CASE_IMPLEMENTATION_NOTES`.
5. **SERIALIZER-DEFAULT-REGRESSION** (4): every common send step of `finite_script_catalog`, the MS NONEXPIRED and MS REFRESH inventories has equal step fields, framing `auto`, and byte-identical source and candidate wire. **`catalog_delta_changed_plus_added`:** changed is exactly `[T05-ORDERLY-CLOSE-DELIMITED-COMPLETE]`, and added is exactly `[T05-ORDERLY-FIXED-LENGTH-COMPLETE]`, immediately after it.
6. **ORDERLY-POSITIVE-SERIALIZATION** (5, renamed from CLOSE-DELIMITED-SERIALIZATION):
   - close-delimited exact bytes, no CL/TE, and the source serializer would append `Content-Length: 2`;
   - **fixed-length exact bytes:** `…Content-Type: application/json\r\nContent-Length: 2\r\nConnection: close\r\n\r\n{}`, framing `auto`;
   - the source serializer gives identical fixed-length bytes.
7. **INVALID-MODE-REFUSALS** (5): unchanged.
8. **CLIENT-COMPLETENESS-VS-DECODE** (6), the actual transport and policy over the host `http.client`:
   - close-delimited accepted (B1 assertions above);
   - **fixed-length accepted:** 200, `{}`, `Content-Length: 2`, gate then json. The extracted `_t05_response_outcome` gives `("response", 200, True, "exact_content_length")`, which is **accepted only under `fixed_length_accept`** and STOPs under `complete_accept`;
   - short-CL `IncompleteRead` before decode; complete invalid JSON is decoded; transport error propagates (all unchanged);
   - **`rebuilt_content_length_trap`:**
     - the close-delimited result with rebuilt CL 2 classifies `close_delimited`; it is accepted under `complete_accept` and STOPs under `fixed_length_accept`;
     - a wire that really adds CL classifies `exact_content_length` and STOPs under `complete_accept`.
9. **OUTCOME-CLASSIFIER** (9): exact labels for `complete_accept` (`close_delimited`), the new **`fixed_length_accept`** (`exact_content_length`), `short_cl_refuse` and `abrupt_distinct`. Every other framing, body, status, legacy boolean shape, class or expectation STOPs.
10. **SUITE-ORDERLY-MAPPING** (5, new): whole-module load of the source and candidate `np_suite`.
    - `validate_inventory_counts()` gives 27 + 4 = 31, with the same case order;
    - the **union of planning IDs is unchanged**;
    - the close-delimited oracle has `planning_ids ()`;
    - `T05-VALID-COMPLETE-CONTENT-LENGTH` is held **only** by the new fixed-length oracle;
    - the ORDERLY declaration is exact, and all 30 other declarations are field-for-field identical to the source.
11. **RUNNER-WIRING** (7): the v2 checks, plus **`orderly_three_observations`**. Exactly three `_t05_observe` calls, in order: (close-delimited script, `complete_accept`), (fixed-length script, `fixed_length_accept`), (short-CL script, `short_cl_refuse`). The observation keys equal the three oracle names.
12. **BATCH-CONFIG** (3): unchanged logic; own root v3, payload manifest pin `D03EA0D6`, with v1 and v2 roots both foreign.
13. **PRIOR-FAKE-APPLICABILITY** (3): unchanged cases. It adds a non-transferred note: the v2 `close_delimited_accepted` and `changed_script_is_only_delta` are superseded.
14. **ACTUAL-SOURCE-MUTANTS** (10), each detected only by its targeted prefix:
    - the six from v1;
    - `wire_framing_predicate_dropped`, now the helper bypass forcing `"close_delimited"` → "client:rebuilt trap negative";
    - **`framing_conflation`** (`exact_content_length` reported as `close_delimited`) → "client:fixed length accepted";
    - **`orderly_mapping_swapped`** (VALID-COMPLETE-CL moved to the close-delimited oracle) → "mapping:close_delimited_oracle_unmapped";
    - **`fixed_expectation_swapped`** (the fixed-length observation run as `complete_accept`) → "wiring:orderly_three_observations".

## Claims that do NOT transfer (current prerequisite named)
- **Peer-close fake PRESERVED** ("only `_close_connection` differs from `5568`"): the serializer changed too. Prerequisite: SERIALIZER-DEFAULT-REGRESSION.
- **MS-refresh fake v2 OAUTH-ROUTE-TABLE** (it executed the old serializer). Prerequisite: SERIALIZER-DEFAULT-REGRESSION wire equality.
- **MS-refresh fake v2 transcript-derived controls** (`ExchangeStep` gained a defaulted field). Prerequisite: step-field equality plus `transcript_functions_identical`.
- **Merge fake ROLE-SELECTION peer row `17EA148E`:** it doesn't describe this root (peer `BFB271D7`).
- **T05 fake v2 `close_delimited_accepted` and `changed_script_is_only_delta`:** superseded by the v3 cases above.

## Not proved
- **Native behavior:** native TLS close_notify/EOF behavior, the native client classes (D2: abrupt stays `SSLEOFError`/`ConnectionResetError`, fail closed; the peer bytes are stimulus only), native peer retirement.
- **T05 scope:** any T05 requirement beyond these finite fixture properties.

## Limits
- **Timing:** 120 s, plus at most one 5 s kill/wait, plus two 5 s reader joins: 135 s nominal, with no separate outer timeout.
- **Capture:** 64 KiB per stream; 256 KiB for the result.
- **Success** requires exit 0, no output, clean readers and the exact 14-control/74-nested inventory; a failure stops and preserves.

## Future command
`Future-Command-HELD.ps1.txt` (admission `06873FB0…60F9`). **Not authorized.**

## History
- **v1:** `scheduler-native-t05-fake-prep-matt-v1` (`4C556393…`).
- **v2:** `scheduler-native-t05-fake-prep-matt-v2` (`C1FB0387…`): Dex P1 rebuilt-header trap.
- Both are preserved; the lineage manifest is `Source-Fake-V2-Input-Manifest.sha256`.
