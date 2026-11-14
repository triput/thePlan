# One active assignment: approved diagnostic fake v2 preparation

To: Matt, thePlan session
From: Dex

Trish explicitly approved fresh-copy preparation of exact proposed diff SHA256 41E0506D38484A176FB7039C1B0373E62BC97142E87369AECA921E41B48601F0. Approval receipt:
C:/Users/trish/Documents/Codex/2026-10-15/trish-wants-to-improve-dex-s/outputs/scheduler-runner-diagnostic-fake-v1.evidence/Fresh-Copy-Preparation-Approval.json

## Objective and baseline

Prepare the corrected diagnostic fake-check packet for independent review and a later separately gated one-shot run. Do not run it.

Use your frozen preparation baseline outputs/scheduler-native-provider-runner-diagnostic-fake-prep-matt-v1 (input manifest SHA256 398F8A3C4CE2C77640AE0D812CB5E6C3FFAECB045D19F2FCFB5D49E7194DCA3D,14 entries). Verify those pins before copying. Do not copy result/receipt or failed staging evidence. The failed staged packet outputs/scheduler-runner-diagnostic-fake-v1 and all evidence remain untouched.

Fresh destination: outputs/scheduler-native-provider-runner-diagnostic-fake-prep-matt-v2. Stop if it already exists; do not overwrite or select a fallback destination without reconciling first. All outputs paths are below C:/Users/trish/Documents/Codex/2026-10-15/trish-wants-to-improve-dex-s/.

## Exact authorized source change

Only packet/verify/check_native_provider.py changes executable bytes. Baseline SHA256 D4010F1BBA744F65DAB118E8FF384C69BD217427BEC0A7FF690CD1D0D954EBE8.

On fallback_mutant's anchor line, replace:
("return original  # Diagnostic failure must not replace the primary kind.", "raise"))
with:
("return original", "raise"))

Preserve indentation, encoding and existing line endings. Expected exact candidate SHA256 BA1C333D5109D38569B6784332B1291B1035EF88737D774D303F34F88D6C4C7A. The actual approved diff is retained at outputs/scheduler-runner-diagnostic-fake-v1.evidence/Proposed-Fallback-Mutation-Anchor.diff. Stop on mismatch; no broader checker repair is authorized.

Keep all14 controls, assertions, expected FileNotFoundError oracle, replacement raise, unique-anchor guard and all subject/producer/host/API bytes unchanged. Wrapper, launcher and outer-admission Python executable roles must remain byte-identical. No new tests, mutation bodies or executable relabeling are authorized. Keep the checker PACKET_NAME and expected-inventory lineage labels byte-identical; explain their retained v1 lineage in docs rather than widening the one-line diff.

## Metadata preparation

Regenerate checker pin, dependent OUTER and VERIFICATION pins, complete input manifest and absolute future-command document for this v2 directory. Both launch_authorized booleans remain false; no EXECUTE acknowledgment exists. Refresh packet/admission/document labels truthfully where this changes data only, preserving scope, limits and interpreter-only provenance. Label inherited historical command/decision documents appropriately; do not leave ambiguous current-invocation claims.

Return the exact one-line source diff, complete input/runtime inventories, all hashes, acyclic admission relationships, exact future command, truthful120+5+5+5=135s nominal supervision exclusions and64KiB streams/256KiB result limits, exclusive fresh evidence paths, and a no-active-writer freeze. No output claims PASS; authored syntax and behavior remain unverified.

## Actions and holds

Read/copy/literal source edit/hash/JSON and manifest/document authoring only. No imports, AST parsing, compilation, tests, helper invocation, checker verification, rerun, installation, sockets, PKI, Docker, database, native execution, Git operations or F:/Code Repo/ThePlan edits. No cleanup. Preserve every predecessor and failed evidence. Stop on failure/mismatch/UNKNOWN; do not improvise a repair.

Up to two subagents are optional within this assignment, only if helpful and subject to the same boundaries. Given your enforcement qualification, use them only for read-only static review; keep one primary writer and record any contributions. No recursive delegation or second assignment. Allow ordinary pickup/work turnaround; no urgency is implied.

Deliver a new signed Matt-thePlan-Scheduler-* handback and hash manifest via Matt-Drops. Actionable questions stay in signed drops. This authorizes preparation only, NOT EXECUTE. Endpoint unbound; all other holds stay.

Signed: Dex