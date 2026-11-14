# Caller trace — event, identity, OAuth → public outcome → later admission

Documents-only. Sources re-pinned under immutable API root
`.../scheduler-d2-fake-v1/packet/payload/workspace/apps/api`. Line citations
are that tree. Not executed.

## Shared transport spine

1. `covering_domain_adapters.make_domain_ports` wraps provider work in
   `covering_provider_transport(transport)` for token
   (`covering_domain_adapters.py:46-47`) and apply
   (`covering_domain_adapters.py:70-74`).
2. `calendar_client` (`covering_provider_context.py:48-52`) returns
   `_CoveringClient` when the context var is set; otherwise ordinary
   `httpx.Client`.
3. `_CoveringClient._request` selects exactly one purpose from
   `transport.routes` and calls `CoveringHTTP.request`
   (`covering_provider_context.py:29-45`).
4. `CoveringHTTP.request` constructs `JoinedTLS` before `try`
   (`covering_http_transport.py:86-89`), runs open/send/begin/body/classify
   inside `try`, maps OAuth uncertainty in `except`
   (`covering_http_transport.py:118-124`), then `finally` closes response
   then transport (`covering_http_transport.py:125-128`).

### Where cleanup can replace an outcome

- Pending success return is cancelled if `finally` raises
  (`covering_http_transport.py:116-128`).
- Pending `CoveringReauthorizationRequired` or `CoveringRootOutcomeUnknown`
  from the exchange/`except` block is replaced if `response.close()` or
  `transport.close()` raises (`covering_http_transport.py:107-128`).
- OAuth mapping does **not** wrap `finally`; a close exception bypasses
  local UNKNOWN remapping (`covering_http_transport.py:118-128`).
- Inside `JoinedTLS.open`, primary failure calls `self.close()`; a close
  exception replaces the open primary (`covering_joined_https.py:72-74`).
  The outer `CoveringHTTP` `finally` still calls `transport.close()`
  (`covering_http_transport.py:128`), but `JoinedTLS.close` sets
  `closed=True` before `sock.close()` (`covering_joined_https.py:107-111`),
  so a later same-owner close is a method call that may skip the raw socket
  attempt.

### Close-method calls vs raw-socket attempts

| Site | Behavior |
| --- | --- |
| `CoveringHTTP.finally` | Always attempts `transport.close()` unless skipped after `response.close()` raise (`covering_http_transport.py:126-128`). |
| `JoinedTLS.open` except | Extra `self.close()` before reraise (`covering_joined_https.py:72-74`). |
| `JoinedTLS.close` | Owner check; if not `closed`, set `closed=True` then `sock.close()` (`covering_joined_https.py:104-111`). Foreign thread refuses before mutation (`covering_joined_https.py:105-106`). |
| Confirmed retirement | **Not** established by `closed=True` alone if `sock.close()` raised after the flag flip. |

Distinction preserved: acknowledged DB rollback (`RootOutcome.ROLLBACK_ACKNOWLEDGED`
via `CoveringTargetTransaction` / parent adapter) ≠ provider socket retirement.

---

## OAuth / token path

**Call chain (native covering):**
`run_bounded_domain` → `_classified_role(TOKEN)` → `ports.token`
(`covering_domain_dispatch.py:201-206`) →
`covering_domain_adapters.token` with `covering_provider_transport`
(`covering_domain_adapters.py:45-52`) →
`_refresh_provider_access_token` (`covering_refresh_import.py:588-601`) →
`google_calendar.get_valid_access_token` / `microsoft_calendar.get_valid_access_token`
→ `refresh_access_token` → `calendar_client(...).post` → `CoveringHTTP.request(purpose="oauth")`.

**CoveringHTTP OAuth classification** (`covering_http_transport.py:107-124`):

- Complete `400` + `error==invalid_grant` → `CoveringReauthorizationRequired`.
- Other OAuth HTTP ≥400 JSON object → `CoveringRootOutcomeUnknown`.
- Any other exception after `transport.sent` → `CoveringRootOutcomeUnknown` (`from None`).
- `CoveringReauthorizationRequired` re-raised unchanged.

**Domain adapter** (`covering_domain_adapters.py:50-52`): catches only
`CoveringReauthorizationRequired` → `TokenRejected(PREFLIGHT_ACCOUNT_DISCONNECTED)`.
Does **not** catch `CoveringRootOutcomeUnknown` or raw cleanup exceptions.

**Public mapping:**

- `TokenRejected` → static preflight row; loop continues
  (`covering_domain_dispatch.py:218-221`).
- Unexpected `ApiError` from token role → forced
  `CoveringRootOutcomeUnknown` (`covering_domain_dispatch.py:207-211`).
- Other exceptions inside `session_scope` → connector quarantines and raises
  `CoveringRootOutcomeUnknown` (`covering_role_connector.py:142-150`).
- Escaping `CoveringRootOutcomeUnknown` → HTTP
  `CALENDAR_REFRESH_OUTCOME_UNKNOWN` (`covering_http_dispatch.py:71-73`).

