# Matt → Dex: independent review of worker-observer native staging: ACCEPT (qualified)

November 12, 2026. This responds to `Matt-thePlan-Scheduler-Worker-Native-Admission-Review-2026-11-12.md` (`63FF14C6D9AD1394C95FAAF75981C2D2E9581EAF3D3049DA9839E70583843723`).

**Read-only:** hashing, `cmp`/`diff`/`grep`, and reading source, config and evidence. Nothing was rerun, imported, parsed, compiled, probed or edited. **This review grants no execution authority**; machine flags are not human permission.

Labels used below:
- **[O]** observed (bytes I hashed or read);
- **[S]** a source-derived conclusion;
- **[A]** an untested runtime assumption.

## Verdict
**ACCEPT, qualified.** I found no concrete blocker. There are two non-blocking notes (section 7).

## 1. Fake prerequisite reconciled (no rerun)
- **[O]** The result `packet/verify/FAKE-NATIVE-PROVIDER-RESULT.json` = `36C329DE…172C` and the launcher receipt = `D7B96DBD…F3FD`, as stated.
- **[O]** The result is `kind fake-native-provider-structural-result`, with passed 10 and failed 0.
  - `control_ids_in_order` matches the 10 control IDs exactly (`SUBJECT-PINS` … `ACTUAL-SOURCE-MUTANTS`).
  - `nested_predicates` is 47. Per control: 1+1+4+5+7+8+6+5+5+5 = 47, and every case reads PASS.
  - All 5 mutants are `DETECTED`.
  - DIFF reports 5 hunks, +41/−0.
  - SUBJECT-PINS lists the six expected subject hashes.
  - `native_proof` is false. `packet` reads `…matt-v1`, the intended lineage label.
  - The checker enforces the order of the nested cases against EXPECTED before writing. The result is written with `sort_keys`, so the key order on disk is alphabetical.
- **[O]** The receipt shows:
  - status PASS, check exit 0, elapsed 0.516 s, killed false, `timed_out` false;
  - 2 readers constructed, started and joined, with clean EOF;
  - `retirement_unknown` false;
  - 0 bytes observed and retained on stdout and stderr (both hashes are the empty-string SHA-256 `E3B0C442…B855`);
  - the result is 4714 bytes with a hash matching `36C329DE`.
- **[O]** In `….evidence/`: the authorization covers one invocation of command `433BD07C` with admission `40686768` and native execution false. The outer receipt shows exit 0 and 0 output items.
  - `Dex-Run-Reconciliation.json` says PASS 10/10 with exactly 47, and lists postpins of 20/15/15/278/283/274.
  - I re-verified the v3 staging manifest at 0 mismatches. It now holds 23 files (20 plus the 2 exclusive evidence files plus the manifest), as reconciled.
- **Proof scope:** finite extracted observer, producer and host fake composition only.

## 2. Native staging pins, tree and lineage
- **[O]** The parent `Input-Manifest.sha256` = `BCF86CA7E187A4D84CE6713F315A3E0103B94967B472762B2CC6B28F614E205F`. It has 283 entries, 0 mismatches, and exactly 283 files on disk excluding the manifest.
- **[O]** The nested manifest = `8C4CAACB…E478` (269 entries, 0 mismatches). The payload `SHA256SUMS.txt` = `D6371471…5708` (257 entries, 0 mismatches).
- **[O]** `Source-Worker-Prep-Input-Manifest.sha256` is byte-identical to my prep's `Input-Manifest.sha256` (`9DCAA6FF…0A68`).
- **[O]** Compared with my prep tree:
  - **Payload:** only `runner-config.json` and `SHA256SUMS.txt` differ. All 234 `api/` files and every fixture executable are byte-identical.
  - **Nested non-payload:** only the two host configs and the nested manifest differ.
  - **Parent:** only `Input-Manifest` differs, plus 5 new Dex documents.
  - **Identities:**
    - runner `341074AEF88A9E438C0F488E6231572103E694FB5EB81D6F3AC6BD30517CD645`;
    - operator `5A8A04B6FC497BEA634C095686B3E7C2B76CE8E64BC526053687C399E66DA7D6`;
    - Docker helper `7F7EA8204879D312624DAEB7941504FEA1402F45C48BDA79DDAD94A23711AC53`;
    - supervisor `A1ADA231…03BC`, unchanged from the prep.
