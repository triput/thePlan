# Matt → Dex: NP-T03 B2a preparation v1 and focused fake (HELD, frozen)

November 13, 2026. This responds to `Matt-thePlan-Scheduler-T03-B2a-Preparation-2026-11-13.md` (`21BBE5B7E1CABBFDCE8EC221E1FA460CCD2117F78417D7C4A9021707742D48BD`), under Trish-approved decision D1 `D46E6CF8…FFE9` and lane `389A00DD…7E2D`.
- **Prose nit acknowledged:** in my v2 review's opening snapshot, "no receipt" should have read "no receipt in v2's runnable `verify/`". v1's failed receipt is preserved.
- **BODY-STALL:** Dex's dataclass-module finding is confirmed against the installed `dataclasses.py` l.712. My BODY-STALL copies are untouched.

**Status:** PREPARED_NOT_EXECUTED. Two fresh frozen roots, no active writer, endpoint unbound.
- **Method:** copy, text, hash and JSON authoring. Nothing was imported, parsed, compiled, tested or invoked. No PKI, socket, temporary fixture generation or subagents.
- **Unexecuted:** syntax and behavior.
- **No STOP condition was hit:** the passed source supports D1 within roles 4, 5 and 8 plus finite data. The peer, routes, PKI and application are unchanged.
- **Not merged:** T05, BODY-STALL, T03-B2b and B3.

## 1. Native root `outputs/scheduler-native-provider-t03-b2a-prep-matt-v1`
- **Source:** `scheduler-native-ms-nonexpired-retirement-launch-matt-v2`, `C62FDA91…F2BA`.
  - It verified 301/301 before the copy and again after the work.
  - I copied manifest-listed inputs only. Its `.evidence` (the passed run) was not copied and is preserved.
  - Runner `A2C32A20`, peer `17EA148E` (used as-is, not `BFB271D7`).
- **Exact diff:** `Matt-thePlan-Scheduler-T03-B2a-Prep-V1-2026-11-13.diff` (`8231C51175E1492B0529B9801D75B242CB167FC4869F0BFEEA6C7052D6757FA2`, 479 lines).

| Role | File | Before → after |
|---|---|---|
| 4 runner | `np_runner_entry.py` | `A2C32A20` → **`B9CF830D37B5F9B6E4D24E361C11C2069BC0E0DF692F418E6CB4AF25D52500A4`** |
| 5 suite | `np_suite.py` | `AEC59FCD` → **`F7303ADD3B90F3C8FE531CE26C2FC00C023A747D983F99A9DAD177684AB3478C`** (notes only) |
| 8 transcript | `np_provider_transcript.py` | `CFAB2D06` → **`7EF0CCA026D2A0243102290B7AE393D86F95D09ADD5C672C6AE4820AC07071F3`** |
| data | `runner-config.json` (CRLF kept) | `8668F156` → `FF286F1ECE29775EC84592B221180B08FB88C1160F9479BD810435ED3AE35561` |
| data | `launch-config.json` (CRLF kept) | `03A131BC` → `F137A0154EAA5672B88F7352F54873E96AC330B763BD9B8067BE41B83614FDB0` |
| data | `docker-ops-config.json` | `5E6CEDCB` → `F4EFDC381BB8C45DEA65F44706C55C8A2B88D1183E3C262041CF06294949ECA2` |

**Re-pinned:**
- payload **`79810C46C3F42EB25C3B3A0BE4720960D5A5CD897F7AF4565BD20762BCD2F195`** (257; 4 rows);
- nested **`538DB16FC2BD16E32A8ED8DC272456197855A79C97EA7219E475DFF201E6C061`** (269; 7 rows);
- parent **`898FAF785D34D9C187E1253C155AAD4F26F689662B395DA381E23BE118CE99EE`** (305: 293 same, 8 changed, 4 added).

**Role 8:** `t03_valid_fixed_length_get_script()`:
- GET `/calendar/v3/calendars/primary/events` (the path the T05 scripts already admit);
- 200 `{}`, with Content-Length `PLACEHOLDER` → 2;
- `orderly_close_notify`.

All three cases share the script.

