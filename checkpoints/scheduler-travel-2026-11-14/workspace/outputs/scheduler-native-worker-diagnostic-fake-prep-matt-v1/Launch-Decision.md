# Worker-exception observer diagnostic: focused fake verification preparation (HELD)

Matt, November 12, 2026. This is for assignment `Matt-thePlan-Scheduler-Worker-Diagnostic-Preparation-2026-11-12.md` (`F6F15372…27FD`). It is the companion to the frozen native successor `outputs/scheduler-native-provider-worker-diagnostic-prep-matt-v1` (runner `341074AE…`, launch-config `EBE26FB5…`).

**No execution is authorized.** Nothing here has been imported, parsed, compiled or run. Both admissions have `launch_authorized=false`. No PASS is claimed.

## Roles
- **Reused byte-identical:**
  - wrapper `Invoke-Fake.ps1` `AE84E632…FEB7`;
  - outer `verify_admission.py` `7DCA32E2…18FB`;
  - launcher `launch_check.py` `D22C37E3…BD07`.
- **New:**
  - checker `check_native_provider.py` **`38BE55DF092E9382FC13655BB6A0226026668C822D5BAC3A90B402EB2D59C4E4`**;
  - EXPECTED **`AEC7B0DB…5FA9`**;
  - OUTER **`D0A24437…6452`**;
  - VERIFICATION **`C185A377D3005152EACEE2B06181E85D1F5CE6CEEA207E0752B1F26D6B3E8F75`**.
  - VERIFICATION holds 12 packet pins and 1 runtime pin, all re-verified against disk.
- **Subjects** (raw-pinned copies):
  - candidate runner `341074AE…`;
  - source runner `40A1BA8E…` (the executed dex-v1 role 4);
  - host `docker_transport.py` `7F7EA820…`;
  - production `covering_http_dispatch.py` `5160780F…` and `covering_role_connector.py` `C5BA15CD…` (CRLF);
  - `Worker-Observer.diff` `2023F97B…` (5 hunks, +41/−0).

## Controls (10 top-level, 47 nested predicates, in order)
1. **SUBJECT-PINS** (raw_pin): a CRLF-safe predicate that rejects bare CR. Raw bytes are never normalized.
2. **DIFF-REDERIVATION** (literal_text): source + diff = candidate exactly; 5 hunks; one file.
3. **PRESERVED-OUTSIDE-CHANGE:**
   - every top-level node except the case function and the new helper is AST-identical;
   - the helper sits immediately before `_install_token_terminal_observer`;
   - `stop_payload` text and the `__main__` guard are identical;
   - the diff is +41/−0.
4. **PRODUCTION-BOUNDARY-STRUCTURE** (structural):
   - `_worker` returns `run_bounded_domain(...)` by module-global name, with no local binding;
   - there is one module-level import from `covering_domain_dispatch`;
   - the connector `CoveringRootOutcomeUnknown() from None` conversions are exactly at lines 74, 106, 150 and 204;
   - the dispatcher maps unknown to `ApiError(503…) from None`;
   - the helper swaps only `dispatch_module.run_bounded_domain`.
5. **OBSERVER-SUCCESS-IDENTITY** (the ACTUAL extracted helper, with fake `app`, `app.services` and dispatch modules in an exact `sys.modules` sandbox):
   - install;
   - result identity;
   - positional and keyword argument identity;
   - nothing captured;
   - restore identity, idempotent;
   - sandbox restored.
6. **OBSERVER-EXCEPTION-IDENTITY.** A connector-shaped fake produces a fault, swallowed teardown noise, then `CoveringRootOutcomeUnknown() from None`.
   - The same object is re-raised and captured.
   - `__cause__`, `__context__` and `__suppress_context__` are unchanged.
   - A non-`Exception` `BaseException` is re-raised as the same object.
   - At most one object is captured.
   - Restore identity holds.
   - **Zero `__str__`/`__repr__` calls.**
   - The sandbox is restored.
7. **RESTORE-WIRING:**
   - both locals are initialized before the outer try;
   - the install is `body[0]` of the POST try;
   - the exact restore `if` is `finalbody[0]`, ahead of `CoveringHTTP.__init__ = real_init`;
   - exactly one install call exists;
   - the extracted restore block calls once and clears;
   - the non-200 block comes after the restore.
8. **CHAINING-WIRING** (the ACTUAL extracted non-200 block):
   - the cause is the captured object, and the first one when there are several;
   - with nothing captured, the fallback is unchained (`__cause__` and `__context__` None);
   - status 200 does not raise;
   - the message is unchanged;
   - the fallback raise is AST-identical to the executed source raise.
9. **PRODUCER-HOST-END-TO-END:**
   - **real exception objects** pass through the actual observer and the actual block, then the actual `stop_payload`. That gives `SuiteStop → CoveringRootOutcomeUnknown → JoinedTLSVerifyFault`, with non-owned checker frames dropped, and the immutable host validator accepts it;
   - fake owned `api/app/**` and `fixture/` frames through the suppressed context are retained exactly, with `truncated=false`;
   - unowned stdlib frames are dropped;
   - a fourth exception is capped;
   - the privacy envelope excludes the secret marker, messages, status, `covering-refresh` and locals, and stays at most 4096 bytes.
10. **ACTUAL-SOURCE-MUTANTS.** Five mutants, each detected only by its targeted oracle:
    - replacement re-raise;
    - swallowed;
    - no restore;
    - unbounded capture (`if not captured:` → `if True:`);
    - chaining removed.

## Not proved
- that the native worker fails inside `run_bounded_domain`. A fault in `CoveringRoleConnector(...)` construction or before it is not observed, and the STOP then stays unchained (the same as the executed run);
- the real production exception classes, frames and paths in the container;
- the 503/401/422/504 discrimination itself;
- thread hand-off under `anyio.to_thread` (structurally, the restore runs after `client.post` returns);
- the native host path.

## Correction to my trace findings
`Matt-thePlan-Scheduler-Native-HTTP-Status-Trace-Findings-2026-11-12.md` cited `from None` at connector lines 150 and 204 only. There are **four** (74, 106, 150, 204). All of them suppress context the same way, so the observer rationale is unchanged and slightly stronger.

## Limits (inherited launcher)
- **Timing:** 120 s, plus at most one 5 s kill/wait, plus two 5 s reader joins: **135 s nominal**, with no separate outer timeout.
- **Capture:** 64 KiB per stream; 256 KiB for the result.
- **Success** requires exit 0, no output, clean EOF readers and the exact ordered 10-control inventory. The checker also enforces the nested inventory against EXPECTED.
- **Exclusive evidence** goes under `packet/verify/`; a failure stops and preserves, with no retry.
