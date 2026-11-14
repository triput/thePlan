# Native NP-T03 B2a preparation v1 (HELD)

Matt, November 13, 2026. This is for Dex `Matt-thePlan-Scheduler-T03-B2a-Preparation-2026-11-13.md` (`21BBE5B7…48BD`), under Trish-approved decision D1 `D46E6CF8…FFE9` (`call_9fe24ed9…` item 2) and lane `389A00DD…7E2D`.

**Status:** PREPARED_NOT_EXECUTED.
- Nothing was imported, parsed, compiled, tested or run.
- No PKI, socket, Docker or DB work.
- **Current documents:** this README, `T03-B2a-Prep-Freeze.json` and `T03-B2a-Native-Command-HELD.ps1.txt`. Every other copied document, command and `Source-*.sha256` is history.
- **Source:** the passed NONEXPIRED retirement v2 (`C62FDA91…`, 301 inputs) was copied manifest-listed inputs only. Its `.evidence` was not copied, and its bytes and evidence are preserved.

## Changes (roles 4, 5 and 8 only, plus finite data)
- **Role 8, transcript:** `t03_valid_fixed_length_get_script()`: GET `/calendar/v3/calendars/primary/events`, then 200 `{}` with Content-Length `PLACEHOLDER` (= 2), then `orderly_close_notify`. The three cases share it.
- **Role 4, runner (additive):**
  - **`_retire_negative_peer_then_observe`:** the D1 barrier, for the negative cases only;
  - **`_t03_observe`:** one peer, one request through the production `CoveringHTTP` default JoinedTLS, one retirement, then classification;
  - **constants;** three bodies through `_run_np_t03_case`; `IMPLEMENTED_CASE_IDS`; the mapper.
  - The positive `_retire_selected_peer_then_observe` and every existing body are byte-identical.
- **Role 5, suite:** three `CASE_IMPLEMENTATION_NOTES` entries only. The declarations are unchanged.
- **Data:**
  - runner-config: gates false, batch of the three cases;
  - launch-config: gates false, batch `np-t03-b2a`, the cases, the implemented list, the payload pin, own-root paths, and a truthful "as authored" note;
  - docker-ops: 7-path root rename only.
- **Unchanged:** peer `17EA148E`, routes `9CBDE09C`, the PKI recipe, all 234 application files, the host/DB/TLS/admission helpers, the operator, the sanitizer and the integrated runner.

## Gates
- Host, candidate staging and runner `launch_ready` are all false, and human authority is false.
- The evidence root is absent. The default receipt applies, with no `-ReceiptPath`.