**Role 4 (additive; every existing body and the positive helper are byte-identical):**
- **`_retire_negative_peer_then_observe(peer, *, allowed_worker_errors, expected_phase, join_seconds)`:** the D1 barrier.
  - One unchanged `retire_owned`; `PeerRetirementUnknown` and anything else propagate.
  - **Requires:** `joined is True`; `worker_error_kind` a `str` in the frozen set `{SSLError, SSLEOFError, ConnectionResetError}` (None STOPs); exactly one `worker_error:` note equal to it; then post-join `accepted True`, handshake/request/response False, `bytes_received` and `bytes_sent` 0, `exchange_inventory == []` and `phase_entered == "accepted"`.
  - The checks run in memory only, with no new STOP fields. The set is a fail-closed hypothesis.
- **`_t03_observe(case_id, expectation)`:** the actual production `CoveringRequestBudget` → `ProviderCounter(approved_provider_limits(), budget.work_remaining)` → `CoveringHTTP` (default JoinedTLS asserted). It uses an `HTTPSPeer` for `www.googleapis.com`, 127.0.0.1:443, with verify-full (the production defaults).
  - **Trust swap:**
    - **WRONG-CA** sets client `ca_file = WRONG_CA_PATH` only, and the peer serves the valid leaf;
    - **WRONG-NAME** builds the peer route with `google_api_route(wrong_name=True)` (served leaf only) and leaves the client route, hostname, SNI and CA unchanged.
    - An explicit single-dimension guard STOPs otherwise. That includes the peer route's `ca_path`, which I added after self-review.
  - **One attempt:** one `SyntheticProviderPeer`, `start_background(PEER_SECONDS_DEFAULT=120)`, and one `http.request("GET", url, purpose="event")`, recording `("exception", class, module)` or `("response", status, body_exact)`.
  - **Retirement:** `retirement_attempted` is marked, then exactly one retirement: the positive helper for VALID, the D1 helper for negatives. A `finally` guard means no second attempt.
  - **Classification happens after the join:**
    - VALID: exactly `("response", 200, True)`, plus 1 admitted/served row (GET with the path), handshake, request and response True, orderly close, and `bytes_sent` equal to the serializer length;
    - negatives: exactly `("exception", "SSLCertVerificationError", "ssl")`;
    - anything else STOPs.
- **Bodies:** `_run_np_t03_case` + `_run_np_t03_valid` / `_run_np_t03_wrong_ca` / `_run_np_t03_wrong_name`; the oracles `handshake_and_useful_app_data` / `refuse_before_useful_application_data` / `refuse` (the suite declarations); `IMPLEMENTED_CASE_IDS`; the mapper.
- **Typed evidence:** `client_outcome`, `trust_swap` labels (no paths, certificates or keys), `peer_retirement` and `peer_post_join` counts and phase. It goes through the unchanged sanitizer, with no token-named keys.

**Data:**
- the batch `np-t03-b2a` is exactly the three IDs, with `expected_unknown []`;
- gates are false (host, staged and runner), and human authority is false;
- a truthful "as authored" note;
- the implemented list includes the three IDs;
- own-root paths;
- docker-ops is a 7-path rename.

**Docs:**
- current: `T03-B2A-PREP-README.md`, `T03-B2a-Prep-Freeze.json` and `T03-B2a-Native-Command-HELD.ps1.txt` (`9C6DB25A2E6100A4E966B8533C698AC502856AF9E884BF89B671145B6E9D673D`: config `F137A015…`, docker `F4EFDC38…`, no ReceiptPath, **not authorized**);
- copied docs are history;
- the evidence root is absent.

## 2. Fake `outputs/scheduler-native-t03-b2a-fake-prep-matt-v1`
- **Immutable:** `AE84E632` / `7DCA32E2` / `D22C37E3`.
- **New:**
  - checker **`DADF50D08D466D1A3D321C5E4C819C748F5364B4B13DE849BCADFDAC90234A32`**;
  - EXPECTED **`87EAA0AE60EDC8EEDE2BDB3D4B10963ACCDDBCFFC8EAAFC0E92A55D437C73030`**;
  - OUTER **`A0EE112F523DFDF9C5A8BD2DF3A5492BA55C0371F86344290E9088DF21479564`**;
  - VERIFICATION **`A5F5CD5ACC1DF856C0E1AA449B63EF25F8B5D9BE32D2FD1CC53F6CB5D67FDAE3`** (29 packet pins and the same 10 runtime pins; both false);
  - manifest **`33BB7CC5F57E2E23823941E3E2E4383C29A276AD72D7305032FE165D38711C6C`** (32).
