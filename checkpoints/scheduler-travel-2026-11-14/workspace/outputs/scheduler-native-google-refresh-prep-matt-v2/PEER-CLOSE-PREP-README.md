# Peer close_notify correction: CURRENT native successor preparation README

Matt, November 12, 2026. This is for assignment `Matt-thePlan-Scheduler-Peer-Close-Preparation-2026-11-12.md` (`34698A96…5DEF`), under Trish's preparation envelope `389A00DD…7E2D` (peer role 7).

**Status: PREPARED_NOT_EXECUTED, frozen, no active writer.** The host `launch_ready`, `candidate_launch_ready_staged` and runner-config `launch_ready` are all false. No EXECUTE acknowledgement exists. The endpoint is unbound.

## Current versus historical
- **Current:** this README, `Peer-Close-Prep-Freeze.json` and `Peer-Close-Native-Command-HELD.ps1.txt`.
- **Historical, copied with the inputs:** `WORKER-DIAG-PREP-README.md`, `Worker-Diag-Prep-Freeze.json`, `Future-Native-Command-HELD.ps1.txt` (the worker-diag prep command; do not use), and the older Dex documents and commands, at both parent and nested level.
- **Lineage manifests:**
  - `Source-Worker-Prep-Input-Manifest.sha256` (`9DCAA6FF…0A68`, 278 entries) is the copy source.
  - `Source-Input-Manifest-dex-v1.sha256` is older lineage.

## Lineage
- Only the 278 manifest-listed inputs were copied from the frozen `scheduler-native-provider-worker-diagnostic-prep-matt-v1`, verified 278/278 before, after and against the copy.
- It's the same unchanged source lineage as the executed 283-input staging `BCF86CA7`, whose only differences were data (paths, flags, notes, dependent hashes).
- No dynamic evidence, public CAs or keys were copied.
- The nested name is kept, so the operator's sibling evidence label resolves to `…\scheduler-native-provider-peer-close-prep-matt-v1\scheduler-native-provider-diagnostic-launch-v1.evidence`, which is **absent**.

## The single executable change: role 7 `payload/fixture/np_provider_peer.py`
`5568AF73…2A55` → **`17EA148E6DE9E30485992FC49C310975076F5F4A71AB3AA9441B3B63C1ADA039`**. This is the exact Dex-accepted diff `023303AC…B30D`: one line in `SyntheticProviderPeer._close_connection`, the orderly branch:

```
-            except ssl.SSLError:
+            except OSError:
```

- **Meaning:** a reset, broken pipe or timeout during the peer's own optional close_notify `unwrap()` is now tolerated like an SSL error. It records the existing `close_notify_unwrap_ssl_error` note, and `finally` still closes the TLS socket.
- **Consequence:** the subsequent `orderly_close_notify_attempted` note is then appended. Before, a propagating error skipped it and ended the whole connection inventory.
- **The note means "attempted", not "a clean TLS closure completed".**
- Non-`OSError` exceptions still propagate.
- `ssl.SSLError` is a subclass of `OSError`, so everything tolerated before is still tolerated.

**Unchanged:**
- all other peer bytes;
- the observer runner `341074AE…`, `stop_payload` and its bounds, the host validator `7F7EA820…`, the operator `5A8A04B6…`, the supervisor and all other fixture roles;
- all 234 API files;
- every assertion, including the exact request path and query checks and the `served == admitted == len(inventory)` oracle;
- the batch `NP-V-MS-NONEXPIRED`, `expected_unknown_cases` `[]`, deadlines and isolation.

There's no refresh or T05 merge.

## Data changes
- **`payload/SHA256SUMS.txt`:** the one peer row is re-pinned; aggregate `250CFD3C…` → **`74B637D46586E1C8FD94EBEE8E3BB29581131C592B881D695D88BA1D509CCE45`** (257 entries).
- **`host/launch-config.json`** → **`5CC778375B6E30FD3EF44957423F33A02F6B9AC47641BAC7DE9D6B3AFBE33DD7`**: 2 path values, `manifest_sha256`, and the candidate note. The gates are false and unchanged.
- **`host/docker-ops-config.json`** → **`27EA171033BF4A8F5295F117EF78CCC945DD6A264184357DA8A004FCC0C74D55`**: only the 7 path values.
- **`payload/runner-config.json`** is unchanged at `9411AC38…` (`launch_ready` false).

## Root-cause qualification
The trace (`F1C72104…`) establishes a connection-establishment failure on the calendar-list request after the default-calendar fetch returned. The peer's `unwrap()` raising a non-`SSLError` `OSError` is a **plausible and testable mechanism**, not a proved runtime cause, because the peer's actual exception wasn't retained. The companion fake `outputs/scheduler-native-peer-close-fake-prep-matt-v1` tests the source mechanism only.
