# Fake-only T02 admission verification — REVIEW (CORRECTED2 authoring, not executed)

Status: AUTHORING ONLY / CORRECTED2 REVISE. `launch_ready=false`. No check invocation, app imports, compilation, sockets, providers, credentials, PKI, Docker/native continuation, deployment, or endpoint binding occurred in this preparation packet.

Parent corrected1 preserved UNTOUCHED: `F:/DropFolder/pending/post-native-t02-admission-prep-jim-v1-corrected1-2026-11-10/` TIP/MANIFEST-SELF `6B4944B8DACE130CFFC3F74993D13D47F4FD81745612EDE2B7D3BB46F2F18625`.

Parent v1 tip preserved UNTOUCHED: `F:/DropFolder/pending/post-native-t02-admission-prep-jim-v1-2026-11-10/` MANIFEST-SELF / TIP `A5C7E1DE33E63857A7A8E503262F6F2A85A34C6E5573C50734538E00147C0526`.

Dex provisional notes: `T02-Corrected1-Provisional-Review.md` + Slack p1794383509, p1794383631, p1794383742, p1794383896. Approval remains `call_61f574d0b91546148d1c5fde581a4e37/1` — verification authoring only; no execution authority added.

## Scope pins
- Preparation-Scope-For-Approval.md `8A427389E46F6318999192A7AD7934A8F96B93F154C719DAEE984FF6DD358A99`
- Proposed-Fix.diff / Source-Changes.diff `BEBCE1010F2086D09DFFD978C4032A1F7C1CF7133A3EC944D1648C3DB97A9979`
- Preparation-Approval.json `B78734994AEE40BDE587DF48BFE912DBA35580F139C25A8FC5C48539A3B51E96` (call_61f574d0b91546148d1c5fde581a4e37/1)
- Prior Jim static review MANIFEST-SELF `0EBDF9D92F026C92250E2213E6419F4E6A853D7B25770019DFEF9078A9EE189B`
- C06 corrected6 MANIFEST-SELF `94BB0D3DDEBED09AF52174B37A478484F35F8B07175154B4F27991967C9024A4` preserved untouched
- Verification-Design.md `0BFDEDFFB632FA862A2953CDAF5207473935FB3A638F494EA0C7062341966167`
- Parent corrected1 TIP/MANIFEST-SELF `6B4944B8DACE130CFFC3F74993D13D47F4FD81745612EDE2B7D3BB46F2F18625`

## Applied prospective pins (unchanged vs corrected1/v1; four files' bytes NOT modified in CORRECTED2)
| File | Prospective SHA256 |
| --- | --- |
| covering_transport_policy.py | `1171F629B596AC0366B9BE495D475FD125507027582491989F96E2BF3D922485` |
| covering_http_transport.py | `A1F68F7529724BFDA709663C353BD8CD65E3FE757D1EC10FB34970E8303CC9DF` |
| covering_domain_adapters.py | `BA82577E8CF4B27D4EDD5A1B9D31B35E87990A381B83E22D4DB2A4D89352A53C` |
| test_covering_transport_policy.py | `4A8C7EF1D4539F48B012797A478628267F2F544C3E62AB891B9E870131B1D342` |

Source-Changes.diff remains approved `BEBCE101…`. F-DIFF disagreement preserved.

## Named expected controls (20)
Unchanged inventory vs corrected1. Provisional-notes closures revise W-TOKEN-AT-EQUALITY, M-C-TOKEN-STOPPED-ONLY, W-COUNTER-IDENTITY-REQUEST-WIDE, W-ORDERED-RESULTS-LATER-LIMIT, W-APPROVED-CEILING-ITEMS-EQUALITY-ALL-PURPOSES, W-APPROVED-CEILING-BYTES-EQUALITY-ALL-PURPOSES criteria/details only.

## Provisional-Notes-Response (Dex mid-flight A–D)

