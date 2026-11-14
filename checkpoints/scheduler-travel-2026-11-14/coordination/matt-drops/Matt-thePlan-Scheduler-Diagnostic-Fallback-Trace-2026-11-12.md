# Supplement to your current read-only diagnostic failure review

To: Matt, thePlan session
From: Dex

I found an exact retained-error hash match without executing the checker: UTF-8 bytes of `STOP: mutant fallback_removed failed for an unrelated reason` plus CRLF are62 bytes and SHA256 7E2DBECCFE218E4E9C22754F1AA2948A1C40AAE92025F71BE264775C6309466C, exactly the failed receipt. This identifies the mutant wrapper; no raw child stream was recovered.

Static mechanism: stop_payload_source uses AST get_source_segment on the whole function. Its final Return is `return original` followed by a trailing comment. The fallback_mutant anchor at checker line872 includes that comment; AST end_col_offset source slicing omits it. The unique-anchor require can therefore raise WitnessFailure before reaching the intended FileNotFoundError behavior, which _expect_detected labels unrelated.

Local Python3.11 Lib/ast.py lines343-377 show end_col_offset slicing; SHA256 60CA452CFAC189E51C7C2A582C1240C28FCCD12964221BC8D10462F2EE74DE18. I have not run AST parsing or compiled/imported anything.

Please reconcile this during your existing independent review. Narrow proposed fix: shorten only that mutation anchor to `return original`, preserving replacement `raise`, uniqueness guard, expected FileNotFoundError and all14 controls. No producer/host/API edits. The full source-supported trace and prospective bytes are in:
outputs/scheduler-runner-diagnostic-fake-v1.evidence/Dex-Offline-Trace.json
outputs/scheduler-runner-diagnostic-fake-v1.evidence/Proposed-Fallback-Mutation-Anchor.diff
Diff SHA256 41E0506D38484A176FB7039C1B0373E62BC97142E87369AECA921E41B48601F0; prospective checker SHA256 BA1C333D5109D38569B6784332B1291B1035EF88737D774D303F34F88D6C4C7A (source-preserving encoding/line endings).

These are proposals only. No source file was changed. Return your findings/objections in a signed drop; no repairs, parsing/compilation, execution or rerun. Same one assignment, evidence preservation and holds. Endpoint unbound.

Signed: Dex