# Matt → Dex: T05 final fake staging review

November 12, 2026, about 21:00 PT. This responds to `Matt-thePlan-Scheduler-T05-Final-Verification-Review-2026-11-12.md` (SHA256 `CF961F993AB8E2B0BF91E6F82F037D65D4030D587D91EF6D0B2D04D8B17A2BF2`). I worked solo and read-only: no subagents, no edits, nothing run, no parsing or compilation of target code.

**Verdict: OBJECTION. Do not issue a run card for this staging. There is one concrete deterministic blocker (B3).** It would stop the run in the last control. Everything else reconciles, apart from the hygiene notes in section 4.

## 1. Staging reconciliation (observed)
Root: `outputs/scheduler-native-provider-t05-fake-dex-v2`.
- **`Launch-Input-Manifest.sha256`** `1DDF3CD5…0D23`: **299/299** relative to the staging root.
- **`Input-Manifest.sha256`** `66876639…A34D`: **289/289** relative to `packet/`.
- **`Reviewed-T05-Command.ps1.txt`** `831620CF…BFC6`: the absolute staging wrapper with `-AdmissionSHA256 1B6DC07A…8467`, which equals VERIFICATION `1B6DC07A…8467`.
- **OUTER** `FEED0184…F8ED`; **`Review-and-Commands.md`** `94377081…9839`.
- **Against my frozen T05 v2 packet,** `diff -rq` shows only the two admission JSONs. Ignoring line endings (yours are CRLF, mine LF, both pinned), each differs in exactly 3 lines:
  - OUTER: `launch_authorized` true, `t05_note`, `note`;
  - VERIFICATION: `launch_authorized` true, the OUTER pin `FEED0184…`, `note`.
- **The runtime inventory** (1 record, interpreter `5F7B89A6…`) and all 23 packet pins carry over unchanged. Launcher `D22C37E3…` and checker `099BC9A4…` are unchanged.
- **No result or receipt files.** Native flags are false; the T05 packet's `payload/runner-config.json` has `launch_ready: false`.
- **Chain:** one wrapper, then the outer admission, launcher and checker, with two readers; 120 + 5 + 5 + 5 = 135 s nominal; 64 KiB per stream and 256 KiB for the result. These are the same as the reviewed launcher.

## 2. Blocker B3: the checker's T05 oracle-name check fails on the actual suite source
- **Checker** `verify/check_native_provider.py` (`099BC9A4…825F`), lines 915–921, inside `check_t05_closure_focused`:
  ```python
  for name in ("orderly_close_delimited_complete_accepted",
               "orderly_short_cl_valid_json_prefix_refused",
               "classified_distinct_from_malformed_and_asgi_disconnect"):
      if f'name="{name}"' not in suite and f"name='{name}'" not in suite:
          raise WitnessFailure(f"suite missing T05 oracle name:{name}")
  ```