### A — Token sentinel (W-TOKEN-AT-EQUALITY + M-C)
- Adopted Dex's **narrow option**: instrumented `db.info` object whose `.get` validates exact key `covering_token_terminal`, increments sentinel observation, raises `AdmissionPassedSentinel` at that lookup — immediately downstream of `admission_exhausted` preflight.
- No invented ORM/lock path. Bare `object()` target is sufficient because locks/pair are never reached.
- Candidate at equality must make **ZERO** `db.info.get` lookups (probe records count/keys; must stay 0).
- Catch **only** `AdmissionPassedSentinel`; unrelated setup errors FAIL.
- Sentinel location pinned/labeled: `db.info.get:covering_token_terminal` (EXPECTED `sentinel_location_pin` + control criteria/details).
- Locks-after-preflight seam **not retained** (avoids owner_id/account_id/subscription_id argument-eval trap on bare `object()`).

### B — W-COUNTER-IDENTITY-REQUEST-WIDE byte budget + wiring
- Framed HTTP responses exceed convenience `response_bytes=64` due to header/framing accounting in production `_Reader`.
- This control now uses **approved 16 MiB** (`APPROVED_RESPONSE_BYTES`) for the byte ceiling. Page/item convenience values remain explicitly labeled. Production byte accounting **unchanged**.
- Wiring proof strengthened (not `id(local)==id(local)`):
  - Observing `make_domain_ports` wrapper records `transport.counter`.
  - Assert that object **is** the `for_request`-constructed `ProviderCounter`.
  - HTTP event/identity path mutates **that same object** (page counters).
  - Composed `domain_ports.token` observes exhaustion of that same object.
  - A **second independent** `for_request` yields a **fresh** counter; first request's pages are undisturbed.

### C — W-ORDERED-RESULTS-LATER-LIMIT
- Fake budget now exposes `check_admission()` (extracted `run_bounded_domain` calls it), not only `check_deadline`.
- Asserts **exact** response cardinality `len(results) == len(body.subscription_ids)`.
- Asserts subscription-ID **order** against `body.subscription_ids`.
- Asserts `token` call count `== 2` and `run_target` call count `== 1` (not merely first status / second code with `len>=2`).
- `FAKE_NOT_NATIVE_DB_ACK` / `FAKE_TRANSACTION_ACKNOWLEDGMENT` labeling retained — **NOT** native/DB-ack proof.

### D — Item/byte equality ALL-PURPOSES
- Creates a **fresh** `ProviderCounter` per purpose (event / identity / oauth).
- Injects only that exact item or byte ceiling on that counter.
- Asserts `stopped=False` (and `admission_exhausted=True`) immediately before each call.
- Asserts zero constructs/opens/sends on refuse.
- Does **not** share one counter across the purpose loop (first refuse must not set `stopped` and pollute later purposes).

### Request-identity wiring note (cross-cuts B)
Observations establish composed domain ports and the HTTP path under test share the `for_request` ProviderCounter object across purposes; a second independent `for_request` gets a fresh counter. Manual HTTP client construction remains a fake transport_factory seam only — no production change demanded; local-vs-local id tautology rejected.

## Findings-Response (Dex REVISE 1–5) — carried from CORRECTED1
CORRECTED1 closures for mutations-from-extracted-defs, for_request/run_bounded_domain composition, deliberate sentinel (now narrowed further in A), item/byte ceilings, and inventory order enforcement remain in force. See parent corrected1 REVIEW for the original 1–5 text; CORRECTED2 does not reopen those except where provisional notes A–D supersede sentinel / counter-identity / ordered-results / equality details above.

## Limits / remaining concerns
- Does **not** close T02 runtime proof or other T01–T08.
- No execution authority; every later run separately gated.
- Unresolved native obligations explicitly NOT claimed: known-rollback vs UNKNOWN, provider/socket retirement, real TLS, DB acknowledgment.
- Parent corrected1 tip, parent v1 tip, prior DropFolder tips (incl C06 corrected5/6, T02 static review), failed workspace `scheduler-c06-fake-v1`, blocked native draft, and base evidence workspace remain UNTOUCHED.
- Four candidate production/test hashes unchanged.

## Dex workspace amendment

Fresh workspace copy of corrected2. Only executable delta is H-INVENTORY-ENFORCER-REJECTS-BAD: accept a complete synthetic baseline first, then derive independent rejection fixtures. All twenty IDs/outcomes, production files and launcher bytes remain unchanged. Original corrected2 is preserved. Exact diff is outside this packet at ../Inventory-Self-Check.diff. No execution occurred; Jim independent review and Trish launch approval remain pending.
