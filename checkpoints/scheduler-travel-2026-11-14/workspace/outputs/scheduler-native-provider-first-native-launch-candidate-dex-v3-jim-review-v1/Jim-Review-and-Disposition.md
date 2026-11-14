# Jim independent static review — first-native launch-candidate Dex v3

Prepared November 12, 2026. Reviewer seat: Justin under Jim's Dex Scheduler lane. Docs-only / static only. No Invoke-Native-Provider, Docker, PKI, sockets, or imports-to-run. Dex v3 packet and jim-v2 / native-ready / fake-v1 / T05 predecessors were not mutated. Human launch authority HELD. Native remains held. Not waiting on Trish. No Slack tip from this seat.

T05 v3 QUALIFIED ACCEPT `0A63DEAE…` noted as concurrent/irrelevant — this review covers native-v3 only.

## Disposition

**QUALIFIED ACCEPT**

Narrow v3 correction is hash-honest and layout-honest: `docker_config` is a Docker CLI **directory** key (not a docker-ops path alias), empty `payload/docker-config/config.json` pins `E3566B3A…`, original 256 payload files vs jim-v2 TIP on-disk `34BBC408…` are byte-identical, helpers/API/fixture code untouched, host+runner `launch_ready=true` aligned with `human_launch_authorized=false`. Qualifications below are execution-card disclosures — not rebuild blockers.

## Packet under review (frozen; not edited)

