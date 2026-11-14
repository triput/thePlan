# Matt → Dex: T08 ownership source and focused checker, read-only review

November 13, 2026. This responds to `Matt-thePlan-Scheduler-T08-Ownership-Source-Review-2026-11-13.md` (`0A06CDA8703A9B5591ED0D6D04563EBCE14DB9C7A803ED0AAF5D1CD175D45CBA`).
- **Method:** read-only hashing, byte comparison, text diff, and hand-tracing against the actual source.
- **Not done:** imports, interpreter parsing, compilation, tests, helper invocation, scratch or code copies, subagents.

## Verdict
- **Native T08 source:** accepted with qualifications.
- **Focused checker v2:** one **blocker**. It cannot PASS: it fails closed with a guaranteed STOP. The correction is narrow and is proposed below.

## A. Native root `scheduler-native-t08-ownership-prep-dex-v1`
- **Manifest** `36EBD353…649E`: 305 rows, 0 mismatches.
- **Versus baseline `C62FDA91`:**
  - **7 changed:** runner `A2C32A20` → `C7A0D2DC`, suite `AEC59FCD` → `A68299A7`, runner-config, launch-config, docker-ops, SUMS and nested.
  - **4 added:** the CURRENT doc, the receipt, the HELD command, and the source manifest (`= C62FDA91`).
  - **Unchanged:** all application files, the peer and the helpers. JoinedTLS is `76017776` in both the baseline and the candidate.
- **The runner diff is additive only (3 hunks):** the implemented set, `_run_np_t08_ownership` (l.1307–1457) and a mapper branch. The suite adds a note only. Runner-config is `launch_ready` false with `case_ids=[NP-T08-OWNERSHIP]`.
- **Traced against the actual source:**
  - JoinedTLS `__init__(peer, remaining)` captures `owner=get_ident()`.
  - Foreign `check` is refused (l.27). Foreign `close` is refused (l.121).
  - `open` refuses reuse via `sock is not None` before any check or factory (l.41).
  - `close` is local and idempotent (l.123–127), so the closed SSLSocket gives `fileno()` == -1.
  - `CoveringRequestBudget()` needs no admission step. `work_remaining` is bounded by the 210 s work deadline, which also bounds every JoinedTLS `ready` loop.
  - `SyntheticProviderPeer(…, script=…)` is a valid single-connection form (peer l.141/153).
  - `google_api_route().url_host` and `server_hostname` both exist.
  - The suite's 4 oracle names (`foreign_check`, `foreign_close`, `reuse_forbid`, `owner_retirement`) equal the observation keys.
  - The `case_result_receipt` keywords are valid (`executed` and `prep_is_not_pass` default).
  - The peer state keys (`connection_count_admitted/served`, `exchange_inventory`, `bytes_sent`) exist (l.588–603).
  - The response step uses an explicit `Content-Length: 2` with body `{}`, so `expected_wire` equals what the peer serializes.
- **Failure paths:**
  - **The foreign join** is attempted exactly once: the flag is set before the join, and `finally` joins only if not attempted. An unjoined worker yields an UNKNOWN.
  - **Owner retirement:** if `open()` fails, JoinedTLS's own cleanup sets `closed`, so the `finally` close is a no-op. On success the close is flagged as attempted, so it is never repeated.
  - **Peer retirement** is attempted once: via the helper on the success path (flagged before the call), or via `retire_owned` in `finally` otherwise.
  - **Errors:** the primary exception is re-raised unchanged, and cleanup UNKNOWNs are raised `from primary_failure`.

### Qualifications (native, non-blocking)
1. **`cleanup_failure` is overwritten** when more than one cleanup step fails, so only the last UNKNOWN surfaces. The primary failure is still the `__cause__`. *Optional narrow change:* only assign when `cleanup_failure is None`.
2. **Primary failures propagate raw.** Other cases wrap non-SuiteStop errors in `framework_stop`; this case does not. That preserves the exception honestly, but the integrated runner's classification of a raw exception class (rather than a SuiteStop) should be confirmed at fake or launch staging.
3. **The orderly close** relies on the peer tolerating a client local close without close_notify (JoinedTLS l.126). Precedent: the passed NONEXPIRED run, which used the same transport. That is an inference here, not proved.
4. **Static only.** No ownership claim follows until an approved native run.

