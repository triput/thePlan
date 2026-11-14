# V4 P4 supplement — exact host-parser source predictions

Dex, November 11, 2026. Static byte/source inspection only; no HTTP parser, checker, extracted code or helper invocation. These are source-supported predictions for the existing byte-fake driver after wiring is corrected, not observed run outcomes and not native3.12 behavior. Reconcile independently before freezing v5.

Frozen v4 basis: TIP A40F0DEA7A01AF9C2361E707F0BBFB081BCB1D2D195510BD96EE2E25C43A01A6; checker755181B7193C12AFDED349E3775018567ADBBFC4EB2E388B2642822857CF5154. All52 wire ID/length/hash entries were independently verified in V4-Frozen-Intake-and-Static-Reconciliation.json.

Host source: C:/Users/trish/AppData/Local/Programs/Python/Python311/Lib/http/client.py, SHA256 3A752927A1257EDEBCABAD42CA9508AD532F91C15431755BFBE437A32AB13EB2. Application HTTP source: E942BB43827364A9F20E36AAB604F031287FFF2B3F15BE5CFE48FDE9E81FF4BD. Fake EOF/driver logic is the frozen checker above. No source or expected file was changed by this review.

## Outcome/exception contradictions

| Existing v4 ID(s) | Frozen prediction | Source-supported original prediction | Reason |
| --- | --- | --- | --- |
| C-ZERO-NO-CRLF | PARSER_ERROR / IncompleteRead | SUCCESS / no exception | _read_next_chunk_size applies int(line,16) to b'0' without requiring CRLF; trailer loop tolerates subsequent EOF. |
| C-TRAILER-LINE-EOF | PARSER_ERROR / IncompleteRead | SUCCESS / no exception | Trailer loop discards b't:' and accepts the following empty read. |
| C-TRAILER-MALFORMED | PARSER_ERROR / LineTooLong | SUCCESS / no exception | b'badtrailer\r\n\r\n' is below _MAXLINE; trailer field syntax is not parsed by this routine. |
| H-DUP-IDENTICAL-LIST; H-CONFLICT-LIST-2-3; H-CONFLICT-LIST-3-2 | PARSER_ERROR / ValueError | SUCCESS / no exception | int('2, 2') or int('2, 3') fails, but begin catches ValueError and sets length=None. Connection:close + body {} then yields a valid object. |
| H-INVALID; H-INVALID-PLUS | PARSER_ERROR / ValueError | SUCCESS / no exception | int('+2') succeeds and reads the two-byte object. |
| H-INVALID-NEG | PARSER_ERROR / ValueError | SUCCESS / no exception | Negative parsed lengths are explicitly discarded as None, then close-delimited {} is read. |
| H-INVALID-EMPTY; H-INVALID-NONDEC; H-INVALID-DECIMAL-EQ | PARSER_ERROR / ValueError | SUCCESS / no exception | Empty length is not parsed; abc and2.0 ValueError is caught. All become length=None and read complete {}. |
| H-TE-LIST | SUCCESS / no exception | PARSER_ERROR / JSONDecodeError | 'chunked, chunked' is not exactly 'chunked'; absent CL, the raw chunk framing is read as close-delimited body and json.loads sees extra data. |
| H-TE-MIXED | REFUSE / CoveringTransportRefused | PARSER_ERROR / JSONDecodeError | Message.get sees the first field 'gzip', so chunk mode is false; no CL; raw chunk framing reaches JSON. Content-Encoding is identity, so the application does not reject it as gzip content encoding. |
| CD-DEADLINE | PARSER_ERROR / IncompleteRead | PARSER_ERROR / RemoteDisconnected | FakeTransport(stall=True) returns b'' on its first receive, before any status line, ignoring the stored wire. _read_status raises RemoteDisconnected, not a body deadline or IncompleteRead. |

The bounded read path remains distinct from response.read() without amt: read(8192) does not enforce the declared remaining Content-Length on EOF. That supports the existing F02/F03/F05 valid-prefix original witnesses; it is not evidence of complete acknowledgment.

## Separate outcome from contract designation

C-ZERO-NO-CRLF and C-TRAILER-LINE-EOF success does not establish a complete terminator; preserve the accepted incomplete-framing witness distinction. Malformed trailer field syntax, invalid/duplicate Content-Length handling and mixed Transfer-Encoding policy must remain explicitly tied to the accepted requirement or separately proposed restriction. A source prediction of success is not automatically a policy approval or a claim of corrected success. Do not change original predictions to a desired rejection, and do not hardcode false contract_miss where a required completeness witness succeeds.

The frozen contract_miss_flag does not cover H-CONFLICT-FIELDS-2-3 or3-2, while their exact predicates expect true. Reconcile that mismatch independently of whether strict handling is an adopted or proposed acceptance policy; outcome and defect designation are separate fields.

## Finite inventory reconciliation

Retain both repeated mixed Transfer-Encoding orders. V4 contains gzip then chunked only; the reverse first-field order has different source-selected chunk behavior. Keep identical duplicate/list and conflicting duplicate/list cases distinct. A lone '02' or a lone '2.0' field does not substitute for a decimal-equivalent repeated-field/list pair. Expand required grouped variants within the existing checker/transcript role;52 is not a cap.

Exception/close counters still need justified exact predictions and later observed checks; no executed counter values are supplied here. In particular, do not accept arbitrary bare ValueError to make stale Content-Length predicates pass: the parser handles those errors internally.

## Carry-forward

This refines P4 within the already delivered P1–P6 REVISE, not a new assignment or source authority. Preserve frozen v4, fix wiring and actual caller reachability first, then refreeze original predictions and observations together. No execution, native collection, production correction or endpoint binding is authorized by this trace. Native-v3 launch card remains separate and pending Trish.