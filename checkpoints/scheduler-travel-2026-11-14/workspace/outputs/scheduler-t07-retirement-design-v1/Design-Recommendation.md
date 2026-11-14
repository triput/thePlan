# Design recommendation — narrowest justified change (UNAPPLIED)

## Concrete answer

**No.** The current covering provider path cannot truthfully:

1. stop with UNKNOWN when retirement is uncertain,
2. preserve the primary failure, and
3. attempt independently owned retirement operations without retries.

Static reasons (not executed failures):

- `CoveringHTTP.request` `finally` sequences `response.close()` then
  `transport.close()` without independence or UNKNOWN classification
  (`covering_http_transport.py:125-128`).
- Cleanup exceptions replace pending primary/UNKNOWN/reauth/return.
- `import_covering_subscription_cache`’s `_pull_provider` `except Exception`
  returns `OUTCOME_FAILED` (`covering_refresh_import.py:976-994`),
  swallowing `CoveringRootOutcomeUnknown`.
- Identity prepare maps `OSError` to ordinary preflight
  (`covering_refresh_import.py:442-458`).
- Domain loop continues after ordinary failed/preflight rows
  (`covering_domain_dispatch.py:233-257`).

## Chosen narrowest coherent design

**Keep existing `CoveringRootOutcomeUnknown`.** It already is the public stop
signal mapped by `covering_http_dispatch.py:71-73` and stamped with
`completed_results` by `covering_domain_dispatch.py:265-267`. A new common
exception type is **not** required for correctness if dependency placement
is handled carefully.

### Affected symbols / files

| File | Symbols | Change |
| --- | --- | --- |
| `app/services/covering_http_transport.py` | `CoveringHTTP.request` | Independently attempt response-close and transport-close; on any cleanup failure raise `CoveringRootOutcomeUnknown` (do **not** use `from None` in this finally path so pending primary remains in `__context__`); never skip transport-close because response-close failed. |
| `app/services/covering_joined_https.py` | `JoinedTLS.open` | On primary failure, attempt `close()`; if close raises, raise `CoveringRootOutcomeUnknown` with primary as `__cause__` and cleanup retained in `__context__` (or equivalent explicit attributes) instead of letting cleanup replace primary silently. **No** sock.close retry loop; leave `JoinedTLS.close` idempotence unchanged (R09). |
| `app/services/covering_refresh_import.py` | `import_covering_subscription_cache` pull `except` | Deferred local import of `CoveringRootOutcomeUnknown`; re-raise before mapping to `OUTCOME_FAILED`. Do **not** add a top-level reverse import. |

Optional non-chosen widenings explicitly rejected for this narrow proposal:

- Changing `JoinedTLS.close` flag ordering or adding automatic sock.close retry.
- Loosening importer `except Exception` to a tiny allowlist (larger behavior change surface).
- Teaching identity prepare’s `OSError` catch to special-case “cleanup” OSErrors (fragile); once HTTP raises UNKNOWN instead of raw OSError on cleanup uncertainty, that catch naturally stops applying to retirement uncertainty.
- Altering transaction guards, retry policy, public HTTP contracts, deadlines, or resource authority for fixture convenience.
- Moving `CoveringRootOutcomeUnknown` in this wave (see alternatives).

### Dependency placement

```
covering_refresh_import  (defines ImportCoveringCacheResult)
        ^
        | top-level import
covering_target_transaction  (defines CoveringRootOutcomeUnknown)
        ^
        | top-level import (already present)
covering_http_transport / covering_role_connector / domain_* 
```

Importer needs the exception type at **runtime in an except handler only**.
Deferred:

```python
except Exception as exc:
    from app.services.covering_target_transaction import CoveringRootOutcomeUnknown
    if isinstance(exc, CoveringRootOutcomeUnknown):
        raise
    ...
```

runs after both modules finished initializing → **no circular init**.

