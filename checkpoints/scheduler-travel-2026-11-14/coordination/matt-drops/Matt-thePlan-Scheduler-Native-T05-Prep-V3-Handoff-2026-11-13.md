# Matt → Dex: native T05 preparation v3: B1 and D1 option 2 reconciled (HELD, frozen)

November 13, 2026. This responds to your consolidated review `Matt-thePlan-Scheduler-Native-T05-Consolidated-V2-Review-2026-11-13.md` (`8893E2425DE0F3C67CFC5F68550525A729CEDB1D2E1D038593A60388B69A56F8`) and your reconciliation note `…-T05-V2-Reconciliation-Continue-2026-11-13.md` (`8078967FE2EB5E7BDDFA869DFAF0FB4900B0DE9179954122A862423544C7F4AE`). Same assignment `62E314AB…3B84` and lane `389A00DD…7E2D`.

**Status:** PREPARED_NOT_EXECUTED. The v3 roots are frozen with no active writer, and every gate and admission flag is false. The endpoint is unbound.
- **Authoring only:** ordinary text, hash, JSON, copy and edit. Nothing was imported, parsed, compiled or run.
- **Text and hash checks only:** sha256 manifest checks, plus a `patch` text round-trip of the three regenerated subject diffs into scratch.
- **Preservation:** v1 and v2 (native and fake) are untouched and verify at 0 mismatches.
- **No conflict:** nothing in `8893E242` conflicted with a role, schema or bound, so nothing was widened.

## B1: fake client model now represents the httpx 0.28.1 adaptation
- **Default model:** `run_scenario` now defaults to `AutoLengthHttpxResponse`, and every client case runs under it.
- **What it models (finite scope, documented in the checker docstring and EXPECTED):** non-empty rebuilt bytes content with no Content-Length gains `Content-Length: len(content)`, and an explicit one is kept. Nothing else of httpx is modelled.
- **`close_delimited_accepted` now asserts the adaptation:** the rebuilt response **has** `Content-Length: 2`, while the **scripted wire** has no CL and no TE (status 200, exact `{}`, gate then json). This replaces v2's no-CL assertion on a model that never added one.
- **Kept, and still load-bearing:**
  - the wire predicate;
  - the trap regression: close-delimited `{}` is accepted despite the rebuilt CL, and a wire that really adds CL STOPs under `complete_accept`;
  - all negative and mutation oracles.

## D1 option 2: separately observed exact fixed-length positive
- **Transcript (role 8):** the new `orderly_fixed_length_complete_script()` (`T05-ORDERLY-FIXED-LENGTH-COMPLETE`).
  - Content-Type plus `Content-Length: 2`, body `{}`, framing `auto`, orderly close_notify.
  - It sits in `finite_script_catalog` right after the close-delimited script.
  - The peer is **unchanged:** its auto path keeps the explicit `2` verbatim.
- **Suite (role 5), `NP-T05-ORDERLY-CLOSE`:**
  - `orderly_close_delimited_complete_accepted` gets **planning_ids `()`** (supplementary);
  - the **new** `orderly_fixed_length_complete_accepted` maps `("T05-VALID-COMPLETE-CONTENT-LENGTH",)`, ACCEPTED;
  - `orderly_short_cl_valid_json_prefix_refused` is unchanged;
  - the case planning_ids are `("T05-VALID-COMPLETE-CONTENT-LENGTH", "T05-SHORT-LENGTH-VALID-JSON")`;
  - the notes are updated.
  - **Still 27 + 4 = 31 declarations.** The union of planning IDs over cases and oracles is unchanged, so all 76 are retained. Every other declaration is unchanged.
- **Runner (role 4):**
  - **New framing helper:** the pure `_t05_scripted_wire_framing(scripted_wire, expected_body)` returns `"close_delimited"`, `"exact_content_length"` or `"other"` (`T05_SCRIPTED_WIRE_FRAMINGS`). `exact_content_length` requires exactly one CL line whose digit value equals the body length, no TE, and a wire body equal to the expected body.
  - `_t05_response_outcome` returns `("response", status, body_exact, scripted_wire_framing)` and still never reads `response.headers`.
  - **Classifier:**
    - `complete_accept` needs `(200, True, "close_delimited")`;
    - the **new** `fixed_length_accept` needs `(200, True, "exact_content_length")`;
    - everything else STOPs.
  - **ORDERLY makes three sequential owned-peer observations:** close-delimited/`complete_accept`, fixed-length/`fixed_length_accept`, short-CL/`short_cl_refuse`. There are three receipts' worth of measured data, inventory and retirements.
  - The measured field is now `scripted_wire_framing` (a class string).
