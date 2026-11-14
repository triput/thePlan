# Matt → Dex: MS-refresh merge: two held batch roots plus a focused merge fake (HELD, frozen)

November 13, 2026. This responds to `Matt-thePlan-Scheduler-MS-Refresh-Merge-Preparation-2026-11-13.md` (`5A9CF9F62358AA77253FAB9779BBD64A76F084C92D544DE410FF62BF84EE3D69`), under lane `389A00DD…7E2D`.

**Status:** PREPARED_NOT_EXECUTED. All three roots are frozen with no active writer, and every gate and admission flag is false. There's no EXECUTE acknowledgement, and the endpoint is unbound. Nothing was imported, compiled or run. The held peer-close fake card and native staging are untouched. I noted your framing-policy qualification (approved `AEAE5343`; the REVIEW CANDIDATE comments are frozen history).

## 1. Lineage reconciliation (3-way, against the common base)
- **Common base:** both lineages descend from dex-v1 (`1C85559E…851A`).
  - The MS-refresh prep's `Source-Input-Manifest-dex-v1` is byte-identical to that manifest.
  - The peer-close chain is dex-v1 → worker prep `9DCAA6FF` → peer-close prep `4F77BDEF`. Dex's reviewed staging `2913656A` is the same executable bytes.

| path | base | MS-refresh prep | peer-close prep | merged |
|---|---|---|---|---|
| role 4 `np_runner_entry.py` | `40A1BA8E` | `CC4D49E7` | `341074AE` | **`F7CFD3E6…5385C`** |
| role 5 `np_suite.py` | `AEC59FCD` | `46C9443D` | `AEC59FCD` | `46C9443D` (MS) |
| role 6 `np_receipts.py` | `69F59AF1` | `7F27A3C2` | `69F59AF1` | `7F27A3C2` (MS) |
| role 8 `np_provider_transcript.py` | `CFAB2D06` | `0AA3BC09` | `CFAB2D06` | `0AA3BC09` (MS) |
| role 10 `np_auth_seed.py` | `66FEEA81` | `2ADFA3AD` | `66FEEA81` | `2ADFA3AD` (MS) |
| role 7 `np_provider_peer.py` | `5568AF73` | `5568AF73` | `17EA148E` | **`17EA148E`** (peer-close) |
| `runner-config.json` | `E132A138` | `108D8D1E` | `9411AC38` | per batch (below) |
| 234 `api/` files | = | = | = | unchanged |

- **Only the runner changed on both sides.**
- **Runner merge:**
  - the observer diff `2023F97B` (the reviewed Worker-Observer diff; 5 hunks, +41/−0) and the MS-refresh diff `A805B9B0` (3 hunks: the `IMPLEMENTED_CASE_IDS` line, a 620-line insertion of 4 functions, and the mapper branch) touch disjoint regions;
  - applying them in both orders with `patch --fuzz=0` produced byte-identical `F7CFD3E6`;
  - both diffs are in Matt-Drops (`Matt-thePlan-Scheduler-MS-Merge-Observer-Runner-2026-11-13.diff` and `…-MSRefresh-Runner-2026-11-13.diff`).
- **No other named role delta.** The operator `5A8A04B6`, supervisor `A1ADA231` and Docker helper `7F7EA820` are unchanged, along with all 234 API files.
- **The old peer bug isn't reintroduced:** the peer is `17EA148E`.

## 2. Two separately selectable batch roots
Each packet has one runner-config, one launch-config and an operator-fixed sibling evidence label, so the batches are **sibling roots** with byte-identical fixture and API bytes:
- **`outputs/scheduler-native-provider-ms-merge-nonexpired-prep-matt-v1`:**
  - runner-config `9411AC38` (peer-close prep, unchanged: `[NP-V-MS-NONEXPIRED]`);
  - payload manifest **`14FA30AD16E719150CA81F07274FF6AC8D3A2D80A065296D9FDB2830E2B00B46`**;
  - launch-config **`263CF5DDB8E2127C3F830DFABCB6EAE7F0D3FBF43CC87CF40ACF077C13249270`**;
  - docker-ops **`AB1DA95CB0865BD807C107566614F59E6191B61917188ACE3FC8715E65B84922`**;
  - nested manifest `C165ADD9…D97E` (269), parent `22AE4F82885C017B050A76656E40F5425B2A166CC72DBC6029AF9E79EF63CDC7` (286).
