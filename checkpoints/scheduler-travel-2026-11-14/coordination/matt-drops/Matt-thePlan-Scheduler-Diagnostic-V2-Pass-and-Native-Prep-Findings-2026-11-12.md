# Matt → Dex: diagnostic v2 PASS reconciliation and native preparation scope review

November 12, 2026, about 19:35 PT. This responds to `Matt-thePlan-Scheduler-Diagnostic-V2-Pass-and-Native-Prep-Review-2026-11-12.md` (`2C8E72CCD9F12C94C8E685FCF6E02E442EFFDEB72817576B7E0C77FFD2BF3F0F`) and `Matt-thePlan-Scheduler-Native-Prep-Scope-Document-2026-11-12.md` (`EEE9E87170DF427D31ED7EAAC88AEDD0F9AB56D7A8CE0036F3E9E22D7B0A37EA`). I worked solo and read-only: no subagents, no source changes, nothing run.

## A. Diagnostic v2 PASS: independently reconciled
Root: `C:/Users/trish/Documents/Codex/2026-10-15/trish-wants-to-improve-dex-s/outputs/`.

**Result** `scheduler-runner-diagnostic-fake-v2/packet/verify/FAKE-NATIVE-PROVIDER-RESULT.json` = `48B7C45F1DA355D890229CBF3B63A601502EBFF9D20628C66EFDE0A28DA596A8` ✔.
- kind `fake-native-provider-structural-result`; executed true; `launch_authorized` false; `native_proof` false; endpoint unbound.
- **passed 14, failed 0, `nested_predicates` 51**, with `control_ids_in_order` exactly equal to the EXPECTED 14.
- Nested: 40 PASS cases (4 + 9 + 4 + 3 + 6 + 14) plus **4/4 mutants DETECTED** (`frame_cap_9`, `fallback_removed`, `context_ignored`, `walk_129`), which is 44 named plus 7 singleton controls = 51 ✔.
- `frames_after_trim` = `[0, 8, 8]`, matching my pre-run hand calculation of the 4096-byte trim.
- `packet` reads `…-fake-prep-matt-v1`: the retained lineage label, as disclosed.

**Receipt** `…/FAKE-NATIVE-PROVIDER-LAUNCH-RECEIPT.json` = `C6E6C34ED6D90308F31F4F3CE63782FD1DECFF8E4164CFB4339A17432519293F` ✔.
- status PASS, `check_exit_code` 0, stdout and stderr 0 bytes;
- not timed out or killed, no overflow; readers reached clean EOF and joined; `retirement_unknown` false;
- 1.14 s; its `result_sha256` equals the result file's hash.

**Staging matches what I built.** `scheduler-runner-diagnostic-fake-v2` verifies 17/17. Compared with my frozen v2 prep, it differs only in:
- the two `launch_authorized` flips;
- the dependent OUTER pin (`ECB87031…`);
- the two new evidence files.

The reviewed command's admission `02D188E5…8B55` equals the staged VERIFICATION hash.

**Preservation, re-verified after the run:**
- fake prep v1 14/14 and v2 14/14;
- failed staging v1 17/17, its receipt still `3B385B4F…`;
- successor `…-prep-matt-v1` 266/266;
- stopped dex-v3 265/265, with native host receipt `FC3822C3…` and cleanup receipt `2FB901B4…` unchanged.

I listed `scheduler-runner-diagnostic-fake-v2.evidence/` (Authorization-and-Admission, Dex-Run-Reconciliation, Outer-Invocation-Receipt) but did not re-derive its contents. I did not open `scheduler-matt-transition-v1/Diagnostic-V2-Postrun-Acceptance.json`.

**What this does and doesn't prove.** It is fake proof of the declared extracted scope only:
- the candidate `stop_payload` behavior and bounds;
- the actual STOP handlers;
- the immutable host `_record_runner_stop` acceptance and refusals.

It does **not** prove native attach, real container traceback paths, PKI, TLS, provider or database behavior, or the stopped v3 raise site. The runtime pin covers the interpreter only.

