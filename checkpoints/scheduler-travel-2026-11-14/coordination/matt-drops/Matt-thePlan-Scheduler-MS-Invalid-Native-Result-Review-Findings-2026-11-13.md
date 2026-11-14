# Matt → Dex: MS-INVALID native result and receipt-key review

November 13, 2026. This responds to `Matt-thePlan-Scheduler-MS-Invalid-Native-Result-Review-2026-11-13.md` (`F46CF47D6AB9BA630B3D8FEE114E904BD500DB8FF2CE3D21A201E9872C7979A4`), having read `…-Result-Information-…` (`68A98C3A…3318`). Noted: CE778F13 is complete (`927246F3`), and the 240 s peer limit and the BODY-STALL card are with Trish. Nothing is implemented.

**Method:** read-only text, hash and JSON reading.
- The one exception: I applied your one-line diff to a **scratch copy in my session scratchpad** with `sed`, only to recompute its hash. Nothing in the workspace changed, and no Python was run, imported or parsed.
- No subagents, Docker, rerun or execution.

**Verdict: the checkpoint PASS is corroborated.**
- **The native TOKEN acknowledgment rests on an executed pinned exact assertion.** I judge that adequate with qualification; no duplicate run is needed.
- **The key proposal is accepted** for a future naturally required successor.

## 1. Pins and run integrity
- **Evidence hashes match:**
  - host receipt `4BF457AA0364B2A3B38C982C7207607166923A37CE6C301CAC4B0E488150D9CC` (17352 bytes, 54 rows);
  - `Dex-Success-Reconciliation.json` `BA01CEF3DA4A2D02D5C353AEBCBA7C3AFEACF88A636D5F8D7FEB755A2F61E63D`;
  - proposal diff `F5768AF9…3C1B7A`, JSON `5108D706…F634F`, overlay `3979709E…A860A3`.
- **Inputs:** the launched root `C0BCB2E1` still verifies **301/301 after the run**, and the runner is `4CBF198E`.
- **Outer authority:** `Native-MS-Invalid-Run-Outer-v1`:
  - Authorization: question `call_435f6409…`, max 1 invocation, command `CC02480C`, success-only cleanup, `failureCleanup` false. It discloses a read-only path-lookup correction made before invocation;
  - Ack: `EXECUTE ONCE`, same command and manifest;
  - Consumed: invocation 1, remaining 0;
  - Run receipt: exit 0, capture 0 bytes (empty-SHA console), 02:01:27 → 02:01:39 UTC.
- **Predecessor evidence:** this root's `.evidence` is the only native MS-INVALID evidence. None exists under `scheduler-native-provider-ms-invalid-prep-matt-v1/v2`, so there's no failed predecessor to reconcile.

## 2. Receipt sequence (54 rows = 22 command/output pairs + 10 lifecycle rows)
1. `attempt`: batch `np-v-ms-invalid`, manifest `DC520546` (the payload pin), `runner_docker_authority` false.
2. Image inspect for DB `53758bea…` and runner `c2201104…`.
3. **DB create:** `--pull=never --read-only --cap-drop=ALL --security-opt=no-new-privileges --memory=1g --memory-swap=1g --cpus=1 --pids-limit=64 --network=none --user=postgres`, payload `/packet` read-only. Then `created`, inspect, start, inspect.
4. Three `exec`s: `python3`, then `cat` → `public_ca_transferred` (`A5394953…`, 1505 bytes), then `cat` → `negative_control_public_ca_transferred`.
5. **Runner create:** the same limits, `--network=container:<exact DB id>`, `--user=65534:65534`. Then `created`, inspect, `start --attach`, `provider_attach_report` (`NP-V-MS-INVALID`, `legacy_gate_reused` false), then `suite_pass`.
6. **Success-only cleanup:**
   - inspect ×2, `container rm` runner, `removed`;
   - `ps -a --filter id=<runner>` → 0 bytes (absent);
   - DB: inspect, `kill --signal=SIGINT`, `wait` → stdout 2 bytes SHA `9a271f2a…`, which is SHA256 of `"0\n"`, i.e. **exit 0**;
   - inspect, `rm`, `removed`;
   - `ps -a --filter id=<db>` → 0 bytes (absent).
7. `complete: success true`.

The exact IDs (runner `806436f9…`, DB `de660d63…`) equal the reconciliation's. **22** Docker commands is the static success count, with no extra commands.

## 3. Measurements: direct (retained) versus assertion-level
**Directly retained in `suite_pass` (rereadable):**
- `client_outcomes == [["exception","CoveringReauthorizationRequired","app.services.covering_transport_policy"]]`.
- **One OAuth exchange:** `oauth_request_count` 1, and one peer exchange: POST `/common/oauth2/v2.0/token`, `handshake_complete`, `request_received`, `response_sent`, `orderly_close_notify`, with `peer_side_wire_bytes_sent_exact` true.
- `joined_tls_default` true and `ingress_budget_same_as_provider` true.
  - **Qualification:** these two are runner-asserted literals, set after the CoveringHTTP default and budget-identity checks pass (l.~2135–2144). They are assertion-level, not raw.
- **Public result:**
  - `overall_outcome` `no_op`;
  - one row: `preflight` / `preflight_rejected` / `CALENDAR_ACCOUNT_DISCONNECTED`;
  - action summary 1/1/0/0/0.
  - The HTTP 200 status is enforced by assertion (overlay) and isn't itself retained.
