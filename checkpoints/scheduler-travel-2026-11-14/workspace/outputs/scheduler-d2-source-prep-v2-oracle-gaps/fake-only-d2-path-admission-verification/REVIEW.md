# Fake-only D2 path-admission verification — REVIEW (authoring, not executed)

Status: AUTHORING ONLY / PREPARATION. `launch_ready=false`. `executed_in_preparation=false`.
No check invocation, admit/launcher run, app imports, compilation, sockets, providers, credentials, PKI, Docker/native continuation, deployment, or endpoint binding occurred in this preparation packet.

## Predecessor
Supersedes frozen v1 tip `A91964DAA5C16E940840A631E8E3B05BF89C7F8260DFC502FD5CF3562AE20C2E` due to Dex provisional oracle gaps (p1794421374).
v1 packet remains IMMUTABLE at:
`F:/DropFolder/pending/post-native-d2-source-fake-prep-jim-v1-2026-11-11/`

Parent successor packet:
`F:/DropFolder/pending/post-native-d2-source-fake-prep-jim-v2-oracle-gaps-2026-11-11/`

Candidate resulting hashes (verified pins; unchanged from v1; unchanged by this fake packet):
| File | SHA256 |
| --- | --- |
| covering_transport_policy.py | `A265F81F72E719B23FE3DE9BF332E2DE01D8E90073F3AC04675EC6A4B2203598` |
| covering_http_transport.py | `AECE10186CFFAE46D3EF2292D3772F1C287FD0A562AA9E764AAC4ABB10C861D8` |
| covering_provider_context.py | `875FBF61A386D661A4DD70609162E41540500F10AD6AEDCACAF790701D693240` |

Diff pin: `CDB3AF210C7DD2BDC725F44F61931AD39B8010D5D259289D5D1FEF3E98E3F4F4`.

## Dex oracle gaps closed in this successor
1. **Mutations (functional oracles):** `M-PATH-ADMIT-NOOP` rebinds noop `admit_covering_path` into CoveringHTTP and drives ORD-SLASH to open/send; unmutated SAME assertion refuses 0/0. `M-HTTP-ALLOW-PATCH` requires mutant PATCH construct/open/send (non-method refuse alone is NOT success). `M-ENCODED-SLASH-BYPASS` neutralizes both encoded-slash and decoded-literal-slash refuses inside extracted `_inspect_opaque_id_segment`, then drives ENC-SLASH through CoveringHTTP. Mutants temporary/in-memory only; never edit production snapshot files.
2. **CTRL-SEP-TARGET-AUTHZ:** replaced tautology with AST+interface evidence that extracted covering surface has no calendar-target-authz binder; `admit_covering_path` returns no authz token; explicitly separate from native I01-C02; no auth proof manufactured.
3. **neg_path context call-site:** every path-admission negative also observes real extracted `_CoveringClient` with sentinel `transport.request` (ZERO delegate calls after unique route selection). Dedicated named additions: `CTRL-NEG-CTX-ORD-SLASH`, `CTRL-NEG-CTX-ENC-SLASH`, `CTRL-NEG-CTX-MALFORM`.

## Authority inputs
- Controls-Plan.md (corrected4): `5072CED783E3ACA08EC28E760D6581D3916F1E5175F3CF830ABD5412C0B845BB`
- Dex oracle overlay: `D2-T01-Corrected4-Dex-Oracle-Overlay.md` `CA51E2D8F40073C260942B5AF634229D253D9E2AA77177C45471037ED3C59B4D`
- Policy decision (routine oracle section): `EF6D4E0B5B2CAFFA87C7F2CBE264B1EA46413F9DE0BBD7C9CD4CD061724CDE6F`

Overlay corrections carried (from v1, still present):
1. Exact-prefix equals full admitted path (`CTRL-POS-G-EXACT-PREFIX` ≠ `CTRL-POS-G-CHILD`).
2. Synthetic STRUCT-PCT helper reach via `/__fixture__/covering/admit/`.
3. PATCH split: CoveringHTTP typed refuse vs `_CoveringClient.patch` AttributeError.
4. Restore `CTRL-POS-G-PAGE-TOKEN` as separate direct-query positive (approved 41-row core retained; counts are not ceilings).
5. `CTRL-CONT-G-PAGE-TOKEN` drives extracted Google `_paginate_events` with 2 scripted pages (setup1+continuation1=2 opens/sends; URL-shaped nextPageToken as query; zero redirect follow-ups).

## Named expected controls (52)
- Approved core functional 41 retained (incl. POS-G-PAGE-TOKEN + CONT-G-PAGE-TOKEN)
- Oracle-gap additions (+3 functional): `CTRL-NEG-CTX-ORD-SLASH`, `CTRL-NEG-CTX-ENC-SLASH`, `CTRL-NEG-CTX-MALFORM`
- Functional total now 44 = 16 positives + 18 negatives + 3 context-named + 2 collision + 4 continuation + 1 separation
- Mutations (3, harness-only): `M-PATH-ADMIT-NOOP`, `M-HTTP-ALLOW-PATCH`, `M-ENCODED-SLASH-BYPASS`
- Inventory self-checks (5): `H-INVENTORY-ACCEPTS-GOOD`, `H-INVENTORY-REJECTS-REORDER`, `H-INVENTORY-REJECTS-DUPLICATE`, `H-INVENTORY-REJECTS-MISSING`, `H-INVENTORY-REJECTS-ALTERED`

## Extraction / composition
AST-extracts candidate helper/HTTP/context plus Google builder (`_calendar_events_base`, `_paginate_events`) and Microsoft `_GRAPH_ORIGIN` / `_absolute_graph_url`. Fully fake peers (TEST-NET numeric addresses), fake transport construct/open/send/close instrumentation, no real dial. Hostnames in peer labels are names only.

## Held launcher limits (documented; not run)
- One pinned Python invocation (`admit_outer.py` → `invoke_d2_fake.py` → check)
- 30s child wait, 5s termination/wait, two 5s reader joins
- 64 KiB stdout/stderr each, 256 KiB result
- Interpreter pin: `C:/Users/trish/AppData/Local/Programs/Python/Python311/python.exe` SHA256 `5F7B89A612C9B8AF1D6456CDFCD1DBE5CA630849E79AEBCED9BEE9A6694952EC`
- Reuses T02 admit_outer / invoke structure with new pins/labels; no old T02 evidence reuse

## Explicitly NOT claimed
- Full provider transport proof
- T01–T08 closure
- Real TLS / provider dial / endpoint or profile binding
- Target calendar authorization (separation oracle only; no manufactured auth proof)
- DB acknowledgment
- Execution authority (`launch_ready` remains false)

## Untouched
- Original T02 trees
- Native trees
- Frozen v1 tip packet (immutable)
- Already-applied three candidate source files / diff pins in the D2 payload
