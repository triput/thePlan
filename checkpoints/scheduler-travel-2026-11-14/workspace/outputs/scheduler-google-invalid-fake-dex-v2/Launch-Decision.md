# NP-V-GOOGLE-INVALID: focused fake verification preparation v2 (HELD)

Matt, November 13, 2026. This is for Dex `5FA59395…C5B1`. It's the companion to the native root `scheduler-native-google-invalid-prep-matt-v1` (parent `D9B3B2C0…8533`, 313).

**No execution is authorized.** Nothing here has been imported, parsed, compiled or run. Both admissions have `launch_authorized=false`, and no PASS is claimed.

## Roles and pins
- **Immutable, byte-identical** to the proven Google fake roles: wrapper `AE84E632`, outer `7DCA32E2`, launcher `D22C37E3`.
- **New:**
  - checker `2226AE06…CC6D`;
  - EXPECTED `24FD0535…5EFE`;
  - OUTER `AE7B0C21…75ED`;
  - VERIFICATION `5CD93974…9E7F` (34 packet pins and 9 partial runtime pins: interpreter, DLL, json ×3, `dataclasses.py`, `ast.py`, `typing.py`, `textwrap.py`).

## Controls: 10 top-level, 47 nested (focused; the unchanged Google success helpers are not re-proved)
1. **SUBJECT-PINS** (1): 28 subjects, including 7 unchanged production files that define the contract.
2. **RUNTIME-PROVENANCE** (4, partial).
3. **DIFF-REDERIVATION** (3): runner (3 hunks), suite, and the CRLF runner-config.
4. **PRESERVED-OUTSIDE-CHANGE** (3):
   - the runner adds exactly 6 units and changes only the implemented set and the mapper;
   - 11 existing bodies and helpers are byte-identical (including the Google success and Microsoft cases);
   - the transcript is unchanged, and the suite changes only its note.
5. **TRANSCRIPT-INVALID-SCRIPT** (2, behavioral): the actual unchanged `google_token_invalid_grant_script` runs in a **registered** ModuleType, and the actual serializer gives a complete fixed-length 400 (`Content-Length` equals the body length, exactly one CL header), not a close-delimited body.
6. **PRODUCTION-CONTRACT** (6, structural, with ordered unique anchors):
   - the transport maps only a complete fixed-length 400 `invalid_grant` to the typed reauthorization, and any other OAuth error to UNKNOWN;
   - the adapter maps to `TokenRejected(DISCONNECTED)` with `changed=False` and requires a ROLLBACK acknowledgement;
   - dispatch's static preflight → `continue` comes before `run_target`, then ASSESSMENT;
   - the preflight literal matches;
   - `no_op` and the preflight row mapping;
   - the exception's module and name.
7. **CASE-WIRING** (11, structural; the case body is not executed):
   - the mapping;
   - the oracle name;
   - production ingress with default TLS, the token route and invalid script, and no legacy shortcut;
   - one retirement;
   - the constants;
   - the seed signature with primary planting in setup only;
   - free names;
   - observers installed **inside** the `try`, restored in `finally`, identity-guarded, with an outer defensive restore;
   - exact public and native guards;
   - exact state, revision and unrelated guards;
   - the peer guard.
8. **RECEIPT-RETENTION** (2): every emitted key passes the actual `_forbidden_key`. The oracle-name drop is disclosed, and the actual `redact_mapping` keeps `token_terminal` and `covering_token_terminal`.
9. **CONFIG-AND-IMMUTABLES** (6): gates false, the single-case batch, payload delta 3, nested delta 6, the 234 API files plus the transcript, peer, seed and sanitizer immutable.
10. **ACTUAL-SOURCE-MUTANTS** (9). Each anchor must be unique **within its unit**.
    - **Behavioral (2):** `invalid_grant_body_changed`, `covering_token_key_unallowlisted`.
    - **Structural (7):** `success_outcome_admitted`, `revision_bump_tolerated`, `parent_check_dropped`, `client_outcome_loosened`, `token_restore_dropped`, `second_retirement`, `unrelated_owner_check_dropped`.

## Not proved
- Execution of the case body.
- Production typed reauthorization, TOKEN rollback, the skipped IMPORT and PARENT, the not-ready readiness values, and unchanged persisted state.
- CoveringHTTP's framing of the 400, native TLS and timing, and any T06 requirement.

## Limits
135 s nominal (120 + 5 + two 5 s). Capture is 64 KiB per stream and the result 256 KiB. No temporary files.

## Future command
`Future-Command-HELD.ps1.txt`. **Not authorized.**

## v2 correction (Dex `C966DF77`)
- **v1 fake `5AE07428` is preserved, unrun and superseded.** Its `check_contract` compared LF literals against the raw CRLF `app/covering_refresh.py` (804 CR / 804 lines), so `contract:public mapping` would have STOPped on valid bytes.
- **The exact executable change is one line,** checker `6A5F2D26` → `2226AE06`: `refresh = subject_text("app/covering_refresh.py").replace("\r\n", "\n")`, plus a two-line comment.
- **The CRLF-to-LF view is scoped to that literal contract comparison only.** Raw subject pins, the bare-CR refusal, raw AST text and the literal diff re-derivation are unchanged.
- **In the LF view both anchors count exactly 1.** No other literal comparison touches a CRLF subject: the other 6 production subjects are LF, and the JSON and manifest reads are newline-agnostic.
- **Unchanged:** all 10 controls, 47 predicates, 9 mutants and every assertion, plus the 28 subjects, the immutable helpers and the native root `D9B3B2C0`.
- **Labels:** EXPECTED and both admissions are relabelled v2. The checker's `PACKET_NAME` stays at its v1 provenance label, to keep the executable delta to one line.
