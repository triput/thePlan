# V5 staged static review — pending final Jim handoff

Dex, November 11, 2026. Read-only source/data inspection; no imports/compilation/checker/helper invocation. Drop staging now includes a freeze manifest, but no final Jim v5 tip was yet found when inspected. Treat these findings as conditional on the same final hashes; do not mutate or execute Jim's copy.

Staged TIP:65DC4D694991374976B3F04409622E333DF3E3C656E7957E69B107988D4F15C3. Checker:4B6933876E98A0B2A1FF191C26641907CD9B41E50B9C6FD503EB5E9D8AAE4689. Launcher:A67AD24CE951332A10B85EFB72D25954EFD24B743B6B1C74C0633A8FB7676C1C. Admission:10F552761685DB83B495A65884E9D701DD578AF6D7C637F263333329ADB83461. Full intake/hash reconciliation remains required after handoff.

## Static carry-forward improvements

P1: manifest now includes ProviderLimits plus the path-helper/constant closure. P2: the extracted UNKNOWN class is explicitly shared with policy/http namespaces and identity assertions. P3: Google token URL/config/refresh_access_token are extracted and the new driver invokes the actual owning function under covering context. P4 improves observed FakeTransport.sent and response begin/read evidence. P5 now labels missing historical command/pyc/_refreeze evidence UNKNOWN rather than verified false, although self-reports remain distinct from retained command receipts. None of these observations is an executed PASS.

## P4 remains open — source-prediction supplement not incorporated

EXPECTED-ORIGINAL retains the contradictions documented in V4-P4-Host-Parser-Prediction-Trace.md (96D3D93C2EC841D03006E40BECF94AE4ADF708FC6415B47F0D89F7DF13BB9C55), including:

- C-ZERO-NO-CRLF still predicts IncompleteRead; the pinned host parses b'0' and tolerates subsequent trailer EOF.
- C-TRAILER-MALFORMED still predicts LineTooLong for a short discarded line.
- H-INVALID-PLUS still predicts ValueError; int('+2') succeeds. Other invalid/list/negative lengths are caught/ignored by begin, not propagated.
- H-TE-LIST still predicts success; nonexact TE is read as raw chunk-framed JSON and predicts JSONDecodeError.
- H-TE-MIXED still predicts CoveringTransportRefused; gzip is a Transfer-Encoding value, while the application's content-encoding check sees identity. First-field lookup causes raw chunk framing to reach JSON.
- CD-DEADLINE still predicts IncompleteRead; its fake empty first receive reaches _read_status and predicts RemoteDisconnected.

A wire-ID allowlist plus VALUEERROR_PARSER_PHASE constant does not observe an actual exception phase. The pinned parser catches these CL conversion ValueErrors internally. Do not accept arbitrary harness ValueError under the same IDs; reconcile exact source predictions first.

The disposition calls one repeated mixed-coding order and a different comma-list stimulus 'both orders'. They are different representations, not reversed field order. Preserve both actual repeated-field orders and decimal-equivalent duplicate/list variants;52 is not a cap.

Observed send/status/body fields improve provenance, but current exact predicates still mainly gate outcome/exception/close counts. Freeze justified send-state/status/body/wire assertions where the control claims them; do not let labels replace the input-specific expected observations. Preserve original behavior versus desired completeness/compatibility distinctions.

## P6 remains open — refusal overwrites the prior receipt

Launcher main checks RECEIPT.is_file() and calls _stop_receipt('preexisting_receipt_refused_not_deleted',...). _stop_receipt calls write_receipt, and write_receipt uses RECEIPT.write_bytes, which overwrites that same prior file. The RESULT guard can also overwrite an accompanying preexisting receipt via this path. Removing RESULT.unlink closed deletion of the result, but did not satisfy preservation of all prior evidence.

Keep the normal wrapper refusal. At the inner launcher, refuse without writing over any existing receipt; use an appropriate stderr/operator outcome and exclusive creation for any newly owned receipt. Reconcile all early failure paths that call write_receipt before the explicit prior-evidence checks, not only the new branch. No failure receipt/result deletion or overwrite is authorized. This is a static source finding, not a performed replay.

## Next disposition

Recheck final tip/pins and take one consolidated readiness decision. These P4/P6 issues prevent a launch card for this inspected copy. Do not re-run or silently repair v5. If still present in Jim's final handback, return them as one same-scope fresh-successor batch; retain v1–v5. Native-v3's separately reviewed source-only launch card remains pending Trish and unaffected. Endpoint unbound; all execution holds remain.