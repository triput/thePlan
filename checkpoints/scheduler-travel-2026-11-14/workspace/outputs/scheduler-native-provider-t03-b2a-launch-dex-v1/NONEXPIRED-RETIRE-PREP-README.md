# Native NP-V-MS-NONEXPIRED selected-retirement successor v1 (CURRENT README)

Matt, November 13, 2026. This is for `Matt-thePlan-Scheduler-MS-Selected-Retirement-Correction-2026-11-13.md` (`BB93F31E…0DF4`), part B, under lane `389A00DD…7E2D`.

**Status: PREPARED_NOT_EXECUTED, frozen, no active writer.**
- **Reset to false:** host launch-config `launch_ready` and `candidate_launch_ready_staged`, and runner-config `launch_ready`. All three were true in the Dex staging source. `human_launch_authorized` is false.
- **Still true, as copied machine data:** the docker-ops-config's `launch_ready` and `candidate_launch_ready_staged`. That is never human authority.
- The original native card `A50C04FB` is **WITHHELD** and not reusable; a new exact card is needed after review.
- The endpoint is unbound.

## Source
- `scheduler-native-provider-peer-close-launch-dex-v1` (manifest `2913656A…`, 287 inputs, verified 287/287; runner `341074AE`, peer `17EA148E`).
- **Lineage:** `Source-Peer-Close-Launch-Dex-V1-Input-Manifest.sha256`.
- **Historical, copied with the inputs:** every other top-level document and command (Peer-Close, Worker, Review, Reviewed command, Future command).

## The only behavioral change (role 4, R1/R2)
- **New pure helper:** `_retire_selected_peer_then_observe(peer, join_seconds=5.0)`, text-identical to the one in invalid-grant v2.
  - It makes one call to the unchanged `retire_owned`.
  - `PeerRetirementUnknown` and every other exception propagate unchanged.
  - It requires `joined is True` **and** `worker_error_kind is None`, then reads `sanitized_state()`.
- **Moved barrier:** `_run_np_v_ms_nonexpired` sets `retirement_attempted = True` and calls the helper right after the token checks, **before** the final peer-state check (served == admitted == 4 connections). That check now uses post-join state.
- **Removed:** the late retirement and `joined`-only check. The receipt (`passed` and `workers_joined` True) follows every predicate.
- **Cleanup unchanged:** the `finally` failure-path retirement still runs only if no attempt was made.
- **Unchanged:** every other assertion (alias rewrite, coverage, OAuth count 0, TOKEN ROLLBACK acknowledgement, public response, budget proof, observer), the 234 API files, peer `17EA148E`, the operator and helpers.

## Hashes
- **Runner:** `341074AE` → `A2C32A2042A523BE932826666D87501AA57A6B4D0E4ECCB173AEDF966794B77D`.
- **Runner-config:** `launch_ready` false gives `9411AC38`, the pre-staging bytes.
- **Payload SUMS:** `5835297919BA3B43DEB767FD5F88F9A8AE41F7EBF0EC3F5B73EB5CCC87251BF3`.
- **Launch-config:** `9BE3C57D…14D9`; **docker-ops:** `29FE19C0…224D`; **nested:** `908C0F6E…C908`.

## Not covered
- **MS-REFRESH:** its inherited analogous boundary is a recorded gap before any later launch. It is not changed here.
- **Unselected case bodies** are not certified by this correction.
- **Not merged:** T05, refresh and transcript.
- **Nothing native has run.**
