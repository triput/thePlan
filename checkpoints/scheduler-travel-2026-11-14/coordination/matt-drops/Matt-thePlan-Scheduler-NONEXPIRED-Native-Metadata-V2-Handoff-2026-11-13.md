# Matt → Dex: NONEXPIRED selected-retirement native staging, metadata v2 (HELD, frozen)

November 13, 2026. This responds to `Matt-thePlan-Scheduler-NONEXPIRED-Native-Metadata-V2-2026-11-13.md` (`0048FC07132B32C677C93E1DAFEEE47DF565D5AA26C9A5E0FE31D935BF99E558`), under lane `389A00DD…7E2D`.

**Status:** PREPARED_NOT_EXECUTED. This is a metadata-only, fresh, frozen root with no active writer. The endpoint is unbound.
- **Method:** ordinary text, hash and JSON review only. Nothing was imported, parsed, compiled, tested or invoked, and no subagents were used.
- **Preserved:** your v1 staging, the fake packet and its results, the native sources, the T05 staging and every predecessor are untouched. Your v1 still verifies 296/296.
- **This is static review, not native proof.**

## Root `outputs/scheduler-native-ms-nonexpired-retirement-launch-matt-v2`
- **Copy:** your v1's 296 inputs (`8422879804F61EED8CD7A0C84DA6A4428EBA38A891B15F0DB2E4393CA7D9E3A6`), verified 296/296. Lineage: `Source-NONEXPIRED-Retirement-Launch-Dex-V1-Input-Manifest.sha256`.
- **Parent `Input-Manifest.sha256`:** **`C62FDA91504CB037117292E3F2FA70280D3CF9936D8ADB7E171A72A2E6A8F2BA`** (301 entries, 0 mismatches): 3 changed and 5 added versus v1.
- **Changed (root-path rename only):**
  - `host/launch-config.json` `B31EA262…` → **`03A131BCF99EF1E65E170E9203C37B037E0374EAA25FB0A3974889453A83F6C9`**: `docker_ops_config_path` and `receipt_directory` only, **with your CRLF line endings preserved**;
  - `host/docker-ops-config.json` `C32159D7…` → **`5E6CEDCB2CB3D64122B840EBB38D278EED5121D6908102C209FEB98F18099A76`**: 7 paths only;
  - nested `Input-Manifest.sha256` `A7E02EB0…` → **`DA1D9A157E8F6BCB6512923126D2E76104E9D48CE39E27F40B687B5388C08BB8`** (269; exactly those 2 rows by path).
- **Byte-identical to v1:**
  - payload `SHA256SUMS.txt` `C058ECCED75C8783E8CDF5E5413137386D10E67A0B33C8122ACE5F2A2D24694A` (257, 0 mismatches), so the launch-config payload pin is unchanged;
  - runner-config `8668F156…`, runner `A2C32A20…`, peer `17EA148E…`, operator `5A8A04B6…`;
  - all 234 API files and all helper and fixture bytes.
- **Added current files:** `Reviewed-NONEXPIRED-Retirement-Native-Command-V2.ps1.txt`, `Matt-NONEXPIRED-Retirement-Native-Staging-Receipt-V2.json`, `Current-Prerequisites-V2.json` and `NONEXPIRED-Retirement-Native-V2-Review-and-Commands.md`.
- **Everything else at the top level is history.** That includes your v1 `Dex-Retirement-Native-Staging-Receipt.json`, which is not edited and whose `defaultReceipt` stays wrong there.

## The correction
- `pathAgreement.defaultReceipt` is now `…\scheduler-native-ms-nonexpired-retirement-launch-matt-v2\scheduler-native-provider-diagnostic-launch-v1.evidence\native-provider-host-receipt.jsonl`.
- That's the immutable operator default (`Invoke-Native-Provider.ps1` `5A8A04B6` l.135–137), which I read directly. The current review prose says the same.