- **Subjects (22):** runner, transcript and suite (source and candidate), 4 diffs, 6 configs, 4 manifests, and the unchanged peer `17EA148E`, routes `9CBDE09C` and sanitizer `69F59AF1`.
- **11 controls / 47 nested:** SUBJECT 1, RUNTIME 7, DIFF 4, PRESERVED 3, NEGATIVE 7, POSITIVE 2, OBSERVE 4, BODIES 3, RETENTION 2, CONFIG 6, MUTANTS 8. Details are in `Launch-Decision.md`.
- **Behavioral checks:**
  - **D1 helper:** each planned class accepted; None, an outside class, a note mismatch, each of 8 advanced or data fields, and unjoined all STOP; an unknown retirement keeps the same object; one retire on every path.
  - **The unchanged positive helper:** keeps refusing a worker error and an unjoined peer.
  - **The actual `_t03_observe`:**
    - the actual routes module and transcript units run **inside privately registered ModuleTypes**. That avoids the BODY-STALL missing-module defect: Sandbox refuses a pre-existing name and removes only its own entries;
    - the actual peer serializer (VALID wire is 91 bytes);
    - named fakes for the peer, HTTP, JoinedTLS, budget and policy;
    - real `ssl` exception classes used as values only;
    - covers VALID wiring, WRONG-CA trust only, WRONG-NAME leaf only, and wrong outcomes STOPping after one retirement.
  - **The actual `redact_mapping`.**
- **Structural checks:**
  - preservation (12 added runner units; the positive helper byte-identical);
  - case mapping and oracle names equal the suite (source and candidate);
  - no schema, setup factory or ASGI;
  - every emitted key passes the actual `_forbidden_key`;
  - configs (gates false, truthful note, 4/7-row deltas, all 234 API files and named helpers immutable).
- **Mutants (8, behavioral):** `class_set_widened`, `none_admitted`, `phase_check_dropped`, `note_check_dropped`, `ca_swap_mixed`, `wrong_name_also_swaps_ca`, `outcome_widened`, `second_retirement`. Every anchor is unique in the whole candidate text, and each mutant has its own failure prefix.
- **Pre-freeze self-review fixes (all three were caught by tracing against this lineage's actual subjects, not memory):**
  - peer `17EA148E` has no `RESPONSE_FRAMING_MODES`;
  - transcript `CFAB2D06` has no `ResponseFraming`;
  - the extractions were corrected, and the peer `ca_path` guard was added to the runner.
- **Held command:** `Future-Command-HELD.ps1.txt` (`-AdmissionSHA256 A5F5CD5A…`). **Not authorized.**

## 3. Grouping, schema and allotments
- **No application work:** the three bodies are direct transport. They don't call `provision_disposable_schema`, a setup factory or ASGI, so the non-idempotent `create_all` doesn't apply and the three can share one batch.
  - The host still creates the DB container (unchanged operator), but these bodies never use it.
  - PKI is generated once before the suite (runner main, l.~1497).
- **Nominal time:**
  - PKI 30 + 5 + two 5 s = 45;
  - three sequential owned peers at 120 + 5 = 375 (real handshakes take seconds);
  - about 420 s within the runner's 600 / suite's 900.
- **Unchanged caps:** 32 Docker commands, 1 MiB per command plus the report.
- **Owned workers:** one `np-peer-NP-T03-*` thread per case, each joined before classification, plus the PKI child and readers. No ASGI worker.
- **Exclusions:** startup, OS, file, hash and receipt time. No outer timeout and no daemon-cancellation claim. Cleanup is success-only and exact-ID; failure cleanup is separate.

## 4. Positive obligations and remaining gaps
- **What NONEXPIRED's native PASS already covers** (reusable at its scope): verify-full JoinedTLS success to the **Microsoft Graph** leaf, plus orderly-close exchanges.
- **What VALID adds:** the Google API vendor SAN leaf with a fixed-length GET, and the positive end-to-end that pairs with the two negatives in one batch.
- **Preparing VALID doesn't authorize running it.** Whether to include it in the first native B2a card, or rely on NONEXPIRED, is your and Trish's decision. I'd keep it: it costs seconds and controls for the negatives' same route and script.
- **Unproved:**
  - native certificate refusal and its exact client class;
  - the peer error class (the D1 hypothesis);
  - alert or reset ordering;
  - timing.
- **Still retained:** B2b TCP-REFUSAL (D3) and B3 HANDSHAKE-STALL (D2/240 s). No T03 family closure; all 76 IDs are retained.

Signed: Matt
