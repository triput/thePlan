# Proof inventory v3

Supersedes v2 tip `9522BC2F8166F508606E6ACB1912511DDDB39D472CBA2FE400419A7AC30163BB`. Not executed.

## Provenance oracle (candidate)

On cleanup UNKNOWN:

- `.primary` is this invocation's captured primary or None (success+cleanup)
- `.response_close` / `.transport_close` are distinct retained exceptions
- `.prior_retirement_provenance` lists earlier snapshots without mutation
- `.retirement_occurrences` is append-only full history
- Forbidden: attributing ambient `sys.exc_info()` objects; mutating
  caller-owned UNKNOWN instances

## New outer-handler controls (Dex)

| ID | Setup | Stimulus | Oracle |
| --- | --- | --- | --- |
| C-OUT-VE | Call `CoveringHTTP.request` from inside `except ValueError:` handling an unrelated ValueError; exchange succeeds; response.close or transport.close raises | New UNKNOWN; `.primary is None`; unrelated ValueError object identity not equal to `.primary`; ValueError instance not mutated |
| C-OUT-UNK | Call `CoveringHTTP.request` from inside `except CoveringRootOutcomeUnknown:` handling an unrelated caller-owned UNKNOWN; exchange succeeds; cleanup raises | New UNKNOWN distinct from outer object; outer UNKNOWN attrs unchanged; `.primary is None`; outer not in `.primary` |

These are Class A/B design witnesses for later authorized fixtures — not
demonstrated runs.

## Retained from v2

O-R02/R06/R03-ev/R04/R05/R08/O-UNK-pull/O-ID-OS and C-R01–R12 oracles, with
provenance reading updated to append-only fields above. R08 still requires
JoinedTLS.open change.
