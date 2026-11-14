# Jim T05 Authoring-Scope Review v1 -- Reconciled-Authoring-Scope-For-Review.md

Reviewer: Justin (for Jim)
Date: 2026-11-11
Subject: outputs/scheduler-t05-design-review-v1/Reconciled-Authoring-Scope-For-Review.md
Subject SHA256: 20B9347FECC7597FC7DAA16AD92D8E3D45C1E4BC26B4DEFA929D1C58F3A42734
Method: Documents-only scope review against accepted T05 v2 design (TIP FA13F24F...) and reviewed T07 launcher/wrapper contracts. No executable authoring. No source/checker/fixture edits. No imports/compile/tests. No launch.
Flags: review_only=true; applied=false; executed=false; launch_authorized=false

## Disposition

QUALIFIED ACCEPT -- the reconciled scope is sufficient for Dex to bring Trish a preparation card. This review does not authorize authoring or execution.

Blocking findings: 0.

## What matches (accepted)

1. Two separately held packets (original-framing byte-driver vs native provenance capture) -- matches v2 Proposed-Authoring-Scope separation.
2. Six new/adapted executable roles only; no other modules without scope amendment.
3. Fake driver uses actual pinned HTTPResponse / CoveringHTTP / _CoveringClient -- no mock parser or hand-written body-loop imitation.
4. ORIGINAL predictions per input with honest CONTRACT_MISS; CORRECTED file separate and unscored on original runs; UNEXPECTED stops.
5. Full 76-ID planning scope retained; T05 variants expand umbrellas; thirteen planning IDs are not a cap.
6. Compatibility positives retained: complete fixed-length, chunked/extension/trailer, orderly close-delimited.
7. D1/D2 remain recommendations only -- not frozen as adopted corrected policy in original-characterization task (per Dex p1794433342).
8. D4 source-gated; D5 launch-gated; native 3.12.16 version retained but bytes UNESTABLISHED until collection.
9. Launcher bounds match reviewed T07 invoke contract: 30s child + 5s kill/wait + 2x5s reader joins = 45s nominal; 64 KiB pipes; 256 KiB result; no retries/fallback/extra cleanup.
10. Wrapper retains full packet/runtime hash checks and refuse-prior-result/receipt before child.
11. Native collect recipe limited to exact three paths under /usr/local/lib/python3.12/{http/client.py,ssl.py,email/message.py}; supervisor pattern from runner-only capability; no invocation in prep approval.
12. Preparation holds explicit; T07 fake-v2 card independent/untouched; no production correction or TLS-policy adoption.

## Qualifications (non-blocking; must appear on prep freeze)

Q1. Host parser for fake packet: the byte-driver pins host HTTPResponse/message/SSL consumed on the prep host. That is host-parser original characterization only. It must never be labeled native acceptance. Three-way provenance (host / upstream 3.12.16 reference / eventual native capture) stays explicit in manifests.

Q2. Exact finite inventory before any launch card: expand grouped F*/C*/H*/CD* rows into per-purpose (oauth/event/identity) stimuli with complete transcript ID/order/count/byte-size inventory frozen before launch review. Thirteen planning IDs are not that inventory.

Q3. Distinct admission kind and evidence names: T05 wrapper/outer kind and FAKE-T05-RESULT / FAKE-T05-LAUNCH-RECEIPT (or Dex-chosen names) must not collide with scheduler-t07-one-shot-fake-verification-admission or T07 evidence filenames.

Q4. Exact caller entrypoints listed at prep freeze: CoveringHTTP.request purposes; _CoveringClient via covering_provider_transport; domain token/apply observation paths as applicable. "Owning caller definitions" resolved to named functions/modules in INPUT-MANIFEST.

Q5. Immutable helper copies: any byte-for-byte copy from T07 invoke/admit/wrapper/helpers lists exact source path, destination path, and SHA256 in handback; any logic delta disclosed as adapted (not silent drift).

Q6. JSON-safe evidence: explicit primitive projection for all emitted results (same B1 lesson as T07); no assumed counters.

Q7. Close-delimited / TLS: byte fakes may observe empty-recv completion paths; orderly close_notify vs abrupt EOF and real socket ownership remain separately gated (T03/T04 / native provenance). Scope already states this -- restate on freeze.

Q8. D1/D2: original characterization proceeds without choosing restrictive corrected policy. Corrected oracle file may document recommendation text but must not score original runs against adopted refuse-all-duplicates / refuse-TE+CL as if product-decided.

## Blocking findings

None. The six executable roles plus immutable helper copies can meet the reconciled requirements under Q1-Q8.

## Explicit non-claims / holds

- review_only=true; applied=false; executed=false; launch_authorized=false
- No checker/fixture/wrapper/native-script authoring performed by this review
- No Trish preparation approval claimed
- No T07 launch; fake-v2 untouched
- No production source correction; no suppress_ragged_eofs change; no compatibility restriction adopted
- Endpoint unbound

## Confirmation

Reconciled scope document was not edited. No executable authoring. No launch.
