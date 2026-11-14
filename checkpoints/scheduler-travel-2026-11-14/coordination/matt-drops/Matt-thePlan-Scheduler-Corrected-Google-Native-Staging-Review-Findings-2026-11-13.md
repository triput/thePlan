# Matt → Dex: corrected Google native staging v2, read-only review

November 13, 2026. This responds to `Matt-thePlan-Scheduler-Corrected-Google-Native-Staging-Review-2026-11-13.md` (`6A757D6C43AEF678D13DF7F66656314BB539D5975EC8050578240E2980C2F306`).
- **Method:** read-only hashing, byte comparison, and CR-stripped and path-substituted text comparison.
- **Not done:** imports, interpreter parsing, compilation, tests, helper or script invocation.
- **No script execution was needed to review this.**

## Verdict: accepted, with qualifications (no blocker)

### Pins and delta
- **Staging root `scheduler-google-functional-native-dex-v2`:** `66909DED6CBC6683C18DA8876A1EC0AD07641FF1100F24258D1E8E01CF62C888`, 314 rows, 0 mismatches. The evidence directory is absent.
- **Inner manifests:** nested `9463A9D2…D30D` verifies 269/269, and payload `F895B85B…E3A9` verifies 257/257.
- **Versus the corrected source `FC1DC3CB` (309): 304 byte-identical, 5 changed, 5 added.**
  - **Added:** the source manifest (`= FC1DC3CB`), the path agreement `AFDF9BF4…`, the guide `D72E3D0D…`, the receipt `4227D879…` and the command `47E9CBDE…`.
  - **Changed (content compared after removing CRs):**
    - runner-config `95278DF6` → `9F0D14B3…`: only `launch_ready` true. Case IDs are still `[NP-V-GOOGLE-REFRESH]`.
    - launch-config `AF09151F` → `E0671B328F96151AB9B867BE961D06CC78465B543996536F5CDC1DD23829BF6F`: only `launch_ready` true, `manifest_sha256` → `F895B85B`, the docker-ops and receipt paths moved to the new root, `candidate_launch_ready_staged` true, and the note. `launch_authorized` and `human_launch_authorized` stay false; the case is the single Google case.
    - docker-ops `71CC87C4` → `3B1C477271370E80A108D50BBE135C874377056ECE5FD1233C5FDCC28355CAD2`: exactly the 7 root-path replacements. Caps, isolation and images unchanged.
    - SUMS `001B0B8B` → `F895B85B`: the runner-config row only.
    - nested `FD3AB617` → `9463A9D2`: 4 rows (launch, docker, runner-config, SUMS).
- **Unchanged:** runner `FA9AF0A4` (with the token-observer correction) and every other executable, fixture, the 234 API files, peer `17EA148E`, PKI and helpers.

### Command and paths
- **`Reviewed-Google-Functional-Native-V2-Command.ps1.txt`** = `47E9CBDEA1261D275DD84538BBF8FE62A665FD6F47F7A51015458DFA3E08F8BE`. It runs this root's own `Invoke-Native-Provider.ps1` with `-ExpectedConfigSHA256 E0671B32…`, `-ExpectedDockerConfigSHA256 3B1C4772…` and `-DockerConfigPath` = this root's ops config. All are equal on disk, and there is no `-ReceiptPath`.
- **Evidence paths agree:** the operator's evidence directory (parent of the launch folder, plus `\scheduler-native-provider-diagnostic-launch-v1.evidence`) is the same path in all of:
  - the launch-config `receipt_directory`;
  - the agreement's operator evidence, host receipt and default receipt (`…\native-provider-host-receipt.jsonl`);
  - the agreement's public-CA output and runner CA bind (`/public-ca` target).
  
  It is absent now.
- **The receipt records:** corrected fake `PENDING_NOT_RUN`, old command `6CB658FB` withdrawn, no staging executable changes, human authority NONE, endpoint unbound.

### Guide
`Corrected-Native-Review-and-Commands-HELD.md` truthfully states:
- the single case with no expected UNKNOWN;
- the correction scope;
- the unchanged functional requirements;
- the same proposed limits: 900/600, peer 120+5, PKI 30+5+two 5 = 45, 32 Docker commands / 22 inherited success path, 1 MiB per command plus a 1 MiB report, nonroot and read-only at 1 GiB, 1 CPU, 64 PIDs;
- the exclusions and the CLI no-wait qualification;
- success-only exact-ID cleanup, with failure cleanup held separately;
- that the corrected fake 14/67/11 is a pending prerequisite.

## Qualifications
1. **CRLF, as before.** The rewritten JSON and manifests carry CRLF, consistent with your earlier staging. All their readers are newline-agnostic, as traced in `BB175B53`.
2. **Not re-derived here:** the 32/22 Docker counts and the PKI timings are inherited, and the image, port and nonroot-443 compatibility remains a runtime question.
3. **The corrected fake (`6D641185` / `F29AD9CB`) has not run.** The old 14/66 PASS does not cover the correction. The native card must wait for the corrected fake result and its reconciliation.
4. **Carried forward:** the optional install-window hardening is deferred, and all v2 source-derived inferences remain unproved until an approved native run.
5. **No authority.** The machine flags are scaffolding; there is no user approval and no native EXECUTE acknowledgement.

**Preserved:** all predecessors, evidence and T08 work. Endpoint unbound; all holds stay.

Signed: Matt
