# Diagnostic fake-packet independent review checklist

Dex, November 12, 2026. Derived by reading the actual approved successor producer (np_runner_entry.py lines 1349-1405) and immutable host _record_runner_stop (docker_transport.py lines 54-128). No imports, parsing, tests or checker invocation. This checklist prepares review; it does not assert a PASS or add source changes.

## Source and extraction

- Candidate exact SHA256 40A1BA8E9C3E320DD7DF9E06102CC29C0E1AFAAD4213EC0FECF9FE34455BF73F; baseline 7FBDCAEE078CDBE3F695191ABBED93B827A31EB6FED55DCD839AB43A84355FF5.
- Immutable validator SHA256 7F7EA8204879D312624DAEB7941504FEA1402F45C48BDA79DDAD94A23711AC53. Controls must exercise its actual extracted method rather than a restated predicate.
- Compare original/candidate STOP handlers and exit125 behavior. Unchanged application/host/helper/other fixture bytes require independent inventory reconciliation.
- Fake source-path/filesystem/traceback inputs must make hash and line validation meaningful. A control that merely expects the desired class or frame without reaching the relevant branch is insufficient.

## Producer behavior to reconcile against named controls

- Explicit cause takes precedence over context; context is used when no cause exists. Current approved code follows context even when suppressed. Do not silently change that behavior.
- At most three unique exception objects; cycles or remaining chain set truncation.
- At most128 traceback nodes walked per exception; retain the last eight accepted owned frames, flagging truncation for discarded/rejected locations.
- Only canonical in-root .py manifest entries with allowed path spelling, exact file SHA256 and in-range source line may appear. Outside paths, missing ownership, changed bytes and invalid line bounds omit the location and mark truncation.
- Sanitized class identifiers in normal diagnostic output; no messages, locals, source text, SQL or arbitrary traceback strings.
- Serialized JSON plus LF must fit4096 UTF-8 bytes. Frame removal preserves valid schema and marks truncation.
- Diagnostic construction exceptions fall back to original status/kind. Preserve the accepted asymmetry: fallback uses the original unsanitized class name, which the host may refuse. No producer repair is authorized by a failing expectation.
- Empty accepted frame lists are permitted. A valid diagnostic with zero frames is different from diagnostic_unavailable fallback.

## Host acceptance/refusal controls

- Only exact owned runner start/attach argv is eligible. Unowned/different command is not recorded as runner STOP.
- Exit code must be a true integer in the declared range. Envelope is nonempty, at most4096 bytes, exactly one terminal LF and no CR. Invalid UTF-8/JSON, duplicate keys or extra schema fields refuse.
- Diagnostic version must be integer1 (not bool); truncation must be bool. One to three exception entries, zero to eight frames each, valid identifiers and exact schemas.
- Host independently verifies canonical source-root boundary, manifest membership, current source hash and true integer line bounds; bool line values refuse.
- First exception kind must match top-level kind. Bare original STOP is accepted with diagnostic_unavailable; invalid metadata records only the fixed refusal code.
- Receipt callback failure must not replace the original command failure. Successful metadata acceptance does not convert failed attach to success or authorize continuation.

## Packet admission and scope

- Finite exact control inventory, meaningful negative/mutation controls, explicit expected refusals and no blanket acceptance of UNKNOWN.
- Subject/full-input/runtime pins and command graph are acyclic; raw bytes and line endings are admitted honestly.
- Exact command, interpreter provenance, child/reader/capture/result limits, termination qualifications and exclusive new evidence paths are disclosed before any card.
- No app/vendor package imports, live sockets/PKI/Docker/database or real dependency operations hidden in fake controls. No verification run has occurred under preparation authority.
- Full handback must freeze all writers, identify subagent contributions, preserve predecessors and distinguish authored behavior from static review and runtime proof.

The inherited native operator evidence-path issue is separately documented. It does not justify expanding this focused diagnostic checker or claiming native provider success.