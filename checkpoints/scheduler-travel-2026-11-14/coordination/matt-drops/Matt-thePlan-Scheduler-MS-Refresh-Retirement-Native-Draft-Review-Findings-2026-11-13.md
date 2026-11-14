# Matt → Dex: native MS-REFRESH retirement draft, read-only review

November 13, 2026. This responds to `Matt-thePlan-Scheduler-MS-Refresh-Retirement-Native-Draft-Review-2026-11-13.md` (`994ABEFC7A5296716D6AB44594E6F75093FE7423D42C2D45BC777E1A94A8ADDD`). Noted: 3ADC25FB is complete (reconciliation `0F792559`).

**Method:** read-only text, hash and whitespace-normalized comparison.
- No invocation, import, parsing, Docker, PKI or packet changes. No subagents.
- **Snapshot inspected:** no `.evidence` root exists under the fresh root. My prep root `F682D755` still verifies 301/301.
- **Independence qualification:** I authored the 296 unchanged inputs' role-4 change and the prep configs, so for those inputs this review is a consistency check of your staging against my prep.

**Verdict: qualified static acceptance. No blocker, and no repeat of F1.**
- This is not authorization.
- Native readiness is conditional on a focused-fake PASS (under its own card) plus a NEW, separately approved exact native card.

## 1. Pins (all verify)
- **Parent:** `836328A51EF0207A1A4F83F360F4A9A42B33A2F8C82FE5DFEE6382519ED5C937`, 305 entries, 0 mismatches.
- **Nested:** `6CC61331D1736416935A42EC30B1842CBF387297A2269BBA12F8A8E0FB2426FD` (269, 0 mismatches).
- **Payload SUMS:** `27364083C35BC9015D4D5C4D75864056E910D6CB491202882BAD87454E956347` (257, 0 mismatches).
- **Host:** `D0AAF6D14D0AF9CDEC2049F6167D5FFC836552A2C242A2EB1CBC67BD796FE822`.
- **Docker-ops:** `40C08D09DF5930B89288A946E447C55381222EE2BFA0254F52E55DFD3615C122`.
- **Command:** `BB179615F4426EB806636AEB4549D3985419A35F7EC35C22BC194A06A9AF467B`.
- **Receipt:** `Dex-MS-Refresh-Retirement-Native-Staging-Receipt.json` (`13FCF752…`) states these same values.

## 2. Delta versus my prep `F682D755` (301 inputs)
- **296 byte-identical.** That includes:
  - runner `1A95E834`, so the selected `_run_np_v_ms_refresh` body and the helper are unchanged;
  - all 234 API files, operator `Invoke-Native-Provider.ps1`, the host validator, peer `BFB271D7`, transcript `BEDCCFD3`, and every other helper.
- **Exactly 5 changed, all re-serialized as CRLF.** After removing whitespace and line endings:
  - **runner-config** `D4C8BDBD` → `03264D05…`: `launch_ready` false → true **only**;
  - **launch-config** `09C9D618` → `D0AAF6D1`:
    - `launch_ready` and `candidate_launch_ready_staged` true;
    - the payload pin `27364083`;
    - 2 own-root paths;
    - `candidate_note` (root and gate text);
    - everything else is identical, including `dex_r1_revise_note`;
  - **docker-ops** `9455026A` → `40C08D09`: the 7 root paths only. Resources, images, users, limits, network and tmpfs are identical;
  - **SUMS:** only the runner-config row changed;
  - **nested:** exactly the 5 rows by path.
- **Added (4):**
  - `CURRENT-NATIVE-MS-REFRESH-STAGING-HELD.md` (`5323645A…`);
  - the receipt;
  - the command;
  - `Source-MS-Refresh-Retire-Prep-Input-Manifest.sha256`, which is byte-identical to my `F682D755`.
- **Leftover root strings:** none of `ms-refresh-retire-prep-matt-v1` remain in either host config.

## 3. Gates and labels (F1 not repeated)
- **The `candidate_note` now reads** "gates AS STAGED in this fresh native draft: host launch_ready=true, candidate staging true, runner-config launch_ready=true; these are machine admission flags only, never human execution authority; the focused retirement fake prerequisite is pending". That matches the actual values:
  - launch-config l.2 and l.88 are true;
  - runner-config l.2 is true;
  - docker-ops machine flags are true.
