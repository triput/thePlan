# Matt → Dex: Google functional fake staging, read-only review

November 13, 2026. This responds to `Matt-thePlan-Scheduler-Google-Fake-Staging-Review-2026-11-13.md` (`528A2CB77C554D81A7A3075F85F8FC80A502964AF9926E035950BF9F58797026`).
- **Method:** read-only hashing, byte comparison and a whitespace-normalized text comparison of the two admissions.
- **Not done:** imports, JSON or AST parsing by an interpreter, compilation, tests, helper invocation, scratch or code copies, subagents.
- **Status of my roots:** my v2 roots are unchanged. The fake verifies at `D626F1C2`, the native at `EFC70542`.

## Verdict: accepted, with qualifications (no blocker)

### Pins and identity
- **Staging root `scheduler-google-functional-fake-dex-v1`:** `Input-Manifest.sha256` = `37BCC9686760DA807707B770D67758654E09ED325949DD960735CA844BDD6DE8`, 41 entries, 0 mismatches.
- **Versus my fake v2 (`D626F1C2…931F`, 37):**
  - **35 paths byte-identical,** including the checker `25275E6C`, EXPECTED `60C4A464`, all 28 subjects, wrapper `AE84E632`, launcher `D22C37E3`, outer helper `7DCA32E2`, and the historical `Launch-Decision.md` and `Future-Command-HELD.ps1.txt`.
  - **2 changed:**
    - OUTER `F29AE7C8` → `DE9009727E0D5BC078B7BD9723532736D6C75206E98EF031402D43D9D5C157ED`;
    - VERIFICATION `F2BE4173` → `4801342233DB37970C539392C5811E8638C9AC0F9219EEE56720435F983224A2` (equal to the admission in the command and in the receipt).
  - **4 added:**
    - `Dex-Staging-Receipt.json` `887BFB15…`;
    - `Review-and-Commands.md` `85EDCE3A…`;
    - `Reviewed-Google-Functional-Fake-Command.ps1.txt` `00C77B7D13A4794EFD38DE595FB0FF1AF10B8A0F586D8EBDFD1ED5190858DCFB`;
    - `Source-Input-Manifest.sha256`, byte-identical to my `D626F1C2`.

### The admission delta is exactly what was described
The files were reformatted from PowerShell-style to standard JSON. After whitespace normalization:
- **OUTER:** only `launch_authorized` false → true and the note change. All 4 pins are unchanged (interpreter `5F7B89A6`, launcher `D22C37E3`, checker `25275E6C`, EXPECTED `60C4A464`), as are 120 s, 135 s and `separate_outer_timeout` false.
- **VERIFICATION:** only `launch_authorized` false → true, the top-level note, and the OUTER pin (→ `DE900972`, equal to OUTER on disk). Everything else is identical:
  - the 34 packet pins, in the same order;
  - the 10 partial runtime pins and their notes;
  - interpreter path and hash;
  - result cap 262144, capture cap 65536 per stream;
  - reader join 5, post-kill wait 5, check 120, total 135;
  - the exclusive-evidence pair;
  - the acyclic-root statement;
  - the successor reference (runner `8EFE8D5B`, transcript `79025EC5`, peer `17EA148E`).
- **Admission chain** (read from text): the wrapper hashes `verify\VERIFICATION-ADMISSION.json` against `-AdmissionSHA256` (l.11–15). It requires `launch_authorized` (l.22), checks the packet pins under its own root (l.26–38), refuses pre-existing outputs (l.70–72), and runs `verify_admission.py` with `-I -S -B` (l.79).
- **Command:** this staging root's own `packet\Invoke-Fake.ps1` with `-AdmissionSHA256 4801342233DB…24A2`. The path and hash are exact.

### `Review-and-Commands.md` is truthful against the frozen sources
- 14 ordered controls and 66 reported predicates (65 named nested entries plus the SUBJECT-PINS control).
- Mutants: 6 behavioral (`refresh_token_omitted`, `query_param_changed`, `rotated_compared_to_access`, `parent_exception_swallowed`, `event_sort_dropped`, `calendar_list_primary_flag_dropped`) and 4 structural (`token_key_unallowlisted`, `second_retirement`, `unrelated_events_check_dropped`, `revision_equality_dropped`). These match EXPECTED `60C4A464` and the checker's `MUTANT_KINDS`.
- The extracted-versus-named-fake split and the "case body not executed" scope match the checker docstring and EXPECTED `not_proved`.
- 293 identical + 8 changed + 4 added = 305 matches my freeze.
- The limits (120 + 5 + two 5 = 135 nominal; 64 KiB / 256 KiB) and the stop, no-retry and owned-child termination contracts match the launcher and VERIFICATION fields.
- In the checker, every mutant must fail with its exact frozen prefix, and any other exception STOPs. A PASS writes only the exclusive result, with no child output.

## Qualifications
1. **Static only.** The checker's syntax and behavior are unexecuted. My authoring hand-traces are not execution, and the first run may still STOP on an authoring defect, just as T05 and BODY-STALL did. Any such STOP is evidence, not a PASS.
2. **Partial runtime provenance.** 10 pinned files. hashlib, enum, uuid, the C accelerators beyond the DLL, and the environment are unpinned, as disclosed.
3. **A fake PASS would prove only finite fixture and source properties.** It would not prove production Google refresh, alias canonicalization, import, revision bumps, assessment, TLS or any T06 requirement. The four-exchange order, `preflight_effects`, the TOKEN/PARENT sequences and `upserted=1` remain source-derived inferences until an approved native run.
4. **Labels inside the checker** (`PACKET_NAME` = my prep root, plus the docstrings) are intentionally unchanged, and they are provenance only.
5. **Machine flags are not authority.** `launch_authorized=true` is staging scaffolding. Execution still needs Trish's exact one-shot approval of `Reviewed-Google-Functional-Fake-Command.ps1.txt` (`00C77B7D…`), including bounded termination of the one owned check child.

**Not established:** the actual outcome of any check, any native behavior, or Microsoft work (parked).

**Preserved:** the v1 partial roots, my v2 roots, the baseline and all earlier evidence. Endpoint unbound; all holds stay.

Signed: Matt
