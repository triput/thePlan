# Peer close_notify correction: focused fake verification preparation (HELD)

Matt, November 12, 2026. This is for assignment `Matt-thePlan-Scheduler-Peer-Close-Preparation-2026-11-12.md` (`34698A96…5DEF`). It's the companion to the frozen native successor `outputs/scheduler-native-provider-peer-close-prep-matt-v1` (peer `17EA148E…`, launch-config `5CC77837…`).

**No execution is authorized.** Nothing here has been imported, parsed, compiled or run. Both admissions have `launch_authorized=false`. No PASS is claimed.

## Roles and pins
- **Reused byte-identical:** wrapper `Invoke-Fake.ps1` `AE84E632…FEB7`, outer `verify_admission.py` `7DCA32E2…18FB`, launcher `launch_check.py` `D22C37E3…BD07`.
- **New:**
  - checker **`CE60B3D3E46E7E41EFD712A9E19CDC672605A36DF45C5B0A7B1C4CC9784F7184`**;
  - EXPECTED **`780456E21BF45BC378D3A1053842042BF9344F628E839F6488C57D991A0402C5`**;
  - OUTER **`6AE4337BC592F308CED8EA5655B54269847BD5121D6F4FDB1D3D17E0ADCBF35D`**;
  - VERIFICATION **`F2B750442D070BD45C158DA6C39E34BE017DD6405F0349720A74620A3C7167DF`**.
  - VERIFICATION holds 9 packet pins and the Python311 interpreter `5F7B89A6…`, all re-verified against disk.
- **Subjects:**
  - source peer `5568AF73…2A55`;
  - candidate peer `17EA148E…A039`;
  - `Peer-Close-Notify.diff` `023303AC…B30D` (1 hunk, −1/+1, line 394).
  - All are LF. The CRLF-pair-safe predicate rejects a bare CR.

## Fake surface
- **Extracted from each subject** (the actual source):
  - the `SyntheticProviderPeer` methods `_select_cert_paths`, `_close_listener`, `_close_client`, `_accept_once`, `_handshake`, `_script_close_mode`, `_recv_request`, `_send_response`, `_send_all`, `_close_connection`, `_run_one_connection`, `execute_script` and `sanitized_state`;
  - the helpers `_http_response_bytes` and `_parse_request_head`.
- **Fakes:**
  - a listener (pending clients and an accept counter);
  - clients;
  - TLS byte objects (request bytes; send, unwrap and close counters; injected unwrap or close exceptions);
  - an `ssl` namespace whose `SSLError` subclasses `OSError`, as CPython's does;
  - a `socket` namespace (constants, with `timeout=TimeoutError`);
  - a no-op `select`;
  - a lifecycle object with the exact `PeerLifecycle` field names (checked structurally).
- **One substitution:** `_build_server_context` returns a fake context. Certificate loading isn't exercised.
- **Not used:** sockets, real `ssl`, app or vendor imports.

## Controls (11 top-level, 35 nested predicates, in order)
1. **SUBJECT-PINS**
2. **DIFF-REDERIVATION:** literal; exactly line 394 changes from `except ssl.SSLError:` to `except OSError:`.
3. **PRESERVED-OUTSIDE-CHANGE:**
   - top-level nodes are AST-identical;
   - every class method except `_close_connection` is identical;
   - the only `_close_connection` change is the single handler type;
   - the fake lifecycle fields equal the `PeerLifecycle` fields.
4. **CLOSE-UNWRAP-SUCCESS** (source and candidate): returns None; unwrap called once and close once; notes are exactly `[orderly_close_notify_attempted]`; the phase is recorded.
5. **CLOSE-OSERROR-RESET-PIPE-TIMEOUT** (`ConnectionResetError`, `BrokenPipeError`, `TimeoutError`):
   - **Source:** the exact object propagates after one close, with **no notes** (neither the caught note nor the attempted marker).
   - **Candidate:** tolerated after one close, with notes `[close_notify_unwrap_ssl_error, orderly_close_notify_attempted]`.