- **Bounds (truthful):** the batch now owns **4 sequential peers**, 3 ORDERLY plus 1 ABRUPT.
  - **Peer side:** 4 × (120 s + 5 s join) = 500 s, within `runner_seconds` 600 (runner-config unchanged).
  - **Client side:** each request is separately bounded by its own `CoveringRequestBudget`.
  - **Hard bound:** the 600 s supervisor; its expiry is UNKNOWN, never PASS.

## D2
- **Class set unchanged:** `{SSLEOFError/ssl, ConnectionResetError/builtins}`, fail closed, no widening.
- **Claim scope:** the peer bytes and abrupt script are peer-side stimulus only. Claims cover the client's actual EOF outcome class only.

## Native root `outputs/scheduler-native-provider-t05-prep-matt-v3`
- **Copy:** v2's 291 inputs, verified 291/291. Lineage: `Source-T05-Prep-V2-Input-Manifest.sha256`.
- **Changed vs v2 (roles 4, 5 and 8 only):**
  - runner `EB76303F` → **`1D70164C8EFD7D1CD0A9ED59F23D9F8A4ED9F68B806364B366E2E707259AAA7E`**;
  - suite `E5C63D9C` → **`9AED74EE4F00C5F88518A1B246D7B03D5E82C05DDF3596958D5483730C376792`**;
  - transcript `46455CD6` → **`562F61CDB9DEF3F35A1693E3C9CC13EB63D9F0535F9A0D3C190BF275E78751BF`**.
- **Byte-identical to v2:** the peer `BFB271D7`, runner-config `96782CB4`, all 234 API files and all helpers.
- **Re-pinned:**
  - payload `SHA256SUMS.txt` **`D03EA0D671DF61AB3E66B2E3B96D34B72AC9BDAF6282676A8A1328DEF853B0C5`** (257, 0 mismatches);
  - launch-config **`FB7968294F521E6155C70CF7EB2588FCF28791E58F3DCDA88C2D07CD616DCD43`** (root rename, payload pin and candidate note);
  - docker-ops **`E90A4512AED3A198AB6BA2D2F95842F96B1B7652D224D99CF528A21BE343CCA8`** (root rename);
  - nested manifest **`4E190C4F82A75BF861338F4AC7993EB1721EEA104C64B45CA6E06E67ED93DD93`** (269, exactly 6 rows changed);
  - parent **`B773B95E5B15998CEB2A356C7B3F58392CD43BD1F037DB66D4A0914A87A8E59B`** (292; 10 changed and 1 added versus v2).
- **Evidence root:** absent.
- **Current docs:** `T05-PREP-README.md` (with a v3 section), `T05-Prep-Freeze.json` (supersedes v2; bounds block) and `T05-Native-Command-HELD.ps1.txt` (`-ExpectedConfigSHA256 FB796829…`, `-ExpectedDockerConfigSHA256 E90A4512…`, the v3 `-DockerConfigPath`, no `-ReceiptPath`). **Not authorized.**

## Fake `outputs/scheduler-native-t05-fake-prep-matt-v3`
- **Roles:**
  - reused byte-identical: AE84 wrapper, 7DCA outer, D22C launcher;
  - checker **`991CF4E99E1B422DF044A623ED6807920E04D67D1848E49BF503D56A07776460`**;
  - EXPECTED **`811AC4866B95492DD6C4AE291FBD8F2B3F0D28D3D0659C5E521EDEEA556B4A7B`**;
  - OUTER **`99A66DA71F1A32137617A68D31BA489CABBBA86AFFB788006165281FB3572124`**;
  - VERIFICATION **`06873FB0FDC86D3719636EF14900B344178EF3835B75F482DE7B32381FE260F9`** (28 packet pins re-verified, plus the same 10 runtime pins; both false);
  - manifest **`090D0758E9F20CF99EE17A934BE0BD3BB3A8F14DB01403A57C8D1FA6F22DD117`** (33).
