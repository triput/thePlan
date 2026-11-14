# NONEXPIRED selected-retirement native staging, metadata v2 (CURRENT), execution HELD

Matt, November 13, 2026. This is for `Matt-thePlan-Scheduler-NONEXPIRED-Native-Metadata-V2-2026-11-13.md` (`0048FC07…E558`). It's a fresh copy of Dex staging `scheduler-native-ms-nonexpired-retirement-launch-dex-v1` (`84228798…E3A6`, 296 inputs, verified 296/296).

## Current files
- this document;
- `Reviewed-NONEXPIRED-Retirement-Native-Command-V2.ps1.txt`;
- `Matt-NONEXPIRED-Retirement-Native-Staging-Receipt-V2.json`;
- `Current-Prerequisites-V2.json`;
- this root's `Input-Manifest.sha256`.

**Everything else at the top level is history**, never current invocation instructions. That includes the copied `Dex-Retirement-Native-Staging-Receipt.json`, whose `defaultReceipt` of `receipt.jsonl` is wrong, plus `Current-Prerequisites-HELD.json`, `NONEXPIRED-Retirement-Native-Review-and-Commands.md`, `Reviewed-NONEXPIRED-Retirement-Native-Command.ps1.txt` and every older command, freeze or README.

## The correction (metadata only)
- **The error:** the operator `Invoke-Native-Provider.ps1` (`5A8A04B6`, unchanged) defaults the receipt to `<evidence>\native-provider-host-receipt.jsonl` (l.135–137). Dex's v1 staging receipt said `receipt.jsonl`.
- **The fix:** the v2 receipt records the actual default.
- **Unaffected:** the operator, `receipt_directory`, public-CA output and CA bind were never affected.

## Changed versus Dex v1 (exactly 2 source entries, plus the nested manifest)
- **launch-config** `B31EA262` → `03A131BCF99EF1E65E170E9203C37B037E0374EAA25FB0A3974889453A83F6C9`: root rename in `docker_ops_config_path` and `receipt_directory` only.
- **docker-ops** `C32159D7` → `5E6CEDCB2CB3D64122B840EBB38D278EED5121D6908102C209FEB98F18099A76`: root rename in 7 paths only.
- **nested manifest** `A7E02EB0` → `DA1D9A157E8F6BCB6512923126D2E76104E9D48CE39E27F40B687B5388C08BB8`: 2 rows by path.
- **Unchanged:**
  - payload `SHA256SUMS.txt` `C058ECCE…694A` (257, 0 mismatches), so the launch-config payload pin is unchanged;
  - runner-config `8668F156`, runner `A2C32A20`, peer `17EA148E`, operator `5A8A04B6`, all 234 API files and all helper and fixture bytes.

## Exact current invocation (HELD, not authorized)
```
& 'C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-native-ms-nonexpired-retirement-launch-matt-v2\scheduler-native-provider-diagnostic-launch-v1\Invoke-Native-Provider.ps1' -ExpectedConfigSHA256 '03A131BCF99EF1E65E170E9203C37B037E0374EAA25FB0A3974889453A83F6C9' -ExpectedDockerConfigSHA256 '5E6CEDCB2CB3D64122B840EBB38D278EED5121D6908102C209FEB98F18099A76' -DockerConfigPath 'C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-native-ms-nonexpired-retirement-launch-matt-v2\scheduler-native-provider-diagnostic-launch-v1\host\docker-ops-config.json'
```
- There's no `-ReceiptPath`.
- The command file's hash is recorded in the handback sidecar.

## Path agreement
- **One evidence directory:** the operator's fixed sibling evidence root (l.42) is `…\scheduler-native-ms-nonexpired-retirement-launch-matt-v2\scheduler-native-provider-diagnostic-launch-v1.evidence`. The host `receipt_directory` and the docker-ops evidence mount name the same path.
- **Default receipt and CA:** the default receipt is `…\native-provider-host-receipt.jsonl` and the public CA goes to `…\public-ca`. That's mounted at `/public-ca` for the runner, whose `bind_runtime_public_ca_hash` and `run_suite` check `/public-ca/ca.crt`.
- **That evidence root is absent.**

## Batch, assertions and contracts (unchanged)
- **Batch:** `case_ids ["NP-V-MS-NONEXPIRED"]` with `expected_unknown_cases []`. No refresh or T05 merge.
- **Unchanged assertions:**
  - the `_run_np_v_ms_nonexpired` retirement barrier: one attempt, joined and no worker error, then a post-join snapshot;
  - four-connection inventory, alias, coverage, TOKEN terminal, assessment and public checks;
  - STOP payload class and location only;
  - resource caps (900/600, 120 + 5, PKI 45 nominal, 32 commands, 1 MiB per command plus a 1 MiB report);
  - pinned images, isolation, and success-only exact-ID cleanup, with no failure cleanup.
- **Flags:** host, runner and docker-ops ready flags are staged true as machine data. `human_launch_authorized` and `launch_authorized` are false.
- **Old card:** `A50C04FB` is WITHHELD, and no approval transfers.

## Prerequisites (current overlay)
- **Selected-retirement fake PASS 13/85** at finite scope: result `A8CDBF04…`, receipt `F0C9A127…`, reconciliation `6004BED4…`.
- **Not proven natively:** there is no native proof, no matching EXECUTE acknowledgement and no human approval.
- **Next step:** Dex independently reconciles this v2 before any exact native card.

Static text, hash and JSON review only. Nothing was run.
