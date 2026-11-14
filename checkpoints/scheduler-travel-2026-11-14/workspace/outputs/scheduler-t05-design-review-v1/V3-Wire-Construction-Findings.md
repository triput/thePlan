# V3 exact-wire construction findings

Dex, November 11, 2026. Read-only raw byte inspection and source reasoning, not a parser/checker execution. Raw paths, lengths, hashes and escaped bytes are retained in V3-Exact-Wire-Byte-Review.json. These findings complete the existing finite-transcript/oracle review; preserve v3 in the same approved fresh successor.

| V3 ID | Actual chunk body bytes, CRLF escaped | Consequence for the stated witness |
| --- | --- | --- |
| C-DATA-SHORT | 3\r\n{}\r\n | Three declared data bytes are available: `{`, `}`, CR. The later separator is short (only LF). It does not isolate short chunk data. A genuine isolated short-data form is3\r\n{} then EOF. |
| C-SEP-SHORT | 2\r\n{}\r\n | Complete data separator, then absent next-size line; byte-identical to C-ZERO-ABSENT (SHA13D1C85B...). It cannot prove either zero-byte or one-byte separator truncation. Those require2\r\n{} then EOF and2\r\n{}\r then EOF as distinct variants. |
| C-SEP-WRONG | 2\r\n{}\r\nXX0\r\n\r\n | Actual separator is valid CRLF. XX corrupts the next size line, whose integer conversion fails. It cannot prove unchecked wrong separator acceptance. The intended wrong-separator form is2\r\n{}XX0\r\n\r\n: exactly two wrong delimiter bytes followed by a valid zero chunk. |
| C-TRAILER-MALFORMED | 2\r\n{}\r\n0\r\nbadtrailer\r\n | No final blank line, so trailer syntax and missing termination are confounded. Add the final CRLF to isolate malformed trailer syntax; keep the EOF variant separately. |
| C-EXT-VALID | 2;ext=valid\r\n{}\r\n0\r\n\r\n | Valid extension positive, but no actual trailer field. A separate complete valid-trailer positive is still required. |

The pinned host _get_chunk_left first consumes exactly two bytes after chunk data, then parses the next size line. This ordering is why C-SEP-WRONG as currently written exercises a different branch. Its _read_next_chunk_size accepts integer zero without independently checking line CRLF, and _read_and_discard_trailer tolerates EOF. C-ZERO-NO-CRLF and C-TRAILER-LINE-EOF therefore need source-supported narrow original predictions and explicit incomplete-framing miss predicates, rather than being omitted from the defect mapping. These remain source predictions until separately approved execution.

H-TE-REPEAT currently repeats identical chunked fields; it does not cover mixed-coding field order. H-TE-LIST supplies chunked,chunked, which is not the same parser path as a first-value exact chunked. H-INVALID currently contains only+2; negative/nondecimal/empty and decimal-equivalent repeated representations remain distinct required variants. Do not retain umbrella IDs while omitting their accepted expanded stimuli.

Fixed-length F01/F02 and OAuth complete/truncated pairs were also inspected: their body bytes end exactly at the object and their declared complete-versus-short lengths differ as intended. This statement is input construction evidence only, not a successful parser or caller outcome.

No fixture/app sources were edited; no source was imported or compiled, no parser/checker was run. No application policy or execution authority is added. Jim retains the existing assignment; endpoint unbound and all holds stay.