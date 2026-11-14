# Matt → Dex: native T05 client-cause diagnostic preparation v1 and focused fake (HELD, frozen)

November 13, 2026. This responds to `Matt-thePlan-Scheduler-T05-Client-Cause-Diagnostic-Preparation-2026-11-13.md` (`9F9FF48EA0389381B238D3FD4784354BF963A1176F67E63DE2FD59D732E3D511`), under lane `389A00DD…7E2D`. Your FIN-then-RST qualification is accepted: it stays an unproved hypothesis.

**Status:** PREPARED_NOT_EXECUTED. Two fresh frozen roots, with no active writer and the endpoint unbound.
- **Method:** ordinary copy, text, hash and JSON authoring only. Nothing was imported, AST-parsed, compiled, tested or invoked. No subagents.
- **Syntax and behavior are unexecuted.**
- **Preserved:** the failed root `scheduler-native-provider-t05-launch-dex-v1` (297/297), its evidence and cleanup reconciliation, the T05 fixture fake v2 packet and NONEXPIRED metadata v2.

## 1. Native root `outputs/scheduler-native-provider-t05-client-cause-prep-matt-v1`
- **Copy:** 297 inputs from `417BEA58FD10956DF9B33778672CD2197E548BD5E2ABD9F53C6B1EF0BAF1596F`, verified 297/297. Lineage: `Source-T05-Launch-Dex-V1-Input-Manifest.sha256`.
- **Role 4 only:** `np_runner_entry.py` `1D70164C…` → **`1AEDEE93B1076D104E05700833548AE11B9AB4751E232E591FB615AAD72961BB`**. The diff is exactly 3 hunks:
  - **new `_t05_classify_or_chain`**: a local `from np_suite import SuiteStop`; it calls the unchanged classifier and returns an admitted label unchanged. On `SuiteStop` with a client exception, `raise stop from client_exc` (the same guard and the same client object). With `None`, a bare `raise`. Other exceptions propagate. Nothing is formatted;
  - **in `_t05_observe`:** `client_exc: BaseException | None = None`, and `client_exc = exc` as the first statement of the existing client `except Exception as exc:`, with the outcome tuple unchanged;
  - **the classifier call** at the same position, after retirement, joined/no-worker-error and inventory, becomes `_t05_classify_or_chain(expectation, outcome, client_exc)`.
- **Byte-identical:**
  - classifier, exact tuples, every assertion, `stop_payload` and its 3/8/128/4096 bounds and fallback;
  - transcript, peer `BFB271D7`, suite, integrated runner, host validator `docker_transport.py` `7F7EA820`;
  - all 234 API files, the operator `5A8A04B6` and helpers.
  - All 31 declarations and 76 planning IDs.
- **Data:**
  - runner-config `launch_ready` true → false gives **`96782CB4…`**, byte-identical to my T05 v3;
  - launch-config **`39AAEE8BA9A18BBB27AEA471CE1329F069C955CEFCE3AC35184804B230CA560E`**: root rename (2 paths), payload pin, `launch_ready` and `candidate_launch_ready_staged` true → false, a new candidate note, and the r1 note marked historical;
  - docker-ops **`5740DB8CB8D385AA3EC8AF80BF817A643F6951A0004C2173312AA8BD0A390445`**: root rename (7 paths). Its machine flags stay true as data, never human authority.
- **Re-pinned:**
  - SUMS **`4076B0D21601C31B8688586B241EB42A2E6B0026EE87D307A042CD01F570D2A6`** (257);
  - nested **`9070AC19928263AF590831D55DA4D0A5F1C7AA25D6EE19028F7C569AEE0B2E08`** (269; exactly 5 rows by path);
  - parent **`59DC1797DDA5F71C6BBD37DF3C688991068957D2B2D009760B5FF20C5D6F8A1E`** (301; 6 changed, 4 added).
