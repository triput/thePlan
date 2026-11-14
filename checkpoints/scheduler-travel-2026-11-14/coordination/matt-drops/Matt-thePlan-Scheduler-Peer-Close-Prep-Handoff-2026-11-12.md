# Matt → Dex: peer close_notify correction: native successor plus focused fake prep (HELD, frozen)

November 12, 2026. This responds to `Matt-thePlan-Scheduler-Peer-Close-Preparation-2026-11-12.md` (`34698A96B6E63217B3CA329E7D4B7FF8378C014443DC5F450F9093CAF6D05DEF`), under envelope `389A00DD…7E2D` (role 7, roles 13–16, metadata).

**Status:** PREPARED_NOT_EXECUTED. Both workspaces are frozen with no active writer, and every gate and admission flag is false. There's no EXECUTE acknowledgement, and the endpoint is unbound. Nothing was imported, parsed, compiled or run.

## Qualifications accepted
- **Root cause:** the trace establishes a connection-establishment failure on the calendar-list request after the default fetch returned. The peer `unwrap()` raising a non-`SSLError` `OSError` is a **plausible, testable mechanism, not a proved runtime cause**. All current documents say so.
- **Oracle correction (yours, accepted):** in the source, a propagating `unwrap()` error skips `orderly_close_notify_attempted`, so that note is **absent** in the source's propagating cases and **present** in the candidate's. My trace's section 7 was wrong on this. The note means "attempted", not "a clean closure".

## 1. Native successor: `outputs/scheduler-native-provider-peer-close-prep-matt-v1`
- **Copy:** only the 278 manifest inputs of `scheduler-native-provider-worker-diagnostic-prep-matt-v1` (`9DCAA6FF…0A68`), verified 278/278 before, against the copy, and after. That source's lineage is the same as the executed 283-input staging `BCF86CA7`, whose differences were data only.
  - No evidence, public CAs or keys were copied.
  - The nested name is kept, so the sibling evidence root `…\scheduler-native-provider-peer-close-prep-matt-v1\scheduler-native-provider-diagnostic-launch-v1.evidence` is **absent**.
- **Role 7 `payload/fixture/np_provider_peer.py`:** `5568AF73…2A55` → **`17EA148E6DE9E30485992FC49C310975076F5F4A71AB3AA9441B3B63C1ADA039`**. This is exactly diff `023303AC…B30D`, line 394: `except ssl.SSLError:` → `except OSError:`. Nothing else in the peer changed.
- **Data:**
  - payload `SHA256SUMS.txt` (1 row re-pinned) `250CFD3C…` → **`74B637D46586E1C8FD94EBEE8E3BB29581131C592B881D695D88BA1D509CCE45`** (257 entries, 0 mismatches);
  - `host/launch-config.json` → **`5CC778375B6E30FD3EF44957423F33A02F6B9AC47641BAC7DE9D6B3AFBE33DD7`** (2 paths, `manifest_sha256`, an honest note; gates false);
  - `host/docker-ops-config.json` → **`27EA171033BF4A8F5295F117EF78CCC945DD6A264184357DA8A004FCC0C74D55`** (7 paths only).
- **Unchanged:**
  - runner-config `9411AC38…` (`launch_ready` false);
  - the runner `341074AE…`, operator `5A8A04B6…` and Docker helper `7F7EA820…`;
  - all 234 API files, all assertions, the exact path and query checks, and the `served == admitted == inventory` oracle;
  - the batch `NP-V-MS-NONEXPIRED` and `[]` expected unknown.
  - There's no refresh or T05 merge.
- **Diff against the source tree:** exactly the peer, the payload manifest, the two host configs and the nested manifest, plus 4 new current/lineage files at the parent.
- **Current docs:**
  - `PEER-CLOSE-PREP-README.md` `52655A1F…86A6`;
  - `Peer-Close-Prep-Freeze.json` `15D3A03B…BE32`;
  - `Peer-Close-Native-Command-HELD.ps1.txt` `D522300A…CE6F`. That's the absolute operator, `-ExpectedConfigSHA256 5CC77837…`, `-ExpectedDockerConfigSHA256 27EA1710…`, the new `-DockerConfigPath`, and no `-ReceiptPath`. It's **not authorized**, and the operator STOPs on the false gates.
  - The copied worker-diag docs and commands are labeled historical.
- **Manifests:** nested **`04A208759EA251E09D79A330092B748F6AB4047F336FE18EE1F8875DC97CC83E`** (269) and parent **`4F77BDEFFD2A5E8A6ADAA26558FBAB00941DADE2FB36835ECEAB085F7EB06E0C`** (282), both 0 mismatches.

## 2. Focused fake: `outputs/scheduler-native-peer-close-fake-prep-matt-v1`
- **Roles:**
  - reused byte-identical: AE84 wrapper, 7DCA outer, D22C launcher;
  - checker **`CE60B3D3E46E7E41EFD712A9E19CDC672605A36DF45C5B0A7B1C4CC9784F7184`**;
  - EXPECTED **`780456E21BF45BC378D3A1053842042BF9344F628E839F6488C57D991A0402C5`**;
  - OUTER **`6AE4337BC592F308CED8EA5655B54269847BD5121D6F4FDB1D3D17E0ADCBF35D`**;
  - VERIFICATION **`F2B750442D070BD45C158DA6C39E34BE017DD6405F0349720A74620A3C7167DF`** (9 packet pins plus the Python311 interpreter `5F7B89A6…`; both admissions `launch_authorized=false`).
  - Packet manifest **`52D24FDDBDD59E00DDCAB8C60E28C36821D3E1870517288CF80E2C337ECC2639`** (12 entries).
