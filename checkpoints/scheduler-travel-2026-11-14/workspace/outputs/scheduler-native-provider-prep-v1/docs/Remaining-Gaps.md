# Remaining gaps — native-provider prep-v1

Flags: `executed=false`; `launch_authorized=false`; `implementation beyond prep=false`; `prep_is_not_pass=true`; endpoint unbound.

## Explicit retained gaps

| ID | Disposition | Note |
| --- | --- | --- |
| T02-ITEMS-OVERFLOW | GAP | Host-fake EXCESS-ITEM-BYTE (framing result 3905A070…) is host-fake refuse only — does not close native/T02 full goal. |
| T02-BYTES-OVERFLOW | GAP | Same as items overrun — retained. |
| T08-NESTED | GAP_OR_FOCUSED_FAKE | ContextVar nesting; focused fake witness declared in `verify/check_native_provider.py` / EXPECTED. |
| T08-RESET | GAP_OR_FOCUSED_FAKE | ContextVar reset; same. |
| T01-ORIGIN-FOREIGN-PORT | HOLD | Port-zero packet prepared, **unexecuted/unapproved**. Copying policy override for assembly does not authorize its run. |
| T07-BOTH-CLOSE-AFTER-PRIMARY-FAILURE | NATIVE case authored | `NP-T07-BOTH-AFTER-FAILURE` — host-fake PRIMARY-BOTH-CLOSES does not close. |

## Assembly / launch holds

- Port candidate `covering_transport_policy.py` pin 5F48FD7E… assembled into `payload/api/` — **unverified**, launch unauthorized.
- Runner/suite/command/PKI/output/retirement bounds not frozen — compute from actual ops before launch card.
- Invocation and fault-retirement authority = later launch card only.
- Failed-container shutdown/removal separately gated.
- Unjoined/unconfirmed retirement → UNKNOWN.
- No failed-attempt reseed/retry.
- Endpoint unbound; no product binding.

## Framing host-fake (not native proof)

- RESULT 3905A070AE06EF2EA6B31C8A8D1407A6F58E46B549E1118FF3928C00866ECBA3
- Receipt 166BB080CCCD19B80F88703BA3CC16B46142DAEF3904BDAF5D7AA9CF3254E6E6
- Do not promote to native TLS / owning-call proof.

## Open decisions (from jim-v2 TIP)

Unresolved decision IDs retained: D1, D2, D3, D4, D5, D7, D8, D9, D10, D11, D12. Resolved: D6.
