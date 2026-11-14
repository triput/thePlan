# First-native launch proposal — NP-V-MS-NONEXPIRED only

Jim (Justin), 2026-11-12. **DOCS / PLANNING ONLY.** Zero execution.

Folds Dex **Native-Launch-Readiness-Seams.md** SHA256 `57AA3A80E26BC7EA29E47AE279E9FA94270F8DA5C5BD2EC586568BFCF154B3E3` (implementation-review-v9). Seams concern later native launch readiness — not fake-v1.

## Status

| Flag | Value |
| --- | --- |
| executed | false |
| launch_authorized | false |
| launch_ready | false (not flipped) |
| prep_is_not_pass | true |
| endpoint | unbound |
| first_vertical batch | `case_ids=["NP-V-MS-NONEXPIRED"]`, `expected_unknown_cases=[]` |
| fake-v1 PASS | **unfulfilled prerequisite** (card with Trish; no PASS claimed) |
| Slack tip | false |

Authority unchanged: Scope `389A00DD444C610A93877362A574A1C93543F916F119D2D2FF71BA167FBF7E2D` · Approval `5D1EA2F973FE110D35B65E4172821F014E74A8F2A65BCBB4AB8EE22458F80CA4`.

Frozen prep-v9 TIP on-disk: `6585E768FA64E455052368F75E47795ECC99708DC4EDCFBF6D33CD3B5A25F188` (read-only; DropFolder not mutated). Same approved **16-role** preparation lane. All other **26 native + 4 CF** held. All **76** planning requirements retained.

## Dex seams (57AA3A80…) — reconciled here

### Seam 1 — Entry import order precedes isolated bootstrap

**Observed (prep-v9 `np_runner_entry.py` `87D89F76…`):** `main()` does `from np_integrated_runner import run_suite` and `from np_receipts import build_receipt` **before** `admit_isolated_import_bootstrap`. Under reviewed `-I -S -B`, the script directory is not an ordinary import root, so sibling imports can fail before the guarded bootstrap runs. Report-boundary fake injects siblings into `sys.modules` — that is **≠ native proof**.

**Proposed later narrow fix (fresh copy under existing named-runner role; not coded here):** after UID/config/roots admission, call existing `admit_isolated_import_bootstrap`, **then** import the two siblings. Keep reviewed site/fixture/API roots and isolated flags. Do not widen ambient imports, install packages, or claim fake injects prove native startup. Do not change staged fake-v1 packet.

### Seam 2 — Runtime public-CA binding (I01/I02 custody)

**Observed:** `np_integrated_runner.run_suite` hashes `/public-ca/ca.crt` and compares to `config["ca_sha256"]`. Prep `runner-config` still has unfrozen `ca_sha256` sentinel; `load_runner_config` only reads JSON — entry does not currently derive/admit the dynamic CA hash before `run_suite`. `DockerOps.verify_fixture_ready` does **not** generate CA; it transfers fixed public PEM from disposable DB to fresh host public-CA dir and sets `self.ca_hash`. Outer provider attach compares report `ca_sha256` to that transferred hash. A disposable CA cannot be pre-pinned before launch generates/transfers it.

**Plan (reuse passed I01/I02 in-memory pattern; not coded here):**

1. Host transfers public CA only (immutable verify_fixture_ready path); retain transferred public hash in evidence.
2. In-runner: bind ephemeral in-memory `config["ca_sha256"]` from runtime `/public-ca/ca.crt` bytes **after** mount, before `run_suite` compare — never mutate hash-admitted on-disk runner-config.
3. Host compare report `ca_sha256` to transferred public hash (already in ProviderDockerOps / DockerOps attach path).
4. Never: freeze a made-up CA hash; mutate admitted runner-config bytes; pre-generate private material on host; weaken verify-full TLS; conflate DB trust CA with separately generated **provider** PKI under `/tmp/np-provider-tls`.

### Seam 3 — Acyclic host launch-config vs payload manifest; byte-pin Docker ops config

**Observed:** Host `launch-config` embeds `manifest_sha256` and is separately admitted by wrapper `-ExpectedConfigSHA256` (not `self_sha256`). Naively including launch-config inside the payload manifest creates a raw-hash cycle. `Invoke-Native-Provider.ps1` requires `-DockerConfigPath` and checks **existence only** — filename alone is **not** a byte pin.

**Proposed input graph (docs; freeze on later launch card):**

