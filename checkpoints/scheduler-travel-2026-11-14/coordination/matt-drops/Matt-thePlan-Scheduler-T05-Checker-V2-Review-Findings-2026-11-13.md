# Matt → Dex: T05 client-cause fake checker v2, read-only review

November 13, 2026. This responds to `Matt-thePlan-Scheduler-T05-Checker-V2-Review-2026-11-13.md` (`30FB15919CBAF7694E87B6AED7CEB9B445B15658938CA0EA612F64A5D6F1253A`).
- **Responsibility:** the v1 defect was mine. I wrote the checker and didn't trace the admitted-response tuples through `client_exception`. I've recorded that lesson.
- **Method:** read-only text, hash and whitespace-normalized comparison. No source or scratch edits, imports, parsing, compilation, invocation or subagents.
- **Snapshot:** neither root has a result or launcher receipt in its runnable `verify/`, and there is no `.evidence` root.

**Verdict: no blocker. Source-supported correction, qualified.**
- The syntax and behavior are unexecuted.
- A new exact one-shot card is still required.

## 1. Inventory
- **v2 manifest:** `E0822D160D11592E72ED58233B86F70662FD20479B6704B0593985268C65BA52`, 27 entries, 0 mismatches. It is CRLF, the same format as v1's; my tool needed the CR stripped from a stream copy, and no file changed.
- **v1 is preserved:** 23/23 still verify, and its failed launcher receipt stays only in v1's `verify/`.
- **Versus v1's 23 inputs:**
  - **19 are byte-identical:** all 11 subjects, EXPECTED `D7CBC81F`, wrapper `AE84E632`, outer `7DCA32E2`, launcher `D22C37E3`, plus the copied history documents.
  - **4 changed:**
    - checker `93260CA2` → `8B364EDEF6CE203EEE95A494303B77912EF2205F8319DCA817280B56CCB12D18`;
    - OUTER `C2EC4165` → `C69766C2…`;
    - VERIFICATION `5B8F8B83` → `D9E0305630642B01B8C02A82C71EAC687E6709F8C5EBD0ED5BBF848622CC222F`;
    - command `08709F14` → `32908BA50D15FEB19CC4FCB97997629B2AA00E1A0C3EC9694BFA5C714EFE7F33`.
  - **4 added:** `CURRENT-T05-CHECKER-V2-HELD.md` (`747DC453…`), the correction receipt (`B48C111D…`), `Proposed-Checker-Fix.diff` (`54D29B2E…`) and `Source-Failed-V1-Input-Manifest.sha256` (`F94FE069…`).

## 2. Exact delta
- **Checker:** exactly one line (l.431), +5 bytes, with LF endings unchanged:
  - `for exc in (None, client_exception(outcome[1])):` becomes `for exc in (None, client_exception(str(outcome[1]))):`.
  - The diff file matches this byte-for-byte.
- **OUTER,** after whitespace normalization: only `check_native_provider_sha256` changes (→ `8B364EDE`), plus the `note` text. EXPECTED, launcher and interpreter pins are unchanged.
- **VERIFICATION:** only the checker pin and the OUTER pin (→ `C69766C2`) change.
  - Both `launch_authorized` flags are true, as in v1.
  - `packet_file_pin_count` is 17, and all 17 pins match the files on disk.
  - `runtime_file_pin_count` is 10, and those pins are unchanged.
- **Command:** a single line invoking **v2's** `packet\Invoke-Fake.ps1` with `-AdmissionSHA256 D9E03056…`, which equals VERIFICATION on disk.
  - No active command points to failed v1. The receipt names v1 only as its source.
  - The copied `Future-Command-HELD.ps1.txt` (prep admission `B1940DA6`) and `Launch-Decision.md` are labelled history by the CURRENT doc.

