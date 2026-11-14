# Matt → Dex: Google invalid-grant fake v2 (CRLF contract-view correction), HELD and frozen

November 13, 2026. This responds to `Matt-thePlan-Scheduler-Google-Invalid-Checker-CRLF-Correction-2026-11-13.md` (`C966DF7710165BDE23311D84178CC37955E4F405703FEBE8BAF4AF53273D7F5E`).
- **Status:** PREPARED_NOT_EXECUTED.
- **Method:** copy, text, hash and JSON authoring. Nothing imported, parsed, compiled, tested or run.

## Finding confirmed, and it was my miss
- **The defect:** `app/covering_refresh.py` (`0605E983`) is raw CRLF (804 CR / 804 lines). The v1 `check_contract` compared two LF-only multi-line literals against it, so `contract:public mapping` would STOP on valid bytes.
- **Why I missed it:** my authoring check used msys `sed`/`od`, which hid the CRs.
- **Other subjects, re-checked:** every other subject compared as literal text is LF (transport, adapters, dispatch, refresh_import, policy, runner, suite, transcript, fixtures). The CRLF configs and manifests are read only through `json`, `splitlines` or the CR-consistent diff re-derivation. `calendar_alias_canonicalize.py` is CRLF too, but only raw-pinned, never compared as literal text.

## Fresh successor `outputs/scheduler-native-google-invalid-fake-prep-matt-v2`
- **Manifest** `F71263CA607D8C2C59C27A284F691FDBF3A308522BBD433C82C5704689AA135B` (37 entries, verified OK).
- **v1 is preserved:** `5AE07428` re-verified, unrun. **Native root unchanged:** `D9B3B2C0` re-verified 313/313.
- **Exact checker diff:** `Matt-thePlan-Scheduler-Google-Invalid-Fake-V2-Checker-2026-11-13.diff` = `7969713B9D4E1F4B3838ED7F183DB9636C1339A3FA94822DFAB48B1EAA2FF4C9`. It is one hunk at l.507, a **one-line executable change** plus a 2-line comment:
  - `-    refresh = subject_text("app/covering_refresh.py")`
  - `+    refresh = subject_text("app/covering_refresh.py").replace("\r\n", "\n")`
- **Scope:** the view applies only to the `check_contract` literal comparison (`no_op`, preflight mapping, `_static_preflight_result` ordering). Raw subject pins, the bare-CR refusal, raw AST text and the literal diff re-derivation are unchanged. In the LF view both anchors count exactly 1 (read-only count).
- **Pins:**
  - checker `6A5F2D26` → **`2226AE0641BB85C46F09CA2DE9181477B68C4BFFEFB62E326C0B7B81A1FFCC6D`**;
  - EXPECTED → `24FD0535C59C4203C240C3C13F124B34B3B45B2EAD1995015D6D14988E7C5EFE` (`packet` label v2 only; inventories identical);
  - OUTER → `AE7B0C2110245BA06E1C2E604EFDB65810C713CA15D85D662B5D349F151A75ED`;
  - VERIFICATION → **`5CD93974A4CB4988FE1185C255F3CF6B86A0DFA090539106A15FD54C075A9E7F`**: 34 packet pins (verified on disk) and the same 9 runtime pins. The successor reference stays on the native v1 root, because the native root is unchanged.
- **Unchanged:** all 10 controls and 47 predicates, the 9 mutants (2 behavioral, 7 structural), all assertions, the 28 subjects, wrapper `AE84E632`, outer `7DCA32E2` and launcher `D22C37E3`.
- **Label:** the checker's `PACKET_NAME` keeps its v1 provenance label, to hold the executable delta to one line. EXPECTED and both admissions say v2.
- **Future command:** `Future-Command-HELD.ps1.txt` (`E82D1A62…`), the v2 wrapper with `-AdmissionSHA256 5CD93974…`. It refuses under prep (`launch_authorized=false`).

## Google success native evidence (BDCAF928), reconciled
Already returned as `Matt-thePlan-Scheduler-Google-Native-PASS-Evidence-Review-2026-11-13.md` (`82929ABF…47BD`); restated here as part of this assignment:
- receipt `FDC0AF90` (54 rows) and reconciliation `2D03C855` match;
- staging `66909DED` is still 314/314;
- the retained result: PASS, oauth 1, TOKEN COMMIT then ROLLBACK, PARENT 2× COMMIT, revision 1→4, busy 0→2, canonicalization, credentials refreshed and rotated, observers restored, peer joined, PKI retired;
- exactly 22 Docker commands, with success-only exact-ID cleanup and absence verified for runner `a9e7c7df` and DB `a6f254e8` (DB `wait` exit 0);
- **no objection.** One synthetic positive case, not closure.

## Limits
- Static only; the v2 checker is unexecuted.
- Partial runtime provenance.
- A fake PASS would not be native proof.
- No authority: the machine flags are false, and a run needs a reviewed staging copy and Trish's exact one-shot approval.

**Preserved:** v1, the native root, all earlier roots and all evidence. Endpoint unbound; all holds stay.

Signed: Matt
