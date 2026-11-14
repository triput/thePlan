# Synthetic provider topology: reusable fixture and unresolved seams

Dex, November 11, 2026. Offline source/design review only. No Docker inspection, sockets, certificate generation, source implementation or runtime probe. Jim remains on the one T07 readiness assignment; this is preparation for later design review.

## Reusable established boundaries

The retained native I01/I02 v4 packet uses two pinned disposable containers: DB network none, runner sharing the exact DB-created network namespace, no published ports, nonroot runner, read-only roots and packet binds, declared tmpfs scratch, bounded workers and exact-ID success cleanup. Its passing receipt established its actual DB/native/TLS-fault scope and both containers were removed. Reuse means a new separately approved fixture, not restarting or reusing those deleted resources.

The runner-owned C06 TLS recipe already separates private key material from public CA transfer. It does not establish a future provider certificate's SAN/hostname, HTTP peer behavior, port availability or new child lifecycle. Keep DB trust and synthetic provider trust separate; do not transfer DB private keys.

## Source-supported options and constraints

HTTPSPeer validates a numeric address and an explicit1..65535 port, and check_url requires exact HTTPS hostname/port with no credentials/fragment/control characters. It does not reject a numeric loopback address. Thus a local high-port synthetic TLS peer can be described without runtime DNS or host port publication. JoinedTLS uses that exact numeric address/port while verifying the configured hostname.

However, real Google event URL construction includes a literal www.googleapis.com origin and OAuth normally uses port443. Microsoft has GRAPH_BASE, _GRAPH_ORIGIN and _LOGIN_BASE, plus one literal graph origin in continuation handling. Merely setting an HTTPSPeer to18443 while retaining a443 URL is a route mismatch. Do not introduce a hidden connect-port translation or hostname bypass to force the fixture to work.

| Candidate proof seam | What it can establish | What remains separate |
| --- | --- | --- |
| Real CoveringHTTP/JoinedTLS with explicit synthetic hostname/high-port profile | Actual bounded TLS/socket/parser/retirement behavior at the reviewed route; no DNS or external peer | Production vendor URL-builder constants and complete vendor-client composition are not exercised by this seam alone. |
| Owning importer/domain with reviewed synthetic provider callback invoking that real transport | Actual transaction/caller classification and continuation for those injected provider outcomes | Callback is a disclosed substitution; do not claim the complete Google/Microsoft HTTP client path ran. |
| Full provider-client composition using original443 URL origins | Exercises actual provider URL construction and context/client routing as well as transport | Requires a viable separately approved local443 listener/certificate topology; nonroot low-port capability is not established by prior receipts. |
| Fixture-specific replacement of URL helpers/constants | May allow full downstream path over explicit high ports | Exact replacements and their coverage impact need review; do not describe changed builders as unchanged production code. |

These are design alternatives, not an adopted compatibility restriction or a reason to omit an accepted test. The full proof plan must preserve all required transport/caller contracts and disclose each injected seam. Prefer reusing existing verified runtime and fixture boundaries; do not add an installation, image build, capability or network change merely for convenience.

## Requirements for the later bounded proposal

Freeze exact peer origins/numeric ports/purposes, CA/SAN trust identities, maximum simultaneous listeners/connections, accepted byte transcripts and selected actual methods. Make foreign-origin refusal, one-request/no-followup redirects and no-DNS/no-fallback counters observable. Server/client workers, sockets and any PKI child/readers need bounded ownership and joining, with resource uncertainty stopping the run.

Retain the original request budget and cumulative counters across targets; do not replace real deadlines with a fresh timeout per exchange. Align the real peer cases with T03/T04 timing and T05 completeness distinctions, and carry T07 uncertain retirement through the actual selected caller/domain path. Prior fake controls are prerequisites, not real socket evidence.

An eventual proposal must identify whether additional fixture source scope or a consequential topology choice needs Trish's call, then return exact reviewed diffs, commands and hashes before any execution. No topology, listener, privileged port, capability, builder replacement or launch is authorized by this note. Endpoint/profile remains unbound; all holds stay.
