# T07 v4 retirement controls: provisional static review

Dex, November 11, 2026. Read-only working-copy review; no imports, compilation or checks executed. This is not a frozen acceptance. Observed checker SHA256 89D508531A4D2273148451F688F8410C9BC034711A301AB0CB58AACFC44F7114; final handback must be rehashed and reconciled.

## Improvements visible in this working version

- run_http now resets fake socket state before applying sock_faults. R07/R08 then check the configured fault remains present before requesting. The previously demonstrated reset ordering defect is corrected in source.
- R08 invokes actual extracted JoinedTLS through CoveringHTTP and requires exactly two method-close entries and one raw close. This distinguishes inner open-handler cleanup from outer HTTP cleanup without demanding a second raw close.
- R09 counts one failed raw close and requires the later method call to perform no additional raw close.
- M-MUTATE-OUTER-UNKNOWN now mutates the actual extracted request method's finally block in memory, compares a caller-owned outer exception before/after, and restores the original method. It is distinct from M-ALLOW-LATER.
- M-ALLOW-LATER rebinds actual role-admission stop behavior and compares unconditional observed later-role/callback counts. This is a local fake-boundary mutation; it does not prove native transaction/retirement behavior or the still-missing linked HTTP/domain fault propagation.

## Remaining precision concern

R07 configures a specific setblocking primary exception with no raw-close failure. Its direct-primary branch is expected for this setup, because setblocking occurs before JoinedTLS.open's internal try and HTTP finally owns cleanup. However, the checker also accepts UNKNOWN and tests `not isinstance(primary, FakeOpenPrimaryError) and probe.constructs < 1`: a mere socket construction can let an unrelated primary pass. It also does not enforce primary object identity, exact close counts or zero sends on the direct-primary branch.

Before freeze, tighten this same control to the exact configured fault and its expected successful outer retirement. If an UNKNOWN variant is intended, give it explicit failed-retirement setup and a distinct oracle rather than accepting it as an interchangeable success. This is a check-oracle correction within the current authoring scope, not a production change or authorization to execute.

The linked-caller finding remains as recorded in V4-Authoring-Linkage-Review.md. Final acceptance additionally requires full manifest/source/control inventory reconciliation, extraction dependency review and exact command/admission preparation. Nothing in this note closes full T07 or T01–T08.