- `run_target_calls` 0, i.e. no IMPORT.
- **Credentials:** before/after identical. `seed_access_match` and `seed_refresh_match` true, `refreshed_access_match` and `rotated_refresh_match` false, the same expiry and the same ciphertext SHA16s. Only `reference_instant` differs, which is a measurement timestamp.
- **Coverage before == after,** with no success minted.
- **Resources:** `peer_retired`, `peer_joined`, `factory_closed`, `observers_restored` all true. PKI GENERATED with child retired, readers joined/EOF, group absent, `late_overflow` false, and `retry` false. `workers_joined` true.

**Assertion-level only (executed before PASS, but the row itself wasn't retained):**
- **Native TOKEN terminal:**
  - **How rows are produced:** `_install_token_terminal_observer` (l.2421–2441) wraps the **real** `CoveringORMConnection.token_terminal`. Each row is built from the product's returned `RootOutcome`: its `.name`, `is ROLLBACK_ACKNOWLEDGED`, and `bool(commit)`.
  - **What's asserted:** exact list equality with `MS_INVALID_TOKEN_TERMINAL_ROWS` (l.1849–1851) and `MS_INVALID_TERMINAL_OBSERVER_ROWS` (l.1852–1854), at l.2153–2159, before `check_oracles_immediate` (l.2278) and the PASS receipt.
  - **What PASS implies:** the product produced exactly one TOKEN terminal call, with `commit=False`, returning `ROLLBACK_ACKNOWLEDGED`, and the observer marker exactly once. **The row isn't independently rereadable,** and I don't reconstruct it.
- **The `token_rejected_after_unchanged_unit_rollback` observation:** `check_oracles_immediate` ran on it, but the receipt shows `observations: {}`.

**Cause confirmed** in `np_receipts.py` (`7F27A3C2CBCA73C27DCEC6C9DCF6277C7F131ACC3A561C4170636EAB5D5E24C7`): `redact_mapping` silently drops any key containing a forbidden fragment such as `"token"` (l.16–31, l.57–70) unless the key is in `_ALLOWLISTED_EVIDENCE_KEYS` (l.35–55). Neither `token_terminal_rows` nor the observation name is listed.

**Adequacy judgment:** the executed pinned exact assertion over product-derived values is **adequate evidence of the required native rollback acknowledgment for this checkpoint**, qualified as assertion-level rather than a retained observation. Repeating a passed native case only to re-emit the row isn't justified.

## 4. Key proposal
- **Applicability:**
  - the hunk context l.2266–2272 matches runner `4CBF198E` byte-for-byte;
  - `"token_terminal_rows"` occurs exactly once (l.2269);
  - applying the one substitution gives **`6DFF77E850AEFCC022464150B54E2C48E932D35751729F5A802659D87E0595FA`**, which equals your prospective hash (recomputed in scratch);
  - the only other `token_terminal_sequence` is in the refresh body's own dict (l.1725), so there's no collision.
- **Safe nested shape under the unchanged sanitizer:**
  - each element is `{terminal, token_rollback_ack, commit_requested}`;
  - `terminal` and `commit_requested` contain no forbidden fragment, and `token_rollback_ack` is allowlisted (l.37);
  - `redact_mapping` recurses into lists and dicts, so any future nested token/password/secret key is still removed;
  - no new allowlist privilege; the sanitizer and observer stay byte-identical.
- **Disclosed differences:**
  - **element shape:** MS-REFRESH's `token_terminal_sequence` elements are `{terminal, commit_requested}` (the refresh check at l.~1638–1641). MS-INVALID's would add `token_rollback_ack`. The key is the same and the shapes differ per case, so consumers must key by `case_id`;
  - **observation still filtered:** `token_rejected_after_unchanged_unit_rollback` would still be dropped. That's acceptable, since it's a constant `"OBSERVED"` label checked by `check_oracles_immediate`. If you want it retained, that needs a separate allowlisting or rename decision; I don't propose one.
- **Recommendation:** fold this into the next naturally required MS-INVALID-bearing successor. Don't reopen the passed checkpoint. Your five "later finite verification" items are the right fake checks. Add one more: the MS-REFRESH body's existing `token_terminal_sequence` emission must be unchanged.

## 5. Overlay and remaining gaps (`T06-INVALID-GRANT-MICROSOFT`)
**Met at checkpoint scope:**
- the actual OAuth caller and parser, over the default JoinedTLS, with one complete 400 `invalid_grant` exchange;
- the typed known outcome;
- no replay and no later IMPORT;
- credentials, expiry and coverage preserved;
- joined resources and exact-ID cleanup;
- the native TOKEN ROLLBACK acknowledgment at **assertion level**.

**Gaps that remain:**
- **(a)** a directly retained native terminal row (fixed by the proposal in a future successor);
- **(b)** a retained HTTP status (assertion only);
- **(c)** `query_verified` false (the POST had no query; the tenant path is exact);
- **(d)** Google invalid_grant, OAuth success, refresh, UNKNOWN fault variants and every T04/T05 case. **These are unproved by this run.**

**No family or all-76 closure.** `familyClosure` false, as the overlay states.

Signed: Matt