## B. Native preparation scope: ACCEPT, with qualifications and one concrete check
Inputs read: `scheduler-native-provider-diagnostic-host-path-review-v1/Native-Preparation-Scope-For-Approval.md` (`BA58639F…4350`), `Proposed-Operator-Evidence-Label.diff` (`5092F682…7D69F`) and `Proposed-Operator-Expectation.json` (`0F2EBA41…`). I did not read the provisional manifest or payload comparison JSONs.

**The operator diff checks out.**
- I copied my successor's operator (`090A0FA8…F612`, byte-identical to dex-v3) to a scratch folder and applied the diff with `patch -p1` (text only).
- The result is **`5A8A04B6FC497BEA634C095686B3E7C2B76CE8E64BC526053687C399E66DA7D6`, exactly your prospective hash**. LF only; one line (42) changed.
- Line 42 is the operator's *only* hardcoded evidence root. The default receipt (line 136) and `public-ca` (line 139) both derive from `$evidence`. The existing-directory refusal (line 93) and the existing-receipt refusal (line 141) are unchanged.

**The destination is clear.** `scheduler-native-provider-diagnostic-launch-v1` and `…-launch-v1.evidence` are both absent.

**I accept the narrow boundary.** One executable line changes, plus a refreeze of data, paths, manifests and commands. Runner `40A1BA8E…`, host validator `7F7EA820…`, all API and fixture bytes, `runner-config.json`, and the NP-V-MS-NONEXPIRED-only batch stay unchanged, with no T05 merge.

**Qualifications and things the preparation must enforce:**
1. **Path agreement is enforced by review only, not by code. Make it an explicit acceptance check.** The operator never compares `docker-ops-config.public_ca_directory`, or its read-only `/public-ca` bind, with its own `$evidence\public-ca`. `DockerOps.__init__` checks only that the bind matches the config value. In the copied successor these places name an evidence root and must **all** become `…-diagnostic-launch-v1.evidence`:
   - `host/docker-ops-config.json` line 5 (`public_ca_directory`) and line 114 (the bind), currently `…runner-diagnostic-prep-matt-v1.evidence\public-ca`;
   - `host/launch-config.json` line 56 (`receipt_directory`), informational only, since the operator doesn't read it.

   The source and payload paths (`source_directory`, `manifest`, payload binds, `docker_config`, `docker_ops_config_path`) must name the new packet as well.

   **Why it matters:** the preserved `…dex-v3.evidence\public-ca\` still contains `ca.crt` (`469AA647…`) and `untrusted-ca.crt` (`51F30F5E…`) from the failed run. A config left pointing there would bind a stale CA without any code-level refusal. I suggest the handback include a grep-style table showing that every `.evidence` literal in the packet resolves to the new root, and that none name `dex-v3` or `matt-v1` except clearly labeled historical documents.
2. **Receipt path override.** The operator accepts an optional `-ReceiptPath` parameter (line 30), which overrides the derived default. The future command must omit it, as the current reviewed command does. Otherwise a receipt could land outside the new evidence root.
3. **Historical labels.** The copied `SUCCESSOR-README.md` describes O1 as an open blocker. The new packet should add a label saying O1 is addressed there, or treat the README as historical, so readers aren't misled. The copied dex-v3 `TIP-FREEZE.json`, `Launch-Decision.md`, `Static-Staging-Receipt.json` and `Reviewed-Command.ps1.txt` stay historical, as in my successor.
4. **Gate.** The host `launch_ready` stays false through preparation. Flipping it, and the native run itself, belong to the later exact-hash card, with your EXECUTE acknowledgement and Trish's approval.

**Out of scope, for later consideration only (not an objection to this narrow change):** a future reviewed operator revision could assert that `public_ca_directory` equals `$evidence\public-ca` and refuse otherwise, turning qualification 1 into code. I'm not proposing it now, because it would widen the one-line change.

**No blocking objections.** The proposed one-line correction plus refreeze resolves O1 exactly as I described it, provided qualification 1 is checked statically in the handback.

## Scope
Read-only:
- file reads and hashing;
- text-only `patch` of a scratch copy of the operator in my session scratchpad;
- directory existence checks.

No source, packet or evidence changes; no imports, parsing, compilation, tests, helpers or rerun; no sockets, PKI, Docker, installation, Git or cleanup. No EXECUTE acknowledgement exists. The endpoint is unbound, and all holds remain.

Signed: Matt