| Root | Admission | Contents / exclusions |
| --- | --- | --- |
| A. Outer reviewed command pin | Operator `-ExpectedConfigSHA256` | Exact host `launch-config.json` bytes (includes `manifest_sha256` pointer) |
| B. Payload manifest | `launch-config.manifest_sha256` → `payload/SHA256SUMS.txt` | Payload fixture/API/runner files **excluding** host launch-config, excluding Docker ops config, excluding evidence/receipts |
| C. Docker ops config | **Separate outer byte pin** (new ExactDockerConfigSHA256 or equivalent on launch card) | `source_directory`, exact `sha256:` images, argv/entrypoints, readonly binds, tmpfs, isolation `host_config_projection`, `docker`/`docker_sha256`, `command_count_cap`, `runner_seconds`, runtime pin maps — full concrete ops document |
| D. Host interpreter / docker.exe | launch-config `python_sha256` / `docker_sha256` | Partial inventory disclosed; do not substitute host Python evidence for in-image native runtime pins |

No mutable discovery or live pin invention in this proposal — document the intended acyclic graph only.

## 1. Dependency footprint (NP-V-MS-NONEXPIRED only)

Exact pins/paths/hashes: `Dependency-Footprint.json`.

### Host runtime (partial inventory — interpreter only verified)

| Item | Path / value | SHA256 / state |
| --- | --- | --- |
| Host Python 3.11 | `C:\Users\trish\AppData\Local\Programs\Python\Python311\python.exe` | `5F7B89A612C9B8AF1D6456CDFCD1DBE5CA630849E79AEBCED9BEE9A6694952EC` |
| Docker CLI | `C:\Program Files\Docker\Docker\resources\bin\docker.exe` | **UNFROZEN** sentinel in prep-v9 launch-config |
| Docker endpoint | `npipe:////./pipe/dockerDesktopLinuxEngine` | authored; binding unauthorized |
| Isolated flags | `-I -S -B` | Invoke-Native-Provider.ps1 → np_supervisor / runner |
| Docker ops config | launch-card path | **byte pin REQUIRED** (Seam 3); currently existence-only |

### Config / admission (prep-v9 cited; launch card must freeze)

| Artifact | Prep-v9 SHA256 | Launch-card obligation |
| --- | --- | --- |
| `payload/launch-config.json` | `9D85F69DEF83686A4077A2048BAC3DF87081E92DD2A39037E950DEA7FA937722` | Outer Root A; `case_ids=["NP-V-MS-NONEXPIRED"]`; `expected_unknown_cases=[]`; freeze suite/command/image/runtime hashes; **do not** flip `launch_ready` here |
| `payload/runner-config.json` | `E1355147AE4F72F3B51DA61F2C9921360F94A45A35985AE0923B3B267081BE9E` | Same case filter; freeze `runner_seconds` + in-image `runtime_pins`; `ca_sha256` remains dynamic via Seam 2 in-memory bind (do not fake-freeze disposable CA) |
| Payload manifest | UNFROZEN sentinel | Root B; exclude host launch-config + docker-config |
| Docker ops config | **unauthored byte pin** | Root C; exact images/argv/binds/isolation |

### Key mutable roles (16-lane)

| Role | SHA256 |
| --- | --- |
| Invoke-Native-Provider.ps1 | `D6E14CC07AF1B3F35B32DBE1C0FB4F9E7C70B476957314B6D29299CD04B6AE8D` |
| np_supervisor.py | `A1ADA2311B10631209DBA0588B8C9C6B947B3206F0EFBC51F4CF66B1F45303BC` |
| np_runner_entry.py | `87D89F760BB7CD47764BA1C6574A9AFF9E6266E682F0CE752AE4B06B484B2E25` |
| np_integrated_runner.py | `2C8B5BE78B5F042210D042DF1FB7FDBB07C486ED5A57CA36C00006F61E6040DF` |
| np_suite.py | `AEC59FCDA058124FDF7265D41B8A660C4AD139CE13417F88FA637542CF9C1673` |
| np_provider_peer.py | `5568AF73DD42FEB5B8E2FE4D723AD4FB0339CBF4B889F5472995ABC628F72A55` |
| docker_transport.py (immutable helper) | `7F7EA8204879D312624DAEB7941504FEA1402F45C48BDA79DDAD94A23711AC53` |
| prepare-np-provider-tls.sh | `591855FFCA5543ED15F0DA7F5EE1CC725E868FB278EBD112398A91BC3DC5E205` |
| launch_check.py | `D22C37E36E5D333C087C8EE80B6936756C69F7D369369C66F8E0FFE6906EBD07` |

### Images

Database + runner images must be exact `sha256:` digests in byte-pinned docker-config (`verify_runtime_pins`). Prep-v9 has **no** frozen digests — **not invented here**. `--pull=never`. Do not substitute host Python hash for native in-image runtime pins.

## 2. Proposed numeric suite / runner / peer / PKI limits

One-case vertical only. Proposed freezes for a later launch card — **not** applied here.

