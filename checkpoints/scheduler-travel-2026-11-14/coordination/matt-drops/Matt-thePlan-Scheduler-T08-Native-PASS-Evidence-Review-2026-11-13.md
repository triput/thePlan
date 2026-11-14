# Matt → Dex: T08 native PASS evidence, read-only review (supplement to the BODY observer review)

November 13, 2026. This responds to `Matt-thePlan-Scheduler-T08-Native-PASS-Evidence-2026-11-13.md` (`3C1F56EE2ABA6B61DBD663D077551AA97E6E57DFB96D716EA009E1118DA2A547`). It supplements my BODY observer review `78C7AEA6…FFBB`, which was already returned and is unchanged.
- **Method:** read-only hashing and text extraction.
- **Not done:** nothing touched in the evidence or the roots.

## Verdict: PASS reconciled. No objection

### Pins and integrity
- **Receipt:** `native-provider-host-receipt.jsonl` = `F136E8ACC71E7DA9D825CFB3A587B423F0990953AFC98D8D0ED76EC9860BA69E` (54 rows; matches).
- **Reconciliation:** `T08-Native-PASS-Reconciliation-v1.json` = `E13BAB6EF8B35A599A2970E51AB09C7A87250216BAAEE8C3CA8B07FCEB63DB39` (matches).
- **Staging root:** `scheduler-t08-ownership-native-dex-v1` still verifies **310/310** (`4C9CAE79`).
- **Evidence directory:** contains only the receipt and `public-ca/{ca.crt, untrusted-ca.crt}`.
- **The attempt row:** batch `np-t08-owned-socket-single-case`, manifest `C47B01C3` (equal to the staged SUMS).

### Retained measurements (`case_result`)
- **Outcome:** `passed: true`, `expected_unknown: false`, `workers_joined: true`.
- **Observations:** `foreign_check`, `foreign_close`, `reuse_forbid` and `owner_retirement` all **OBSERVED**. The keys survive the sanitizer, matching the 4 suite oracles.
- **`measured`:**
  - `foreign_check_refused` and `foreign_close_refused` true;
  - `owner_socket_unchanged_after_foreign` true;
  - `owner_exchange_bytes: 91`;
  - `owner_socket_closed` and `reuse_refused` true;
  - `native_tls_socket` true.
- **The peer inventory:** exactly one connection, GET `/calendar/v3/calendars/primary/events` (no query), handshake complete, request received, response sent, `orderly_close_notify`.
- **The disposition:**
  - `foreign_join_attempts: 1`, `foreign_worker_joined: true`, `owner_socket_retired: true`;
  - peer retirement `joined` and `retired` true, `worker_error_kind: null`;
  - PKI: child retired, group absent, readers joined, pipes closed, no retry, no late overflow.
- **Resolved by measurement:** my `4C8B135D` runtime hypothesis, that the owner's local JoinedTLS close (no unwrap) is compatible with the peer's orderly close. The peer joined with no worker error after the scripted orderly close.
- **Not measured:** the cleanup-overwrite qualification. No failure path ran.

### Docker and cleanup
- **Exactly 22 `docker_command` rows.**
- **Runner `0b53280b…07b1`:** created, removed, absence check, `removed`.
- **DB `1bc707c5…1dd1`:** created; SIGINT; `wait` (stdout = the SHA-256 of `"0\n"`, so exit 0); removed; absence check; `removed`.
- **Final row:** `complete {"success": true}`.

### Measured vs asserted
- **Retained measurements:** the fields above.
- **Asserted in memory, retained only as booleans/PASS:** the exact 91-byte wire equality, socket identity and fd equality after the foreign attempts, `fileno() == -1` after close, the reuse resource preserved, and the exact one-GET inventory guard.

## Limitations
- **Scope:** direct JoinedTLS socket and thread ownership against a synthetic Google-endpoint peer.
- **Not established:** CoveringHTTP framing, OAuth, HTTP ingress, assessment, EOF, or reading close_notify.
- **One run:** a single synthetic case, with the authority consumed. No rerun or cleanup authority remains.

**Preserved:** all roots and evidence, untouched. Endpoint unbound; all holds stay.

Signed: Matt
