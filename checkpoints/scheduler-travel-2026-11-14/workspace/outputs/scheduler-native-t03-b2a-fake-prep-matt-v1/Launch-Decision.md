# Native T03 B2a: focused fake verification preparation v1 (HELD)

Matt, November 13, 2026. This is for Dex `21BBE5B7…48BD`, under Trish-approved decision D1 `D46E6CF8…FFE9`. It's the companion to `scheduler-native-provider-t03-b2a-prep-matt-v1`.

**No execution is authorized.** Nothing here has been imported, parsed, compiled or run. Both admissions have `launch_authorized=false`, and no PASS is claimed.

## Roles and pins
- **Immutable, byte-identical:** wrapper `AE84E632`, outer `7DCA32E2`, launcher `D22C37E3`.
- **New:**
  - checker `DADF50D0…4A32`;
  - EXPECTED `87EAA0AE…3030`;
  - OUTER `A0EE112F…9564`;
  - VERIFICATION `A5F5CD5A…FDAE3` (29 packet pins, the same 10 partial runtime pins).

## Controls: 11 top-level, 47 nested
1. **SUBJECT-PINS** (1).
2. **RUNTIME-PROVENANCE** (7, partial).
3. **DIFF-REDERIVATION** (4): runner, transcript, suite and the CRLF runner-config.
4. **PRESERVED-OUTSIDE-CHANGE** (3, structural):
   - the runner adds exactly 12 units and changes only `IMPLEMENTED_CASE_IDS` and the mapper;
   - the positive helper is byte-identical;
   - the transcript adds 3 units, and the suite changes only its notes.
5. **NEGATIVE-HELPER** (7), using the actual D1 helper with a named fake peer:
   - each planned class in the frozen set is accepted;
   - None STOPs;
   - an outside class STOPs;
   - a note mismatch STOPs;
   - each of 8 advanced or data-bearing state fields STOPs;
   - unjoined STOPs, and an unknown retirement keeps the same object;
   - exactly one retire on every path.
6. **POSITIVE-HELPER-PRESERVED** (2): the actual unchanged helper accepts a clean joined peer and refuses a worker error or an unjoined peer.
7. **OBSERVE-WIRING** (4), using the actual `_t03_observe` over the **actual routes module and transcript units, registered as private ModuleTypes**, the actual peer serializer, and named fakes for the peer, HTTP, JoinedTLS, budget and policy:
   - VALID: one attempt and one retirement, `start:120`, the exact URL, verify-full identity;
   - WRONG-CA: changes client trust only;
   - WRONG-NAME: changes the served leaf only (hostname unchanged, peer CA unchanged);
   - a wrong client outcome STOPs after exactly one retirement.
8. **CASE-BODIES** (3, structural):
   - an exact mapping of IDs to expectations;
   - oracle names equal the suite declarations (source and candidate);
   - no schema, setup factory or ASGI.
9. **RECEIPT-RETENTION** (2): every emitted key passes the actual `_forbidden_key`, and the actual `redact_mapping` keeps typed evidence while dropping `private_key`.
10. **CONFIG-AND-IMMUTABLES** (6):
    - runner-config and launch-config (gates false, truthful note);
    - the docker rename;
    - a 4-row payload delta and a 7-row nested delta;
    - all 234 API files, plus the peer, routes, sanitizer and helpers, immutable.
11. **ACTUAL-SOURCE-MUTANTS** (8, all behavioral): `class_set_widened`, `none_admitted`, `phase_check_dropped`, `note_check_dropped`, `ca_swap_mixed`, `wrong_name_also_swaps_ca`, `outcome_widened`, `second_retirement`. Every anchor is unique in the whole candidate text.

## Not proved
Native certificate verification, the actual OpenSSL/TLS client and peer exception classes, alerts, timing, and any T03 requirement.

## Limits
135 s nominal (120 + 5 + two 5 s). Capture is 64 KiB per stream and the result 256 KiB. No temporary files. Runtime provenance is partial.

## Future command
`Future-Command-HELD.ps1.txt`. **Not authorized.**