- **[O] Whitespace-normalized config deltas:**
  - **`runner-config.json`:** only `launch_ready` false → true. The result `E132A138…A160` equals the original pre-observer runner-config, and the `SHA256SUMS` row changes accordingly.
  - **`host/launch-config.json`** (`A5D59CE4…36BA`):
    - `launch_ready` → true and `candidate_launch_ready_staged` → true (with runner-config, those are the **3 machine flags**);
    - the **2 host-root paths** (`docker_ops_config_path`, `receipt_directory`);
    - the dependent `manifest_sha256` → `D6371471`;
    - `candidate_note`;
    - one **added** key, `worker_observer_runner_sha256` = `341074AE`;
    - `human_launch_authorized` stays false.
  - **`host/docker-ops-config.json`** (`8F93471E…2C56`): exactly **7 Docker-root paths**: `source_directory`, `manifest`, `public_ca_directory`, the DB payload bind, the runner payload bind, the runner public-ca bind and `docker_config`. Nothing else changed.

## 3. Command, config and path agreement (static)
- **[O]** The command file `8C8D43F8…68FB` is the absolute operator in this parent, with `-ExpectedConfigSHA256 A5D59CE4…`, `-ExpectedDockerConfigSHA256 8F93471E…` and `-DockerConfigPath` set to this parent's `host\docker-ops-config.json`. There's **no `-ReceiptPath`**. Both pins match disk.
- **[S] Operator** (`Invoke-Native-Provider.ps1`):
  - `:42`: the evidence root is `Split-Path $PSScriptRoot -Parent` + `scheduler-native-provider-diagnostic-launch-v1.evidence`, which resolves to `…\scheduler-native-provider-worker-diagnostic-launch-dex-v1\scheduler-native-provider-diagnostic-launch-v1.evidence`;
  - `:136`: the default receipt is `<evidence>\native-provider-host-receipt.jsonl`;
  - `:138`: public-ca is `<evidence>\public-ca`;
  - all of these equal `Worker-Native-Path-Agreement.json`, the host `receipt_directory`, the Docker `public_ca_directory` and the runner read-only bind `[<evidence>\public-ca, /public-ca]`;
  - `docker_transport.py:51` requires that bind to equal `ca_path.parent`, and it does.
- **[O]** That evidence root is **absent**.
- **[O]** A grep of the host configs, the runner-config, the operator and the whole payload finds **no** reference to `worker-diagnostic-prep-matt-v1` or the old executed `scheduler-native-provider-diagnostic-launch-dex-v1` root.
- **[S] Admission chain:**
  - `:52`: launch_ready gate;
  - `:59-69`: pin syntax;
  - `:70-78`: interpreter, Docker and raw config hash;
  - `:87-89`: manifest hash;
  - `:90-92`: evidence directory must be absent;
  - `:94-108`: every payload row re-hashed;
  - `:120`: Docker config hash;
  - `:124-134`: both configs physically outside the payload;
  - `:141`: no existing receipt;
  - then the supervisor runs with `-I -S -B`.
  - The supervisor (`np_supervisor.py:332-345`) re-checks `launch_ready` and `endpoint` and builds the Plan from `case_ids` and `expected_unknown_cases` (`:297-309`).
  - The runner (`np_runner_entry.py:103-105`) requires runner-config `launch_ready` to be true.
- **[S]** `receipt_directory` and `docker_ops_config_path` in the launch config are declarative. Neither the operator nor the supervisor reads them; the actual paths come from `$PSScriptRoot` and the command. They still agree, and no new guard is claimed.

## 4. Batch and identities
- **[O]** The launch-config and runner-config `case_ids` are both exactly `["NP-V-MS-NONEXPIRED"]`; `expected_unknown_cases` is `[]` in both; `batch_id` is `np-v-ms-nonexpired-first-vertical`; `endpoint` is `unbound`.
- **[S]** The supervisor requires the report's `case_ids`, `passed`, `unexpected_unknown` = 0 and `expected_unknown_cases` to match the Plan exactly (`np_supervisor.py:228-234`).
- **[O]** There's no refresh or T05 content: the runner is unchanged at `341074AE`, and the payload differs from my prep only in runner-config and its manifest.

## 5. Bounds, isolation and disclosure
- **[O] Config values:**
  - `suite_seconds` 900, `runner_seconds` 600, `peer_seconds` 120, `peer_retire_join_seconds` 5;
  - provider PKI: gen 30 + reap 5 + reader join 5 (×2 per the brief) = 45 total, matching `provider_pki_retirement_total_seconds` 45;
  - `command_count_cap` 32; `static_success_docker_command_count` 22; `output_byte_cap` 1048576 in both configs.
- **[O] Both roles (DB and runner):**
  - pinned images `53758bea…` and `c2201104…`;
  - Memory and MemorySwap 1073741824; NanoCpus 1e9; PidsLimit 64;
  - CapDrop ALL; no-new-privileges; ReadonlyRootfs; RestartPolicy no; no published ports;
  - **DB:** NetworkMode `none`, user `postgres`;
  - **runner:** `container:<exact-created-database-ID>`, user `65534:65534`, run as `python3 -I -S -B /packet/fixture/np_runner_entry.py`, with no Docker socket.
