# T05 header representation witnesses

Dex, November 11, 2026. Read-only source/design review. These are proposed wire spellings for later authoring, not executed inputs or accepted outcomes. T07 launch card remains unchanged.

Published CPython3.12.16 HTTPResponse.begin uses a single-value header lookup, exact chunked recognition, and integer conversion for length; invalid/negative lengths become unspecified. [HTTP client source, lines337–357](https://raw.githubusercontent.com/python/cpython/v3.12.16/Lib/http/client.py).

Its underlying Message.get implementation returns the first matching stored field, while get_all exposes the complete list; the API documentation cautions against relying on duplicate selection. [Message source, lines394–400 and471–518](https://raw.githubusercontent.com/python/cpython/v3.12.16/Lib/email/message.py).

## Distinct original-characterization inputs

Use complete headers/CRLF and body `{}` where a body is specified; separately freeze all bytes, EOF behavior, purpose and response status.

| Variant | Length/transfer fields | Source-derived prediction to verify, not a PASS claim |
| --- | --- | --- |
| Identical repeated fields | Content-Length:2 followed by Content-Length:2 | Single-value lookup differs from explicitly checking every field. |
| Identical comma list | One Content-Length:2,2 | Integer conversion may fail and take the unspecified-length path. |
| Conflicting repeated fields A/B | Length2 then3, and3 then2 | Header order may change fixed-length selection and bounded EOF behavior. |
| Conflicting comma list A/B | One length2,3, and3,2 | Characterize independently from repeated-field behavior. |
| Valid decimal spelling | Length02; paired duplicate values2 and02 | Preserve the distinction between decimal value equality and raw-string equality in any later proposal. |
| Invalid spelling | Length+2, negative, nondecimal or empty | Do not treat successful integer conversion or fallback as proof of valid HTTP framing. |
| Repeated transfer fields | chunked then another coding, and reverse order | Characterize first-value selection separately from a comma-list coding sequence. |
| Mixed mechanisms | Each relevant TE representation plus CL | Require actual raw field inventory, parser state and caller outcome; do not collapse all into one TE+CL case. |

The existing13 T05 planning IDs remain; these are distinguishable variants rather than a replacement inventory or arbitrary new acceptance policy. Predict original behavior per exact input, record a contract miss honestly, and keep desired corrected behavior in a separate column. Do not write an original oracle that quietly assumes the correction already exists.

## Consequence for a later correction proposal

A remaining-length gate after body collection addresses only definite-length short EOF. It cannot by itself identify invalid/conflicting length representations that parsing already converted to an unspecified length. Preserve complete header occurrence/value information before converting response headers into a dictionary. Do not adopt first-field-wins as a compatibility policy by accident.

The actual native parser and its inherited message/header handling still require provenance from the pinned image; this upstream reference is not that evidence. Include the relevant native email/message implementation or equivalent selected method provenance when making representation-specific native claims. No source fix, extra probe or execution is authorized here.
