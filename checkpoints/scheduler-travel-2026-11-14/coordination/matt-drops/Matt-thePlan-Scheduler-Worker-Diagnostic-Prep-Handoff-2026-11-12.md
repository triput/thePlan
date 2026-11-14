# Matt → Dex: worker-exception observer diagnostic: native successor plus focused fake prep (HELD, frozen)

November 12, 2026. This responds to `Matt-thePlan-Scheduler-Worker-Diagnostic-Preparation-2026-11-12.md` (`F6F15372…27FD`).
- **Authority:** Trish's approved envelope `389A00DD…7E2D`: a same-contract fresh-successor role-4 correction.
- **Disclosure:** within the existing diagnostic approval, as you reconciled.

**Status:** PREPARED_NOT_EXECUTED. Both workspaces are frozen with no active writer. Every gate is false. There's no EXECUTE acknowledgement, and the endpoint is unbound. Nothing was imported, parsed, compiled or run.

## 1. Native successor: `outputs/scheduler-native-provider-worker-diagnostic-prep-matt-v1`
- **Fresh copy:** the 274 manifest inputs of `scheduler-native-provider-diagnostic-launch-dex-v1` (`1C85559E…851A`), verified 274/274 before and after. Re-checked again at handback.
  - No dynamic evidence was copied.
  - The nested name is kept, so the unchanged operator label resolves to the sibling `…\scheduler-native-provider-worker-diagnostic-prep-matt-v1\scheduler-native-provider-diagnostic-launch-v1.evidence`, which is **absent**.
- **Role 4** `payload/fixture/np_runner_entry.py`: `40A1BA8E…F73F` → **`341074AEF88A9E438C0F488E6231572103E694FB5EB81D6F3AC6BD30517CD645`**.
  - The exact diff is `Matt-thePlan-Scheduler-Worker-Observer-Runner-2026-11-12.diff` (`2023F97B…2468`): 5 hunks, **+41/−0**.
  - `stop_payload` and `__main__` are unchanged.
  - The changes:
    1. New `_install_worker_exception_observer(captured)`. It swaps `app.services.covering_http_dispatch.run_bounded_domain` (the module global that `_worker` looks up) for a pure delegate:
       - identical arguments and result;
       - on `BaseException`, it keeps **only the first** object and does a **bare `raise`**;
       - it never formats anything;
       - it returns an exact `restore()`.
    2. Locals `worker_exceptions` and `restore_worker_observer` (None).
    3. The install is the first statement in the POST `try`. The restore is first and unconditional in its `finally`, before `CoveringHTTP.__init__ = real_init`.
    4. The non-200 path (now line 978) raises the same `SuiteStop(f"covering-refresh status:…")`, chained `from worker_exceptions[0]` when present. Otherwise it's the original unchained raise.
- **Data:**
  - `runner-config.json` → `9411AC38…E929` (`launch_ready` false; batch `["NP-V-MS-NONEXPIRED"]`; `expected_unknown_cases` `[]`).
  - Payload `SHA256SUMS.txt` `3B25ABB6…` → **`250CFD3C39944C2A238371B957267719900B861368CF8C3118DCB274052D2A70`** (257 pins, 2 changed).
  - `host/launch-config.json` → **`EBE26FB58EE7ADE11AD90E16B7FE8E1C4A8D96BEDCF233701090F0719C0FBE1C`**:
    - `launch_ready` and `candidate_launch_ready_staged` false;
    - paths moved;
    - `manifest_sha256` `250CFD3C…`;
    - note.
  - `host/docker-ops-config.json` → **`CB2F70F5D13F781EBC36CF75C0F4A371DB2528EF5D07C3B67CFF586757BDFDF7`** (only the 7 path values).
- **Immutable:** the operator `5A8A04B6…D7D6`, `docker_transport.py` `7F7EA820…`, all 234 API files and the other fixture roles.
- **Diff against the source tree:** exactly 6 files. Those are the runner, `runner-config`, `SHA256SUMS`, the two host configs and the nested `Input-Manifest`.
- **Static path agreement:** all 9 absolute config paths are under the new nested root or its sibling `.evidence`.
- **Current docs** (historical copied docs are listed as such in the README):
  - `WORKER-DIAG-PREP-README.md` `1122B401…3BA7`;
  - `Worker-Diag-Prep-Freeze.json` `F0D7D156…7726`;
  - `Future-Native-Command-HELD.ps1.txt` `10D30852…B3CF`. That's the absolute operator, `-ExpectedConfigSHA256 EBE26FB5…`, `-ExpectedDockerConfigSHA256 CB2F70F5…`, the new `-DockerConfigPath`, and no `-ReceiptPath`. The operator STOPs on the false gates.
- **Manifests:** nested `Input-Manifest.sha256` = **`3FCA24140806E42A69959C9E72EE12A2612D50E54538780CDDF35E78BFB3D1A3`** (269). Parent = **`9DCAA6FF06FF890E53AB867ECFDFA5617115A0B684762304E49AF6BE07F00A68`** (278). Both verify 0 mismatches.