- **Subjects refreshed:**
  - runner, suite and transcript candidates;
  - cumulative MS-merge → v3 diffs: runner `F646720F` (3 hunks), transcript `97DF0CD7` (5), suite `A1CD1378` (3);
  - launch-config `FB796829`;
  - payload manifest `D03EA0D6`.
  - The peer and runner-config diffs are unchanged.
- **Inventory: 14 controls, 74 nested (v2: 13 / 60).**
  - **SERIALIZER-DEFAULT-REGRESSION:** `catalog_delta_changed_plus_added`. Changed is `[CLOSE-DELIMITED-COMPLETE]`, and added is `[FIXED-LENGTH-COMPLETE]` right after it. Every common script's wire is still source-identical.
  - **ORDERLY-POSITIVE-SERIALIZATION** (renamed): adds fixed-length exact bytes (`…Content-Length: 2\r\nConnection: close\r\n\r\n{}`), which the source serializer reproduces identically.
  - **CLIENT-COMPLETENESS-VS-DECODE:**
    - B1 `close_delimited_accepted`, as described above;
    - the **new** `fixed_length_accepted`: actual transport and host parser, giving `exact_content_length`; accepted only under `fixed_length_accept`, STOP under `complete_accept`;
    - the trap: the close-delimited outcome STOPs under `fixed_length_accept`, and a real CL wire gives `exact_content_length`, which STOPs under `complete_accept`.
  - **OUTCOME-CLASSIFIER** (9): adds the `fixed_length_accept` exact case and its mismatch STOPs. Stale boolean shapes STOP.
  - **SUITE-ORDERLY-MAPPING** (new, 5), a whole-module load of the source and candidate `np_suite`:
    - `validate_inventory_counts` gives 27 + 4, with the same order;
    - the planning-ID union is unchanged;
    - the close-delimited oracle is unmapped;
    - VALID-COMPLETE-CL is held only by the new oracle;
    - ORDERLY is exact, and the other 30 declarations are identical.
  - **RUNNER-WIRING:** adds `orderly_three_observations`, three `_t05_observe` calls in order with exact (script, expectation) pairs, and observation keys equal to the oracle names.
  - **ACTUAL-SOURCE-MUTANTS** (10):
    - `wire_framing_predicate_dropped` (now: the helper is bypassed, forcing `close_delimited`) → "client:rebuilt trap negative";
    - **`framing_conflation`** → "client:fixed length accepted";
    - **`orderly_mapping_swapped`** → "mapping:close_delimited_oracle_unmapped";
    - **`fixed_expectation_swapped`** → "wiring:orderly_three_observations".
  - **PRIOR-FAKE-APPLICABILITY:** lists the superseded v2 client and delta claims as non-transferred.
- **Held fake command:** `Future-Command-HELD.ps1.txt` → `…\scheduler-native-t05-fake-prep-matt-v3\packet\Invoke-Fake.ps1 -AdmissionSHA256 06873FB0…`. The current description is in `Launch-Decision.md`.

## Exact diffs (in Matt-Drops)
- **`Matt-thePlan-Scheduler-Native-T05-V2-to-V3-2026-11-13.diff`** (`106C4AA2…2E67`): runner, transcript, suite, checker and EXPECTED, v2 → v3.
- **`Matt-thePlan-Scheduler-Native-T05-Prep-V3-2026-11-13.diff`** (`1DB14ABB…67A0`): cumulative from the MS-merge NONEXPIRED source to v3 for the runner, peer, transcript, suite and runner-config. These are exactly the fake's five subject diffs.

## Not claimed
- No runtime PASS and no native proof.
- No claim about how far the client got into the headers or body.
- Full T05 is not closed: the other 11 T05 planning IDs keep their existing dispositions.

## Preservation
All verify at 0 mismatches:
- v1 roots: native `704A16D1`, fake `4C556393`;
- v2 roots: native `C36E3078`, fake `C1FB0387`;
- MS-merge NONEXPIRED `22AE4F82` and REFRESH `9A62B5C4`;
- the merge fake `9290909C`, combined-witness fake `7BA33B54` and peer-close fake `52D24FDD`.

The pending three-fake decision is unaffected; none of those packets was run. The endpoint is unbound, and all other holds stay.

Signed: Matt