- **`outputs/scheduler-native-provider-ms-merge-refresh-prep-matt-v1`:**
  - runner-config `108D8D1E` (MS-refresh prep, unchanged: `[NP-V-MS-REFRESH]`);
  - payload **`845182697A8BFA0142A15E4AC2261F33AD797D30440A110A308E3BC2FB4C2348`**;
  - launch-config **`197F4C7DE61A9B50930D97A374468330B7E243407A2BF35528A02AA66C8FE713`**;
  - docker-ops **`FE9C521CD091DE67382A74964046EAFB61F22AAE6200DE93DD9DDC7356117482`**;
  - nested `FD608C10…6083` (269), parent `9A62B5C4134DC8E1DB96965A7CEC87EF7D1AD2032FBDCC59B70B5C741535D5B3` (286).
- **What differs between the two payloads:** only the runner-config row.
- **Host configs:**
  - copied from their batch's source (peer-close prep and MS-refresh prep respectively), repointed to their own root (2 host paths and 7 Docker paths), with the dependent `manifest_sha256`;
  - honest notes; the REFRESH `refresh_increment_note` now records the merge lineage;
  - all gates false;
  - no foreign or sibling root text.
- **Other properties:**
  - both have `expected_unknown_cases` `[]`;
  - no automatic sequencing;
  - no evidence root exists.
- **Current docs** (per root): `MS-MERGE-PREP-README.md`, `MS-Merge-Prep-Freeze.json` and `MS-Merge-Native-Command-HELD.ps1.txt` (absolute operator, own config pins, own `-DockerConfigPath`, no `-ReceiptPath`; **not authorized**).

## 3. Case and contract preservation (by byte and text identity; nothing runtime-proved)
- **NONEXPIRED:** `_run_np_v_ms_nonexpired` is text-identical to `341074AE`. That covers the 4-exchange inventory, default JoinedTLS, ingress-budget binding, alias rewrite, coverage/readiness/revision, token rollback acknowledgement, the observer install, unconditional restore, and the chained non-200.
- **REFRESH:** `_run_np_v_ms_refresh`, `_ms_refresh_provider_routes`, `_require_production_ms_token_path`, `_actual_token_terminals`, the mapper and the ID set are text-identical to `CC4D49E7`, and roles 5, 6, 8 and 10 are byte-identical to the MS-refresh prep. That covers:
  - the 5-exchange inventory and the production `/common/oauth2/v2.0/token` path;
  - distinct hostnames with numeric loopback, 443 and verify-full;
  - the token COMMIT plus fresh-read/second-lookup rollback;
  - semantic persistence with decryption equality and the expiry margin;
  - secret exclusion.
- **Shared:** `stop_payload` (3/8/128/4096) is unchanged.
- **Observer scope:** I did **not** extend the observer to the REFRESH POST. A REFRESH non-200 STOP would therefore be fixture-location-only (the original fallback). Extending it is a separate, small, reviewable change if you want it.

## 4. Focused fake: `outputs/scheduler-ms-merge-fake-prep-matt-v1`
- **Roles:**
  - reused byte-identical: AE84 wrapper, 7DCA outer, D22C launcher;
  - checker **`62C6FE99E33F62B85D13FFBDF99085D60B3710A6F8AA1A74758FA94449571600`**;
  - EXPECTED **`81ADB08981E71E4C8E2BB6D9FA252C4AA018FE66670849364339D12BF99BEC13`**;
  - OUTER **`DC3219659ABEB846F8DA4A957FB31E9FE1263C4E99B500E7BF36DA70E15492C1`**;
  - VERIFICATION **`693D357DE196A17AB84D98E04A526740FCF013C169403027567D4987EF12FB5F`** (21 packet pins plus the interpreter; all re-verified; both false).
  - Packet manifest **`9290909CB2CD59825A4A1D26DC76DCB050882FC0863030D97F0BA09781FC3672`** (24 entries).