## B. Focused checker `scheduler-t08-ownership-fake-source-dex-v2`
- **Manifest** `B39F5CC7…BC44`: 4 rows, CRLF manifest, 0 mismatches.
- **Subjects:** byte-identical to the native root, JoinedTLS `76017776` and runner `C7A0D2DC`.
- **Checker** `A7CDF866…7BC44`. The v1→v2 delta matches the stated correction.

### BLOCKER: the `reuse_guard` anchor is not unique, so `mutants()` always STOPs
- **Where:** checker l.176: `("reuse_guard", "        if self.sock is not None:\n", "        if False:\n", reuse, "reuse:live resource preserved")`. l.181 then requires `source.count(before) == 1`.
- **Why it fails:** in JoinedTLS `76017776` that 8-space text occurs **twice**: at l.41 (`open`) and as a substring of l.125 (`close`, indented 12 spaces). Both lines match `grep -nF "        if self.sock is not None:"`.
- **Effect:** `mutants()` raises `WitnessFailure("mutant:unique anchor:reuse_guard")`, and `run()` exits 125 before writing any result. The check fails closed, so there's no false PASS, but it cannot PASS.
- **Also in v1:** the same anchor is in v1 l.165.
- **Proposed narrow correction (anchor only):**
  - `before = "    def open(self):\n        if self.sock is not None:\n"`
  - `after  = "    def open(self):\n        if False:\n"`
  
  `def open(self)` occurs once, so this pins the `open` guard. Nothing else changes.

### With that anchor fixed, the v2 reuse correction catches the intended guard
- With the guard removed, `open()` calls `check()` (budget 0 → 1), then the fake `ipaddress` (version 4), then the fake `socket.socket`. That is `refused_socket_factory` (factory 0 → 1), which raises `Refused`.
- The `self.sock=socket.socket(…)` assignment is **outside** `open`'s `try`, so `Refused` propagates directly, with no `close()` and no `errno`/`selectors` lookup. `transport.sock` stays the owned fake.
- So `refused(transport.open, "reuse:live refusal")` passes, and the next `require` fails on `budget_calls == 0 and socket_factory_calls == 0` with exactly `reuse:live resource preserved`.
- An unrelated exception (NameError and the like) maps to `mutant:unrelated exception`, and a wrong prefix maps to `mutant:unrelated failure`. Neither can PASS. **The v1 weakness is closed.**

### The other controls, traced
- **`foreign_check`:** id 202 versus 101, so it raises `Refused`; budget 0, not closed, closes 0. Its mutant (`if self.closed:`) returns `remaining()`, which fails `foreign-check:refusal`.
- **`foreign_close`:** `Refused`, with sock, closed, fileno and budget all preserved. Its mutant (`if False:`) closes, which fails `foreign-close:refusal`.
- **`owner_use_close`:**
  - check → 123.0;
  - send: `bytearray.extend(memoryview)` gives a count of 13;
  - receive(5) → `owner`, then receive(100) → `-response`;
  - a double close gives exactly 1 close and fileno -1;
  - check after close is refused with no budget call.
- **`reuse`:** live refusal and retired refusal, with the resource preserved.
- **`native_wiring`:** all 11 literal fragments are present in the candidate case text, with no stores to `.owner` or `.sock`.
- **Unique anchors:** the `foreign_check` (l.27) and `foreign_close` (l.121) anchors are unique.
- **Labels are honest:** the result says `native_proof: false`, and the limitations are stated truthfully.

### Checker qualifications
- **Fakes stand in for real ownership:** owner identity, the already-owned socket and the factory are named fakes. There are no real threads or TLS, and the case body, its failure paths and peer retirement are unexecuted.
- **Not yet a launch packet:** this is source only, with no EXPECTED, admission or launcher. Staging will need those.

**Preserved:** all predecessors, including v1 `ECE21AF0`, `scheduler-t08-ownership-source-dex-v1`, my Google roots and the baseline. No edits. Endpoint unbound; all holds stay.

Signed: Matt
