# C06 corrected2 frozen review

TIP SHA25691E699ED7A490D0A070A4D44EB33F3B62CD5D1C9D83F55A0D77634B9D62DC74A verified stable during review. All20 artifact,268 payload and6 verification manifest entries match. All269 payload files match the held workspace staging copy at scheduler-native-i01-i02-v2/payload, so no new fixture source changes were introduced. No execution occurred.

The accepted-client context-manager fake and retirement observation, post-entry setup clock injection, held-reader primary expectations and static root labeling are now present. These close the corresponding corrected1 static findings, subject to later verification.

Disposition: REVISE CHECK ONLY; no launch card. Two source-supported issues remain:

- The shared-deadline upper bound adds gen_s30 to C06_DISCLOSED_RETIREMENT_SECONDS45, although that constant is the total collection/retirement budget. Assert the total45 directly; retain separate18-second remaining-generation witness after12 seconds of setup.
- The Windows check injects the host signal module into Linux fixture helpers and references signal.SIGKILL. Use a narrow fake Linux signal namespace consistently; do not probe or send real signals during fake checks. Real Linux fixture bytes remain unchanged.

Dex sent these before/around the freeze at Slack1794376874.594979 and1794377131.049509, including instructions to preserve any frozen corrected2 and use a fresh copy. Continue the same one active check-only authoring assignment, not a new source scope or request for Trish approval.

No tests, imports, PKI, sockets, child launches, Docker or native execution were performed. The original v1/corrected1/corrected2 snapshots, passing fake22/nativev9 evidence and blocked draft remain authoritative. The full integration/transport goal is incomplete.