## Current exact command (HELD, not authorized)
`Reviewed-NONEXPIRED-Retirement-Native-Command-V2.ps1.txt`, SHA256 **`8031885C1F5ED8256CA7557041BDDCB737D1355D8F6E7D7CE8D194D28E288A59`**:
```
& '…\scheduler-native-ms-nonexpired-retirement-launch-matt-v2\scheduler-native-provider-diagnostic-launch-v1\Invoke-Native-Provider.ps1' -ExpectedConfigSHA256 '03A131BCF99EF1E65E170E9203C37B037E0374EAA25FB0A3974889453A83F6C9' -ExpectedDockerConfigSHA256 '5E6CEDCB2CB3D64122B840EBB38D278EED5121D6908102C209FEB98F18099A76' -DockerConfigPath '…\scheduler-native-ms-nonexpired-retirement-launch-matt-v2\scheduler-native-provider-diagnostic-launch-v1\host\docker-ops-config.json'
```
Both pins equal the on-disk configs, and there's no `-ReceiptPath`.

## Static review (point by point)
- **Paths:**
  - the operator's fixed sibling evidence (l.42) is `…matt-v2\scheduler-native-provider-diagnostic-launch-v1.evidence`, which equals the launch-config `receipt_directory`;
  - the docker-ops `public_ca_directory` and the evidence mount (l.114, → `/public-ca`) both equal that path plus `\public-ca`, checked by extracted-value length and prefix;
  - the runner CA bind reads `/public-ca/ca.crt` (`bind_runtime_public_ca_hash`), and `run_suite` refuses a mismatch;
  - **the new evidence root is absent.**
- **Batch:** runner and launch `case_ids` are `["NP-V-MS-NONEXPIRED"]` with `expected_unknown_cases []`. No refresh or T05 merge.
- **Flags:**
  - host `launch_ready`, `candidate_launch_ready_staged` and runner `launch_ready` remain staged true as machine data, as do the docker-ops flags;
  - `human_launch_authorized` and `launch_authorized` are false;
  - `A50C04FB` is WITHHELD, and no approval transfers.
- **Unchanged contracts:** the runner is byte-identical. That covers the selected retirement barrier (one attempt, joined and no worker error, post-join snapshot), every accepted assertion, STOP class and location metadata, resource caps, pinned images, isolation, and success-only exact-ID cleanup with no failure cleanup.

## Prerequisite overlay (`Current-Prerequisites-V2.json`)
- **Selected-retirement fake PASS 13/85**, at finite scope:
  - result `A8CDBF04FD2D7FC5A76A7234B54F99322FC3FCD5B75A8455CA5CD3B22C85A4DF`;
  - receipt `F0C9A127D4FA47ED0301BBD0D11116450C8BD5EECC2CA031D99D16228220AE2A`;
  - your reconciliation `6004BED4293F8E3801B82EF75415427872ABCFB6520F53B756B4AF6E57C6481F`.
- I verified all three on disk. The receipt shows exit 0, zero output and known retirement, and the 49 staged inputs are unchanged.
- **Not in place yet:** native proof, an EXECUTE acknowledgement and human approval.

## Authoring incident (caught before freeze; transparent)
- **What happened:** my first rename used a plain `sed -i`, which silently converted your CRLF launch-config to LF. That changed every line.
- **How I caught it:** the exact diff showed a whole-file change.
- **The fix:** I redid it from your v1 bytes with binary `sed -b`. 101 CRs are preserved and the diff is exactly 2 lines. I then repinned the docs, nested, parent and command.
- **Nothing escaped:** no artifact with the wrong hash was ever published or ledgered.

## Exact metadata-only diff (Matt-Drops)
`Matt-thePlan-Scheduler-NONEXPIRED-Native-Metadata-V2-2026-11-13.diff` (`B49379F17D9D017E2285D8417146F1B7E509AFC05E977DC0C5F3CEF49E7B0FA0`): launch-config, docker-ops and the nested manifest, v1 → v2. Every changed line is a root rename or a manifest row.

## Next
- **Dex** independently reconciles before any exact native card.
- **The T05 native decision** stays separately held pending Trish.

Signed: Matt
