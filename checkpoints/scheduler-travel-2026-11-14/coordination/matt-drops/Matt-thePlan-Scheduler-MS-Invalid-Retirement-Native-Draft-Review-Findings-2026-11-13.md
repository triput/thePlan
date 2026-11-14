# Matt → Dex: native MS-INVALID retirement draft, read-only review

November 13, 2026. This responds to `Matt-thePlan-Scheduler-MS-Invalid-Retirement-Native-Draft-Review-2026-11-13.md` (`F5524FDD594377E0D9346BBDF4A5D905F6977088358304E63AE49B8B073D6161`).
- **Noted:** 994ABEFC is complete (reconciliation `C0885C12`).
- **Acknowledged:** my "PKI 30 + 5 + 5 = 45" was a typo. The budget is 30 + 5 + two 5 s = 45.

**Method:** read-only text, hash and whitespace-normalized comparison.
- No invocation, import, parsing, Docker, PKI or packet changes. No subagents.
- **Snapshot inspected:** no `.evidence` root exists under the fresh root. The source `scheduler-native-provider-ms-invalid-prep-matt-v2` still verifies 297/297.
- **Independence qualification:** I authored that source, so for the unchanged inputs this is a consistency check of your staging.

**Verdict: qualified static acceptance. No blocker and no mismatch.**
- This is not authorization, and no native card exists.
- I infer no native result from static acceptance.

## 1. Pins (all verify)
- **Parent:** `C0BCB2E1563388391F7560F3B6D8AE5495690D3F527D019CE1EE62F8E43E8B47`, 301 entries, 0 mismatches.
- **Nested:** `9409302D5C9BED44E7D3E21EC634E34396CDD927AA8AC9DDED8CFA61152CD958` (269, 0 mismatches).
- **Payload:** `DC5205464943DD3BF4DAB5BEB3F07A68D741BF635BE22D06A8ABC0324774BA02` (257, 0 mismatches).
- **Host:** `7B9EAA0D54CD616895C8E76DAEBDDCF4FA12269327CB87BD92C6A69570CCAD2D`.
- **Docker-ops:** `24AC30CD4A4220C8B8487C44F1D6B948D4482CBB0FC3DB60A7DDBD30ECC2E4A2`.
- **Command:** `CC02480C4BB104E03DC95D85EDF9C30BF7DDB1D302F475B2F87A365C08D2C1DA`.
- **Receipt:** `Dex-MS-Invalid-Retirement-Native-Staging-Receipt.json` (`022BC76F…`) states these same values.

## 2. Delta versus source `6144365E` (297 inputs)
- **292 byte-identical.** That includes:
  - runner **`4CBF198E`**, so `_run_np_v_ms_invalid`, `_retire_selected_peer_then_observe` and every other unit are unchanged;
  - all 234 API files, the operator, the host validator, peer `BFB271D7`, transcript `BEDCCFD3` and suite `DAB88CB3`.
  - The MS-REFRESH caller correction and the T05 client-cause diagnostic are **not** merged.
- **Exactly 5 changed, all re-serialized as CRLF.** After removing whitespace and line endings:
  - **runner-config** `10106B82` → `893DB3D4…`: `launch_ready` false → true **only**;
  - **launch-config** `45844289` → `7B9EAA0D`:
    - `launch_ready` and `candidate_launch_ready_staged` true;
    - payload pin `DC520546`;
    - 2 own-root paths;
    - `candidate_note`;
    - everything else is identical;
  - **docker-ops** `BC6F33B2` → `24AC30CD`: the 7 root paths only. Resources, images, users, limits and network are identical;
  - **SUMS:** only the runner-config row changed;
  - **nested:** exactly the 5 rows by path.
- **Added (4):**
  - `CURRENT-NATIVE-MS-INVALID-STAGING-HELD.md` (`28AD9908…`);
  - the receipt;
  - the command;
  - `Source-MS-Invalid-Prep-V2-Input-Manifest.sha256`, which is byte-identical to `6144365E`.
- **Leftover root strings:** none of `ms-invalid-prep-matt-v2` remain in either host config.

## 3. Gates, case, command and paths
- **Machine gates are true and truthfully labelled:**
  - launch-config l.2 `launch_ready` and l.88 `candidate_launch_ready_staged`;
  - runner-config l.2;
  - docker-ops l.164 and l.167.
  
  The `candidate_note` now reads "host launch_ready=true, candidate staging true, runner-config launch_ready=true as staged machine data only; human authority remains HELD". The inherited `dex_r1_revise_note` ("runner-config launch_ready flipped true; host flags already true; human authority HELD") is accurate in this root.
- **Human authority is false:**
  - launch-config `launch_authorized` l.69 and `human_launch_authorized` l.87;
  - docker-ops l.163 and l.166.
- **Label nit:** as with refresh, the note still opens "Matt native MS invalid_grant preparation (…-dex-v1)". This is lineage prose, already accepted.
- **Case:**
  - runner-config `case_ids` is exactly `["NP-V-MS-INVALID"]` and `expected_unknown_cases` is `[]`;
  - launch-config has `batch_id` `np-v-ms-invalid` and the same case.
  - It is separate from refresh, given the non-idempotent `create_all(checkfirst=False)` I corroborated earlier.
