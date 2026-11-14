# D2 stopped-run trace and narrow proposed check correction

Dex, November 11, 2026. Offline trace only after the authorized one-shot D2 attempt stopped. No retry, repair or rerun. Jim's separately approved T07 fresh-copy preparation continues; this proposal adds no work to that assignment.

## Verified failure and retirement

The reviewed invocation exited1. Result status FAIL, source hashes verified, control_ids_in_order empty: zero of52 controls completed. Failure occurred in extract_symbols before Google definitions were selected: its unconditional CR-byte refusal rejected the unchanged pinned google_calendar.py. The result and launch receipt remain in the original packet.

The child PID214132 exited1 normally in0.182 seconds of launcher collection; no timeout, interrupt or termination action was reported. Both capture readers joined EOF; stderr length0. Postrun reconciliation verified all252 reviewed packet files and12 runtime provenance pins unchanged. This is a fixture/checker failure, not a demonstrated application path failure. See Dex-Run-Reconciliation.json and Run-ToolResult.json.

Result SHA256: `B9E06AEE93AD981D0AFD4FC7CB05E03FD40D9FFC259364982351804677896ED7`.

Launch receipt SHA256: `AC36E46D7A772E9D897673BBE05768BB619C3658F29CF475FA5295410E201D90`.

## Root cause from unchanged input bytes

All eight extraction source pins match. The three candidate transport/context files and three original base files use LF. google_calendar.py contains1461 CRLF pairs and microsoft_calendar.py2252; neither contains a bare CR. Their raw SHA256 values match the reviewed manifest. Thus normalizing or rewriting those application sources would change preserved evidence unnecessarily.

extract_symbols reads raw bytes, decodes UTF-8, rejects any CR, then calls ast.parse and records the raw-byte SHA256. Its LF-only rule is an incompatible checker assumption for these already pinned inputs. The separate mutation-source loader sees only the LF transport/policy inputs in this inventory and need not be changed for this failure.

## Narrow proposed fresh-copy preparation

Apply only Proposed-CRLF-Check-Fix.diff to the check script in a NEW D2 packet. Within extract_symbols, permit CRLF pairs but continue refusing a lone CR. The predicate uses a temporary string for that inspection; the original decoded text is still passed unchanged to ast.parse, and raw bytes still supply the provenance hash. No source normalization, replacement application bytes, relaxed source pins, AST selection change or path-policy change is proposed.

Preserve all52 existing controls, original/candidate extraction names, mutation and ordered-inventory oracles, isolated Python flags and capture/retirement behavior. Regenerate the successor's labels, hashes/admission/command references and truthful format descriptions: authored packet text uses LF, while pinned application source bytes retain their original LF/CRLF forms. Do not execute the successor during preparation. Return exact delta, commands and hashes for a separate one-shot run decision.

Dex can prepare this small check-only successor while Jim continues the approved T07 assignment. The stopped-run source-change/no-repairs hold requires Trish's approval before editing even the new check copy. No rerun, imports/tests/compilation, application edits, sockets, PKI, installation, Docker/native launch or endpoint binding. Preserve the failed packet, all evidence and all other holds.
