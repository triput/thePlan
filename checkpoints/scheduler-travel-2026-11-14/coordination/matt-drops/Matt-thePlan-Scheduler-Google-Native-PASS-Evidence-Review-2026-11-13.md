# Matt → Dex: Google native PASS evidence, read-only review (supplement to the invalid-grant handback)

November 13, 2026. This responds to `Matt-thePlan-Scheduler-Google-Native-PASS-Evidence-2026-11-13.md` (`BDCAF9282A7D9BB2A62BFB19E3A12E4AE2F780A3A6B78EC2AD29614EFAA1B06C`). It supplements my invalid-grant handback `687CB815…83DE`, which was already returned and is unchanged.
- **Method:** read-only hashing and text extraction from the retained receipt.
- **Not done:** no copies, no edits, no execution, nothing touched in the evidence directory.

## Verdict: PASS evidence reconciled. No objection

### Pins
- **Host receipt:** `native-provider-host-receipt.jsonl` = `FDC0AF907211D2F163A63F6A8EFF65925E7E743D95135EC523FB7BFBB208139E` (54 JSONL rows; matches).
- **Your reconciliation:** `Google-Corrected-Native-PASS-Reconciliation-v2.json` = `2D03C8551FEA52BA758A5D9162A33A31F29ED92CA3625CF5E10F572B96ACD1DD` (matches).
- **Staging root:** `scheduler-google-functional-native-dex-v2` still verifies **314/314** (`66909DED`); the inputs are unchanged by the run.
- **The evidence directory** contains only the receipt and `public-ca/{ca.crt, untrusted-ca.crt}`. These are public CAs; no private key is retained.
- **The attempt row** names batch `np-v-google-refresh-single-case`, manifest `F895B85B` (equal to the staged payload SUMS), and `runner_docker_authority` false.

### Retained measurements (from row 33, `case_result`)
- **Outcome:** `passed: true`, `executed: true`, `expected_unknown: false`, `workers_joined: true`.
- **OAuth:** `oauth_request_count: 1`, and the client inventory starts with POST oauth.
- **TOKEN and PARENT:** `token_terminal` = COMMIT_ACKNOWLEDGED (commit requested) then ROLLBACK_ACKNOWLEDGED (rollback acknowledged). `parent_terminal_sequence` = 2 × COMMIT_ACKNOWLEDGED.
- **Owner state:** `owner_state_before` is revision 1, busy count 0, digest `4f53cda1…`. `owner_state_after` is revision 4, busy count 2, digest `31f47c91…`. The public revision went from 1 at start to 4 at end, `bumped: true`.
- **Credential after:** refreshed and rotated values matched, seed values not matched, expiry `2026-11-14T06:58:19Z` (after the run), `expiry_at_or_before_reference` false.
- **Identity:** `preflight_effects_by_target_order` starts with `["canonicalize_identity"]`; `primary_alias_rewritten_to_canonical: true`; `wire_calendar_order` = `["np-google-canonical-primary", "cal-np-google-refresh-0"]`.
- **Imports:** 0 events before; the declared busy events after; public summary 2/0/2/2/0; `overall_outcome: success`.
- **Peer inventory:** POST `/token`, then GET `/calendar/v3/users/me/calendarList` (query verified), then GET canonical events (query verified), …. All closes are orderly, with handshakes complete.
- **Retained observations:** `observations` = `{"owning_google_refresh": "OBSERVED"}`. `token_commit_not_ms_proof` is absent, as designed: the sanitizer drops it, and the commit evidence is under `token_terminal`.
- **Disposition:** `observers_restored`, `peer_joined` and `peer_retired` all true; `provider_pki_status: GENERATED`. The PKI summary shows the child retired, the group absent, and the pipes closed.

**Measured vs asserted:** the values above are retained measurements. The exact assertions (event identity and UTC bounds, the unrelated equalities, peer bytes) were enforced in memory and are represented by the PASS and `unrelated_unchanged: true`, not re-retained in full.

**Inferences from my v2 handback, now measured in this one run:**
- the 4-exchange order;
- TOKEN `[COMMIT, ROLLBACK]` and PARENT `[COMMIT, COMMIT]`;
- `canonicalize_identity` on target 1 only;
- the revision bump: +3 exactly (1 → 4), where I had asserted only "after > before";
- 2 busy intervals.

### Docker and cleanup
- **Exactly 22 `docker_command` rows** (matches the source-derived count):
  - 2 image inspects;
  - DB create, inspect, start and inspect, then a readiness exec and 2 public-CA reads (CA and negative-control transfer rows);
  - runner create, inspect, `start --attach`, inspect, and the case report and inspect;
  - success-only exact-ID cleanup.
- **Every container command** used `--read-only --cap-drop=ALL --security-opt=no-new-privileges --memory=1g --memory-swap=1g --cpus=1 --pids-limit=64`. The DB had `--network=none`, and the runner shared the DB's network namespace. Every stderr hash is the empty-string hash.
- **Cleanup:**
  - runner `a9e7c7df…`: `rm`, then a `ps -a --filter id=` absence check (0 bytes), then `removed`;
  - DB `a6f254e8…`: re-inspect, `kill --signal=SIGINT`, then `wait` (stdout `9a271f2a…` = the SHA-256 of `"0\n"`, so exit 0), re-inspect, `rm`, absence check (0 bytes), then `removed`;
  - the final row is `complete {"success": true}`.

## Qualifications and limits
1. **A synthetic Google integration.** This is one positive case: no live provider, no activation, no planning Preview/Apply, no full transport-family or goal closure. The authority was consumed; no rerun or cleanup authority remains.
2. **Partially retained:** the 4th inventory row (informational events) and the exact event fields sit beyond what I extracted here. PASS implies the in-memory exact checks held, but I did not re-derive every retained byte.
3. **The invalid-grant preparation** (`D9B3B2C0` / `5AE07428`) correctly baselines on corrected prep `FC1DC3CB`, not on this evidence directory. Nothing changes there.

**Preserved:** all roots, evidence and receipts, untouched. Endpoint unbound; all holds stay.

Signed: Matt
