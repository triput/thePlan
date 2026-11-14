# Design recommendation v3 (UNAPPLIED)

Supersedes v2 tip `9522BC2F8166F508606E6ACB1912511DDDB39D472CBA2FE400419A7AC30163BB`. Official note: Python 3.11 `sys.exc_info`
returns the exception being handled on the **current stack**, which can be an
outer handler's exception even when the nested call succeeded
(https://docs.python.org/3.11/library/sys.html#sys.exc_info).

## Concrete answer

**No** on current source. Narrowest justified unapplied change remains three
files, with corrected primary capture and provenance rules.

## Primary capture (no ambient sys.exc_info)

In `CoveringHTTP.request`:

1. Initialize `invocation_primary = None` before try.
2. On oauth typed raises inside try, assign the raised object to
   `invocation_primary` before raise.
3. `except CoveringReauthorizationRequired as exc`: set
   `invocation_primary = exc` if not already set; re-raise.
4. `except BaseException as exc`: oauth+sent remaps to a new
   `CoveringRootOutcomeUnknown` assigned to `invocation_primary`; else
   `invocation_primary = exc`; re-raise.
5. `finally` uses **only** `invocation_primary` plus locally caught
   `response_close_exc` / `transport_close_exc`. Never `sys.exc_info()`.

### Why this defeats outer-handler contamination

Success path leaves `invocation_primary is None`. If `request()` was invoked
under an unrelated `except ValueError:` or `except CoveringRootOutcomeUnknown:`,
ambient stack state may still name that outer exception, but finally ignores
it. Cleanup failure constructs a **new** UNKNOWN with `.primary is None`
(success) or this invocation's primary — and does **not** attribute or mutate
the outer object.

### Provenance: append-only, no mutation

On cleanup uncertainty, always:

```text
unknown = CoveringRootOutcomeUnknown()  # NEW instance
unknown.primary = invocation_primary    # may be prior UNKNOWN from JoinedTLS/oauth
unknown.response_close = response_close_exc
unknown.transport_close = transport_close_exc
current = (invocation_primary, response_close_exc, transport_close_exc)
prior = copy of invocation_primary.retirement_occurrences
        or [invocation_primary.retirement_provenance] if present
unknown.prior_retirement_provenance = tuple(prior)
unknown.retirement_provenance = current
unknown.retirement_occurrences = tuple(prior) + (current,)
raise unknown
```

Earlier JoinedTLS/open retirement evidence remains on the **inner** UNKNOWN
object referenced by `.primary` and also listed in
`.prior_retirement_provenance` / `.retirement_occurrences`. The inner object
is never written.

## JoinedTLS.open (R08; still required)

HTTP-only remains insufficient (closed=True then sock.close raise => outer
transport.close no-op). open raises a **new** UNKNOWN with explicit attrs;
does not mutate `primary`.

## Importer

Deferred re-raise of CoveringRootOutcomeUnknown unchanged intent from v2.

## Alternatives rejected for primary capture

- `sys.exc_info()` in finally (Dex rejection; ambient contamination).
- Mutating an existing UNKNOWN found via isinstance on exc_info (mutates
  caller-owned objects under outer UNKNOWN handlers).
- Boolean cleanup_failed without retained exception objects.

## Prospective resulting hashes (unapplied; in-memory only)

See INPUT-PINS.json `prospective_resulting_sha256`.
