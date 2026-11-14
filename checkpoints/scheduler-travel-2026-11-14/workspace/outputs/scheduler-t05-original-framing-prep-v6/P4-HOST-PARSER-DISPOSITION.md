# P4 host-parser disposition (v6)

Sources (static read only; no parser/checker execution):

| Pin | SHA256 |
| --- | --- |
| `V4-P4-Host-Parser-Prediction-Trace.md` | `96D3D93C2EC841D03006E40BECF94AE4ADF708FC6415B47F0D89F7DF13BB9C55` |
| Host `http/client.py` (Python 3.11) | `3A752927A1257EDEBCABAD42CA9508AD532F91C15431755BFBE437A32AB13EB2` |
| Dex v5 REVISE intake | `661E2537552FB07E2262D5DBA65843C1296CFF472BBB436FEF9247AC12847730` |
| Superseded v5 tip | `65DC4D694991374976B3F04409622E333DF3E3C656E7957E69B107988D4F15C3` |

Original vs desired remain separate fields. Flips below are **source-supported originals**, not desired stricter policy.

## ID → old (v5) → new (v6) + contract_miss + reason

| ID | Old prediction | New prediction | contract_miss | Reason (client.py) |
| --- | --- | --- | --- | --- |
| C-ZERO-NO-CRLF | PARSER_ERROR / IncompleteRead | SUCCESS / no exception | **true** (incomplete terminator) | `_read_next_chunk_size` applies `int(line,16)` to `b'0'` without requiring CRLF; trailer loop tolerates subsequent EOF. |
| C-TRAILER-LINE-EOF | PARSER_ERROR / IncompleteRead | SUCCESS / no exception | **true** (incomplete terminator) | Trailer loop discards `b't:'` and accepts following empty read. |
| C-TRAILER-MALFORMED | PARSER_ERROR / LineTooLong | SUCCESS / no exception | false (final blank terminator present) | `b'badtrailer\r\n\r\n'` below `_MAXLINE`; trailer field syntax is not parsed. |
| H-DUP-IDENTICAL-LIST | PARSER_ERROR / ValueError | SUCCESS / no exception | false | `int('2, 2')` fails; `begin` catches ValueError → `length=None`; `Connection: close` reads `{}`. |
| H-CONFLICT-LIST-2-3 | PARSER_ERROR / ValueError | SUCCESS / no exception | false | Same catch path for `int('2, 3')`. |
| H-CONFLICT-LIST-3-2 | PARSER_ERROR / ValueError | SUCCESS / no exception | false | Same catch path for `int('3, 2')`. |
| H-INVALID | PARSER_ERROR / ValueError | SUCCESS / no exception | false | `int('+2')` succeeds; reads two-byte object. |
| H-INVALID-PLUS | PARSER_ERROR / ValueError | SUCCESS / no exception | false | Same as H-INVALID. |
| H-INVALID-NEG | PARSER_ERROR / ValueError | SUCCESS / no exception | false | Negative length discarded as None; close-delimited `{}`. |
| H-INVALID-EMPTY | PARSER_ERROR / ValueError | SUCCESS / no exception | false | Empty CL falsy/not parsed → `length=None`. |
| H-INVALID-NONDEC | PARSER_ERROR / ValueError | SUCCESS / no exception | false | `int('abc')` caught → `length=None`. |
| H-INVALID-DECIMAL-EQ | PARSER_ERROR / ValueError | SUCCESS / no exception | false | `int('2.0')` caught → `length=None`. Lone `2.0` ≠ dup/list variants. |
| H-TE-LIST | SUCCESS / no exception | PARSER_ERROR / JSONDecodeError | false | `'chunked, chunked'` ≠ exact `'chunked'`; no CL; raw chunk framing → `json.loads` extra data. |
| H-TE-MIXED | REFUSE / CoveringTransportRefused | PARSER_ERROR / JSONDecodeError | false | First TE field `gzip` → not chunk mode; CE identity; raw chunk framing → JSONDecodeError. |
| CD-DEADLINE | PARSER_ERROR / IncompleteRead | PARSER_ERROR / RemoteDisconnected | false | `FakeTransport(stall=True)` returns `b''` before status; `_read_status` raises `RemoteDisconnected`. |

## contract_miss reconciliation (unchanged outcomes, fixed flags)

| ID | contract_miss | Note |
| --- | --- | --- |
| H-CONFLICT-FIELDS-2-3 | **true** | Predicates already expected true; kept in `CONTRACT_MISS_TRUE`. |
| H-CONFLICT-FIELDS-3-2 | **true** | Same. |
| C-ZERO-NO-CRLF / C-TRAILER-LINE-EOF | **true** | Success ≠ complete terminator; accepted incomplete-framing witness. |

## Inventory expansion (52 is not a cap; now 57 wire IDs)

| New ID | Stimulus | Source-selected behavior |
| --- | --- | --- |
| H-TE-MIXED-CHUNKED-GZIP | TE fields chunked then gzip | First field `chunked` → chunk mode → SUCCESS (peer of gzip-then-chunked H-TE-MIXED). |
| H-DECIMAL-DUP-FIELDS | CL `02` then CL `2` | First wins `int('02')=2` → SUCCESS. |
| H-DECIMAL-DUP-LIST | CL `02, 2` | `int` fails → `length=None` → SUCCESS. |
| H-DECIMAL-EQ-DUP-FIELDS | CL `2.0` then CL `2` | First `int('2.0')` fails → `length=None` → SUCCESS. |
| H-DECIMAL-EQ-DUP-LIST | CL `2.0, 2` | `int` fails → `length=None` → SUCCESS. |

Identical duplicate/list and conflicting duplicate/list cases remain distinct. Lone `02` / lone `2.0` do not substitute for these grouped variants.

## ValueError policy

`VALUEERROR_PARSER_WIRES` emptied. A wire-ID allowlist does not observe an exception phase; `begin` catches CL conversion `ValueError` internally. Checker no longer admits bare `ValueError` as `OBSERVED_PARSER_ERROR`.

## Close counters

Predicted `response_close_calls=1` / `transport_close_calls=1` for covering_http rows: `CoveringHTTP.request` finally always attempts `response.close()` (when response object exists) and `transport.close()`. CD-DEADLINE creates the response object before `begin()` raises, so both close paths still run. Counters are source-justified predictions — **not** executed Dex observations.