- **[S] Helper** (`docker_transport.py`):
  - `:134`: the call count is capped by `command_count_cap`;
  - `:176-177`: combined stdout and stderr per command is capped at `output_byte_cap`;
  - `:188-191`: on exit it calls `proc.kill()` on a live CLI with **no wait** and records `cli_stopped_container_state_unknown`. That matches the brief: CLI termination does not prove the daemon cancelled.
- **[S] The 22-command success path** (2 + 7 + 4 + 9) is Dex's derivation, which I didn't fully re-derive. It's partially corroborated **[O]**: the executed dex-v1 receipt `27341732` showed 12 `docker_command` events through runner start/attach (2 + 7 + 3).
- **[S] STOP disclosure:**
  - `stop_payload` is byte-identical to the approved producer (proved in fake control 3);
  - its bounds are 3 exceptions, 8 frames, 128 traversal, 4096 bytes and class names only;
  - the host validator `7F7EA820` is unchanged.
  - **[A]** Natively, the observer misses faults before `run_bounded_domain`, and deeper chains may truncate.
- **[A] Not established:**
  - image presence and port/state compatibility (no live probe);
  - the native observer, TLS and DB behavior;
  - the actual non-200 cause;
  - the `anyio` thread hand-off;
  - wall-clock exclusions (startup, outer, file, hash, receipt, OS) and the absence of a separate outer timeout, as the brief states.

## 6. Cleanup posture
- **[O]** The brief limits a future bundled cleanup to **success-only**, exact-ID: remove the exited runner and verify; SIGINT the exact DB, require exit 0, remove and verify; retain receipts. Failure cleanup stays separately gated.
- **[S]** The operator's non-zero path throws "preserve evidence; no retry, repair or failure cleanup" (`:149-151`). That's consistent.

## 7. Non-blocking notes
1. **The added launch-config key** `worker_observer_runner_sha256` is outside the "flags, paths, note" list in your assignment text, though your staging receipt mentions an "explicit current runner label". **[S]** It's inert: the operator reads fixed keys via `ConvertFrom-Json`, the supervisor uses `config.get`/`[]` on fixed keys, and neither enforces a key set.
2. **Lineage labels** (`packet`, the historical docs) intentionally predate this staging. The `Worker-Native-*` documents and this command are the only current authority, and I agree with that framing.

## Hash inventory (verified)
| item | SHA256 |
|---|---|
| review drop | `63FF14C6D9AD1394C95FAAF75981C2D2E9581EAF3D3049DA9839E70583843723` |
| parent Input-Manifest (283) | `BCF86CA7E187A4D84CE6713F315A3E0103B94967B472762B2CC6B28F614E205F` |
| nested Input-Manifest (269) | `8C4CAACB9252C85C2238CB73F147B1B2E18F783D531AAE22BD77B7B7C09CE478` |
| payload SHA256SUMS (257) | `D6371471DFF17B8D7A30A54EA420B931443B19023DA1EC182E73E8C6C7B95708` |
| Worker-Native-Review-and-Commands.md | `C047455156D0FA7D046452463759FC5D3E49EA084E93236BAA3DC5C9030D2FEB` |
| Reviewed-Worker-Native-Command.ps1.txt | `8C8D43F8B7B628A2EC78A54C9771CF3D68AC72CAC4BC4447DA5EFF3AF99168FB` |
| host launch-config | `A5D59CE4EB15F8825925BDCA1A3B3762213D868248E4E7AC71D39E86003136BA` |
| docker-ops-config | `8F93471ED6C8487DB15C195DBB0725F4B8E6F81B9246581A75CBCD7E4C812C56` |
| runner-config | `E132A138D1A01530984C2E90603B48E5A37801CD4097808D59E599A60C43A160` |
| runner | `341074AEF88A9E438C0F488E6231572103E694FB5EB81D6F3AC6BD30517CD645` |
| operator | `5A8A04B6FC497BEA634C095686B3E7C2B76CE8E64BC526053687C399E66DA7D6` |
| Docker helper | `7F7EA8204879D312624DAEB7941504FEA1402F45C48BDA79DDAD94A23711AC53` |
| source prep manifest (278) | `9DCAA6FF06FF890E53AB867ECFDFA5617115A0B684762304E49AF6BE07F00A68` |
| fake result / receipt | `36C329DE…172C` / `D7B96DBD…F3FD` |

## Preservation
I modified nothing. The evidence root for this staging is absent. MS REFRESH stays held, and the endpoint is unbound.

Signed: Matt
