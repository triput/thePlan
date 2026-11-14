# NP-V-MS-REFRESH focused fake verification: preparation (HELD)

Matt, November 12, 2026. Companion to the fixture preparation `outputs/scheduler-ms-refresh-prep-matt-v1`.

**No execution is authorized.** Nothing here has been imported, parsed, compiled or run. Both admissions have `launch_authorized=false`. No PASS is claimed.

## Roles
| Role | File | Hash | Origin |
| --- | --- | --- | --- |
| Wrapper | `packet/Invoke-Fake.ps1` | `AE84E632…FEB7` | byte-identical reuse |
| Outer admission | `packet/verify/verify_admission.py` | `7DCA32E2…18FB` | byte-identical reuse |
| Launcher | `packet/verify/launch_check.py` | `D22C37E3…BD07` | byte-identical reuse |
| Checker | `packet/verify/check_native_provider.py` | `532D8741…356C` | new |
| Expected inventory | `packet/verify/EXPECTED-FAKE-STRUCTURAL.json` | `FD98745D…DB71` | new |
| OUTER admission | `packet/verify/OUTER-ADMISSION.json` | `D2E3A414…F56B` | new, false |
| VERIFICATION admission | `packet/verify/VERIFICATION-ADMISSION.json` | `E2779EFF…8346` | new, false; 18 packet pins + 1 runtime pin |

**Subjects** (raw copies, pinned by both the admission and the checker):
- **candidate** fixture roles 4, 5, 6, 8 and 10, plus the unchanged peer;
- **source** baseline copies of roles 4, 5, 6, 8 and 10 (from the diagnostic launch packet);
- **production** `microsoft_calendar.py` `6A52B10F…`.

**Acyclic chain:** the wrapper takes the VERIFICATION hash; VERIFICATION pins OUTER; OUTER pins the checker, launcher, expected inventory and interpreter.

## Controls (10 top-level, in order; each labeled with its proof layer)
1. **SUBJECT-PINS** (raw_pin).
2. **NONEXPIRED-AND-DIAGNOSTIC-PRESERVED** (extracted_text_identity). These are identical between source and candidate:
   - `_run_np_v_ms_nonexpired`, `_ms_provider_routes`, `stop_payload` and the related runner helpers;
   - the seed function and coverage measure;
   - the NONEXPIRED transcript scripts and the invalid-grant script;
   - the receipt builders and suite oracle functions;
   - the `NATIVE_CASES` registry;
   - the seed literals.
3. **TENANT-PATH-AGREEMENT** (extracted_behavior_fake): the actual production `_LOGIN_BASE`, `_normalize_tenant` and `_token_url` versus the actual transcript `ms_token_endpoint_path`, giving `/common/oauth2/v2.0/token`. Five non-normalized tenants are refused.
4. **OAUTH-ROUTE-TABLE** (extracted_behavior_fake): the actual route functions with a fake HTTPSPeer. Three unchanged graph routes plus one distinct `login.microsoftonline.com` OAuth route sharing address, port and CA.
5. **REFRESH-INVENTORY-ORDER** (extracted_behavior_fake):
   - the actual transcript module: five scripts in exact order, with request heads;
   - the Graph scripts equal the NONEXPIRED inventory;
   - the token body equals the declared synthetic values;
   - the actual peer `_http_response_bytes` sends the body verbatim with the rewritten length;
   - non-two calendar lists are refused.
6. **SEMANTIC-PERSISTENCE-ADMISSION** (extracted_behavior_fake): the actual `measure_account_credential_state`, using a fake model and a **randomized** fake crypto. It covers: before seed; after refresh; **changed ciphertext with unchanged plaintext, not admitted**; wrong token; missing rotation; expiry at check+30 s refused; naive UTC; missing expiry, ciphertext or account and a naive reference refused; no plaintext in the projection.
7. **SECRET-EXCLUSION-PROJECTION** (extracted_behavior_fake): the actual `np_receipts`. Declared plaintext and secret values never serialize; the allowlisted `token_commit` and `token_terminal_sequence` and the credential-state keys survive.
8. **REGISTRY-MAPPING** (structural_source): the implemented set, both mapper bindings, and the REFRESH oracle declaration and note.
9. **REFRESH-BODY-SHAPE** (structural_source): required checks are present in `_run_np_v_ms_refresh`; banned constructs are absent; one primary plus one guarded cleanup retirement. **This is shape only, not behavior.**
10. **ACTUAL-SOURCE-MUTANTS** (actual_source_mutant). The real subject text is mutated and must be caught by its targeted oracle:
    - ciphertext-only persistence;
    - legacy token path;
    - missing token script;
    - graph-only routes.

## Not proved by this packet
- native OAuth over JoinedTLS;
- native database persistence and real Fernet;
- the single peer serving both hostnames;
- the second target's ROLLBACK without a request;
- native TOKEN, IMPORT and ASSESSMENT terminals and the runtime response;
- `_run_np_v_ms_refresh` behavior (shape only).

## Limits (inherited launcher)
- **Timing:** 120 s, plus at most one 5 s kill/wait, plus two 5 s reader joins: **135 s nominal**, with the same exclusions and no separate outer timeout.
- **Capture:** 64 KiB per stream and 256 KiB for the result.
- **Success** requires exit 0, no output, joined clean EOF readers and the exact ordered 10-control PASS inventory.
- **Exclusive evidence** is written under `packet/verify/`; a failure stops and preserves, with no retry.

## Future command
`Future-Command-HELD.ps1.txt` (admission `E2779EFF…`). The wrapper refuses while the flags are false.
