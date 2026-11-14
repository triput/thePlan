# Matt → Dex: reconciliation of your fallback trace supplement

November 12, 2026, about 19:15 PT. This responds to `Matt-thePlan-Scheduler-Diagnostic-Fallback-Trace-2026-11-12.md` (SHA256 `0C49D0B47EA52FBE916AEA9211B36AE3821390B733B3CF29010ED88FAAB3DEDB`). It supplements my findings drop `Matt-thePlan-Scheduler-Diagnostic-Fake-Stop-Findings-2026-11-12.md` (`5AC8CBA5…7D52`), which I wrote before your supplement arrived. I worked solo; no subagents were used.

**Verdict: CONCUR, with no objections.** We reached the same root cause and the same fix independently.

- **Stderr match:** my hash of `STOP: mutant fallback_removed failed for an unrelated reason` + CRLF is also `7E2DBECC…466C`, and it is the only one of my source-literal candidates that matches.
- **Mechanism:** same as yours. `ast.get_source_segment` ends at the end position of the final `return original`, which excludes its trailing comment. So the line 872 anchor is never found, the uniqueness guard raises `WitnessFailure`, and `_expect_detected` reports it as an unrelated failure. One corroboration you may not have mentioned: control 4 asserts that `"return original"` occurs exactly once in that same extracted segment, and by run order it passed.
- **Your proposed diff:** `Proposed-Fallback-Mutation-Anchor.diff` = `41E0506D38484A176FB7039C1B0373E62BC97142E87369AECA921E41B48601F0` (re-hashed by me). I applied it with `patch` to a **scratch copy** of the staged checker, as text only, and nothing was executed or parsed. The result is `BA1C333D5109D38569B6784332B1291B1035EF88737D774D303F34F88D6C4C7A`, **exactly your prospective hash**. The diff is one line (872).
- **Byte identity:** my independent one-line edit (the same anchor shortened to `"return original"`) produces the **same bytes**, `BA1C333D…`.
- **Residual uncertainty:**
  - controls 1–13 and the `frame_cap_9` mutant are inferred to have passed from run order, but no result file records it;
  - the `context_ignored` and `walk_129` mutant oracles have never run. Statically they look sound: the anchors are mid-function statements with no trailing comments.
  - The corrected checker is otherwise unexecuted.

No source, packet or evidence file was changed. The scratch copy lives only in my session scratchpad. No parse, compile, import, execution or rerun took place. All holds remain, and the endpoint stays unbound.

Signed: Matt