Root: `C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-native-provider-first-native-launch-candidate-dex-v3\`

Compared to: `...\outputs\scheduler-native-provider-first-native-launch-candidate-jim-v2\` (TIP on-disk `34BBC408549BA80F54A9DB189C11A37377484B1424FF33F5190836C3224BC440`)

Supplemental audit (read-only): `...\outputs\scheduler-native-provider-first-native-launch-dex-review-v2\V3-Execution-Path-Audit.md` (22-command success path, 32 hard cap, exact-ID success cleanup only).

## Exact hashes reviewed (observed = claimed)

| Role | Path | SHA256 |
|---|---|---|
| Reviewed command | `Reviewed-Command.ps1.txt` | `3550CC2BE81894722E488F94750823D5C925CE86A5D8EA603A7A009314F8182B` |
| Operator | `Invoke-Native-Provider.ps1` | `090A0FA89549D33A381A9DDFF64DFC6AEE59E22F6832AD36018F7ACF8D3AF612` |
| Host launch-config | `host/launch-config.json` | `0F3B0DAD9BA91FC97A61E0633E3295F03201CD2C3DDE3E4B22777E639C369F20` |
| Docker ops config | `host/docker-ops-config.json` | `FB13F282F32905E98515D771BB4C66356E529DF48F7BB0145586A44B08D74B64` |
| Payload manifest | `payload/SHA256SUMS.txt` | `336576063E21ECB1718D2C89DF715E570B6A45FD7EA51ECBCA71EA533F24C06D` |
| Docker CLI config | `payload/docker-config/config.json` | `E3566B3A06430868D71E9287DFD6C6C520A3DA027AABEA01951D407EE131DC2F` |
| Input manifest | `Input-Manifest.sha256` | `26560DF4DF4C33E3FCB1B9A983F30BF8F1569AB0BC5C9D23EC7F892C17B31EAF` |
| Runner config | `payload/runner-config.json` | `E132A138D1A01530984C2E90603B48E5A37801CD4097808D59E599A60C43A160` |

Also observed: `Static-Staging-Receipt.json` = `0C2019F698C9F4E4778E179917C9F5D0E2D6D27952CC47EFBEC9BBFA27B972DA`; `Launch-Decision.md` = `933BBB6AD5159A1C677E8DEDB996B465AC3451F5F4590BE5E80811FA03B7757D`; Dex packet TIP on-disk = `870596144AAAC3B2DE4894E27639F0D69C581AA621304921AA9E59A6AC3C96CF` (tip_sha256 preimage `07C895D68363CD8EF9D09064B543BAD2B7C0D3230F0A8F4783B7D7A1428B7F77`, CR=0).

## 1. Hash integrity

- Recomputed claimed command / operator / host launch-config / docker-ops / payload manifest / CLI config hashes: **MATCH**.
- `Input-Manifest.sha256`: **265** entries; file SHA256 **MATCH** `26560DF4…`.
- Payload exact-set: **257** manifest pins, all present and hash-ok; on-disk payload files = **258** (257 + `SHA256SUMS.txt` itself). API files = **234** unchanged claim holds.
- `payload/docker-config/config.json`: size 4 (`{}\r\n`), CR=1, SHA256 `E3566B3A…` **MATCH** claimed I01/I02 empty nonsecret config.
- Dex packet TIP tip_sha256 preimage rule verified: claimed `07C895D6…` **MATCH**.

## 2. docker_config directory layout + path wiring honesty

- jim-v2 `host/docker-ops-config.json` lacked `docker_config`. Dex v3 adds exactly one new top-level key:
  - `docker_config` → `...\candidate-dex-v3\payload\docker-config` (**directory**, exists; contains `config.json`).
- Immutable `DockerOps._cmd` forms `docker --config <docker_config> --host <endpoint> …` — directory key is the required shape; pointing at the ops JSON path would be wrong. Correction is correctly typed.
- Operator parameters `-ExpectedDockerConfigSHA256` / `-DockerConfigPath` continue to admit **`host/docker-ops-config.json`** (historical naming; operator comments say "Docker ops config"). CLI directory is admitted indirectly via ops-config bytes + payload exact-set pin of `docker-config/config.json`. No new naming lie introduced by v3; wiring to `_cmd` is honest via the new key.
- Reviewed-Command absolute path pins ops-config SHA `FB13F282…` and absolute ops-config path under dex-v3.

## 3. Delta vs jim-v2 (TIP on-disk `34BBC408…`)

- Payload content: **256 identical** original files; **1 added** (`docker-config/config.json`); **1 changed** (`SHA256SUMS.txt` only, to pin the addition). **0** silent helper/API/fixture/code drift.
- Helper pins checked identical to jim-v2: `np_runner_entry.py`, `np_supervisor.py`, `docker_transport.py`, `np_suite.py`, `np_provider_peer.py`, `np_auth_seed.py`.
- `payload/runner-config.json` byte-identical to jim-v2 (`E132A138…`); `launch_ready=true` retained.
- `Invoke-Native-Provider.ps1`: equal to jim-v2 after packet-path rename only (no logic drift).
- `host/docker-ops-config.json`: after packet-path normalization, shared keys equal; sole structural add = `docker_config`.
- `host/launch-config.json`: path/label rebinds + `manifest_sha256` update + `fake_v1_pass_prerequisite` now `VERIFIED_PASS_16_OF_16_RESULT_88805F6E_RECON_8D489C62` + `source_candidate_v2_tip_on_disk=34BBC408…`. No T05 fold-in.
- Unused fake prep docs/checkers outside payload correctly omitted from this native-only packet (predecessors preserved elsewhere).

## 4. launch_ready / authority alignment

- Host `launch_ready=true`; runner `launch_ready=true` — aligned.
- Host `human_launch_authorized=false`; `launch_authorized=false`; `executed=false`; receipt `human_launch_authorized=false`; `native_execution_authorized=false`.
- Staged `launch_ready` is **not** Trish permission. Native remains held.

## 5. Absolute command / evidence / scope / retirement

Exact `Reviewed-Command.ps1.txt` (CR=0):

```text
& 'C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-native-provider-first-native-launch-candidate-dex-v3\Invoke-Native-Provider.ps1' -ExpectedConfigSHA256 '0F3B0DAD9BA91FC97A61E0633E3295F03201CD2C3DDE3E4B22777E639C369F20' -ExpectedDockerConfigSHA256 'FB13F282F32905E98515D771BB4C66356E529DF48F7BB0145586A44B08D74B64' -DockerConfigPath 'C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-native-provider-first-native-launch-candidate-dex-v3\host\docker-ops-config.json'
```

- Absolute operator + absolute ops-config path; pins match observed hashes.
- Fresh evidence path (authoritative): `...\candidate-dex-v3.evidence` — **does not exist** (operator/config require absence before run; Launch-Decision brief wraps before `.evidence` suffix).
- Scope: exactly `NP-V-MS-NONEXPIRED`; `expected_unknown_cases=[]`; other 26 native + 4 CF held; 76 planning IDs retained; T05 not folded.
- Caps: suite 900 / runner attach 600 / peer 120+5 / provider PKI retirement 45; hard Docker command admission **32**; static success path **22** (matches supplemental V3-Execution-Path-Audit recount). Exact-ID success cleanup only; failure cleanup separately gated; no retries/force/install.
- Fake prerequisite fulfilled (RESULT `88805F6E…` / receipt `8AA3F9E9…`, authority consumed) — cited correctly as prep/fake scope only; **does not prove** native entry/operator/transport/DB/PKI.

## Qualifications (non-blocking)

1. Jim QUALIFIED ACCEPT clears independent static review of the v3 correction; it is **not** the Trish execution card and does not flip `human_launch_authorized`.
2. Image presence and port-443 bind remain `*_verified_this_prep=false` until an authorized run.
3. Operator parameter names `ExpectedDockerConfig*` still mean docker-**ops** JSON; CLI directory is the inner `docker_config` key — historical naming, correct wiring.
4. Empty CLI `config.json` retains CR=1 matching the I01/I02 pin; packet TIP/command remain LF (CR=0).
5. Postrun independent reconciliation of result / input preservation / exact-ID cleanup remains required after any future authorized invoke (per Launch-Decision + V3 audit).

## REVISE blockers

None.

## Confirmations

- No invoke / no Docker / no PKI / no sockets / no imports-to-run during this review.
- Dex v3 packet untouched; jim-v2 / tipped predecessors untouched.
- Human launch authority HELD; native held.
- Not waiting on Trish.
- Slack tip not sent from this seat.