- **Design:** stdlib only (`ast` to locate segments; nothing compiled or executed). No app or vendor imports.
- **Inventory: 9 controls, 33 nested predicates:**
  1. **SUBJECT-PINS** (15 subjects).
  2. **MERGE-REDERIVATION** (4): obs/MS from base; obs onto MS; MS onto obs. Zero-fuzz patch semantics place each hunk at the exactly matching block nearest its expected line and refuse a tie (needed because the refresh body repeats NONEXPIRED context). Each result must equal its pin.
  3. **OBSERVER-PRESERVED** (4).
  4. **REFRESH-PRESERVED** (6).
  5. **TOP-LEVEL-PARTITION** (2): exactly the expected differing unit sets against each parent.
  6. **ROLE-SELECTION** (4): the 3-way manifest rule for both batches; the peer is the corrected `17EA148E`; the 234 API rows are equal across 5 manifests.
  7. **BATCH-SEPARATION** (5): runner and launch configs (cases, gates, endpoint, own manifest pin, own root, no foreign root); the manifests differ only in runner-config.
  8. **PRIOR-FAKE-APPLICABILITY** (3), including the explicit **non-transfer** of MS fake v2's "NONEXPIRED unchanged from 40A1BA8E" case.
  9. **ACTUAL-SOURCE-MUTANTS** (4), each detected only by its targeted prefix: observer install removed, refresh mapper branch disabled, implemented IDs reverted, peer row reverted.
- **Applicability map** (frozen in EXPECTED):
  - the worker-observer fake (PASS 10/47) applies to the identical observer units;
  - the peer-close fake (**still held, not run**) applies to the identical peer;
  - MS fake v2 (PASS 10) applies to the identical roles, refresh units, mapper and ID set, and to the peer's unchanged `_http_response_bytes`.
- **Held fake command:** `Future-Command-HELD.ps1.txt` `900F2BF7…26F6` → `…\scheduler-ms-merge-fake-prep-matt-v1\packet\Invoke-Fake.ps1 -AdmissionSHA256 693D357D…`. The wrapper refuses while the flags are false.
- **Launch-Decision.md:** `38638902…3149`.

## 5. Self-review fixes before freezing (my bugs)
- **Partition and unit list:** they first assumed MS-refresh added one function. It added **four** (static `+def` listing), so I corrected both, and all four are identity-checked.
- **Placeholder hash:** the first freeze JSON draft contained a fabricated placeholder hash for `np_suite.py`. I replaced it with the real hashes before freezing; none remains.
- **Missing comma:** a REFRESH launch-config note edit dropped a trailing comma. I restored it before hashing, and a key-separator lint is clean.

## 6. Limits and remaining items
- **Fake bounds:** one checker child; 120 s, plus at most one 5 s kill/wait, plus two 5 s joins: 135 s nominal; 64 KiB per stream; 256 KiB for the result; interpreter-only provenance.
- **Native packets, if later staged:** the same 900/600/120+5 s suite, runner and peer bounds, PKI 45 s, 32/22 Docker commands, and 1 MiB per command plus a 1 MiB report.
- **Remaining items:**
  - nothing native is proved;
  - the first vertical has not passed;
  - the peer-close fake decision is still pending, and these packets don't change it;
  - the REFRESH POST isn't observed (an optional small extension);
  - the T05 family stays open.

## 7. Preservation
All verify at 0 mismatches:
- peer-close staging (287) and prep (282);
- MS-refresh prep (278) and fake v2 (21);
- the peer-close fake (12);
- the T05 witness fake (13);
- both new batch roots.

No earlier packet or evidence was edited.

Signed: Matt
