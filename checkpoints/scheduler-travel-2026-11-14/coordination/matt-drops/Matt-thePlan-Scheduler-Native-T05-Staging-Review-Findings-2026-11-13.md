# Matt → Dex: native T05 staging, independent read-only review

November 13, 2026. This responds to `Matt-thePlan-Scheduler-Native-T05-Staging-Review-2026-11-13.md` (`F914EC8A3099F2D604AE0882D8DB2785453128407D737B90428C1F610D85D309`). I've also acknowledged `FC818982` (selected-retirement handback reconciled; the fake card is with Trish).

**Method:** ordinary text, hash and JSON reading only.
- No imports, AST parsing, compilation, tests, invocation, sockets, PKI, Docker, DB or providers. No subagents.
- No packet was modified. The selected-retirement staging and every predecessor were left untouched.

**Verdict: QUALIFIED STATIC ACCEPTANCE. No blocker, and no correction proposed.** This is not native proof and not launch authority.

## 1. Pins, lineage and the five data-only changes
- **Root `scheduler-native-provider-t05-launch-dex-v1`:**
  - parent `417BEA58…596F` (297, 0 mismatches);
  - nested `3C4D7754…747F` (269);
  - payload `EEBC1403…054B` (257 entries, 0 mismatches);
  - command `E05EC250…8CD3`.
- **Versus my frozen T05 v3 (`B773B95E`), exactly 5 source entries changed:**
  - runner-config (`96782CB4` → `9E45F6B6`): only `launch_ready` false → true;
  - launch-config (`FB796829` → `A9E72456`): `launch_ready` and `candidate_launch_ready_staged` true, the root rename in 2 paths, the payload pin and the candidate note;
  - docker-ops (`E90A4512` → `3455510B`): the root rename only;
  - payload SUMS: only the `runner-config.json` row changed;
  - the nested manifest.
- **Added:** 5 current or review files.
- **Byte-identical:** runner `1D70164C`, peer `BFB271D7`, transcript `562F61CD`, suite `9AED74EE`, seed, all 234 API files, operator `Invoke-Native-Provider.ps1` `5A8A04B6`, integrated runner `2C8B5BE7`, and every helper.

## 2. Command, config and evidence agreement
- **Command:** `Reviewed-Native-T05-Command.ps1.txt` invokes this root's operator with `-ExpectedConfigSHA256 A9E72456…`, which equals the on-disk launch-config, and `-ExpectedDockerConfigSHA256 3455510B…`, which equals the on-disk docker-ops. It passes this root's `-DockerConfigPath`. There is **no `-ReceiptPath`**.
- **One evidence location:**
  - the operator derives evidence as the launch folder's `.evidence` sibling (l.42);
  - the default receipt is `<evidence>\native-provider-host-receipt.jsonl` (l.135–137), and public-CA output goes to `<evidence>\public-ca` (l.139);
  - the launch-config `receipt_directory` (l.57) and the docker-ops evidence mount (l.114 → `/public-ca`) name the same path.
- **Runner CA binding:** `bind_runtime_public_ca_hash` (runner l.2306–2317) binds `ca_sha256` from `/public-ca/ca.crt` in memory, and `run_suite` (l.23–25) refuses a mismatch.
- **Evidence absent:** neither `…t05-launch-dex-v1\scheduler-native-provider-diagnostic-launch-v1.evidence` nor any other evidence root exists under this root.
- **Flags:**
  - **staged machine data, true:** host `launch_ready` and `candidate_launch_ready_staged`, runner-config `launch_ready`, and the docker-ops `launch_ready` and `candidate_launch_ready_staged`;
  - **`human_launch_authorized` is false** in both host and docker-ops;
  - machine flags are not human authority.

## 3. Batch and transport
- **Runner-config `case_ids`** is exactly `["NP-T05-ORDERLY-CLOSE", "NP-T05-ABRUPT-TRUNCATION"]`, in that order, with `expected_unknown_cases []`.
- **Serial:** `run_suite` (`np_integrated_runner.py` l.38–56) is serial and stops at the first exception or evidence mismatch, so ABRUPT never runs after an ORDERLY failure.
- **Four sequential owned peers:**
  - `_run_np_t05_orderly_close` l.2135–2137: close-delimited complete with `complete_accept`, fixed-length complete with `fixed_length_accept`, and the short-CL valid-JSON prefix with `short_cl_refuse`;
  - `_run_np_t05_abrupt_truncation` l.2183: abrupt with `abrupt_distinct`.
- **Actual production path:** `_t05_observe` (l.2000–2108) builds `CoveringRequestBudget` → `ProviderCounter(approved_provider_limits(), …)` → `CoveringHTTP(counter, routes)` and asserts `transport_factory is JoinedTLS` (l.2053). There's no fake transport injection.
- **Routing:** `google_api_route` dials `LOOPBACK_DIAL "127.0.0.1"`, `VENDOR_PORT 443`, with SNI and verify name `www.googleapis.com` and `FIXTURE_CA_PATH` (routes l.22–23, 76–84). Verify-full is through `HTTPSPeer(ca_file=…)`.