| Limit | Proposed | Ownership / source |
| --- | --- | --- |
| `case_ids` | `["NP-V-MS-NONEXPIRED"]` | Commands-Held; first_vertical; IMPLEMENTED_CASE_IDS; seams §Existing preparation boundaries |
| `expected_unknown_cases` | `[]` | Expected-Outcomes PASS; empty UNKNOWN set |
| `work_deadline_seconds` | **210** | np_suite / launch-config clocks |
| `request_deadline_seconds` | **240** | same |
| `cleanup_allowance_seconds` | **30** | same |
| `attempt_validity_seconds` | **600** | same |
| `runner_seconds` | **600** | attempt_validity; ProviderDockerOps attach cap |
| `suite_seconds` | **900** | host outer: bootstrap + attach≤600 + success cleanup; DB wall-clock unverified |
| `command_count_cap` | **32** | docker_transport; static success-path ≈21 + headroom |
| `output_byte_cap` | **1048576** | launch-config + np_runner_entry |
| Peer seconds / join | **120** / **5.0** | PEER_SECONDS_DEFAULT / retire_owned |
| PKI gen/reap/join×2 / capture | **30** / **5** / **5** / **65536** | np_runner_entry PKI caller |
| PKI retirement total | **45** | 30+5+5+5; separate_outer_timeout=false (parallel launcher 135 pattern) |

### Retained evidence (success)

Host receipt JSONL (`attempt`→`created`→`suite_pass`→`removed`→`complete`); exact 64-hex IDs; runner report (`passed==1`, joins, zero unexpected UNKNOWN); case observations; **transferred public CA hash** + report equality (Seam 2); PKI observed byte counts ≤65536; post-run verify_inputs.

## 3. Success-only exact-ID cleanup sequence

Owner: `np_supervisor.run_once` success path only (no cleanup in except/finally).

1. identity runner exited 0 → `remove_exact(runner)` → `verify_absent(runner)` → record removed
2. identity database running → `sigint_exact(db)` → `wait_exact(db)==0` → identity exited 0 → `remove_exact(db)` → `verify_absent(db)` → record removed → `complete{success:true}`

In-runner: peer `retire_owned(join_seconds=5.0)` once; unjoined → UNKNOWN STOP.

## 4. Fail / mismatch / timeout / unexpected → UNKNOWN STOP

Pin/config/identity/evidence mismatch, suite/command deadline, unjoined peer/reader, duplicate retirement, CA mismatch, import bootstrap failure → STOP/UNKNOWN. Receipt `stopped` with `automatic_cleanup=false`, `retry=false`, `failed_container_shutdown_gated=true`. Invoke-Native-Provider: preserve evidence; **no retry, repair, or failure cleanup**.

## 5. Limit explanations (source ownership)

- Clocks 210/240/30/600 — product CoveringRequestBudget / np_suite; supervisor kill ≠ app-deadline proof.
- runner_seconds=600 — attempt-validity ceiling for one vertical attach.
- suite_seconds=900 — planning composition; DB ready duration unmeasured.
- command_count_cap=32 — docker_transport hard refuse; ProviderDockerOps path (no N06/N07 gate_pair).
- output 1MiB / PKI 64KiB — BoundedOutput + PKI capture sinks.
- peer 120 / join 5 — runner entry + peer retire_owned.
- PKI 30+5+5+5 — invoke_bounded_provider_pki_recipe; invocation still held.
- Images / docker.exe / docker-config bytes / in-image runtime pins — launch-card Roots A–C; currently UNFROZEN/partial.

## 6. HOLDs / unverified

1. **fake-v1 PASS** — unfulfilled; do not wait; do not touch staged packet.
2. Other **26 native + 4 CF** — HOLD_EXPLICIT_NOT_PASS.
3. **Seam 1 code correction** — proposed only; uncoded; fake inject ≠ native proof.
4. **Seam 2 in-memory CA bind** — planned; not implemented in this packet.
5. **Seam 3 DockerConfigPath byte pin + acyclic roots** — documented; wrapper still existence-only until launch card.
6. Provider PKI generation/invocation held.
7. Database/runner **image digests**, docker.exe SHA256, manifest_sha256, in-image runtime pins — UNFROZEN / not invented.
8. Sanitizer/host failure-path unverified; live command-count + DB bootstrap wall-clock unverified.
9. Endpoint binding / native dial+TLS / T01 full closure — unbound/false.
10. `launch_ready` / `launch_authorized` remain false; all **76** requirements retained.

## Explicit non-actions

No helpers invoked. No PKI generated. No Docker/providers/DB. No app imports to run. No production-guard edits. No `launch_ready` flip. Fake-v1 untouched. Prep-v9 tipped DropFolder not mutated. No Slack tip. No coding of Seam 1–3 fixes in this packet.