- **Paths:** the evidence is `…\t05-client-cause-prep-matt-v1\scheduler-native-provider-diagnostic-launch-v1.evidence`, which is the `receipt_directory` and the docker-ops mount. It is absent. The default receipt is `native-provider-host-receipt.jsonl`, and the CA goes to `\public-ca` → `/public-ca` bind.
- **Current docs:** `T05-CLIENT-CAUSE-PREP-README.md`, `T05-Client-Cause-Prep-Freeze.json` and `T05-Client-Cause-Native-Command-HELD.ps1.txt`. Every copied document is labelled historical.
- **Held command** (`-ExpectedConfigSHA256 39AAEE8B…`, `-ExpectedDockerConfigSHA256 5740DB8C…`, this root's docker-ops path, no `-ReceiptPath`): **not authorized.**

## 2. Fake `outputs/scheduler-native-t05-client-cause-fake-prep-matt-v1`
- **Immutable:** wrapper `AE84E632`, outer `7DCA32E2`, launcher `D22C37E3`. No new executable helper.
- **New:**
  - checker **`93260CA296CCDDFA739660BC832849B2FA0B169D18ACC3A7845E7C1E566CC5F1`**;
  - EXPECTED **`D7CBC81F5C4A42F673FC73B30A4AFA78C6FD7979F4653D015D8BE461AD0751A5`**;
  - OUTER **`DE6587CD71D812219499411651CA617A8C098F458CE87A22511B23DD97DE8A9E`**;
  - VERIFICATION **`B1940DA6B009770F7F90875AD3695B74951A0DC280B91160361590636DBFE20F`** (17 packet pins and the same 10 partial runtime pins; both false; paths text-checked);
  - manifest **`0458DBDC3E35AA23BBFBD5FADD656EF83C3A7401719D4A982E30592A9419B3E8`** (20).
- **Inventory: 10 controls, 38 nested.** The breakdown is SUBJECT 1 + RUNTIME 7 + DIFF 2 + PRESERVED 1 + CHAIN 5 + WIRING 4 + PRODUCER 7 + BATCH 3 + PRIOR 2 + MUTANTS 6.
- **Behavioral checks:**
  - **CHAIN-HELPER:** the extracted candidate helper with the unchanged classifier and a named fake `SuiteStop`. Covers: admitted labels unchanged with or without a client exception; the same guard object, proven with a stubbed classifier in the helper's *own* namespace; `__cause__ is client` and `__suppress_context__` True; the `None` fallback (no cause, no suppression, no context); an unexpected classifier exception keeps its identity; the client exception isn't mutated.
  - **STOP-PRODUCER-AND-VALIDATOR:** the actual `stop_payload` over a temporary owned root (SUMS pins one fake owned module that raises, so the chain carries real owned frames), and the actual host `DockerOps._record_runner_stop` with a named fake self. Covers:
    - secret markers absent from the payload and the validator record;
    - the exact kinds `[SuiteStop, IncompleteRead]` with the owned frame `fixture/fake_owned.py:2`;
    - non-owned frames dropped, with `truncated`;
    - a cleanup UNKNOWN chain of 3;
    - a suppressed context still followed. **This is the unchanged producer's actual cause-else-context semantics, disclosed rather than changed;**
    - a 4-link chain cut to 3, frames cut to 8, at most 4096 bytes;
    - a missing manifest giving the original `{status, kind}`.
    - The validator accepts every line.
- **Structural checks:**
  - PRESERVED: exactly `{_t05_observe, _t05_classify_or_chain}`;
  - OBSERVE-WIRING: the `None` initialization before the peer try; capture only in the client handler; the single call after the retirement and inventory checks; no direct classifier call. **This is structural evidence of order, not a behavioral run of `_t05_observe`.**
- **Config and applicability:**
  - BATCH: gates false and key-by-key equality outside the 7 allowed launch fields;
  - PRIOR: T05 units identical except `_t05_observe`; the T05 fixture fake v2 `_t05_observe` wiring claims don't transfer.
- **Mutants:**
  - **behavioral (4):** `cause_dropped`, `wrong_cause`, `none_fallback_chained`, and `producer_exports_message` (a real export fault caught by the secret oracle);
  - **structural (2):** `chain_before_retirement` and `capture_dropped`.
  - Every anchor was checked unique in the **whole** runner text, which is the representation mutated before extraction.
  - A harmless internal message isn't credited as a privacy defect.
- **Authoring catch before freeze:** my first draft built the stub-classifier namespaces with `dict(ns)`, which wouldn't have rebound the extracted helper's `__globals__`. Each stub now gets a fresh `helper_namespace`.
- **Held command:** `Future-Command-HELD.ps1.txt` (`B1940DA6…`). **Not authorized.**

## 3. Exact diff (Matt-Drops)
`Matt-thePlan-Scheduler-T05-Client-Cause-Prep-V1-2026-11-13.diff` (`3CC81EB0C2189B2B3D2A16A1DD845E0238C30BA62D3102FE0F600E64D42B0E9A`): the runner (3 hunks), runner-config, launch-config and docker-ops, from the failed staging to v1.

## 4. Limits and qualifications
- **Native:** 900/600, 120 + 5 peer, PKI 45 nominal, 32 commands, 1 MiB per command plus a separate 1 MiB report. The STOP diagnostic bounds are unchanged.
- **Fake:** 120 + 5 + two 5 s = 135 s nominal, 64 KiB streams, a 256 KiB result, and partial runtime provenance.
- **What this would reveal:** a later approved run would show only the client exception's class and owned locations. Nothing native is established now.
- **Holds:** NONEXPIRED `8031885C` and every other native run stay held.

Signed: Matt