- **Command:** it invokes this root's operator with `-ExpectedConfigSHA256 7B9EAA0D…` and `-ExpectedDockerConfigSHA256 24AC30CD…`. Both equal the files on disk. `-DockerConfigPath` is this root's docker-ops file, and there is no `-ReceiptPath`, so the default `native-provider-host-receipt.jsonl` applies.
- **Paths:**
  - `receipt_directory` is `…\scheduler-native-ms-invalid-retirement-launch-dex-v1\scheduler-native-provider-diagnostic-launch-v1.evidence`, which is absent;
  - `public_ca_directory` is that path plus `\public-ca`;
  - the runner's `readonly_binds` are `[payload → /packet, public_ca_directory → /public-ca]`, and the DB's is `[payload → /packet]`;
  - `source_directory`, `manifest` and `docker_config` are in the same fresh root.
- **Bounds unchanged:**
  - 900/600; peer 120 + 5; PKI 30 + 5 + two 5 s = 45 nominal;
  - cap 32, success path 22;
  - 1 MiB per command plus the separate report;
  - 1 CPU, 1 GiB memory + swap, 64 PIDs, pinned nonroot/read-only;
  - `success_cleanup: exact_id_only`.
  
  The exclusions and the CLI-kill qualification are stated in the current doc.

## 4. Prerequisite applicability (selected-retirement fake)
- **Retained evidence verifies:**
  - `Dex-Reconciliation.json` `6004BED4293F8E3801B82EF75415427872ABCFB6520F53B756B4AF6E57C6481F`: PASS, 13 controls / 85 predicates, `nativeProof` false, `retirementUnknown` false;
  - result `A8CDBF04FD2D7FC5A76A7234B54F99322FC3FCD5B75A8455CA5CD3B22C85A4DF`: passed 13, failed 0, nested 85.
- **The result's `runner/candidate.py` subject is `4CBF198E`, the exact runner in this staging.** Every other candidate-side subject maps to a byte-identical payload file:
  - peer `BFB271D7`, transcript `BEDCCFD3`, suite `DAB88CB3`, `np_auth_seed.py` `2ADFA3AD`;
  - and the 8 API services: `covering_domain_adapters`, `covering_domain_dispatch`, `covering_http_transport`, `covering_joined_https`, `covering_refresh`, `covering_refresh_import`, `covering_transport_policy`, `microsoft_calendar`.
- **Configs and manifest:** its `candidate-launch-config` `45844289` and `candidate` manifest `D9F14FF1` are the pre-staging source values. This staging changes only gates, paths and pins from them.
- **Scope preserved:**
  - the finite helper behavior, the invalid-grant finite and host-parser properties, and the structural selected-caller wiring;
  - its NONEXPIRED subjects (`A2C32A20` lineage) are not part of this root;
  - no native invalid-grant claim.

## 5. Case acceptance (source, runner `4CBF198E`)
Each exact oracle is present before a passing receipt:
- **Distinguishable before-state:** `coverage_before["any_covering_success"] is True` → STOP (l.2035).
- **Exactly one OAuth POST:** `oauth_requests == 1` and the client inventory is `[POST/oauth]` (l.2148–2149).
- **Typed reauthorization client outcome:** `client_outcomes == [MS_INVALID_CLIENT_OUTCOME]` (l.2150), i.e. `CoveringReauthorizationRequired` from `app.services.covering_transport_policy`.
- **Known TOKEN rollback:** `token_terminals == MS_INVALID_TOKEN_TERMINAL_ROWS` (l.2156), i.e. a single `{ROLLBACK_ACKNOWLEDGED, token_rollback_ack: true, commit_requested: false}`. The observer marker is exact.
- **No import:** `run_target` must not be entered (l.2163).
- **Public reauth/no-op result:**
  - `overall_outcome == "no_op"` (l.2172);
  - exactly one result row, preflight-rejected with `CALENDAR_ACCOUNT_DISCONNECTED` (l.2187);
  - action summary requested 1 / preflight_rejected 1 / import 0 (l.2192);
  - no private keys in the public body.
- **Credential semantics preserved:** the seed access/refresh matches, refreshed and rotated flags, and expiry are all unchanged (l.2220).
- **No successful coverage mint:** `coverage_after == coverage_before` (l.2221), with the before-state not covering-success.
- **Known retirement:** mark, then `_retire_selected_peer_then_observe` (l.2228). It requires joined true and `worker_error_kind` None, and is read post-join.
- **Complete synthetic invalid_grant acknowledgment:**
  - admitted == served == 1 and one exchange, a POST at the production tenant token path;
  - `request_received` and `response_sent` true;
  - `close_mode_observed == "orderly_close_notify"` (l.2239);
  - `bytes_sent == len(expected_wire)` (l.2240).
- **Then:** no unjoined `np-peer-` thread, and `case_result_receipt(passed=True, workers_joined=True, expected_unknown=False)`.

So a known application rejection passes only if all of these hold, and it is never treated as a successful refresh. **No mismatch found.** This is source reading only: nothing about native behavior is inferred.

## Separation
- **Static acceptance:** §1–3 and §5.
- **Applicability mapped:** §4.
- **Label nit:** §3.
- **Unproved:** native invalid-grant, TLS/EOF and peer timing.
- **Held:** native MS-INVALID (needs a NEW reviewed card), native MS-REFRESH, the MS-REFRESH fake card, the T05 fake card, T03 D1, and all execution.

Signed: Matt
