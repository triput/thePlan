# Exact-port admission: bounded preparation proposal

Dex, November 11, 2026. Source-supported offline finding; no new verification run.

## Finding and narrow correction

HTTPSPeer.check_url currently compares (u.port or 443) with the approved peer port. The pinned local urllib.parse port property converts an ASCII numeric port with int(), accepts the range 0 through 65535, and returns that integer (lines 176–185). Therefore an explicit :0 becomes integer zero and the truthiness fallback substitutes 443. For an approved peer at 443, that origin can be admitted. HTTPSPeer itself disallows a configured peer port of zero.

This is an exact-origin admission mismatch. The actual dial still uses the configured numeric peer and configured port; this finding does not establish an arbitrary-destination connection or a runtime exploit.

The proposed one-line correction defaults only an absent parsed port (None) to 443. Explicit zero then fails against every permitted configured peer. No URL normalization, rerouting, destination, TLS, counter, deadline, result, transaction or retry change is proposed.

## Requested extension to the approved workspace-authoring lane

Authorize fresh-copy preparation of exactly this additional application file: app/services/covering_transport_policy.py, limited to the one expression in Proposed-Fix.diff. Preserve every other byte in that file, including D2 path helpers and ProviderCounter. Keep the existing three-file/four-verification-role lane and all its boundaries.

Within the existing fake check role, prepare finite original/candidate controls for an approved peer at 443: absent port and explicit 443 stay accepted; explicit 0 and 444 refuse. Add a nondefault permitted peer port case so an absent URL port cannot acquire that peer's nondefault port. Use the actual pinned urlsplit definition through the disclosed host standard-library dependency, with fake peers/transports and no sockets. Record original/candidate observations honestly; a source read is not an executed PASS. Return exact applied diff, application/input/runtime hashes, finite expected observations and held invocation for later launch review.

Jim remains implementation lead with one active framing assignment. Dex may prepare this small extension separately for speed and then reconcile it into the final staged candidate with Jim. No fifth executable role, native fixture, provider operation or new dependency is authorized.

## Holds

This document and diff are proposals only. The application file is outside the currently approved three-file lane, so no application or check change has been applied. Approval requested here is preparation only: no imports, compilation, tests, helper invocation, execution or rerun; no sockets, PKI, Docker, installation, build, credentials, deployment or endpoint binding. Preserve existing packets and all evidence. Every launch remains separately gated. Endpoint unbound; all other holds stay.