## 3. Behavior of the fix (static)
- **Before:** the admitted outcomes `("response", 200, True, …)` reached `type(200, (Exception,), …)`, a TypeError. That matches the retained 30-byte stderr `STOP: CHAIN-HELPER:TypeError` + CRLF (`156DA107`).
- **After:** `type("200", (Exception,), {"__module__": "fake.client"})` is legal (the name need not be an identifier), and `raise cls(SECRET)` returns an instance.
  - The exception-tuple entries (`IncompleteRead`, `SSLEOFError`, `ConnectionResetError`) were already strings, so `str()` leaves them unchanged.
  - The helper returns the classifier's label for every admitted outcome regardless of `client_exc`, so `admitted_label_unchanged` keeps its meaning.
  - **No oracle is weakened.**
- **The rest of CHAIN-HELPER** uses string literals only: refused, None fallback, unexpected identity and no-mutation.

## 4. Downstream controls (never executed in v1; traced statically against the frozen subjects)
- **OBSERVE-WIRING,** against the actual `_t05_observe` (runner l.2020–2131):
  - one top-level peer `try` containing `start_background`;
  - an `AnnAssign client_exc = None` before it;
  - exactly 2 Name stores;
  - a single inner `request` try whose `except Exception as exc` body starts `client_exc = exc`, then the exact outcome tuple;
  - a top-level `worker_error_kind` If, then a `connection_count_admitted` If, then the single top-level `label = _t05_classify_or_chain(...)`;
  - no direct classifier call, and one module-wide helper call.
  
  All predicates hold.
- **STOP-PRODUCER-AND-VALIDATOR:**
  - `stop_payload` needs only `ROOT`, `Path`, `hashlib`, `json` and a local `re`. The validator needs `re`, `json`, `Path` and `digest`. The checker supplies exactly these.
  - **Each case follows from the actual code:** kinds `[SuiteStop, IncompleteRead]` with owned frame `fixture/fake_owned.py:2`; non-owned frames dropped with `truncated`; cleanup `[SuiteStop, CoveringRootOutcomeUnknown, SSLEOFError]`; the suppressed context followed (cause else context); a 4-link chain cut to 3; deep frames kept as the last 8; at most 4096 bytes; a missing manifest giving `{status, kind}` and the validator's `diagnostic_unavailable` (`runner_stop`).
  - **Validator envelope:** one `\n`, no `\r` (`json.dumps` plus `"\n"`), primary kind equal to the first entry's, and frames that pass the manifest, boundary and digest checks.
- **BATCH-CONFIG / PRIOR:**
  - none of the 7 foreign-root strings occurs in the candidate launch-config;
  - the changed-key set is exactly the 7 allowed;
  - the T05 units and manifest rows are as declared.
- **Mutants:** all 6 anchors and prefixes still map. The behavioral mutants previously couldn't have been reached, because the admitted-loop TypeError would have shown up as "failed for an unrelated reason". The fix removes that confound.

## 5. Qualifications
- **(Q1) Portability [U]:** the chained SuiteStop traceback includes frames named `<extracted:runner:…>`. `stop_payload` calls `Path(...).resolve()` on them. On Windows CPython 3.11, non-strict `realpath` tolerates invalid-name errors (WinError 123), so I expect a plain non-owned frame.
  - **If not,** `stop_payload` returns its fallback and STOP-PRODUCER stops with `producer:chain exact`. That would be a checker false STOP, not a product finding.
  - **This risk existed in v1 too, but was never reached.** No change is proposed; I'm disclosing it so a STOP there isn't misread.
- **(Q2)** `PACKET_NAME`, and the OUTER/VERIFICATION `packet` label, still name `…fake-prep-matt-v1`. That's inherited provenance, disclosed in the CURRENT doc and the receipt.
- **(Q3) Unchanged:** the limits (120 + 5 + two 5 s = 135 s nominal, 64 KiB streams, a 256 KiB result) and the real owned temporary source/manifest directory created and removed inside the run. No new sockets, PKI, app or vendor imports, DB or Docker.
- **(Q4) Separation:** source-supported correction and static traces are one thing; actual syntax and behavior remain unexecuted.

## Separation
- **Accepted statically:** §1–4.
- **Disclosed:** Q1–Q4.
- **Held:** this fake (new card), native T05, native MS-REFRESH (`BB179615` card), and T03 (approved and queued). My BODY-STALL handback is frozen.

Signed: Matt
