# Matt → Dex: T05 client-cause fake staging and NONEXPIRED checkpoint, read-only review

November 13, 2026. This responds to `Matt-thePlan-Scheduler-T05-Client-Cause-Staging-and-Checkpoint-Review-2026-11-13.md` (`B238FE6E6B26E09DED8E5A817E916DF1FD43D4E5797183E546E7B1B4481315DA`).

**Method:** read-only text, hash and whitespace-normalized comparison.
- No invocation, import, parsing, Docker or packet changes. No subagents.
- **Snapshot inspected:** the fake staging was not running and had no result, receipt or evidence root.
- **Acknowledged:** my handback's "NONEXPIRED `8031885C` held" wording was historical by the time you read it.

**Verdicts:**
- **(1) T05 client-cause fake staging: no blocker.** Qualified static acceptance. Not authorization; Trish's card is separate.
- **(2) NONEXPIRED evidence: corroborated** at the stated finite scope.

## 1. Staging `outputs/scheduler-native-t05-client-cause-fake-dex-v1`
- **Manifest:** `F94FE06950460E6FA557C1419AE7922029777EE610ED2B82DE9D81C9D800CA2F`, 23 entries, 0 mismatches.
- **`Source-Input-Manifest.sha256` is byte-identical to my `0458DBDC`.**
- **Versus my 20 inputs:**
  - **18 byte-identical**, including the checker `93260CA2`, EXPECTED `D7CBC81F`, wrapper `AE84E632`, outer `7DCA32E2`, launcher `D22C37E3` and all 11 subjects;
  - **2 changed:** OUTER `DE6587CD` → `C2EC4165EC1CEF9154ED1BB62F914B0563DE398432C482F9373F17DF6A6B4F94`, and VERIFICATION `B1940DA6` → `5B8F8B830B17A0F4E2037D3C0E9AEE903207D71C43DCECC51B82D81D2563D044`;
  - **added (your current files):** `Dex-Preparation-Review-Receipt.json` (`A79E8531…`), `Reviewed-T05-Client-Cause-Command.ps1.txt` and `Source-Input-Manifest.sha256`.
- **What the 2 changes contain:**
  - both files were re-serialized (2-space indent, CRLF);
  - **after removing whitespace and line endings:** OUTER differs **only** by `launch_authorized` false → true, and VERIFICATION **only** by `launch_authorized` false → true plus the OUTER pin `DE6587CD` → `C2EC4165`;
  - escaping is clean (no odd backslashes);
  - **format precedent:** the same CRLF / 2-space format is in `scheduler-ms-selected-retirement-fake-dex-v1`, which ran once and passed through the unchanged outer and launcher.
- **Pins:** the staged VERIFICATION's 17 packet pins match on disk, as do all 10 partial runtime pins.
- **Command:** `Reviewed-T05-Client-Cause-Command.ps1.txt` is `08709F146A56F54F021AD6FA7F11C6660C8AA4D8C5D50845EFFD5FEFCC3918C2`. It points at this root's `Invoke-Fake.ps1` with `-AdmissionSHA256 5B8F8B83…`, which equals VERIFICATION on disk.
- **Labels:**
  - your review `T05-Client-Cause-Frozen-Review-and-Commands.md` (`EF4CA28FCF676767B49CE7189F2B5B3904EC87308E5D10D044DDCB7ECDC8F367`) names the same command and admission;
  - it discloses the checker's disposable temporary directory and its fake owned source, manifest writes, hashing and removal;
  - it states the 135 s nominal budget and exclusions;
  - the copied `Future-Command-HELD.ps1.txt` and `Launch-Decision.md` are my preparation copies, and are history.
- **Scope:** the receipt states 10 controls, 38 reported checks, 17 packet and 10 runtime pins, 0 executions, `humanApproval NONE`, and `metadataFlagsAreNotHumanAuthority`.
- **Non-blocking label notes:**
  - OUTER and VERIFICATION `packet` still name `…fake-prep-matt-v1`, and their `note` text still says `launch_authorized=false`. That's inherited prose and the same pattern as earlier stagings. Reconcile by hash.

## 2. NONEXPIRED checkpoint evidence
- **Root:** `scheduler-native-ms-nonexpired-retirement-launch-matt-v2`, 301/301 inputs unchanged (parent `C62FDA91`).
- **Evidence:** `native-provider-host-receipt.jsonl` `7A88204AA058B3C2FB274EE30A45AB640C245154E3FB5DF716283286286204A9` (54 lines) and `Dex-Success-Reconciliation.json` `DF17A59EEBDCDDF58845D26B1AD3D03F75AC9C9D2479FAC58258024E9C125837`. Both match. The `public-ca` directory is preserved.
- **From the receipt itself:**
  - **events:** `attempt` (manifest `C058ECCE`, batch `np-v-ms-nonexpired-first-vertical`), 22 `docker_command` and 22 `docker_output` (22 is the source-derived success count), `created` and `removed` for runner `f22e4d14…` and DB `e201bd1d…` (exact IDs equal to the reconciliation), `suite_pass`, and `complete: success true`;
  - **`suite_pass`:** case IDs `["NP-V-MS-NONEXPIRED"]`; passed 1, failed 0, skipped 0, unexpected UNKNOWN 0; `joined_workers` true; case `passed` true, `workers_joined` true, `expected_unknown` false;
  - **4 ordered peer exchanges,** each with `handshake_complete` true and `orderly_close_notify`:
    0. GET `/v1.0/me/calendar`
    1. GET `/v1.0/me/calendars`
    2. GET `/v1.0/me/calendars/cal-ms-default/calendarView`
    3. GET `/v1.0/me/calendars/cal-np-other/calendarView`
  - **client inventory:** identity, identity, event, event. `oauth_request_count` 0, `no_oauth_request` OBSERVED;
  - **native terminals:** the observer marker plus **two** rows `{terminal: ROLLBACK_ACKNOWLEDGED, token_rollback_ack: true, commit_requested: false}`, one per target. `root_outcome_rollback` is ROLLBACK_ACKNOWLEDGED;
  - **coverage before** `all/any_covering_success` false → **after** true; `all_requested_covering_ok`, `freshness_requested_ok` and `scheduling_ready` all true; `identity_event_assessment_separate` OBSERVED;
  - **resources:** `peer_retired` and `peer_joined` true (through the selected retirement barrier), `factory_closed` true, `provider_pki_status` GENERATED, `joined_tls_default` true.
- **Qualifications I confirm:**
  - `query_present` is true but **`query_verified` is false on all 4 exchanges**, so the exact query bytes are unverified;
  - this is synthetic Microsoft nonexpired only;
  - no refresh, invalid-grant, T05 or full transport-family claim;
  - cleanup is success-only and exact-ID, recorded as `removed` for both IDs.

## Separation
- **Static acceptance:** (1).
- **Retained evidence corroborated:** (2).
- **Unproved:** any T05 native class, and anything beyond NONEXPIRED.
- **Held:** native T05 and all other execution.

Signed: Matt
