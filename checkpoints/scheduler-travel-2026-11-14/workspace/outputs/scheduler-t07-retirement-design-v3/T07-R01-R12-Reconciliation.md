# T07-R01–R12 reconciliation v3

Supersedes v2 tip `9522BC2F8166F508606E6ACB1912511DDDB39D472CBA2FE400419A7AC30163BB`. Hypotheses only.

Provenance fields: `.primary`, `.response_close`, `.transport_close`,
`.prior_retirement_provenance`, `.retirement_provenance`,
`.retirement_occurrences` (append-only). No `sys.exc_info()` primary.

## Branch table (delta from v2)

R01–R03, R07, R09, R12: unchanged intent; success+cleanup uses
`invocation_primary is None`.

R04–R06: primary from `invocation_primary` (body/parser exception), not
ambient stack; both cleanups retained as distinct objects on R06.

R08: JoinedTLS.open still required; raises new UNKNOWN with open primary +
transport_close; HTTP finally may later append another occurrence if outer
close also fails, without mutating the JoinedTLS UNKNOWN (referenced as
`.primary` / prior list).

R10–R11: oauth remapped exceptions assigned to `invocation_primary` before
raise; cleanup builds new UNKNOWN with that primary preserved by reference.

## Added cross-cutting controls

See Proof-Inventory C-OUT-VE and C-OUT-UNK.