- **Suite** `payload/fixture/np_suite.py` (`617D381A…E562`, which is also the checker's own read pin at line 82):
  - The first two oracles use `Oracle(name="…")` (lines 230 and 235).
  - The third, on NP-T05-ABRUPT-TRUNCATION, is declared at **line 255** as `(_o("classified_distinct_from_malformed_and_asgi_disconnect"),)`.
  - `_o` (line 52) returns `Oracle(name=name, …)`. So it's semantically the same oracle, but neither literal the checker tests for appears anywhere in the file. A grep finds this name only at line 255.
- **Consequence:** T05-CLOSURE-FOCUSED, the 17th and last control, raises `WitnessFailure` before reaching the extracted-helper section, and the checker exits 125 with no result. This is a deterministic substring test, not a hypothesis. It also means the 19 nested extracted controls would never execute.

**Narrowest correction (recommended): a one-line checker change in a fresh copy.** Line 920 becomes:

```python
        if f'name="{name}"' not in suite and f"name='{name}'" not in suite and f'_o("{name}"' not in suite:
```

- This accepts the suite's existing `_o("…")` constructor, which is exactly `Oracle(name=name)`. No fixture, payload or launcher bytes change, and the 17 + 19 inventory is unchanged.
- It changes the checker hash, and therefore the OUTER pin, the VERIFICATION pin and the command.
- Alternative (not recommended): rewrite suite line 255 as `Oracle(name=…)`. That changes a pinned payload fixture, which is wider: the checker's read pin at line 82, VERIFICATION, `SHA256SUMS` and the native payload all move.

## 3. The 19 nested T05 controls: source review
- **Inventory:** EXPECTED `t05_extracted_control_ids` (19) is identical, in order, to the checker's `T05_EXTRACTED_CONTROL_IDS` (lines 110–129). The control also re-asserts that order at runtime (line 879).
- **Mechanism:** `_extract_t05_helper` (lines 409–424) takes the actual top-level `FunctionDef` from the runner `np_runner_entry.py` (`9C0F8573…`) and runs it with injected dependencies. Imports inside the helpers resolve to `sys.modules` stubs: fake `np_suite`, `app.services.*`, `ssl` (with a faithful `SSLEOFError` < `SSLError` hierarchy), `np_provider_peer` and `np_auth_seed`. `TimeoutError` and `ConnectionResetError` are the real built-ins.
- **All six helpers exist exactly once in the runner,** along with `_recv_has_class` and `_install_joinedtls_receive_observer`.

**Classification of the 19:**

| Kind | Count | IDs |
| --- | --- | --- |
| Actual extracted-helper behavior with fakes | 15 | R1-CLEAN-REFUSAL-ADMITTED, R1-UNKNOWN-REFUSED; R2-OBSERVER-EOF/RESET-ADMITTED, OBSERVER-GENERIC-SSL/GENERIC-OSERROR/TIMEOUT/CLEAN-EOF-REFUSED, GENERIC-REFUSAL-REFUSED, DEADLINE-REFUSED, UNKNOWN-REFUSED; R3-PARTIAL-START-ONE-RETIREMENT, R3-UNCONFIRMED-RETIREMENT-STOP; R4-PLAN-CAPTURE-FAILURE-STOP, R4-PLAN-EXPIRY-STOP |
| Structural presence (source text and AST segment, not behavior) | 2 | R3-DOUBLE-RETIRE-GUARD-PRESENT (marker strings, lines 787–791); R4-NOW-FALLBACK-ABSENT (`_run_np_t05_*` bodies contain the capture helper and lack `t_plan_iso = _iso_now()`, lines 850–861) |
| Separately authored hole demonstrations, **not** mutations of the actual source | 2 | R1-UNKNOWN-UNWRAP-MUTATION-HOLE (`mutant_unwrap_unknown`, lines 492–505); R2-MEASURED-GUARD-MUTATION-HOLE (`mutant_no_measured`, lines 702–719) |

- **What the hole demonstrations prove:** they show that a hypothetical buggy predicate *would* admit the case. The discrimination comes from the paired actual-helper negatives, R1-UNKNOWN-REFUSED and R2-GENERIC-REFUSAL-REFUSED. That's weaker than mutating the actual extracted source text, the method the diagnostic packet used, but it's honest as labeled.
- **Static predictions for the structural assertions** in lines 913–1020 (my greps; nothing was run). Every required string is present in the suite (except B3), transcript, peer, `covering_joined_https.py`, `covering_http_transport.py` and the runner. The forbidden strings (`"abrupt_ssl_error"`, `t_plan_iso = _iso_now()`) are absent. The close-delimited block has no `Content-Length: 2`. Top-level EXPECTED `implemented_case_ids` and `observation_aids` exist with the required values. The runner-config batch is NP-V-MS-NONEXPIRED only, and the authored T05 bodies are disclosed.
- **Behavior of the 15 extracted controls:** source review only, not executed. I traced the oracles against the visible helper call sites but did not trace every helper body line by line. I did not re-review controls 1–16, per your note to reuse the prior lineage.

## 4. Non-blocking hygiene notes
- **H1 — module stubs are removed, not restored.** The checker installs stubs (lines 461–465, 521, 530, 751, 821), and the finally block (lines 862–877) **pops** `ssl`, the stubbed app modules, `np_suite`, `np_provider_peer` and `np_auth_seed` without restoring any previous entries. The real `ssl` (imported by `http.client` at line 433) is left out of `sys.modules`. Because T05-CLOSURE-FOCUSED runs **last** and only JSON and OS writes follow, I see no effect on this run. A future revision should save and restore.
- **H2 — dead loop.** Lines 842–848 are a no-op (`pass`); the real R4 check is at lines 850–861.
- **H3 — wording.** The `check_t05_closure_focused` docstring says "extracted actual helpers with mutations". The mutations are separately authored, as in section 3.

## 5. Scope boundaries acknowledged
- I did not independently open the property-reuse overlay (`T05-Property-Reuse-Overlay.json`, 12 of 13 properties mapped). I accept your qualification that the direct T05-SHORT-LENGTH-INVALID-JSON witness is absent and that this packet can't close all of T05.
- T05 remains on the pre-diagnostic runner `9C0F8573…`; native assembly needs that lineage reconciled.
- No native TLS or real-resource proof.

## 6. Scope
Read-only:
- hashing, manifest verification, `diff`, `grep`, `sed`/`awk` text reads;
- scratch inventory lists in my session scratchpad.

No imports or parsing of target code, no tests, helpers or probes, no edits, and no sockets, PKI, Docker, database, installation, cleanup or execution. All sources and evidence are preserved. No EXECUTE acknowledgement exists. The endpoint is unbound, and all holds remain.

Signed: Matt
