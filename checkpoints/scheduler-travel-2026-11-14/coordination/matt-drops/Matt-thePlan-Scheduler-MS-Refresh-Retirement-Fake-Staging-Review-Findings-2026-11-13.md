# Matt → Dex: MS-REFRESH retirement fake staging, read-only review

November 13, 2026. This responds to `Matt-thePlan-Scheduler-MS-Refresh-Retirement-Fake-Staging-Review-2026-11-13.md` (`3ADC25FB0FBEAC08A6B5CE88EB37F2781CC5B6B4384D62CE8FE1C63968B77A15`). Noted: 6ED9B65F is complete, and the displaced late joined guard is not claimed byte-preserved, only mapped to the helper's stronger predicate.

**Method:** read-only text, hash and whitespace-normalized comparison.
- No invocation, import, parsing, compilation, Docker or packet changes. No subagents.
- **Snapshot inspected:** the staging was not running. There is no `FAKE-NATIVE-PROVIDER-RESULT.json`, no launch receipt and no `.evidence` root.
- **Independence qualification:** I authored the 22 unchanged inputs, including the checker and EXPECTED. My re-trace of the checker's oracles and mutant paths is therefore a careful self-check, not independent review.

**Verdict: no blocker. Qualified static acceptance.** This is not authorization; Trish's one-shot card is separate.

## 1. Inventory
- **Manifest:** `157C6863BA157298E910439D9FF71B8E4F8124B665A7331AFF54918B13EF6CCF`, 27 entries, 0 mismatches. 28 files are on disk, the extra one being the manifest itself.
- **`Source-Input-Manifest.sha256` is byte-identical to my `E85D5C92`,** and my prep root still verifies 24/24.
- **Versus my 24 inputs:**
  - **22 byte-identical:** checker `BF7A7355`, EXPECTED `22CE02C4`, wrapper `AE84E632`, outer `7DCA32E2`, launcher `D22C37E3`, all 15 subjects, and the copied `Launch-Decision.md` and `Future-Command-HELD.ps1.txt`;
  - **2 changed:**
    - OUTER `25BB93FD` → `AD6B95D1E86B7850CA85F929D54531F96DB826840B5516626A197F02B8BE470B`;
    - VERIFICATION `B42F0AC3` → `DE4C94308F1E44FD72E56086F6F9EF4E93FF938B5AD59DA8739D411F635E5F1A`;
  - **3 added:**
    - `Dex-MS-Refresh-Retirement-Staging-Receipt.json` (`13629CEE…`);
    - `Reviewed-MS-Refresh-Retirement-Command.ps1.txt` (`7B617AC0…`);
    - `Source-Input-Manifest.sha256`.

## 2. What the 2 changes contain
- **Format:** both files were re-serialized (2-space indent, CRLF).
- **After removing whitespace and line endings:**
  - OUTER differs **only** by `launch_authorized` false → true;
  - VERIFICATION differs **only** by `launch_authorized` false → true, plus the OUTER pin `25BB93FD` → `AD6B95D1`. That pin equals OUTER on disk.
- **Escaping is clean:** only `\\` pairs.
- **The pins OUTER holds are unchanged:** checker `BF7A7355`, EXPECTED `22CE02C4`, launcher `D22C37E3`, interpreter `5F7B89A6`.
- **Format precedent:** the same CRLF / 2-space re-serialization went through the unchanged outer and launcher in `scheduler-ms-selected-retirement-fake-dex-v1`, which passed 13/85.
- **EXPECTED still says `launch_authorized` false.** That's harmless: only the wrapper (l.22), the outer (l.74) and the launcher (l.82) read the flag, and they read it from the admissions. The same pattern appears in the selected-retirement fake that ran.

## 3. Pins
- **VERIFICATION:** `packet_file_pin_count` is 21, and all 21 packet pins match the files on disk.
- **Runtime pins:** `runtime_file_pin_count` is 10, and the 10 runtime hashes are identical to my prep.
- **Successor reference:** runner `1A95E834`, transcript `BEDCCFD3`, peer `BFB271D7`. These match the native prep root.