6. **CLOSE-SSL-ALREADY-TOLERATED** (`SSLEOFError`, `SSLError`): both tolerate it; one close; both notes.
7. **CLOSE-NON-OSERROR-PROPAGATES** (`ValueError`): both propagate the exact object after one close, with no notes.
8. **CLOSE-CLEANUP-GUARD:**
   - an `OSError` from `close()` is swallowed by the existing guard in both (attempted note only);
   - a `ValueError` from `close()` propagates in both (no notes).
   - Nothing is broadened.
9. **OTHER-CLOSE-MODES-UNCHANGED:**
   - abrupt: SO_LINGER, SHUT_RDWR, close, abrupt note;
   - normal (`close_mode=None` gives `"normal"`): close plus `close_mode:normal`;
   - both identical between source and candidate, and the branch text is byte-identical.
10. **COMPOSITION-INVENTORY:** the actual `execute_script` → `_run_one_connection` → `_accept_once`, `_handshake`, `_recv_request`, `_send_response` and `_close_connection`, with 2 fake connection scripts (`/v1.0/me/calendar`, `/v1.0/me/calendars`).
    - **Source, with a reset on the first close:** the exact object propagates. There's exactly 1 accept, the log is `[accept, listener_close]`, and the second client is never accepted. The inventory is empty, and the notes are `[exact_request:GET:/v1.0/me/calendar]` only. The first TLS object was closed twice: once in `_close_connection`'s `finally` and once in `_run_one_connection`'s `finally` via `_close_client`.
    - **Candidate, with the same reset:** both connections are served (`served == admitted == 2`), with exact inventory rows. There are 2 accepts, the listener closes once after the last accept, each TLS object is closed once, and the notes come in exact order.
    - **Clean run:** the source and candidate states are identical.
11. **ACTUAL-SOURCE-MUTANTS** (on the candidate source). Each is detected only by its targeted oracle prefix:
    - `tolerance_reverted` (`except OSError` → `except ssl.SSLError`) → "candidate tolerance";
    - `selectivity_broadened` (→ `except Exception`) → "non-oserror selectivity";
    - `cleanup_removed` (orderly `finally` `tls.close()` → `pass`) → "cleanup count";
    - `keep_listener_dropped` (`execute_script` `keep = False`) → "full inventory not served".
    - The anchors were statically read as unique in the candidate source.

The checker also enforces the nested inventory and the total of 35 against EXPECTED before writing.

## Semantics notes
- `orderly_close_notify_attempted` means **attempted**. It's not evidence of a clean TLS closure.
- I corrected my trace's section 7 per Dex: in the source, a propagating `unwrap()` error skips the attempted note.

## Not proved
- **Native runtime cause:** the actual cause of the native refusal. The peer's real exception wasn't retained, and this fake tests a plausible source mechanism only.
- **Platform behavior:** real CPython, OpenSSL and kernel behavior (whether an RST surfaces as an `OSError` in `unwrap()`).
- **Native run:** native TLS closure, and the remaining NONEXPIRED vertical after the identity list.

## Limits (inherited launcher)
- **Timing:** 120 s, plus at most one 5 s kill/wait, plus two 5 s reader joins: 135 s nominal, with no separate outer timeout. Startup, file and OS latency are excluded.
- **Capture:** 64 KiB per stream; 256 KiB for the result.
- **Success** requires exit 0, no output, clean joined EOF readers and the exact ordered inventory.
- **Exclusive evidence** goes under `packet/verify/`; a failure stops and preserves, with no retry.
- **Deadline inside the composition:** `execute_script(seconds=1)`. The fakes return immediately; a stray accept would end at that 1 s deadline.

## Future command
`Future-Command-HELD.ps1.txt` (admission `F2B75044…`). The wrapper refuses while the flags are false.
