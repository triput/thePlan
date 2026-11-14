# B1–B7 disposition (v4 fake four-role)

Sources: `Initial-Preparation-Static-Findings.json`, `V2-Preparation-Reconciliation.json`, `V3-Fake-Remaining-Static-Findings.md`, `V3-Provisional-Custody-and-Static-Review.json`.

| ID | Source location | v3 pin / defect | v4 disposition | Changed pin |
| --- | --- | --- | --- | --- |
| B1 | Initial B1/B2; V3-Fake §1 | policy_ns empty before dataclass/IP/URL eval; txn whole-module risk | `seed_policy_namespace` before extract; txn extracts `CoveringRootOutcomeUnknown` only | check `755181B7…` |
| B2 | Initial B2; V3-Fake §2 | httpx Client only; missing Request/Response | Fake `httpx.Request` / `httpx.Response` constructors supplied | check `755181B7…` |
| B3 | Initial B3; V3-Fake §3 | Broad allowed_outcomes; classifier oauth-remaps | Exact `exact_predicate` per wire; classifier does not duplicate oauth remap | EXPECTED + check + invoke gate |
| B4 | Initial B4 | contract_miss conflated with outcome | `contract_miss` bool separate from `observed_outcome` | EXPECTED predicates |
| B5 | Initial B5; V3-Fake §4 | Manual `_CoveringClient`; owning refresh absent | `calendar_client` under covering context; `CALLER-REFRESH-TOKEN-F04` named owning boundary | check + manifest callers |
| B6 | Initial B6 | Stall≡deadline / TLS claims | Explicit `stall_is_not_deadline_proof` / `byte_fake_eof_only`; no TLS proof claim | CD-* predicates |
| B7 | Initial B7; V3-Fake §5–6 | null status/body; close counters unchecked; broad outcomes | Fake response primitives recorded; exact close counters in predicate + invoke gate | check + invoke |
| B8 | Initial B8 | Native supervisor | **Deferred to Dex** `native-dex-v3` — no Jim re-impl | n/a (document only) |

## Wire construction disposition

| Control | v3 defect | v4 intended form | v4 SHA256 |
| --- | --- | --- | --- |
| C-DATA-SHORT | `3\r\n{}\r\n` (CR as 3rd data byte) | `3\r\n{}` + EOF | `5CFFB2738B3D56487CADBB2A8CC5870F2D6A8789C34F4BF318FCA3397B7A6A83` |
| C-SEP-SHORT | identical to C-ZERO-ABSENT | `2\r\n{}\r` + EOF | `1AEC0F54DAF220586736DEF77DE39E8D7AFE6DF9B7D7EB25DB680C09CDD2F821` |
| C-ZERO-ABSENT | identical to C-SEP-SHORT | `2\r\n{}` + EOF | `E69CB0CEB14578282AD18648A88145D0F1C1802CB3CC87A6E0748E7EA3E781A7` |
| C-SEP-WRONG | valid CRLF before XX0 | `2\r\n{}XX0\r\n\r\n` | `C24CC2E9091879CA8F938AC2260B05EE5E488A69EA87B9989CA8C3D63C4CE44C` |
| C-TRAILER-MALFORMED | missing final blank line | `…badtrailer\r\n\r\n` | `58D5A7288F7FD26F4200C389C26DE7B62C90FC72642A4E6E164A140D17A40720` |
| C-EXT-VALID | extension without trailer field | extension + `X-Trailer: ok` | `9A751FB3DF44B331427727DBFEB59367592A9CBFEC93921679776875085EF789` |
| C-TRAILER-VALID | (missing positive) | trailer field, no extension | `FF58E4A04C7FAC656406ED71494DC2561C01F2F413F811783C8EAA0E219DE7E9` |
| H-INVALID-* | umbrella +2 only | PLUS/NEG/EMPTY/NONDEC/DECIMAL-EQ variants | see WIRE-INVENTORY |
| H-TE-MIXED | missing mixed-coding | gzip then chunked fields | `5B3407984CB288C16B69C4457D5E8A3581345C4E95F0920633AC9C843623A774` |