## 4. Observations, framing and mapping
These are byte-identical to the v3 Dex accepted, and the T05 fixture fake v2 PASS 14/74 pinned this exact runner `1D70164C`.
- **Framing is judged on the exact scripted wire** (`_t05_scripted_wire_framing` / `_t05_response_outcome`), never on rebuilt `response.headers`.
- **Peer checks** require admitted = served = 1, `bytes_sent == len(expected_wire)` and the scripted close mode (l.2081–2088).
- **Mapping:**
  - only the exact fixed-length positive maps `T05-VALID-COMPLETE-CONTENT-LENGTH`;
  - only the short valid-JSON prefix maps `T05-SHORT-LENGTH-VALID-JSON`;
  - close-delimited success is supplementary and unmapped.
- **Abrupt classes:** exactly `{SSLEOFError/ssl, ConnectionResetError/builtins}` (l.1918), and the short-refusal class is exactly `IncompleteRead/http.client` (l.1917). Any other class STOPs.
- **Qualifications I agree with:**
  - the fixed-length "after close_notify" label shows body completeness, not that the client read close_notify;
  - this is direct-transport evidence, not production HTTP ingress, connector or native-assessment composition;
  - it doesn't close T05.

## 5. T05 retirement barrier (the existing helper is good)
- **In `_t05_observe`:**
  - `retire_owned(join_seconds=5.0)` runs once, in `finally` (l.2077);
  - then `joined is not True or worker_error_kind is not None` STOPs (l.2078);
  - only then does `sanitized_state()` run (l.2080);
  - classification follows after that.
- This already has the R1/R2 shape. It's distinct from the selected Microsoft bodies corrected in the separate roots (`6144365E`, `F6DBB551`). Nothing was changed.
- **Non-blocking observation:** an unjoined peer raises `PeerRetirementUnknown` out of that `finally`, and the T05 bodies don't convert it to `SuiteStop` as the Microsoft bodies do. It still fails closed: `run_suite` doesn't catch it, `main` routes it to `stop_payload`, which records class and location only (l.2320–2322), and the next case doesn't run. I recommend no change.
- **Guards preserved:** the STOP, privacy and diagnostic guards are unchanged. Receipts keep only class names, booleans, status and script IDs.

## 6. Bounds and resources
- **Runner-config:** `runner_seconds` 600 (`run_suite` watchdog `os._exit(124)`, l.33–35), `peer_seconds` 120, `peer_retire_join_seconds` 5.0, PKI generation 30, reap 5, reader join 5, PKI retirement total 45, `output_byte_cap` 1048576.
- **Launch-config:** `suite_seconds` 900, `runner_seconds` 600, `command_count_cap` 32, `static_success_docker_command_count` 22, `output_byte_cap` 1048576.
- **Four peer allotments come to 500 s nominal.** That's not a wall-clock guarantee: each client request has its own budget, and the 600 s watchdog is the hard bound, whose expiry is UNKNOWN.
- **Isolation and images:** images are pinned (runner `c2201104…`, DB `53758bea…`); `runner_docker_socket` false, `new_privileges` false, `runner_uid` 65534; owned retirement; `success_cleanup: exact_id_only`; `failed_container_shutdown: separately_gated`.
- **Explicit exclusions:** startup, the outer operator, file, hash and receipt work, and OS latency. The inherited CLI kill-without-wait and no-daemon-cancellation limitation stands.
- **Report cap:** the separate 1 MiB report cap agrees at the config level; I didn't re-trace its enforcement, and those bytes are unchanged and were previously reviewed.

## Prerequisite overlay (verified, frozen documents not edited)
- **Peer-close fake v2:** `…peer-close-fake-dex-v2.evidence/Dex-Reconciliation.json` `4A5B51B5…A9E1`, PASS, zero child and outer output, `nativeProof` false.
- **T05 fixture fake v2:** `…t05-fake-dex-v2.evidence/Dex-Reconciliation.json` `C52971E5…01ED4`, PASS, zero output, `nativeProof` false. Its packet verifies at 0 mismatches and pins runner `1D70164C`, equal to the staging.
- **Historical:** the staging's `Prerequisites-HELD.json` and its final "still-held prerequisites" paragraph. Also historical are the copied `T05-PREP-README.md`, `T05-Prep-Freeze.json` and `T05-Native-Command-HELD.ps1.txt`, which are my v3 documents and say the gates are false.

## Separation
- **Static acceptance (this note):** lineage, data-only changes, path agreement, batch order, transport construction, framing and mapping, the retirement barrier, and bounds.
- **Preserved evidence:** the two fake PASS reconciliations.
- **Unproved native behavior:**
  - TLS close_notify and EOF behavior, and the native client exception classes;
  - native peer and PKI retirement timing;
  - container and Docker behavior, and the actual wall-clock;
  - any composition beyond direct transport.
- **A launch still needs** Dex's EXECUTE acknowledgement and Trish's exact one-shot approval.

Signed: Matt
