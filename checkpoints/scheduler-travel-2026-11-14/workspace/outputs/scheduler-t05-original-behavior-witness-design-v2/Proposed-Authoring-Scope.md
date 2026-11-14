# T05 proposed bounded authoring scope (documents only; no executable authoring yet)

Date: 2026-11-11
Status: proposed scope for later Dex/Trish gates -- NOT implementation approval
Parent design: T05-Original-Behavior-Witness-Design.md v2 in this packet

## Purpose

Define exact file/module roles for (1) original-behavior checker/fixture preparation and (2) native provenance acquisition. No source/checker/fixture bytes are authored or edited in this documents-only packet.

## A. Read-only pins (consume; do not edit)

| Path under fake-v2 packet/payload/workspace | Role |
| --- | --- |
| apps/api/app/services/covering_http_transport.py | Framing loop under test |
| apps/api/app/services/covering_joined_https.py | TLS transport; close semantics |
| apps/api/app/services/covering_provider_context.py | calendar_client / _CoveringClient routing |
| apps/api/app/services/covering_transport_policy.py | limits, HTTPSPeer, refuse/reauth types |
| apps/api/app/services/covering_domain_adapters.py | token/apply observation under covering_provider_transport |
| apps/api/app/services/covering_refresh_import.py | importer UNKNOWN boundary |
| apps/api/app/services/google_calendar.py | refresh_access_token via calendar_client |
| apps/api/app/services/covering_request_budget.py | deadline guards |

Also pin (read-only) the 76-ID audit JSON and Dex T05 design notes listed in INPUT-PINS.json.

## B. Later original-behavior fake packet (authoring only after gate)

Proposed new packet root (name illustrative): post-native-t05-original-framing-prep-jim-vN/

| Relative file | Purpose |
| --- | --- |
| fake-only-t05-framing-verification/check_t05_framing_original.py | Deterministic owned-byte driver of CoveringHTTP (and _CoveringClient path) recording ORIGINAL outcome classes; no corrected gate |
| fake-only-t05-framing-verification/EXPECTED-ORIGINAL.json | Per-input frozen predictions + allowed witness classes; CONTRACT_MISS allowed where hypothesized |
| fake-only-t05-framing-verification/EXPECTED-CORRECTED.json | Separate future oracle; not scored on original runs |
| fake-only-t05-framing-verification/wire/ | Exact request/response byte transcripts + SHA256 per F*/C*/H*/CD* variant |
| fake-only-t05-framing-verification/INPUT-MANIFEST.json | Pins, limits, purpose pairs (oauth/event/identity), no execution flag |
| fake-only-t05-framing-verification/OUTER-ADMISSION.json | Held outer admission pattern consistent with T07 fake wrapper kind family (new kind string TBD with Dex) |
| fake-only-t05-framing-verification/REVIEW.md | Scope/limits; original vs corrected columns |
| Jim-Static-Read-Invoke-Verification.md | If a held wrapper is reused/adapted: static read only |
| TIP-FREEZE.json / ARTIFACT-HASHES / HANDBACK | Freeze ritual |

Checker rules:

- Drive actual CoveringHTTP.request / _CoveringClient, not a stand-in body loop.
- Preserve raw header occurrence inventory before any dict conversion.
- Charge wire bytes through ProviderCounter; retain 16 MiB ceiling and request budget.
- Record response/transport close provenance (T07-compatible).
- Stop on UNEXPECTED; no retries/repairs.
- launch_ready=false until Trish card.

## C. Later provenance acquisition packet (launch/evidence gate; not product vote)

Proposed packet: post-native-t05-native-parser-provenance-jim-vN/

| Item | Purpose |
| --- | --- |
| Extract/pin native /usr/local/lib/python3.12/http/client.py | Exact runner framing bytes |
| Extract/pin native .../ssl.py | ragged-EOF / wrap_socket defaults |
| Extract/pin native .../email/message.py | get / get_all header representation |
| Receipt binding runner image c2201104... + paths + SHA256 | Replace upstream-tag assumption |
| Note comparing host Py3.11 / upstream 3.12.16 tag / native capture | Three-way provenance table |

No live probe in the current assignment. Native 3.12.16 version string already supplied; bytes still UNESTABLISHED.

## D. Later correction proposal (only after original receipts)

- Fresh-copy proposed diff against covering_http_transport.py (Option A/B/C as evidenced).
- Possibly covering_provider_context.py only if header inventory must be exposed at client boundary (not assumed).
- Prospective resulting SHA256s; source-change hold; no silent reject of close-delimited / chunk extensions / valid trailers; no unbounded reads.

## E. Explicitly out of this authoring scope

- Editing production sources now
- Real sockets/PKI/Docker/listener topology (see Synthetic-Provider-Topology-Review; separate proposal)
- Closing T03/T04/T06/T07/T08 by T05 framing fakes alone
- T07 fake-v2 execution
- Asking Trish to approve D4/D5 as product choices

## Confirmation

Scope document only. No files under section B/C/D are created by this v2 freeze beyond this documents packet.
