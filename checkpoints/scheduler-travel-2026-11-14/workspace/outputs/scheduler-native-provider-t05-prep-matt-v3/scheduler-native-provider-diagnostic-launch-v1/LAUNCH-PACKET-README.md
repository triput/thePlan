# Native diagnostic launch packet v1: CURRENT README (preparation only)

Matt, November 12, 2026. Assignment `Matt-thePlan-Scheduler-Native-Diagnostic-Preparation-2026-11-12.md` (`0215F8A7…C2AA`); approved scope `FCB1B4BB…7891`.

**Status: PREPARED_NOT_EXECUTED.** Host `launch_ready` is false, so the operator stops before starting any child. No EXECUTE acknowledgement exists. The endpoint is unbound.

## This is the current document set
- **Current:** `LAUNCH-PACKET-README.md` (this file), `Launch-Packet-Freeze.json` and `Future-Native-Command-HELD.ps1.txt`.
- **Historical records, not current authority:** `TIP-FREEZE.json`, `Launch-Decision.md`, `Static-Staging-Receipt.json` and `Reviewed-Command.ps1.txt` are byte-identical dex-v3 records. `Reviewed-Command.ps1.txt` points at the **stopped** dex-v3 operator and must not be used.
- **`SUCCESSOR-README.md` is historical too.** It is the diagnostic successor README, and its **O1 statement ("successor is not launchable…") is superseded here**: this packet's operator line 42 names the new sibling evidence root.

## Lineage and the single source change
- **Fresh copy of** `scheduler-native-provider-runner-diagnostic-prep-matt-v1`, whose 266/266 inputs verified before copying (manifest `899B06F6…0DA7`).
- **Operator** `Invoke-Native-Provider.ps1`: the approved diff `5092F682…7D69F`, applied with `patch -p1`, changes line 42 only. Hash `090A0FA8…F612` → **`5A8A04B6FC497BEA634C095686B3E7C2B76CE8E64BC526053687C399E66DA7D6`**.
  ```
  -$evidence = Join-Path (Split-Path $PSScriptRoot -Parent) 'scheduler-native-provider-first-native-launch-candidate-dex-v3.evidence'
  +$evidence = Join-Path (Split-Path $PSScriptRoot -Parent) 'scheduler-native-provider-diagnostic-launch-v1.evidence'
  ```
- **Unchanged:**
  - the payload, 257/257, `SHA256SUMS.txt` `3B25ABB6…2A90`, including all 234 API files;
  - runner `40A1BA8E…F73F`, host validator `7F7EA820…AC53` and `runner-config.json` `E132A138…A160`;
  - every other fixture and helper byte, and the operator's refusals and admission order;
  - the NP-V-MS-NONEXPIRED batch, images, isolation, budgets and caps.

## Data changes (host configs, outside the payload)
- **`host/docker-ops-config.json`** (`B930542A…6508`): 8 path strings changed from `…runner-diagnostic-prep-matt-v1` to `…diagnostic-launch-v1`. No other bytes changed.
- **`host/launch-config.json`** (`A7535D80…CE43`):
  - packet name, `docker_ops_config_path` and `receipt_directory` now name the new packet and its evidence root;
  - the candidate note was rewritten;
  - the O1 note was marked HISTORICAL and resolved;
  - four `launch_packet_*` lineage keys were added;
  - **`launch_ready` and `candidate_launch_ready_staged` remain false**, and `manifest_sha256` is unchanged (`3B25ABB6…`).

## Static path agreement (review only; no code enforces it)
| Consumer | Resolves to |
| --- | --- |
| Operator evidence root (line 42) | `…\outputs\scheduler-native-provider-diagnostic-launch-v1.evidence` |
| Default receipt (line 136, derived) | `<evidence root>\native-provider-host-receipt.jsonl` |
| Public-CA output (line 139, derived) | `<evidence root>\public-ca` |
| Docker config `public_ca_directory` (line 5) | `<evidence root>\public-ca` ✔ |
| Runner read-only `/public-ca` bind (line 114) | `<evidence root>\public-ca` ✔ |
| Host `receipt_directory` (launch-config line 56; informational, not read by the operator) | `<evidence root>` ✔ |
| `source_directory`, `manifest`, payload binds (database and runner), `docker_config`, `docker_ops_config_path` | under `…\scheduler-native-provider-diagnostic-launch-v1\` ✔ |

- **Every active `.evidence` literal** (operator, host configs, payload) names `scheduler-native-provider-diagnostic-launch-v1.evidence`.
- **No active path** names the stopped dex-v3 root or the matt-v1 root. Two launch-config **label** keys (`diagnostic_successor_of`, `launch_packet_prepared_from`) carry lineage names and are not paths.
- **Why the agreement matters:** the operator does not compare the config's `public_ca_directory` with its own `$evidence\public-ca`, so the agreement is static review only. The stopped `…dex-v3.evidence\public-ca\` still contains `ca.crt` and `untrusted-ca.crt`, and no active input points there.
- The evidence root `…diagnostic-launch-v1.evidence` **does not exist** at freeze. The operator refuses an existing root.

## Future command (HELD)
See `Future-Native-Command-HELD.ps1.txt`. It contains:
- the absolute new operator path;
- `-ExpectedConfigSHA256 A7535D80…CE43` and `-ExpectedDockerConfigSHA256 B930542A…6508`;
- the new `-DockerConfigPath`;
- **no `-ReceiptPath`**.

Against these configs the operator stops on `launch_ready=false`. A launch requires:
- a reviewed staging flip, which changes the launch-config hash;
- Dex's EXECUTE acknowledgement;
- Trish's one-shot approval of the final hashes.

## Proof boundary
This packet is authored and statically reviewed only. Diagnostic fake v2 PASS (`48B7C45F…`) proves extracted runner and host-validator behavior with fakes only. Nothing in this packet has been executed: no native, Docker, PKI, TLS, provider or database proof. `Input-Manifest.sha256` covers every file except itself.