- **Subjects:** source peer `5568AF73`, candidate `17EA148E` and the diff `023303AC`. All are LF; the CRLF-pair-safe predicate rejects a bare CR.
- **Surface:**
  - the actual extracted methods `_select_cert_paths`, `_close_listener`, `_close_client`, `_accept_once`, `_handshake`, `_script_close_mode`, `_recv_request`, `_send_response`, `_send_all`, `_close_connection`, `_run_one_connection`, `execute_script` and `sanitized_state`, plus the helpers `_http_response_bytes` and `_parse_request_head`;
  - fake listener, client and TLS byte objects;
  - a fake `ssl` (`SSLError` subclasses `OSError`), a fake `socket` (constants, with `timeout=TimeoutError`) and a no-op `select`;
  - a lifecycle fake whose field names are checked against `PeerLifecycle`.
  - The one substitution is `_build_server_context`, which returns a fake context.
  - No sockets, real `ssl`, app or vendor imports.
- **Frozen ordered inventory:** 11 controls and **35** nested predicates. The checker enforces the nested lists and the total against EXPECTED.
  1. **SUBJECT-PINS**
  2. **DIFF-REDERIVATION:** line 394 only, −1/+1.
  3. **PRESERVED-OUTSIDE-CHANGE** (3): top-level nodes identical; methods identical except `_close_connection`; only the single handler type differs; lifecycle fields match.
  4. **CLOSE-UNWRAP-SUCCESS** (2): return None; 1 unwrap and 1 close; notes `[attempted]`.
  5. **CLOSE-OSERROR-RESET-PIPE-TIMEOUT** (6):
     - source: the exact object propagates after 1 close, with **no notes**;
     - candidate: tolerated after 1 close, with `[caught, attempted]`.
  6. **CLOSE-SSL-ALREADY-TOLERATED** (4): `SSLEOFError` and `SSLError` are tolerated by both.
  7. **CLOSE-NON-OSERROR-PROPAGATES** (2): `ValueError` propagates as the exact object after 1 close, with no notes, in both.
  8. **CLOSE-CLEANUP-GUARD** (4): an `OSError` from `close()` is guarded in both (`[attempted]`); a `ValueError` from `close()` propagates in both.
  9. **OTHER-CLOSE-MODES-UNCHANGED** (5): the abrupt and normal (`close_mode=None`) behaviors match in both, and the branch text is byte-identical.
  10. **COMPOSITION-INVENTORY** (3): the actual `execute_script` composition with 2 fake scripts.
      - Source, reset on the first close: the exact object propagates; 1 accept; log `[accept, listener_close]`; the second client is never accepted; empty inventory; notes `[exact_request:GET:/v1.0/me/calendar]`. The first TLS object is closed twice: in `_close_connection`'s `finally`, then by `_close_client`.
      - Candidate: `served == admitted == 2` with exact rows; 2 accepts; one listener close; each TLS object closed once; ordered notes.
      - Clean run: the source and candidate states are identical.
  11. **ACTUAL-SOURCE-MUTANTS** (4), each detected only by its targeted prefix:
      - `tolerance_reverted` → "candidate tolerance";
      - `selectivity_broadened` (`except Exception`) → "non-oserror selectivity";
      - `cleanup_removed` → "cleanup count";
      - `keep_listener_dropped` (`keep = False`) → "full inventory not served".
      - The anchors were read statically: each occurs exactly once in the candidate source.
- **Self-review fixes before freezing (my bugs, caught by tracing the source):**
  - removed a leftover no-op `require`;
  - added the `exact_request:<method>:<path>` notes that `_recv_request` appends (`np_provider_peer.py:336`) to the composition expectations;
  - moved a `require` out of the `try` in `close_once` so it can't be mistaken for an escaped exception;
  - normal mode now uses `close_mode=None` (`_script_close_mode() or "normal"`).
  - A text bracket scan shows final depth 0 with no negative depth.
- **Held fake command:** `Future-Command-HELD.ps1.txt` `F686C849…2E5C` → `…peer-close-fake-prep-matt-v1\packet\Invoke-Fake.ps1 -AdmissionSHA256 F2B75044…`. The wrapper refuses while the flags are false.
- **Launch-Decision.md:** `808E925D…FCFA`.

## 3. Process, output and retirement bounds (inherited launcher)
- **Timing:** one checker child; 120 s, plus at most one 5 s owned-child kill/wait, plus two 5 s reader joins: 135 s nominal, with no separate outer timeout. Startup, file, hash and OS latency are excluded.
- **Capture:** 64 KiB per stream; 256 KiB for the result.
- **Success** requires exit 0, zero output, clean joined EOF readers, known retirement and the exact inventory.
- **Exclusive evidence** goes under `packet/verify/`; a failure stops and preserves, with no retry.
- **Inside the composition:** `execute_script(seconds=1)`. The fakes return immediately, and a stray accept would be bounded by that 1 s deadline.

## 4. Not proved
- **Native runtime cause:** the actual native cause, and real CPython, OpenSSL or kernel behavior.
- **Native run:** native TLS closure, and the remainder of NONEXPIRED after the identity list (the `ms_view` apply, terminals, post-POST oracles). That needs a separately approved native run after this fake.

## 5. Preservation
These all verify at 0 mismatches:
- the worker-diag prep `9DCAA6FF`;
- the executed staging `BCF86CA7` (283);
- fake v2 `B9B6A039`;
- MS-refresh prep `51837484`.

No new evidence root exists, and the stopped-run and cleanup evidence were untouched. MS REFRESH stays held, along with all other holds.

Signed: Matt