**Cleanup-failure substitution on token:** if `finally` raises e.g. `OSError`
after a selected `invalid_grant`, the pending
`CoveringReauthorizationRequired` is replaced; adapter does not see reauth;
connector turns the raw exception into UNKNOWN. That stops later admission,
but loses typed reauth unless provenance is retained on the UNKNOWN.

**DB vs provider:** token durable commit/rollback is via native
`terminal(commit=changed)` expecting `RootOutcome`
(`covering_domain_adapters.py:58-60`). That acknowledgment is not socket
retirement evidence.

---

## Identity path

**Call chain:** apply → `import_covering_subscription_cache` →
`prepare_requested_subscription_for_covering`
(`covering_refresh_import.py:911-919`) → when evidence required,
`fetch_account_identity_evidence`
(`calendar_alias_canonicalize.py:158-213`) →
`list_google_calendars` / Microsoft list helpers → `calendar_client.get` →
`CoveringHTTP.request` with identity purpose (not oauth).

**Broad catch that can turn uncertainty into ordinary preflight:**
`prepare_requested_subscription_for_covering` catches
`(httpx.TransportError, json.JSONDecodeError, OSError)` and returns
`PREFLIGHT_EVIDENCE_UNAVAILABLE`
(`covering_refresh_import.py:442-458`). A `finally`-raised `OSError` from
socket close matches this catch → ordinary preflight import result, not
UNKNOWN.

`CoveringRootOutcomeUnknown` is **not** in that tuple; if it survives
`CoveringHTTP` out to prepare, prepare’s outer `except Exception` re-raises
(`covering_refresh_import.py:480-484`), and there is no broad catch around
prepare inside `import_covering_subscription_cache`, so UNKNOWN can escape
apply → `CoveringTargetTransaction.run` → connector → public UNKNOWN and
**stop** later targets/assessment (`covering_domain_dispatch.py:265-267`).

`fetch_account_identity_evidence` itself only maps `ApiError` to
`fetch_succeeded=False` (`calendar_alias_canonicalize.py:170-176`,
`196-203`); it does not catch UNKNOWN or OSError.

---

## Event path

**Call chain:** `ports.apply` → `import_covering_subscription_cache`
(`covering_domain_adapters.py:70-74`) → `_pull_provider`
(`covering_refresh_import.py:968-975`) →
`google_calendar._pull_subscription_changes` /
`microsoft_calendar._pull_subscription_changes` → list/view helpers →
`calendar_client.get` → `CoveringHTTP.request` (event purpose).

**Critical swallow:** `_pull_provider` is wrapped in `except Exception`
returning `OUTCOME_FAILED`, `rollback_required=True`,
`needs_failure_unit=True` (`covering_refresh_import.py:976-994`).
`CoveringRootOutcomeUnknown` subclasses `Exception`
(`covering_target_transaction.py:30`), so a truthful transport UNKNOWN
raised from HTTP (oauth-style or proposed cleanup classification) becomes an
**ordinary failed import**.

**After failed import (current):**

1. `CoveringTargetTransaction.run` expects rollback, calls `finish_root`,
   then `retire_parent`, then optional failure recorder
   (`covering_target_transaction.py:108-160`).
2. Successful DB rollback + parent lease retirement still say nothing about
   provider TLS/socket retirement.
3. `run_bounded_domain` appends the failed result and **continues** the
   target loop, then may admit assessment
   (`covering_domain_dispatch.py:233-257`).

So uncertain provider retirement on the event path can surface as a normal
failed row with later target/assessment admission — the opposite of a
truthful stop.

Apply-stage DB exceptions use a separate `except Exception`
(`covering_refresh_import.py:1080-1098`); that is post-pull local apply, not
provider HTTP retirement, but it likewise never re-raises UNKNOWN.

---

## Assessment / later admission gate

| Outcome shape | Later targets | Assessment |
| --- | --- | --- |
| `CoveringRootOutcomeUnknown` escaping domain loop | Stopped; prior rows attached on exc (`covering_domain_dispatch.py:265-267`) | Not admitted |
| Ordinary `OUTCOME_FAILED` / preflight `ImportCoveringCacheResult` | Continues | May run if not exhausted |
| Public HTTP UNKNOWN | `covering_http_dispatch.py:71-73` | N/A (request already failed closed) |

Legacy orchestrator `run_covering_refresh` similarly only stops the import
loop on `CoveringRootOutcomeUnknown` (`covering_refresh.py:724-726`) and
would also accept importer-returned `OUTCOME_FAILED` as a normal row
(`covering_refresh.py:631-673`).

---

## Import dependency hazard (for any repair)

`covering_target_transaction` imports `ImportCoveringCacheResult` /
`OUTCOME_FAILED` from `covering_refresh_import` **before** defining
`CoveringRootOutcomeUnknown` (`covering_target_transaction.py:19-34`).
A naive top-level reverse import of `CoveringRootOutcomeUnknown` into
`covering_refresh_import` is an initialization cycle hazard. Deferred
local import inside an except handler runs after both modules finished
loading and avoids that cycle; a dependency-neutral base type is the
alternative if top-level typing is required.
\n