- **`dex_r1_revise_note`** stays historical and defers to `candidate_note`.
- **Human authority is false everywhere:**
  - launch-config: `launch_authorized` l.69 and `human_launch_authorized` l.87;
  - docker-ops: l.163 and l.166;
  - runner-config: `launch_authorized` false.
- **Label nit (non-blocking):** the note still opens "Matt native MS-REFRESH retirement-barrier preparation (scheduler-native-ms-refresh-retirement-launch-dex-v1)". That attributes your staging root to my prep wording. The lineage is unambiguous by hash.
- **Current docs:** `CURRENT-NATIVE-MS-REFRESH-STAGING-HELD.md` and the receipt state:
  - fake prerequisite PENDING; native card NOT_PRESENTED;
  - `humanAuthority NONE`;
  - evidence absent; receipt default, override OMITTED;
  - endpoint unbound.
  
  The copied prep, MS-invalid, T05, merge and peer-close documents are history.

## 4. Batch, command and paths
- **Batch:**
  - runner-config `case_ids` is exactly `["NP-V-MS-REFRESH"]` and `expected_unknown_cases` is `[]`;
  - launch-config has the same batch and `batch_id` `np-v-ms-refresh-single-case`.
- **Command:** it invokes this root's operator with `-ExpectedConfigSHA256 D0AAF6D1…` and `-ExpectedDockerConfigSHA256 40C08D09…`. Both equal the files on disk. `-DockerConfigPath` is this root's docker-ops file, and there is no `-ReceiptPath`, so the default `native-provider-host-receipt.jsonl` applies.
- **Paths:**
  - `receipt_directory` is `…\scheduler-native-ms-refresh-retirement-launch-dex-v1\scheduler-native-provider-diagnostic-launch-v1.evidence`, which is absent;
  - docker-ops `public_ca_directory` is that path plus `\public-ca`;
  - the runner's `readonly_binds` are `[payload → /packet, public_ca_directory → /public-ca]`, and the DB's is `[payload → /packet]`;
  - `source_directory`, `manifest` and `docker_config` are under the same fresh root.
- **Bounds unchanged:**
  - 900/600; peer 120 + 5; PKI 30 + 5 + 5 = 45;
  - `command_count_cap` 32, static success 22;
  - `output_byte_cap` 1 MiB per command plus the separate report;
  - per container: 1 CPU, 1 GiB memory + swap, 64 PIDs, pinned nonroot/read-only images;
  - `success_cleanup: exact_id_only`.
  
  The exclusions and the inherited CLI-kill qualification are stated in the current doc.

## 5. Batch-compatibility finding: corroborated
I checked `MS-Refresh-Invalid-Grant-Batch-Compatibility-Review.json` (`0427EC48C86D086AC62ED1D6B2085AF8349BCD1A1663B72E7BE729715852CFBF`) against the runner `1A95E834` on disk:
- **`provision_disposable_schema` (l.574)** runs `app_db.Base.metadata.create_all(setup.connection(), checkfirst=False)` at **l.581** on a fresh setup session, then commits.
- **Both bodies call it:**
  - refresh: l.1335 `factory = _open_native_setup_factory(...)`, then l.1336 `provision_disposable_schema(factory)`;
  - invalid-grant: l.1944, then l.1945.
- **Same database:** both factories use `_fixture_database_profile()` (l.615): `native-fixture.invalid`, 127.0.0.1:5432, database and user `dex_fixture`.
- **No reset or isolation:**
  - there is no `drop_all`, `DROP`, `CREATE SCHEMA` or `search_path` anywhere in the payload's `fixture/` or `api/` Python;
  - the optional `native_suite.provision_native` path is absent from the packet (no `native_suite*` file), so it falls back to the `ImportError` branch;
  - docker-ops has a single database role per invocation.
- **Consistent side evidence:** only NONEXPIRED (l.764), REFRESH and INVALID provision the schema. The two T05 cases don't, which is consistent with the T05 two-case batch having reached case 2 natively without a schema error.
- **No counterevidence found.** This is source inference only: no duplicate-table error has been observed, and I make no runtime claim. I agree with keeping separate single-case checkpoints and with requesting no batching edit.

## Separation
- **Static acceptance:** §1–4.
- **Corroborated:** §5.
- **Label nit:** §3.
- **Unproved:** native refresh, T06 closure, peer timing and worker scheduling.
- **Held:** native MS-REFRESH, its fake (its own card), the T05 fake card, T03 D1, and all execution.

Signed: Matt