## 2. Focused fake: `outputs/scheduler-native-worker-diagnostic-fake-prep-matt-v1`
- **Roles:**
  - reused byte-identical: AE84 wrapper, 7DCA outer, D22C launcher;
  - checker **`38BE55DF092E9382FC13655BB6A0226026668C822D5BAC3A90B402EB2D59C4E4`**;
  - EXPECTED **`AEC7B0DB1909C1C269840EA44F72336A7EDA1DE13B5EEF567218BBD498B95FA9`**;
  - OUTER **`D0A24437F521E37940911B75E1AC2CCC20E73F2433717E15AAA15C7FAA2B6452`**;
  - VERIFICATION **`C185A377D3005152EACEE2B06181E85D1F5CE6CEEA207E0752B1F26D6B3E8F75`** (12 packet pins plus the Python311 interpreter `5F7B89A6…`; both `launch_authorized=false`).
  - Packet manifest **`A2EEE664D39736C577EBDB48B52633E6D4AA1E54736CBFB4A546EA39E21A7985`** (15).
- **Subjects:**
  - candidate `341074AE`;
  - source `40A1BA8E`;
  - host `7F7EA820`;
  - production `covering_http_dispatch.py` `5160780F` and `covering_role_connector.py` `C5BA15CD` (CRLF; CRLF-safe predicate);
  - the diff.
- **Finite inventory:** 10 controls and **47 nested predicates**. The checker also enforces the nested lists against EXPECTED.
  1. **SUBJECT-PINS**
  2. **DIFF-REDERIVATION:** literal; 5 hunks; +41/−0.
  3. **PRESERVED-OUTSIDE-CHANGE:**
     - all other top-level nodes are AST-identical, and the helper placement is checked;
     - `stop_payload` and `__main__` are identical;
     - the change is purely additive.
  4. **PRODUCTION-BOUNDARY-STRUCTURE:**
     - `_worker` uses a global lookup, and there's one module import;
     - the connector `from None` conversions are at 74/106/150/204;
     - unknown maps to `ApiError 503 from None`;
     - the helper swaps only `dispatch_module.run_bounded_domain`.
  5. **OBSERVER-SUCCESS-IDENTITY:** 7 cases, using the actual extracted helper under an exact `sys.modules` sandbox.
  6. **OBSERVER-EXCEPTION-IDENTITY:** 8 cases, including:
     - a connector-shaped `from None` fault keeps the same object;
     - the chain attributes are unchanged;
     - a BaseException is re-raised;
     - only one object is kept;
     - **no `__str__`/`__repr__` calls**.
  7. **RESTORE-WIRING:** 6 cases.
  8. **CHAINING-WIRING:** 5 cases on the actual extracted non-200 block, including fallback-raise identity against the executed source.
  9. **PRODUCER-HOST-END-TO-END:** 5 cases.
     - Real exception objects run through the actual observer, the actual block and the actual `stop_payload`, giving `SuiteStop → CoveringRootOutcomeUnknown → JoinedTLSVerifyFault`. The immutable host validator accepts the result.
     - Owned `api/app/**` frames are retained exactly.
     - Unowned frames are dropped; a deeper chain is capped; the privacy envelope holds.
  10. **ACTUAL-SOURCE-MUTANTS:** 5 mutants (replacement re-raise, swallowed, no restore, unbounded capture, chaining removed), each detected only by its targeted oracle.
- **Held fake command:** `Future-Command-HELD.ps1.txt` (`17987B79…EC00`), `-AdmissionSHA256 C185A377…`. The wrapper refuses while the flags are false.
- **Launch-Decision.md:** `5D1586ED…8792`.

## 3. Truthful limits
- **Not observed:** a fault in `CoveringRoleConnector(...)` construction, or anything else before `run_bounded_domain`. The STOP then stays unchained, exactly as in the executed run.
- **Out of scope:** an `ApiError` raised in `dispatch_covering_http` itself after the worker. Its body is the `CoveringDeadlineExceeded` and unknown mapping, so the captured worker exception still identifies the cause.
- **Thread hand-off:** the worker runs in `anyio.to_thread` with `abandon_on_cancel=False`, and the restore runs after `client.post` returns. That's structural only, not proved natively.
- **Producer limits:** at most 3 exceptions and 8 newest owned frames. Library frames are dropped, and exotic class names are sanitized.
- **The fake proves extracted-block behavior only.** It says nothing about real classes, paths or the native host.

## 4. Correction to my trace findings (`CD7B1963…`)
I cited the connector's `from None` at 150 and 204. There are **four** (74, 106, 150, 204). Each suppresses context the same way, so the rationale holds.

## 5. Preservation checks (read-only, at handback)
- the dex-v1 source is 274/274 OK;
- the native host receipt is still `27341732…0382`;
- the MS-refresh prep v1 and fake v2 manifests have 0 mismatches;
- the new native successor is 0 mismatches;
- no `.evidence` exists under the successor.

MS REFRESH stays held.

## Scope
Offline authoring, hashing, `diff` and `cmp` only. No imports, parsing, compilation, tests, Docker, database, PKI, network, Git or ThePlan repo edits.

Signed: Matt
