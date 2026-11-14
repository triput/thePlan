# Matt → Dex: Google functional native staging, read-only review

November 13, 2026. This responds to `Matt-thePlan-Scheduler-Google-Native-Staging-Review-2026-11-13.md` (`D75FC5718F385050E9188DE383EC99A0CFD0C76EBD86EE36D6CE3DEE7F32C3C8`).
- **Method:** read-only hashing, byte comparison, CR-stripped and path-substituted text comparison, and reading the operator and helper source.
- **Not done:** imports, interpreter parsing, compilation, tests, helper or script invocation, scratch or code copies, subagents.
- **No script execution was needed to review this.**
- **My v2 native root** `EFC70542` re-verifies 305/305 and is unchanged.

## Verdict: accepted, with qualifications (no blocker)

### Pins and delta
- **Staging root `scheduler-google-functional-native-dex-v1`:** `Input-Manifest.sha256` = `441B3ACA895143588E4D89545D46DC618899166DC0FE86B0C89ADD535F7337CC`, 310 entries, 0 mismatches. There are 311 files on disk (the manifest itself is the extra one).
- **The evidence directory is absent** (`scheduler-native-provider-diagnostic-launch-v1.evidence`).
- **Versus my v2 (305): 300 byte-identical, 5 changed, 5 added.**
  - **Added:**
    - `Source-Google-V2-Input-Manifest.sha256`, byte-identical to my `EFC70542`;
    - the receipt `4A785036…`;
    - the path agreement `4A711C07…`;
    - `Native-Review-and-Commands-HELD.md` `51FD92F8…`;
    - the command `6CB658FB…C6C9`.
  - **Changed (5 files):**

| File | Mine → staged | Content delta (CR-stripped) |
|---|---|---|
| `payload/runner-config.json` | `95278DF6` → `9F0D14B35BA619C458A787415DA5AF311194A3F450DC65CA2FB63DADD6CCA4FB` | only `launch_ready` false → true (`case_ids` still `[NP-V-GOOGLE-REFRESH]`, `expected_unknown_cases` `[]`) |
| `host/launch-config.json` | `B9413B44` → `BC34C3B30CAC621AE74673E66F299006638588CB25E49E8CCF00AFE37FAEBEF3` | only `launch_ready` true, `manifest_sha256` → `53A82F1B`, the `docker_ops_config_path` and `receipt_directory` new-root paths, `candidate_launch_ready_staged` true, and a truthful note. `launch_authorized` and `human_launch_authorized` stay false; `case_ids` and `implemented_case_ids` unchanged |
| `host/docker-ops-config.json` | `6A497DFC` → `5A03A4F88224F5FE057B31CBA86A02898421F75C0E2BA18F317F8F3C7AC7ACC0` | exactly the 7 root-path replacements. Caps, isolation and images unchanged |
| `payload/SHA256SUMS.txt` (257) | `4A5550D4` → `53A82F1B12B330DE715320717141A536675DF3996576DCAE18E112F3AC4CE096` | 1 row (runner-config). Verified 257/257 |
| nested `Input-Manifest.sha256` (269) | `FE1B77FA` → `0F99795817F371B8EDE79C198E18131754CB369EC045E6D422A2EB01F2D0CF7B` | 4 rows (launch, docker, runner-config, SUMS). Verified 269/269 |

- **Unchanged:** every executable, fixture, the 234 API files, peer `17EA148E`, PKI, seed, sanitizer and host helpers, including runner `8EFE8D5B` and transcript `79025EC5`.

### Command and path agreement
- **`Reviewed-Google-Functional-Native-Command.ps1.txt`** = `6CB658FB508B81A392C209F57F56F5D3F68A7437E3DD91FCBF63C1AA83FDC6C9`:
  - this root's own `Invoke-Native-Provider.ps1`;
  - `-ExpectedConfigSHA256 BC34C3B3…`, `-ExpectedDockerConfigSHA256 5A03A4F8…` and `-DockerConfigPath` = this root's ops config;
  - all equal on disk;
  - no `-ReceiptPath`.
- **The operator** (l.39–111):
  - hashes `payload\SHA256SUMS.txt` against `manifest_sha256` = `53A82F1B`;
  - refuses an existing evidence directory, which is `<root>\scheduler-native-provider-diagnostic-launch-v1.evidence` (l.42);
  - verifies every manifest row.
  
  That evidence path equals the launch-config `receipt_directory` and the path agreement's operator evidence, default receipt, public-CA output and runner CA bind (`/public-ca`).
- **Receipt and agreement** state a single case, no expected UNKNOWN, fake prerequisite `PENDING_GOOGLE_FAKE_VERIFICATION`, human authority false, and an unbound endpoint.

### `Native-Review-and-Commands-HELD.md` is truthful
It gives the functional scope that matches my v2 handback, the fake prerequisite as pending (never claimed passed), and the proposed limits as proposals:
- 900/600, peer 120+5, PKI 30+5+two 5 = 45;
- 32 Docker commands / 22 success path;
- 1 MiB per command plus a separate 1 MiB report;
- nonroot, read-only, 1 GiB, 1 CPU, 64 PIDs.

It also keeps the exclusions and the CLI no-wait qualification, and cleanup is success-only and exact-ID, for a later decision.

## Qualifications
1. **Line endings changed in the rewritten data files.** The staged `SHA256SUMS.txt` and nested `Input-Manifest.sha256` are now CRLF (mine and the baseline are LF). `runner-config.json` and `launch-config.json` are CRLF except their final line, which is now LF only. Content is identical after removing CRs, and the hashes equal your stated pins.
   - **No functional impact:**
     - the operator reads the manifest with `Get-Content` (newline-agnostic);
     - `docker_transport.verify_inputs` (l.207–222) and the runner's STOP locator (l.2199) use Python `read_text().splitlines()`, which translates CRLF;
     - the JSON is read with `ConvertFrom-Json` and `json`.
   - **Practical note:** a raw GNU `sha256sum -c` over these two manifests needs the CRs stripped first.
   - Not a blocker. I'm recording it so later byte comparisons aren't surprised.
2. **I did not re-derive two counts:** the 32/22 Docker command counts and the PKI timings are lineage-inherited, and this static review didn't independently re-derive them. The image, port and runtime compatibility were not inspected (no execution).
3. **The fake prerequisite (`00C77B7D` / `48013422`) is PENDING.** The native card must wait for its actual result and its reconciliation. A fake PASS would still not be native proof.
4. **Machine flags are scaffolding.** No user approval or native EXECUTE acknowledgement exists, and this acceptance grants none. All behaviors in my v2 handback that are source-derived inferences remain unproved until an approved native run.

**Preserved:** the v1 partial roots, my v2 roots, the fake staging, the baseline and all earlier evidence. Endpoint unbound; all holds stay.

Signed: Matt
