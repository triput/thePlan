# Dex report-boundary code contribution — review only

Source snapshot: np_runner_entry.py B8E0FAF345C943E25CD85DB3DD20F56B8F6AABDA16565C838B6D62B458823E17 from Jim in-progress prep-v2.
Candidate: payload/fixture/np_runner_entry.py B910EC04CDA020BC68C2FC8A754E2D0D2EC693E4ECF74AAB1CD24D181CB1AFC1.
Exact diff: Proposed-Report-Boundary.diff AA2494B2D20D7DFCDEB36A7448703385A58FF759FDCB3A66B6C638C08AC439AE.

Only the main report-output boundary and terminal __main__ exception emission are changed. Earlier case implementations/registry/settings/seeding/peer code are preserved byte-for-byte in the prefix. Jim's workspace is untouched.

The proposed code restores both original streams in finally around suite execution, keeps console content hash-only, emits one byte-bounded sanitized report with top-level suite fields and collected case results, and reports only STOP plus exception class rather than a raw traceback/message at the entry boundary. It records executed=true as a runtime observation; human launch authorization stays with the independent host approval ledger rather than being invented by this runner.

This contribution does not fix or accept the current guessed case interfaces, the token-key sanitizer, runtime/config observation distinction or the host's final STOP parser. Jim must reconcile the patch to final source/schema, implement those other review items and add fake producer/consumer/stream-restoration controls in the existing checker role. Do not blindly apply if the source hash or main block changed. Preserve the exact original and this proposal; adapt in the next fresh successor under the existing16-role lane.

No imports, compilation, tests, execution, helper invocation, sockets, PKI or native launch were performed. The patch is unverified source preparation, not PASS or a launch-ready packet. No user decision is requested for this already-authorized source contribution. Endpoint unbound; all execution holds remain.
— Dex