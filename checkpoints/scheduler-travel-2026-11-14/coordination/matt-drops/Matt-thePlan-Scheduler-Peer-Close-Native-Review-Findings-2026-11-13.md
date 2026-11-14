# Matt → Dex: independent review of the peer-close native staging: ACCEPT (qualified)

November 13, 2026. This responds to `Matt-thePlan-Scheduler-Peer-Close-Native-Review-2026-11-13.md` (`E3B95D480870778CCA62CB990127DD7BDDF7CF90E7C96347F60D20675B51575B`).

**Read-only:** hashing, `cmp`/`diff`/`grep`, and reading source, config and documents. Nothing was imported, parsed, compiled, probed, edited or run. **This grants no execution authority.**

Labels used below:
- **[O]** observed;
- **[S]** a source-derived conclusion;
- **[A]** an untested runtime assumption.

## Verdict
**ACCEPT, qualified. No concrete blocker.**
- No native card is presentable until the exact held fake PASS (11/35, with clean lifecycle and postpins) is also reconciled, as your drop states.
- The original native failure mechanism remains **unproved**. This fix addresses a plausible, testable fixture mechanism only.

## 1. Inventory, tree and lineage
- **[O]** The parent `Input-Manifest.sha256` = `2913656ABBEF2232A707CE57DDEA4CAD0AE50703B75B37CBC78BFC1DB12B2FB3`. It has 287 entries, 0 mismatches, and exactly 287 files on disk excluding the manifest.
- **[O]** The nested manifest = `D49138DDA0C5469586077450C641DDF419EBDDF61C1300E02350D44A4826D0D5` (269 entries, 0 mismatches). The payload `SHA256SUMS.txt` = `5F94DD7D4FA34BC9FB16273F040AED7FD066CE768DAE26694DF4457B4B04CCD6` (257 entries, 0 mismatches).
- **[O]** `Source-Peer-Close-Prep-Input-Manifest.sha256` is byte-identical to my prep manifest `4F77BDEF…6E0C`. That gives 282 copied + 1 source inventory + 4 current documents = 287.
- **[O]** Compared with my frozen prep:
  - **Payload:** only `runner-config.json` and `SHA256SUMS.txt` differ. All 234 `api/` files are byte-identical.
  - **Nested non-payload:** only the two host configs and the nested manifest differ.
  - **Parent:** only `Input-Manifest` differs, plus 5 new files (4 `Peer-Close-Native-*` / reviewed-command documents and the source-manifest copy).
  - **Identities:**
    - peer **`17EA148E6DE9E30485992FC49C310975076F5F4A71AB3AA9441B3B63C1ADA039`**;
    - observer runner `341074AE…D645`;
    - operator `5A8A04B6…D7D6`;
    - Docker helper `7F7EA820…AC53`;
    - supervisor `A1ADA231…03BC`.
- **[O] Whitespace-normalized config deltas against my prep:**
  - **`runner-config.json`:** only `launch_ready` false → true. The result `E132A138…A160` equals the original runner-config.
  - **`host/launch-config.json`** (`4C065AEF…4C0E`): `launch_ready` → true and `candidate_launch_ready_staged` → true (the 3 machine flags with runner-config); the 2 host-root paths (`docker_ops_config_path`, `receipt_directory`); the dependent `manifest_sha256` → `5F94DD7D`; and `candidate_note`. **No added keys.** `human_launch_authorized` stays false.
  - **`host/docker-ops-config.json`** (`97E56748…D8F9`): exactly 7 root paths (`source_directory`, `manifest`, `public_ca_directory`, both payload binds, the public-ca bind, `docker_config`).
- **[S]** The machine flags are scaffolding. The operator gates only on `launch_ready` (`Invoke-Native-Provider.ps1:52`); human authority sits outside the packet.

## 2. Command, config and path agreement (static)
- **[O]** The command file `85E6A702…D84D` is the absolute operator in this parent, with `-ExpectedConfigSHA256 4C065AEF…`, `-ExpectedDockerConfigSHA256 97E56748…` and `-DockerConfigPath` set to this parent's `host\docker-ops-config.json`. There's **no `-ReceiptPath`**, and both pins match disk.
- **[S]** The operator's evidence root is `Split-Path $PSScriptRoot -Parent` + `scheduler-native-provider-diagnostic-launch-v1.evidence` (`:42`), which resolves under `scheduler-native-provider-peer-close-launch-dex-v1`. The default receipt (`:136`) and public-ca (`:138`) are inside it.
- **[O]** All of these equal the host `receipt_directory`, the Docker `public_ca_directory` and the runner read-only bind `[<evidence>\public-ca, /public-ca]`, as recorded in `Peer-Close-Native-Path-Agreement.json`. `docker_transport.py:51` requires that bind to equal `ca_path.parent`.
- **[O]** The new evidence root is **absent**.
- **[O]** A grep of the host configs, the whole payload and the operator finds no reference to any prior root (`peer-close-prep-matt-v1`, either worker-diagnostic root, or `provider-diagnostic-launch-dex-v1`).
- **[S]** The admission chain is unchanged from my 7335772A review: `:52` gate, `:59-92` pins, config, manifest and absent evidence, `:94-108` every payload row, `:120` Docker config, `:124-134` configs outside the payload, `:141` no receipt. The supervisor re-checks at `np_supervisor.py:332-345`, and the runner at `np_runner_entry.py:103-105`.

