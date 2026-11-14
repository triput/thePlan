# Next transport design assignment — T07 retirement and caller classification

Dex to Jim, November 11, 2026. This is the sole new Jim assignment after the completed D2 source/check preparation. Documents-only investigation and proposal; no source/check authoring, application imports, compilation, execution, sockets, PKI, Docker, installation or endpoint binding. D2's pending exact-hash fake-verification card is unchanged and grants no authority until Trish answers it.

## Concrete question

Can the current covering provider path truthfully stop with UNKNOWN when retirement is uncertain, preserve the primary failure, and attempt the independently owned retirement operations without retries? Trace the actual callers, not only CoveringHTTP.finally. Return the narrowest justified proposed change and original/candidate proof design for review. Do not apply a change or author executable checks.

## Authoritative current source

Use the immutable API copy under C:/Users/trish/Documents/Codex/2026-10-15/trish-wants-to-improve-dex-s/outputs/scheduler-d2-fake-v1/packet/payload/workspace/apps/api. Hash all consumed source and quote exact local locations. Current rechecked SHA256 values:

| Source in app/services | SHA256 |
| --- | --- |
| covering_http_transport.py | AECE10186CFFAE46D3EF2292D3772F1C287FD0A562AA9E764AAC4ABB10C861D8 |
| covering_joined_https.py | C58382900BE1C190ED39242B4992FE88E1155E55F7E8C33D32065DBFCC993468 |
| covering_refresh_import.py | C57A5F956BEA5A364B781C586B595C984013F357F337355B30C4182230BFE1F0 |
| covering_target_transaction.py | 8ADC67737002512BD66D87A6A874E6970250094BA1CF7FCE69E7A66B966A235A |
| covering_role_connector.py | C5BA15CDE276586CFFA2DE24A51E79F40CC6479D3A5A1D6663D23A20D930B288 |

Use the existing Transport-Proof-Matrix.md, T07-Retirement-Branch-Review.md (including its November 11 caller/import dependency update), T05-Framing-Branch-Review.md and accepted transport addendum as prior design evidence. Historical assignment statements in those notes are superseded by this assignment. These notes establish hypotheses and requirements, not executed failures or repair authority.

## Required handback

1. Trace event, identity and OAuth paths through caller/transaction/connector to public outcome and later target/assessment admission. Show where cleanup failure can replace an outcome and where broad catches can turn uncertainty into an ordinary failed import. Preserve the distinction between acknowledged DB rollback and provider retirement.
2. Reconcile all twelve T07-R01–R12 candidate branches. For each, name the current-source observation to test, acceptance oracle, primary/cleanup provenance, close-method calls versus raw-socket attempts and confirmed retirement. Do not call an unexecuted witness a demonstrated failure.
3. Recommend the smallest coherent design. Include exact affected symbols/files and dependency placement. The target-transaction module imports importer result types before defining CoveringRootOutcomeUnknown; a naive reverse top-level import is unsafe. State whether an existing common exception type suffices, a dependency-neutral definition is needed, or a different narrow route is preferable. Compare alternatives with their consequences, not a manufactured consensus.
4. Specify original-versus-candidate functional/mutation witnesses, including actual caller-level UNKNOWN/no-later-admission observations. Distinguish fake acknowledgments from future real local TLS/socket retirement evidence. Avoid changing transaction guards, retry policy, public contracts, deadlines or resource authority as a fixture convenience.
5. Identify actual decisions separately from routine preparation. Return a frozen documents-only handback with input pins, exact proposed diff if justified (unapplied), proof inventory, scope/limits for any later preparation/run, open questions and hashes. No executable fixture authoring is authorized by this assignment.

Do not constrain the full T01–T08 inventory to this T07 subset. The goal remains incomplete until the full required proof is independently verified. Preserve the D2 packet and every prior run. Allow normal authoring turnaround; send one frozen handback when ready, or an explicit approval-wait/blocker if encountered.
