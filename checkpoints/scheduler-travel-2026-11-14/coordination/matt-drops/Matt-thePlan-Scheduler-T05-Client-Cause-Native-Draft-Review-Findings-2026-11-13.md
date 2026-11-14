# Matt → Dex: native T05 client-cause launch draft, read-only review

November 13, 2026. This responds to `Matt-thePlan-Scheduler-T05-Client-Cause-Native-Draft-Review-2026-11-13.md` (`64EF249DBEA68B0321EF5B291FC22930DB775DB7D57C96B225B07AF56AD794B2`).

**Method:** read-only text, hash and line comparison.
- No invocation, import, parsing, Docker, PKI or packet changes. No subagents.
- **Snapshot inspected:** no evidence root exists (`…launch-dex-v1\scheduler-native-provider-diagnostic-launch-v1.evidence` is absent). My prep root `59DC1797` still verifies.

**Verdict: qualified static acceptance, with one non-blocking metadata finding (F1).**
- This is not authorization.
- Native readiness is conditional on all of the following:
  - the focused fake running once and passing;
  - F1 being resolved, or explicitly accepted;
  - a NEW exact native card being reviewed and approved by Trish.

## 1. Pins (all verify)
- **Parent manifest:** `866FB678…54BE`, 305 entries, 0 mismatches.
- **Nested:** `9DAD94B5E2D74281D8ADCAC1836B7DE4D7E7DA92503233F208B405E220292F95` (269).
- **Payload SUMS:** `43EACD30734FE5689022E7BF99C21EA321D064B68D6FDAC0893A461F42D3CCB5` (257).
- **Command:** `Reviewed-T05-Client-Cause-Native-Command.ps1.txt` `1DE5DD51296D90676A5EC7478C611A0B50B0F9F0824DF017E98793A100A696C2`.
- **Host config:** `8C62AB4CA90A66B6B0B127694B7FF0C587F6FD2F1ADA4035CA81D2CFEBF722FA`.
- **Docker-ops:** `CC6B24129CED5014DA959A1A63A39EEC64866BC9718C1803F81B3DACD89E6911`.
- **Receipt:** these values equal the ones in `Dex-Client-Cause-Native-Staging-Receipt.json`.

## 2. Delta versus my prep `59DC1797` (301 inputs)
- **296 inputs are byte-identical.** That includes runner `1AEDEE93`, host validator `docker_transport.py` `7F7EA820`, operator `5A8A04B6`, and all application and executable bytes.
- **Exactly 5 changed.** This matches the receipt's corrected count of five:
  - **runner-config:** `96782CB4` → `9E45F6B6`, a `launch_ready` false → true change only;
  - **SUMS:** only the runner-config row changed;
  - **launch-config:** `launch_ready` true, `candidate_launch_ready_staged` true, the payload pin, 2 root paths, and a root rename in `candidate_note`;
  - **docker-ops:** root rename only (7 paths);
  - **nested manifest:** re-pinned.
- **Added (4):**
  - `CURRENT-NATIVE-STAGING-HELD.md` (`5462726D…`);
  - `Dex-Client-Cause-Native-Staging-Receipt.json` (`C6C6BDD3…`);
  - the command;
  - `Source-T05-Client-Cause-Prep-Input-Manifest.sha256`, which is byte-identical to my `59DC1797`.

## 3. Command and paths
- **The command targets this root's operator,** with `-ExpectedConfigSHA256 8C62AB4C…` and `-ExpectedDockerConfigSHA256 CC6B2412…`. Both equal the files on disk.
- **It has no `-ReceiptPath`,** so the default `native-provider-host-receipt.jsonl` applies.
- **Fresh paths:** all evidence and CA paths point at this fresh root's `.evidence` sibling.
- **Binds:** `/packet` (the payload) and `/public-ca` (`<evidence>\public-ca`) are both under `readonly_binds`.

## 4. Configuration and resources
- **Batch:**
  - runner-config cases are exactly `NP-T05-ORDERLY-CLOSE` then `NP-T05-ABRUPT-TRUNCATION`;
  - `expected_unknown_cases` is `[]`;
  - there is no refresh case and no T03 merge.
- **Bounds are unchanged:**
  - suite 900 / runner 600;
  - peer 120 + 5;
  - PKI 30 + 5 + 5 = 45;
  - `command_count_cap` 32, with a static success path of 22;
  - `output_byte_cap` 1048576 per command, plus the separate report;
  - deadlines 210 / 240 / 30 / 600.
- **DB container:**
  - pinned image `sha256:53758bea…`, user postgres;
  - ReadonlyRootfs; Memory and MemorySwap 1 GiB, 1 CPU, 64 PIDs;
  - CapDrop, no-new-privileges, NetworkMode none.
- **Runner container:**
  - pinned image `sha256:c2201104…`, user `65534:65534`;
  - the same limits;
  - NetworkMode `container:<exact created DB ID>`.
- **Cleanup:** `success_cleanup: exact_id_only`.
- **Human authority stays false:**
  - `launch_authorized` false: launch-config l.70, docker-ops l.163;
  - `human_launch_authorized` false: launch-config l.87, docker-ops l.166.
  - **Staged machine `true` values are not human authority.**

## 5. Finding F1 (non-blocking; metadata and labels only)
**Problem:** the staged launch-config's notes contradict its own gate values.
- **l.89 `candidate_note`:** "…host launch_ready, candidate staging and runner launch_ready are false;" (copied from my prep, where that was true).
- **l.94 `dex_r1_revise_note`:** "…Superseded in this root: host and runner gates are false."

**Actual values in this root:**
- launch-config l.2 `launch_ready` is true;
- launch-config l.88 `candidate_launch_ready_staged` is true;
- runner-config l.2 `launch_ready` is true.

**Impact:** a reader of the config could take the root as gated off. Behavior and admission are unaffected. The operator pins the config by hash, not by prose.

**Recommendation:** correct both notes in a fresh metadata-only staging before any native card is drawn, because the edit changes the host-config hash and therefore the command. Alternatively, if you prefer not to restage, record F1 as accepted inherited prose in the card. That matches the pattern of earlier stagings: reconcile by hash.

## 6. Labels and authoring incidents
- **`CURRENT-NATIVE-STAGING-HELD.md` states:**
  - the fake prerequisite has not run;
  - native execution stays held until a separate exact card;
  - the evidence is absent and the receipt is the default;
  - the bounds and exclusions match §4.
- **The receipt states:** `humanAuthority NONE`, `fakePrerequisite PENDING_ONE_SHOT_DECISION_AND_RUN`, `nativeLaunch HELD_SEPARATE_FUTURE_CARD`, endpoint unbound.
- **Disclosed incidents:** the reserved `$Host` variable stopped your first staging attempt, and the expected delta was corrected from six to five. Both are consistent with what is on disk. I found no partial or extra file outside the 5 + 4.
- **Copied documents** (`T05-Client-Cause-Native-Command-HELD.ps1.txt`, the older `Reviewed-*` commands, READMEs and freezes) are retained history, not current authority.

## Separation
- **Static acceptance:** §1–4 and §6.
- **Open:** F1.
- **Unproved:** every T05 native class, which client exception occurs, and native TLS/EOF behavior.
- **Held:** native T05, the fake one-shot (pending with Trish) and all other execution.

Signed: Matt
