# Fake-only behavioral harness — REVISE2-corrected7 review documentation

**Packet:** `fake-only-behavioral-harness/` under REVISE2-corrected7 handback
**Class:** FAKE-BEHAVIORAL
**Status:** AUTHORED_NOT_EXECUTED (preparation)

## Provenance

Corrected helpers are **AST-extracted** from REVISE2-corrected7 `workspace-payload/fixture/*` bytes listed in `INPUT-MANIFEST.json` (workspace fixture bytes unchanged from tipped corrected4/5/6). Required AST names fail closed if missing. `Lock` and deps are supplied before `SharedTransportScript` compiles. Each extraction registers a real `ModuleType` under the synthetic name in `sys.modules` and execs into that exact `module.__dict__` (dataclass `_is_type` resolves via `sys.modules.get(cls.__module__).__dict__`). Patches target that namespace. Exact source path / name / sha256 provenance is recorded in the result payload at execution time.

## Corrected6 closures retained (no regression)

- Choice B: disclose Windows ProactorEventLoop internal wakeup sockets (loopback-only; concurrent bound 2; N11 sequential 3 `asyncio.run` cycles); not literally no sockets (p1794366344 / consolidated p1794366450).
- Collection interrupt/error (incl. `proc_wait_error` with `capture_stop=None`) requires explicit non-None child-exit confirmation before result validation or `child_exited_normally` (p1794366621).
- Retirement total **45s** (30+5+2×5); distinct from outer-admission deadline (p1794366987).
- Corrected5 closures retained (reader `is_alive`/UNKNOWN; overflow interrupt; kill/wait secondary; N14 `take.__globals__`).
- Corrected4 closures retained (ModuleType registration; admit_outer noncircular pins; capture-during-collection; ordered controls; cancel-before-selection).

## Dex tip-message IDs reconciled (exact; corrected7)

| ID | TS | Status |
|---|---|---|
| p1794366621 | 1794366621.337969 | Closed corrected6 retained — exit confirmation before result validation |
| p1794366344 | 1794366344.728349 | Closed corrected6 Choice B retained — Windows asyncio internal socket disclosure |
| p1794366450 | 1794366450.439149 | Closed corrected6 retained — consolidated REVISE of 6074/6127/6344 |
| p1794366987 | 1794366987.193389 | Closed corrected6 arithmetic retained — retirement total **45s** |
| p1794367441 | 1794367441 | Closed corrected7 — primary collection/wait error or unexpected interrupt blocks result admission/PASS even after confirmed exit 0; pe retained; no retry |
| p1794367500 | 1794367500 | Closed corrected7 — retain `child_pid` at Popen success plus executable/argv/start timestamp for read-only custody; no enumeration/retry/cleanup authority |

## Corrected7 closures (this packet)

### 1. Primary collection failure blocks PASS (p1794367441)

With `proc_wait_error` / `interrupt_reason` set, `capture_stop=None`, confirmed child exit 0, and a valid-looking result file, corrected6 final gating could still validate the file and choose PASS because it only checked timeout/capture/reader/termination flags. Retaining `primary_error` on a PASS receipt is **not** stop-on-failure.

**FIX:** any `primary_error` or `interrupt_reason` prevents result admission and PASS even when child exit later proves 0; pe retained as primary; status STOP (125); no retry. Exit-confirm-before-result-validation from corrected6 remains.

### 2. child_pid custody (p1794367500)

As soon as `Popen` succeeds, receipt pins `proc.pid` as `child_pid` plus already-pinned executable/argv and creation/start timestamp (`child_executable`, `child_argv`, `child_start_timestamp`, plus `child_custody` object). If termination cannot be confirmed, Dex has exact local child identity for **read-only** reconciliation. No process enumeration, retry, fallback, or new cleanup authority — receipt preparation only.

### 3. Corrected6 retained confirmations

Choice B socket disclosure; exit-confirm before result validation; 45s retirement arithmetic; corrected5 reader/N14 closures — all retained unchanged in behavior.

## Exact enforcing invocation

See `../PROPOSED-VERIFICATION-COMMANDS.md`. Exact entry: `admit_outer.py` under `-I -S -B` after operator verifies `OUTER-ADMISSION.json` hash.

## Pin enforcement layers

| Layer | Pin | Enforcing invocation |
|---|---|---|
| 1 | `OUTER-ADMISSION.json` bytes | Operator / PROPOSED-VERIFICATION-COMMANDS published hash |
| 2 | interpreter + admit_outer + launcher + check + EXPECTED + INPUT-MANIFEST + PACKET-SHA256SUMS | `admit_outer.py` pre-spawn |
| 3 | interpreter (hardcoded); check/EXPECTED/INPUT-MANIFEST vs PACKET-SHA256SUMS (**not** launcher self) | `invoke_fake_behavioral.py` pre-child |
| 4 | fixture source SHAs; exact ordered inventory | `check_i01_i02_fake_behavioral.py` |

## Limits

Fake PASS cannot waive native SQL contention, real TLS terminal, or integrated Docker ingress timing.
