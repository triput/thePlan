# Matt → Dex: native diagnostic launch packet preparation handback

November 12, 2026, about 19:50 PT. This responds to `Matt-thePlan-Scheduler-Native-Diagnostic-Preparation-2026-11-12.md` (SHA256 `0215F8A7EFA1DAEAE791444C022C658E0BADEAC35C08DA582C6322CE7952C2AA`). I worked solo; no subagents were used.

**Status: PREPARED_NOT_EXECUTED, frozen, no active writer.** Host `launch_ready` and `candidate_launch_ready_staged` are false. No EXECUTE acknowledgement exists. The endpoint is unbound.

## Authority checked
- The approved scope `Reconciled-Native-Preparation-Scope-For-Approval.md` is `FCB1B4BB…7891`, matching `Native-Preparation-Approval.json` (Trish's card answer at 03:28:01Z, preparation only, execution false, cleanup false).
- The diff `Proposed-Operator-Evidence-Label.diff` is `5092F682…7D69F`.

## Packet
`C:/Users/trish/Documents/Codex/2026-10-15/trish-wants-to-improve-dex-s/outputs/scheduler-native-provider-diagnostic-launch-v1`
- **Baseline** `…-runner-diagnostic-prep-matt-v1` verified 266/266 (manifest `899B06F6…0DA7`) before copying. Neither the target nor `…-diagnostic-launch-v1.evidence` existed beforehand.
- **`Input-Manifest.sha256` = `73991C344CD8E9F77A16381EC6BA571F1256395E4B0B8A1C95B1D600C9423B28`.** It has 269 entries with paths relative to the packet root, covers every file except itself, and verifies 269/269.
- **Full diff against the baseline:** `Matt-thePlan-Scheduler-Native-Launch-Packet-Diff-2026-11-12.diff` (`F640BA5A…ADF6`). The changed files are the operator, the two host configs and three new current documents.

## Exact source diff (the only executable change)
`patch -p1` (dry run first) applied it to `Invoke-Native-Provider.ps1` line 42:
```
-$evidence = Join-Path (Split-Path $PSScriptRoot -Parent) 'scheduler-native-provider-first-native-launch-candidate-dex-v3.evidence'
+$evidence = Join-Path (Split-Path $PSScriptRoot -Parent) 'scheduler-native-provider-diagnostic-launch-v1.evidence'
```
Hash `090A0FA8…F612` → **`5A8A04B6FC497BEA634C095686B3E7C2B76CE8E64BC526053687C399E66DA7D6`**, exactly as approved. `diff` shows line 42 only. Refusals (lines 93 and 141), admission order and supervision are unchanged.

## Unchanged-executable and API comparison
`diff -rq` against the baseline lists only the 3 modified files plus the 3 new documents.
- **Payload:** `payload/SHA256SUMS.txt` `3B25ABB6…2A90` verifies 257/257 (relative root `payload/`), including all 234 API files.
- **Runner:** `40A1BA8E…F73F`.
- **Host validator:** `7F7EA820…AC53`.
- **`payload/runner-config.json`:** `E132A138…A160`, byte-identical, with the inherited internal `launch_ready: true` (Q1).
- **Everything else unchanged:** all fixture and helper bytes, images, isolation, budgets and caps, and the NP-V-MS-NONEXPIRED batch. No T05.

## Data changes (outside the payload)
- **`host/docker-ops-config.json` → `B930542A56EA47C3EDA65B04A9C958D8CE67103AE7D92635B8D08E34B80E6508`.** Only its 8 path strings changed (`…runner-diagnostic-prep-matt-v1` → `…diagnostic-launch-v1`).
- **`host/launch-config.json` → `A7535D803B7351DFD2B814880698BC7509437C8697D302C77F42EE584E03CE43`:**
  - packet name, `docker_ops_config_path` and `receipt_directory` updated;
  - candidate note rewritten;
  - O1 note marked HISTORICAL and resolved;
  - four `launch_packet_*` lineage keys added;
  - `manifest_sha256` unchanged; **launch flags false.**
- **New current documents:**
  - `LAUNCH-PACKET-README.md` `41373F62…F496`;
  - `Launch-Packet-Freeze.json` `C4ED3D6E…CDC4`;
  - `Future-Native-Command-HELD.ps1.txt` `ECB91E88…451E`.
- **Historical records stay byte-identical** and are labeled in the README and freeze record: `TIP-FREEZE.json`, `Launch-Decision.md`, `Static-Staging-Receipt.json`, `Reviewed-Command.ps1.txt` (which points at the stopped operator; do not use) and `SUCCESSOR-README.md` (its O1 statement is superseded by this packet).

## Path-agreement table (static review only; no code enforces it)
| Consumer | Value |
| --- | --- |
| Operator evidence root, line 42 | `…\outputs\scheduler-native-provider-diagnostic-launch-v1.evidence` |
| Default receipt, line 136 (derived; future command omits `-ReceiptPath`) | `<root>\native-provider-host-receipt.jsonl` |
| Public-CA output, line 139 (derived) | `<root>\public-ca` |
| docker-ops-config `public_ca_directory`, line 5 | `<root>\public-ca` ✔ |
| Runner read-only `/public-ca` bind, line 114 | `<root>\public-ca` ✔ |
| launch-config `receipt_directory`, line 56 (declaration only; the operator doesn't read it) | `<root>` ✔ |
| `source_directory`, `manifest`, database and runner payload binds, `docker_config`, `docker_ops_config_path` | under `…\scheduler-native-provider-diagnostic-launch-v1\` ✔ |

- **Every active `.evidence` literal** (operator, host configs, payload) names the new root.
- **No active path** names the dex-v3 or matt-v1 roots. Only two launch-config **label** keys carry lineage names: `diagnostic_successor_of` and `launch_packet_prepared_from`.
- **Static review only:** the operator doesn't compare `public_ca_directory` with `$evidence\public-ca`, and `receipt_directory` isn't read. Agreement holds by review and the hashes, not by code.
- **The evidence root is absent at freeze.**

## Future command (HELD; current shape)
```
& 'C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-native-provider-diagnostic-launch-v1\Invoke-Native-Provider.ps1' -ExpectedConfigSHA256 'A7535D803B7351DFD2B814880698BC7509437C8697D302C77F42EE584E03CE43' -ExpectedDockerConfigSHA256 'B930542A56EA47C3EDA65B04A9C958D8CE67103AE7D92635B8D08E34B80E6508' -DockerConfigPath 'C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-native-provider-diagnostic-launch-v1\host\docker-ops-config.json'
```
- It omits `-ReceiptPath`.
- Against these configs the operator stops on `launch_ready=false` before starting any child.
- A launch needs a reviewed staging flip, which changes the launch-config hash and therefore this command, plus your EXECUTE acknowledgement and Trish's one-shot approval of the final hashes.

## Inventories and the acyclic chain
- **Packet relative root:** the packet directory.
  - `Input-Manifest.sha256` (269) pins every file;
  - `payload/SHA256SUMS.txt` (257, relative root `payload/`) pins every payload file except itself;
  - the host configs live outside the payload.
- **Admission chain:**
  - the operator admits the launch config and the docker-ops config only through caller-supplied expected hashes;
  - the launch config pins the payload manifest hash;
  - the operator verifies the interpreter `5F7B89A6…52EC` and `docker.exe` `8985CD8A…9A70` hashes from the launch config;
  - images are pinned by digest in the configs.
- **No self-hash fixed point:** the freeze record doesn't pin `Input-Manifest`, and this handoff's hash manifest pins `Input-Manifest`.

## Preservation (re-verified after the work)
- successor matt-v1: 266/266
- stopped dex-v3: 265/265
- fake prep v1: 14/14; v2: 14/14
- failed staging v1: 17/17, receipt `3B385B4F…`
- PASS staging v2: 17/17, result `48B7C45F…`, receipt `C6E6C34E…`
- native host receipt `FC3822C3…` and cleanup receipt `2FB901B4…`
- old CA evidence `…dex-v3.evidence\public-ca\ca.crt` `469AA647…` and `untrusted-ca.crt` `51F30F5E…`, both untouched

## Proof boundary
- **Authored:** the one-line operator change, the data refreeze and the documents.
- **Static:** the diffs, hashes, manifests and path table above.
- **Not executed:** the operator, the configs and the native path.
- Fake v2 PASS covers extracted runner and host-validator behavior only. No native, Docker, PKI, TLS, provider or database proof.

## Scope statement
Only reading, copying, the one literal `patch`, `sed` path and label substitutions in the two host JSON configs, hashing, and document and manifest authoring.
- No imports, parsing, compilation, tests, helper or check invocation, or refusal probes.
- No PKI, sockets, Docker, database, launch, installation, cleanup or Git, and no `F:/Code Repo/ThePlan` edits.
- No evidence or CA deleted, and no predecessor modified.

JSON validity of the two edited configs was checked by eye only. The edits were value substitutions plus appended keys, with a comma added on the preceding line.

Signed: Matt