## 4. Command and labels
- **The command** `Reviewed-MS-Refresh-Retirement-Command.ps1.txt` is `7B617AC019D5AD2D5AD5BD02DDC3258073F8897B80EE1AC4AD45DEE128D7BAC2`. It is a single line that invokes this staging root's `packet\Invoke-Fake.ps1` with `-AdmissionSHA256 DE4C9430…`, which equals VERIFICATION on disk.
- **The staging receipt** matches on everything I checked:
  - source `E85D5C92`, 24 inputs, 22 unchanged, exactly those 2 metadata-only changes;
  - the command and admission hashes;
  - 10 controls / 41 predicates / 21 packet pins / 10 runtime pins;
  - `humanAuthority NONE`, `executions 0`, endpoint unbound.
- **Your review `MS-Refresh-Retirement-Frozen-Review-and-Commands.md`** is `2B03F0D4C779F3F57E66D38E309DABF63009EE29B70F3414E34F03CB23D18980`.
  - It names the same command, admission and manifest.
  - Its 10/41 breakdown, 3 behavioral / 4 structural mutant split, the structural qualification, the 135 s nominal budget and its exclusions, and the 64 KiB / 256 KiB caps all match EXPECTED and the checker.
  - **Its statement "no extra temporary fixture-directory lifecycle" is correct.** Unlike the T05 client-cause checker, this one imports no `tempfile` and creates no owned root. Its only writes are the result and receipt files.

## 5. Self-check of the unchanged checker
I re-traced each oracle against the frozen subjects by reading the code only.
- **Anchors:**
  - the barrier block, the worker-error guard and both pre-join helper lines each occur exactly once in the candidate runner;
  - the bare helper-call line occurs twice (MS-INVALID and MS-REFRESH), which is why the block anchor includes `retirement_done`.
- **Each mutant hits its own prefix first:**
  - `worker_error_guard_removed` → `retire:worker error refused`;
  - `worker_error_truthiness` → `retire:empty error refused`;
  - `helper_pre_join_snapshot` → `retire:post-join state`;
  - `body_pre_join_snapshot` → `barrier:post-join state only` (the attempt mark and the done flag still bracket the call);
  - `body_second_retirement` → `barrier:no second retirement`;
  - `attempt_guard_missing` → `barrier:attempt marked before helper`;
  - `helper_ignored` → `barrier:helper called once`.
- **Literals I confirmed:**
  - the 4-statement late block and the snapshot occur once each in the source main try;
  - `check_oracles_immediate` and `case_result_receipt` appear once each in the refresh function;
  - the 7 source-root occurrences in docker-ops;
  - the 9 dependency rows, and the 3 peer interface lines (one occurrence each).
- **Not established:** this is not a run. Syntax and behavior remain unexecuted, so a PASS is still required.

## 6. Qualifications (non-blocking)
- **Inherited labels:**
  - OUTER and VERIFICATION `packet` still name `scheduler-native-ms-refresh-retire-fake-prep-matt-v1`;
  - their `note` text says `launch_authorized=false` and "do not invoke under preparation";
  - the copied `Launch-Decision.md` and `Future-Command-HELD.ps1.txt` name my prep root and admission `B42F0AC3`.
  - This is the same inherited-prose pattern as earlier stagings. The current exact booleans and hashes, your review and the human gate control.
- **Not re-derived by me:** your "234 application / 250 other executable files" counts. I confirmed the 291 unchanged native inputs by manifest, and there is no contradiction.
- **A PASS would establish only** the finite helper and source properties. Native refresh, T06 closure, peer timing and worker scheduling stay unproved.

## Separation
- **Static acceptance:** §1–5.
- **Qualifications:** §6.
- **Held:** this fake (its own one-shot card), the T05 fake card, T03 D1, and every native run.

Signed: Matt
