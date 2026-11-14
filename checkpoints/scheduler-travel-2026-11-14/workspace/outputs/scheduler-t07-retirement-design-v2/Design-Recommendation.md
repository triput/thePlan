# Design recommendation v2 — narrowest justified change (UNAPPLIED)

Supersedes v1 tip `ABA0923505155EC0D7555B13A61CB6F7CFFE662051F0E2B5C439BEAC48800F2A` (immutable). Documents-only.

## Concrete answer

**No.** The current covering provider path cannot truthfully stop with UNKNOWN
when retirement is uncertain, preserve the primary failure, and attempt
independently owned retirement operations without retries.

## Chosen narrowest coherent design (three files; no two-file ceiling)

Keep existing `CoveringRootOutcomeUnknown`. Add optional sanitizable
provenance attributes on instances raised from retirement paths:

- `.primary` — exchange/open primary exception object or None
- `.response_close` — exception from `response.close()` or None
- `.transport_close` — exception from `transport.close()` / `JoinedTLS.close` or None
- `.retirement_provenance` — frozen tuple `(primary, response_close, transport_close)`

Do **not** claim `__context__` automatically retains cleanup exceptions caught
in `except` blocks (exiting those blocks clears the active exception before
UNKNOWN is raised).

### Affected symbols / files

| File | Symbols | Change |
| --- | --- | --- |
| `covering_http_transport.py` | `CoveringHTTP.request` | Dual independent close attempts; retain `response_close_exc` / `transport_close_exc`; raise or enrich UNKNOWN with explicit provenance attrs; import `sys` for `sys.exc_info()` primary capture. |
| `covering_joined_https.py` | `JoinedTLS.open` | **Required for R08.** On primary failure, attempt `close()` once; if close raises, raise UNKNOWN with `.primary` and `.transport_close` set (`.response_close=None`). No sock.close retry. |
| `covering_refresh_import.py` | pull `except` | Deferred local import; re-raise `CoveringRootOutcomeUnknown` before `OUTCOME_FAILED` mapping. |

## Why HTTP-only is insufficient for R08 (Dex p1794424179)

Current `JoinedTLS.close` (`covering_joined_https.py:107-111`) sets
`closed=True` **before** `sock.close()`. Sequence under R08:

1. Connect/TLS primary fails inside `JoinedTLS.open` try.
2. `open`'s except calls `self.close()`.
3. `sock.close()` raises **after** `closed=True`.
4. Today that cleanup exception **replaces** the open primary and escapes
   `open()`.
5. `CoveringHTTP.finally` still calls `transport.close()`, but because
   `closed` is already True the method returns without touching the socket
   and **does not raise**.
6. Therefore an HTTP finally that only classifies exceptions **newly raised
   by the outer** `transport.close()` never sees the earlier sock.close
   failure. Event/identity callers may still observe a raw `OSError` (or
   whatever escaped from step 4) and downgrade it (importer
   `OUTCOME_FAILED`; identity prepare `OSError` to
   `PREFLIGHT_EVIDENCE_UNAVAILABLE`) despite uncertain retirement.

**Conclusion:** classifying only outer-close raises cannot recognize R08
uncertainty or preserve the open primary. The JoinedTLS.open change is
required. This handback does **not** force a two-file ceiling.

Candidate behavior with the JoinedTLS.open change:

- Close failure inside open raises `CoveringRootOutcomeUnknown` with
  `.primary` = open primary and `.transport_close` = cleanup exception.
- Outer `CoveringHTTP.finally` may still call `transport.close()` (no-op).
  If that outer call does not raise and no response-close failure exists,
  finally does not need to invent a second UNKNOWN; the UNKNOWN from open
  already carries provenance and propagates through the request except path
  (non-oauth re-raise) unless an oauth remapping applies.
- Importer deferred re-raise prevents swallow into `OUTCOME_FAILED`.

## Dual cleanup provenance (Dex p1794424460)

v1's `cleanup_failed=True` boolean discarded the actual close exceptions.
Caught cleanup errors are **not** automatically available on `__context__`
after the except block exits.

v2 finally shape:

1. `response_close_exc = None` / `transport_close_exc = None`
2. Attempt each close in its own try/except; store the exception object
3. If either is not None: read pending primary via `sys.exc_info()[1]`
4. Attach explicit attributes on UNKNOWN (or enrich an already-pending
   UNKNOWN) before raise

Witnesses assert identity/type (and sanitized message class, not raw
secrets) of `.primary`, `.response_close`, and `.transport_close`
independently — including **both** cleanup failures for R06.

Same attribute inventory on JoinedTLS.open UNKNOWN (with
`.response_close is None`).

## Alternatives

### A — Chosen: three-file + explicit provenance attrs

Pros: closes R08; closes dual-cleanup observation; reuses UNKNOWN; no
sock retry; deferred importer import avoids cycle.
Cons: JoinedTLS imports transaction exception type; optional attrs are
convention until a typed helper is added.

### B — Neutral base type in covering_transport_policy

Pros: JoinedTLS avoids importing target_transaction.
Cons: wider type relocation; not required to close R08/provenance.

### C — HTTP+importer only (reject for R08)

Fails R08 as shown above.

### D — Relocate exception module / large refactor

Not narrowest.

## Deliberately not done

No apply, no execution, no sock.close retry, no public UNKNOWN contract
string change, no D2 packet mutation, no reliance on `__context__` for
caught cleanup provenance.

### Enrichment merge rule

If finally sees an already-raised `CoveringRootOutcomeUnknown` (for example from `JoinedTLS.open`) and only some cleanup locals are non-None, assign only those non-None attrs so a closed=True outer no-op does not wipe JoinedTLS `.transport_close`.