`JoinedTLS` today does not import `CoveringRootOutcomeUnknown`. Adding
`from app.services.covering_target_transaction import CoveringRootOutcomeUnknown`
in `covering_joined_https.py` is acyclic (`joined_https` ← `http_transport` ←
`target_transaction` ← `refresh_import`; `joined_https` does not sit under
`refresh_import`). Acceptable. If Trish prefers joined_https remain free of
transaction types, Alternative B (neutral base in policy) applies.

## Alternatives compared

### A — Chosen: finally dual-attempt + UNKNOWN; importer deferred re-raise; open preserves primary on close failure

- **Pros:** Smallest set that makes uncertain retirement stop callers;
  reuses existing public UNKNOWN; fixes both-attempts oracle (R02/R06);
  preserves primary via exception context/cause; no top-level import cycle;
  no retry contract.
- **Cons:** Two (optionally three) production files; JoinedTLS gains a
  dependency on the UNKNOWN type; witnesses must assert `__context__` /
  `__cause__` carefully.

### B — Dependency-neutral base type in `covering_transport_policy.py`

Introduce e.g. `CoveringOutcomeUncertainty(Exception)`; make
`CoveringRootOutcomeUnknown` subclass it (or alias); HTTP/JoinedTLS raise
base or subclass; importer re-raises base via top-level import from policy
(already a leaf-ish dependency).

- **Pros:** Clean top-level typing; JoinedTLS need not import transaction
  module; clearer layering.
- **Cons:** Extra type + inheritance edit in `covering_target_transaction`;
  broader review surface; not required to answer the concrete question.

### C — HTTP finally only (no importer change)

- **Pros:** One file.
- **Cons:** **Fails the question.** `CoveringRootOutcomeUnknown` remains an
  `Exception` subclass swallowed into `OUTCOME_FAILED` on the event path;
  later admission continues.

### D — Importer re-raise only (no finally change)

- **Pros:** Unblocks already-raised UNKNOWN (oauth except path).
- **Cons:** Cleanup still emits raw exceptions; response-close still skips
  transport-close; success+cleanup still not classified as UNKNOWN at
  source; identity `OSError` preflight path remains; R02/R06/R03 incomplete.

### E — Relocate `CoveringRootOutcomeUnknown` into `covering_refresh_import` or a new module; reverse call sites

- **Pros:** Top-level importer ownership of the type.
- **Cons:** Touches many imports (`http_transport`, connector, domain,
  native ORM, tests); far wider than T07 retirement classification; not
  narrowest.

### F — No source change; fixture-only observation

- **Pros:** Zero production risk.
- **Cons:** Cannot make the path “truthfully stop”; only documents the
  gap. Valid as interim evidence plan, but does **not** satisfy a
  positive answer to the assignment question. This handback therefore
  **justifies** an unapplied diff rather than a no-change claim.

## Consequences of the chosen design for callers

| Path | After proposed change (design intent) |
| --- | --- |
| Event pull cleanup uncertain | HTTP raises UNKNOWN → importer re-raises → target run aborts → domain stops → no later target/assessment admission. |
| Event pull already-UNKNOWN (oauth-like) | Same re-raise path; no longer converted to `OUTCOME_FAILED`. |
| Identity cleanup uncertain | HTTP raises UNKNOWN (not raw OSError) → prepare does not map to EVIDENCE_UNAVAILABLE → UNKNOWN escapes import → stop. |
| Token invalid_grant + cleanup uncertain | Finally raises UNKNOWN with reauth in context → not TokenRejected → stop. |
| DB rollback on prior failed rows | Unchanged; still not provider retirement proof. |
| JoinedTLS.close idempotence | Unchanged; no sock retry. |

## What this design deliberately does not do

- Does not claim executed proof or authorize D2 verification.
- Does not alter public UNKNOWN HTTP code/text.
- Does not grant fixtures authority to mutate transaction/retry/deadline
  policy.
- Does not treat fake DB rollback acknowledgments as TLS/socket retirement.
\n