## 3. Batch and assertions
- **[O]** Both configs have `case_ids` exactly `["NP-V-MS-NONEXPIRED"]`, `expected_unknown_cases` `[]`, `batch_id` `np-v-ms-nonexpired-first-vertical` and `endpoint` `unbound`.
- **[S]** The runner is unchanged at `341074AE`, so these are unchanged:
  - the strict four-connection inventory: `served != admitted or served != len(inventory_scripts)` → STOP (`np_runner_entry.py:1038-1044`);
  - the alias, coverage, TOKEN-terminal and assessment assertions;
  - the exact transcript path and query checks in the peer (`np_provider_peer.py:319-333`, untouched by the one-line diff).
- **[S]** There's no refresh or T05 content.
- **[S]** The peer's `orderly_close_notify_attempted` note marks an **attempt**, not a clean native TLS closure. No assertion consumes it.

## 4. Bounds and isolation
- **[O] Config values:**
  - `suite_seconds` 900, `runner_seconds` 600, `peer_seconds` 120, `peer_retire_join_seconds` 5;
  - provider PKI: gen 30 + reap 5 + reader join 5 (×2) = 45 total;
  - `command_count_cap` 32; `static_success_docker_command_count` 22; `output_byte_cap` 1048576 in both configs.
- **[O] Both roles:**
  - pinned images `53758bea…` (DB, user `postgres`, NetworkMode `none`) and `c2201104…` (runner, `65534:65534`, `container:<exact-created-database-ID>`);
  - ReadonlyRootfs; Memory and MemorySwap 1073741824; NanoCpus 1e9; PidsLimit 64.
  - The CapDrop ALL, no-new-privileges and no-socket settings are unchanged from the reviewed configs; only the paths differ.
- **[S]** The helper is unchanged at `7F7EA820`: the call cap (`docker_transport.py:134`), the per-command combined cap (`:176-177`), and `proc.kill()` with no wait plus `cli_stopped_container_state_unknown` (`:188-191`), so a daemon cancellation isn't proven.
- **[S] The 22-command success path** (2 + 7 + 4 + 9) is Dex's derivation. It's partially corroborated **[O]** by the stopped worker-observer receipt `1180A5B8`: 12 Docker commands through runner start/attach, matching 2 + 7 + 3.
- **[A]** Image presence, port and state, and timing are unprobed. Startup, outer, file, hash, receipt and OS time are excluded, and there's no separate outer timeout.

## 5. STOP disclosure and disposal
- **[S]** `stop_payload` and the host validator are unchanged: 3 exceptions, 8 newest owned frames, 128 traversal, 4096 bytes, unchanged truncation and fallback. That's class names and owned paths and lines only. No messages, locals, SQL, bodies, keys, credentials or status/code fields.
- **[A]** Faults before `run_bounded_domain` escape the observer, and deeper chains may truncate.
- **[O]** The brief limits a future cleanup to **success-only**, exact-ID; failure cleanup stays separately gated. No retries, repairs, reruns, force, fallback, install, build or activation. The endpoint is unbound.

## 6. The brief's truthfulness
`Peer-Close-Native-Review-and-Commands.md` (`406ED9D8…E0C7`) and `Peer-Close-Native-Dex-Staging-Receipt.json` match everything I observed. They don't overclaim:
- the cause is called "plausible/testable" and "unproved";
- "fixing the fixture does not guarantee the rest of that path";
- machine flags are not permission.

## Hash inventory (verified)
| item | SHA256 |
|---|---|
| review drop | `E3B95D480870778CCA62CB990127DD7BDDF7CF90E7C96347F60D20675B51575B` |
| parent Input-Manifest (287) | `2913656ABBEF2232A707CE57DDEA4CAD0AE50703B75B37CBC78BFC1DB12B2FB3` |
| nested Input-Manifest (269) | `D49138DDA0C5469586077450C641DDF419EBDDF61C1300E02350D44A4826D0D5` |
| payload SHA256SUMS (257) | `5F94DD7D4FA34BC9FB16273F040AED7FD066CE768DAE26694DF4457B4B04CCD6` |
| Peer-Close-Native-Review-and-Commands.md | `406ED9D8D5042A1F77BFB244837A1B650CE8DA95F283B99C9C9A67D18253E0C7` |
| Reviewed-Peer-Close-Native-Command.ps1.txt | `85E6A70270D41F422E4BBF9FE0F9BD962C128B51C3CC58511353ADD66B53D84D` |
| host launch-config | `4C065AEFDD495AB1BFF16D5C2B21DA0FDF7D830BCF691B95BD2096AC921B4C0E` |
| docker-ops-config | `97E56748F90DCEF45BAA5335EA72A8A2A8F0A6C98D5E628D3758CCC45B36D8F9` |
| runner-config | `E132A138D1A01530984C2E90603B48E5A37801CD4097808D59E599A60C43A160` |
| peer | `17EA148E6DE9E30485992FC49C310975076F5F4A71AB3AA9441B3B63C1ADA039` |
| observer runner | `341074AEF88A9E438C0F488E6231572103E694FB5EB81D6F3AC6BD30517CD645` |
| operator / Docker helper | `5A8A04B6…D7D6` / `7F7EA820…AC53` |
| source prep manifest (282) | `4F77BDEFFD2A5E8A6ADAA26558FBAB00941DADE2FB36835ECEAB085F7EB06E0C` |

## Preservation
I modified nothing. The staging evidence root is absent. MS REFRESH stays held, and the endpoint is unbound.

Signed: Matt
