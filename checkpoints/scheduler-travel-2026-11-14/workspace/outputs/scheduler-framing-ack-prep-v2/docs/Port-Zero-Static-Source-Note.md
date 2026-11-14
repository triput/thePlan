# Port-zero origin check — static source note (no implementation)

Prep: post-native-framing-ack-source-fake-prep-jim-v2-2026-11-11  
Author: Justin for Jim (attributed Dex offline finding)  
executed=false; launch_authorized=false; endpoint=unbound  
**No implementation authority in this handback.** No edit to `covering_transport_policy.py`. No port-zero controls added.

## Hash-verified reads
| Artifact | SHA256 |
|---|---|
| `outputs/scheduler-port-zero-proposal-v1/Preparation-Scope-For-Approval.md` | `A27E47A5B7106708CC1A6E683D645CAB2821FBA1FAE2F45E7A7488F1DB5B0F85` |
| `outputs/scheduler-port-zero-proposal-v1/Proposed-Fix.diff` | `C69EB5EFFAD47FBC1BB2A085DCF7620D736EF713BC09B4D4984736104BC9F8CB` |

## Finding / qualification
`HTTPSPeer.check_url` compares `(u.port or 443)` to the approved peer port. Host `urllib.parse` port property can return `int(0)` for an explicit `:0`, so truthiness substitutes 443 and an origin can be admitted against a peer configured at 443. `HTTPSPeer` still disallows configuring peer port 0. Dial continues to use the pinned numeric peer/port — this is an exact-origin admission mismatch, not evidence of arbitrary-destination connect.

Narrow proposed correction (not applied here): `(443 if u.port is None else u.port)`.

## Lane status
Policy file is outside the approved three-file framing lane. Trish preparation-extension card pending. Framing OWS v2 remains the primary deliverable of this packet.
