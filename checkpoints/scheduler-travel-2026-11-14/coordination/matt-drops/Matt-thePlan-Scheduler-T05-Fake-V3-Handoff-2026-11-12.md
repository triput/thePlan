# Matt → Dex: T05 fake v3 preparation handback (B3 fix)

November 12, 2026, about 21:15 PT. This responds to `Matt-thePlan-Scheduler-T05-V3-Preparation-2026-11-12.md` (SHA256 `7F1852AF3C38C1F69191D0A0B4C117671FF1337F4787CF85CED12A1EBB888FBC`). It runs under approved scope `389A00DD…7E2D` (Trish approval `5D1EA2F9…0CA4`, role 13 plus data, same-contract fresh copy). I worked solo; no subagents were used.

**Status: PREPARED_NOT_EXECUTED, frozen, no active writer.** Both prep `launch_authorized` flags are **false**, and native flags are false. Nothing was imported, parsed, compiled, tested or invoked. **No PASS is claimed.**

## Workspace
`C:/Users/trish/Documents/Codex/2026-10-15/trish-wants-to-improve-dex-s/outputs/scheduler-native-provider-t05-fake-v3`. It didn't exist beforehand.
- **Base** `…-t05-fake-v2` (manifest `103B3561…02A6`): verified 289/289 before copying and after. It is untouched.
- **Rejected staging** `…-t05-fake-dex-v2`: re-verified 299/299 and untouched.

## Exact code diff (the only executable change)
Your `Proposed-T05-Oracle-Constructor.diff` (`09DFA0B73DBA0233270635BA660E90A4E88A6AD1C647521ACDB84A8FB7656933`, re-hashed) was applied with `patch -p1` (dry run first) to `packet/verify/check_native_provider.py`, line 920:
```
-        if f'name="{name}"' not in suite and f"name='{name}'" not in suite:
+        if f'name="{name}"' not in suite and f"name='{name}'" not in suite and f'_o("{name}"' not in suite:
```
- Hash `099BC9A4…825F` → **`BF5E28A98C2533C967FF1DD51EDE63D9F50885627B656937D9CE7DFAE24D7F64`**, exactly your prospective hash. LF only; `diff` shows line 920 only.
- **Static B3 check:** suite (`617D381A…`, unchanged) line 255 `_o("classified_distinct_from_malformed_and_asgi_disconnect")` contains the newly accepted `_o("…"` substring. The first two oracles still match `name="…"`.

## Data diff
- **`packet/verify/OUTER-ADMISSION.json`** → **`3F9DE7E1393D38326313559E08C5B5C8C2E90506990F5DA6720CAAA259B65289`:**
  - `check_native_provider_sha256` → `BF5E28A9…`;
  - `t05_note` and `note` updated to v3;
  - `launch_authorized` false.
- **`packet/verify/VERIFICATION-ADMISSION.json`** → **`4BEB687B61A684C06FE254C52095EFB984C96FAAD1571FADCD31E13B07364F5D`:**
  - checker pin → `BF5E28A9…`; OUTER pin → `3F9DE7E1…`;
  - `note` updated to v3;
  - `launch_authorized` false.
  - The runtime inventory (1 record, interpreter `5F7B89A6…`) and the other 21 packet pins are unchanged.
- **Change set:** `diff -rq` against v2 `packet/` shows exactly these three files. All 23 VERIFICATION pins and the 3 OUTER subject pins verify against disk.

## Current documents (top level)
- `T05-V3-PREP-README.md` `015C732F…AC63`;
- `T05-V3-Freeze.json` `87D0685F…EB68`;
- `Future-Command-HELD.ps1.txt` `1552AB24…8BDD`, rewritten for v3:
  ```
  & 'C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-native-provider-t05-fake-v3\packet\Invoke-Fake.ps1' -AdmissionSHA256 '4BEB687B61A684C06FE254C52095EFB984C96FAAD1571FADCD31E13B07364F5D'
  ```
  The wrapper refuses while the flags are false. A run needs your separately reviewed staging copy plus Trish's one-shot approval, including owned-child termination authority.
- **History, labeled in the README:** the copied `T05-V2-PREP-README.md` and `T05-V2-Freeze.json`, and the v1 `Launch-Decision.md`, `Reviewed-Command.ps1.txt` (v1 wrapper; do not use) and `Static-Staging-Receipt.json`, plus the `packet/` lineage documents. No executable reads any of them.

## Manifest and chain
- **`Input-Manifest.sha256` = `DD108B3D1E957DBF0E66657F1A5A2FC034B3AE78CAC4A73FC8C38AE621B3EEC5`:** 289 entries relative to `packet/`, verifies 289/289.
- **Acyclic:** the wrapper takes the VERIFICATION hash; VERIFICATION pins 23 files (including OUTER) plus 1 runtime file; OUTER pins the launcher, checker, EXPECTED and interpreter. Nothing pins back up the chain.

## Unchanged
- launcher `D22C37E3…BD07`, EXPECTED `080268BC…260A`, wrapper `9AE55D26…`, outer admission script `08975D02…`;
- suite and every fixture, API and subject byte;
- the 17 and 19 control IDs and assertions;
- limits: 120 + 5 + 5 + 5 = 135 s nominal (with the same exclusions, and no separate outer timeout), 64 KiB per stream and 256 KiB for the result;
- exclusive evidence `packet/verify/FAKE-NATIVE-PROVIDER-RESULT.json` and `…-LAUNCH-RECEIPT.json`, both absent.

## Deferred and retained, as instructed
- **Deferred, not changed:** H1 (`sys.modules` save/restore), H2 (dead loop), H3 (docstring).
- **19 nested controls classified accurately:** 15 actual extracted-helper behaviors with fakes, 2 structural checks, 2 separately authored hole demonstrations. No actual-source mutant is claimed. T05-CLOSURE-FOCUSED stays last, and nothing after it depends on the removed stubs.
- **Retained gap:** the T05-SHORT-LENGTH-INVALID-JSON combined witness is not filled. T05 stays on the pre-diagnostic runner `9C0F8573…`.

## Proof boundary
- **Static:** B1, B2 and B3 are resolved by inspection; pins and manifests verify.
- **Not run:** this checker has never executed in the T05 lineage, so the 17 and 19 behaviors remain unproved.
- No native or TLS proof.

## Scope
- Reading, copying, the one literal `patch`, `sed` value and label substitutions in the two admission JSONs, hashing, and document and manifest authoring.
- No imports, parsing, compilation, tests, helper or wrapper invocation, probes, sockets, PKI, Docker, database, installation, cleanup or execution.
- No frozen copy repaired.

JSON validity of the edited admissions was checked by eye only. The changes are value swaps; the OUTER note contains properly escaped `\"`.

Signed: Matt
