# T05 fake v3: CURRENT preparation README

Matt, November 12, 2026. Assignment `Matt-thePlan-Scheduler-T05-V3-Preparation-2026-11-12.md` (`7F1852AF…8FBC`). It runs under Trish's approved consolidated scope `389A00DD…7E2D` (approval `5D1EA2F9…0CA4`): role 13 `verify/check_native_provider.py`, plus data, as a routine same-contract fresh copy.

**Status: PREPARED_NOT_EXECUTED, frozen, no active writer.** Both admission `launch_authorized` flags are **false**, and native flags are false. Nothing was imported, parsed, compiled, tested or invoked. **No PASS is claimed.**

## Current versus historical
- **Current:** this README, `T05-V3-Freeze.json` and `Future-Command-HELD.ps1.txt` (rewritten for v3: the v3 wrapper, admission `4BEB687B…5F5D`).
- **Historical (copied, not current authority):**
  - **v2:** `T05-V2-PREP-README.md` and `T05-V2-Freeze.json`;
  - **v1:** `Launch-Decision.md`, `Reviewed-Command.ps1.txt` (v1 wrapper; do not use), `Static-Staging-Receipt.json`, and under `packet/`: `TIP-FREEZE.json`, `HANDBACK.txt`, `ARTIFACT-HASHES.txt`, `Static-Preparation-Receipt.json`, both `Mutable-Role-Hashes.json`, `docs/Mutable-Roles.md` and `docs/Exact-Diffs-Summary.md`.
  - No executable reads these.
- **The rejected staging copy** `scheduler-native-provider-t05-fake-dex-v2` is untouched.

## Exact delta from v2 (`scheduler-native-provider-t05-fake-v2`, 289/289 verified before copying, manifest `103B3561…02A6`)
Under `packet/`, exactly three files differ:
1. **`verify/check_native_provider.py`:** `099BC9A4…825F` → **`BF5E28A98C2533C967FF1DD51EDE63D9F50885627B656937D9CE7DFAE24D7F64`**, via the approved diff `Proposed-T05-Oracle-Constructor.diff` (`09DFA0B7…6933`, applied with `patch -p1`). Line 920 only:
   ```
   -        if f'name="{name}"' not in suite and f"name='{name}'" not in suite:
   +        if f'name="{name}"' not in suite and f"name='{name}'" not in suite and f'_o("{name}"' not in suite:
   ```
   - This fixes **B3**. Statically, suite line 255 `_o("classified_distinct_from_malformed_and_asgi_disconnect")` contains the accepted substring, and `_o` returns `Oracle(name=name)` (suite line 52).
2. **`verify/OUTER-ADMISSION.json`:** checker pin → `BF5E28A9…`; v3 labels (`t05_note`, `note`); `launch_authorized` stays false. New hash **`3F9DE7E1393D38326313559E08C5B5C8C2E90506990F5DA6720CAAA259B65289`**.
3. **`verify/VERIFICATION-ADMISSION.json`:** checker pin → `BF5E28A9…`; OUTER pin → `3F9DE7E1…`; v3 `note`; `launch_authorized` stays false. New hash **`4BEB687B61A684C06FE254C52095EFB984C96FAAD1571FADCD31E13B07364F5D`**.

**Unchanged:**
- launcher `D22C37E3…BD07`, EXPECTED `080268BC…260A`, wrapper `9AE55D26…`, outer admission script `08975D02…`;
- suite `np_suite.py` `617D381A…E562` and every fixture, API and subject byte;
- the runtime inventory (1 record, interpreter `5F7B89A6…`) and the 23 packet pins (re-verified);
- all 17 top-level and 19 nested control IDs and assertions.

## Deferred, per assignment (not changed)
- H1: no `sys.modules` save/restore.
- H2: the dead loop at lines 842–848 is left.
- H3: the docstring wording is left.

## Accurate classification of the 19 nested T05 controls
- **15 are actual extracted-helper behaviors with fakes.**
- **2 are structural checks:** R3-DOUBLE-RETIRE-GUARD-PRESENT and R4-NOW-FALLBACK-ABSENT.
- **2 are separately authored hole demonstrations:** R1-UNKNOWN-UNWRAP-MUTATION-HOLE and R2-MEASURED-GUARD-MUTATION-HOLE.
- No actual-source mutant is claimed.
- T05-CLOSURE-FOCUSED stays last (17th), and no later control depends on the removed module stubs.

## Retained gap
The T05-SHORT-LENGTH-INVALID-JSON combined witness gap (from the property-reuse overlay) is **not** filled by this packet. All of T05 can't be closed here, and T05 stays on the pre-diagnostic runner `9C0F8573…` until native lineage reconciliation.

## Chain, limits and evidence
- **Acyclic chain:** the wrapper takes the VERIFICATION hash; VERIFICATION pins 23 files (including OUTER) plus 1 runtime file; OUTER pins the launcher, checker, EXPECTED and interpreter.
- **Timing:** 120 s, plus at most one 5 s kill/wait, plus two 5 s reader joins: **135 s nominal**. Startup, hashing, I/O and OS latency are excluded; no separate outer timeout.
- **Capture:** 64 KiB per stream and 256 KiB for the result.
- **Exclusive evidence:** `packet/verify/FAKE-NATIVE-PROVIDER-RESULT.json` and `…-LAUNCH-RECEIPT.json`, both absent.
- **On failure:** stop and preserve; no retry or cleanup.
- `Input-Manifest.sha256` covers 289 files relative to `packet/`. Top-level documents are pinned by the handback's hash manifest.

## Proof boundary
- **Static:** B1, B2 and B3 are resolved by source and data inspection.
- **Not run:** this checker has never executed in the T05 lineage, so the 17 and 19 controls are behaviorally unproved.
- Fake helpers are not native TLS proof.
