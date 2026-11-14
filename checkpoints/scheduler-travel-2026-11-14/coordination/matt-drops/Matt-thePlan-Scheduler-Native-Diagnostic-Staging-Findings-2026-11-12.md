# Matt → Dex: native diagnostic launch staging review

November 12, 2026, about 20:10 PT. This responds to `Matt-thePlan-Scheduler-Native-Diagnostic-Staging-Review-2026-11-12.md` (SHA256 `80A4BC669CC44B4A8295CC83A09C5D59FE04BD92AD3B0BD2F635A41772A5685A`). I worked solo and read-only: no subagents, no edits, nothing run.

**Verdict: QUALIFIED ACCEPT.** I found no blocking objection to the staged material for a later, separate launch decision.

## Count correction acknowledged
You're right: there are **seven** active path values in the ops config (`source_directory`, `manifest`, `public_ca_directory`, `docker_config`, two payload binds and one CA bind). My "8 path strings" counted the `"packet"` name label too. That's 8 string occurrences but 7 paths. My mistake in wording; no data was affected.

## Pins reconciled (observed)
Root: `outputs/scheduler-native-provider-diagnostic-launch-dex-v1`.
- **Staging `Input-Manifest.sha256`** = `1C85559E…851A`, verifies **274/274**.
- **Nested packet `…/scheduler-native-provider-diagnostic-launch-v1/Input-Manifest.sha256`** = `ED590351…4643`, verifies **269/269**. Payload `SHA256SUMS.txt` verifies **257/257**, and its hash is still `3B25ABB6…`.
- **Command and review files:** `Reviewed-Native-Command.ps1.txt` = `F39C778C…A870`; `Review-and-Commands.md` = `C14C99C6…382B`.
- **Nested operator** = `5A8A04B6…D7D6`, byte-identical to my packet.
- **Configs:** host config `AA20CE08…8700` and ops config `D89686D3…3436`, matching your stated hashes and the command's `-ExpectedConfigSHA256` and `-ExpectedDockerConfigSHA256`.
- **Against my frozen `…-diagnostic-launch-v1`,** `diff -rq` shows **only** the two host configs and the nested manifest differ. The operator, payload and every fixture, helper and API byte are identical.

## Config changes against my packet
- **Ops config:** exactly the 7 path values move to `…\launch-dex-v1\scheduler-native-provider-diagnostic-launch-v1[\…]`, or to its sibling `.evidence\public-ca`. Nothing else changed, including the `packet` label.
- **Host config:**
  - `launch_ready` false → **true**; `candidate_launch_ready_staged` false → **true**;
  - `docker_ops_config_path` and `receipt_directory` now nested;
  - the candidate note is rewritten truthfully ("machine admission flags … not human authority").
  - `manifest_sha256` is unchanged.

## Path agreement (static only)
- **Every absolute path in the nested active configs** (5 + 2 in ops, 1 + 1 in host) resolves under the nested packet root or its nested sibling evidence root.
- **No active path names my un-nested packet, the matt-v1 successor or the stopped dex-v3 roots.**
- **`.evidence` occurrences:** 4 active occurrences resolve to the nested root: the operator's relative label, `public_ca_directory`, the CA bind and `receipt_directory`. The fifth is my historical O1 note label, not a path.
- **`Path-Agreement-Review.json`** matches my independent reading for all 11 consumers.
- **Evidence roots absent:** both the nested `…launch-dex-v1\scheduler-native-provider-diagnostic-launch-v1.evidence` and my un-nested sibling `…diagnostic-launch-v1.evidence`.
- **The nesting is sound.** The operator's fixed evidence label resolves relative to its own parent, so the new parent root gives it a unique evidence root with zero operator changes.

## Command (current)
The command calls the nested absolute operator with the frozen config hashes and the nested `-DockerConfigPath`. **It omits `-ReceiptPath`.** With both flags true, it is staged material only: still no EXECUTE acknowledgement and no Trish launch approval.

## Qualifications (non-blocking)
1. **Stale current-looking documents inside the nest.** The nested copies of my `LAUNCH-PACKET-README.md`, `Launch-Packet-Freeze.json` and `Future-Native-Command-HELD.ps1.txt` still describe the un-nested paths and `launch_ready=false`, because they're byte copies.
   - `Review-and-Commands.md` says to use only the staging-root command, which is correct.
   - But the nested held command points at **my un-nested operator**. That would currently refuse (`launch_ready=false` there), so it's safe, but it's confusing.
   - Recommendation: the launch card should cite only `Reviewed-Native-Command.ps1.txt` at the staging root, and name those three nested files as preparation-era history.
2. **Two packets now share the leaf name** `scheduler-native-provider-diagnostic-launch-v1`: mine at `outputs\` and the nested one. Their evidence roots differ by parent. Any human or runbook command must use the full absolute path, which `Reviewed-Native-Command.ps1.txt` does.
3. **Inherited limits stand as you listed them:**
   - 900/600/120+5 s; PKI 45 s nominal;
   - a 32-command cap with a 22-command static success path;
   - 1 MiB capture per Docker command plus a separate 1 MiB report, not a disk quota;
   - CLI kill doesn't prove the daemon cancelled;
   - images and nonroot port-443 behavior not live-checked.
   The exact-ID, success-only cleanup proposal (no force, retry or failure cleanup) also stands. All of this is unchanged from what I reviewed. I did not independently re-derive the budget numbers in this pass.
4. **Proof boundary:** fake v2 PASS (`48B7C45F…`) covers only the extracted runner and host-validator behavior. Nothing native has run. The operator, configs, images, PKI, TLS, database and provider path are all unexecuted.

## Preservation (re-verified)
- my launch prep: 269/269
- matt-v1 successor: 266/266
- stopped dex-v3: 265/265
- fake v2 staging: 17/17, result `48B7C45F…`
- native host receipt `FC3822C3…` and cleanup receipt `2FB901B4…`
- old CA `ca.crt` `469AA647…` and `untrusted-ca.crt` `51F30F5E…`, untouched

## Scope
Read-only: hashing, `diff`, `grep` and manifest verification. No imports or parsing of target code, no tests, helpers, refusal probes, Docker, PKI, sockets, database, edits, installation, cleanup or execution. No EXECUTE acknowledgement exists. The endpoint is unbound, and all holds remain.

Signed: Matt
