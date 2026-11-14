# Framing acknowledgment fake v4 — Dex narrow follow-through

Prepared under the approved three-application-file/four-verification-role workspace lane. No execution. Jim's immutable v3 TIP is BD52764433172FD2FA54938C8DCA4C142C2E626DB6723AE095C2B02621773209. Its v2 pin/schema/caller-label corrections are carried forward. V3 still compares policy_pending metadata as absent runtime data before emission, and its Commands-Held file performs only hash checks with the wrapper invocation commented out. Dex prepared these two small corrections for speed; Jim's independent review is required before launch review.

## Exact changes

1. Check source: delete only the single policy_pending entry from assert_match's flat runtime-field whitelist. Measured outcomes/exceptions/close counters remain asserted; emit_wire_candidate continues to emit the declared policy label as metadata, and the launcher still checks its exact nested output predicate. Proposed-Check-Fix.diff SHA25686EDAB63C424856C6305C244E97EE9081F0D56A22653638A011D8776F270704F. Checker SHA2561A422FB3D669B66C2FF590C4F74F8942D23DB3811087D0E3E7B8620896477080.

2. Operator command data: Commands.ps1.txt now has an exact absolute wrapper path, exact wrapper/admission guards and the actual held wrapper invocation. It is not invoked during preparation. No fifth executable role is introduced. Wrapper/launcher/outer role code is unchanged from Jim v3.

3. Dependent data freeze: rebuild PACKET-SHA256SUMS/OUTER-ADMISSION and the root admission. Root admission now hashes all537 actual packet files before Python, rather than v3's75 listed inputs; all468 application bytes remain identical to v3. The unused stale verify/VERIFICATION-ADMISSION.json mirror is not copied; the root admission is authoritative. Runtime inventory combines already reviewed host pins with the header parser source dependencies, deduplicated by resolved absolute path:21 partial provenance pins. No installed runtime or dependency is changed, and no complete transitive stdlib/DLL closure is claimed.

EXPECTED.json is byte-identical to v3 (08C2367D886205C33100C8BEC6C95E5502D7AA75622B4145D77D076960F9FEA2); all73 semantic control oracles remain unchanged. All original/candidate application files are preserved. Port-zero is not merged. The accepted header policy remains in force; native orderly-versus-abrupt TLS and actual candidate owning-caller proof remain open as declared by v3. Historical caller evidence is not a new candidate owning-call PASS.

## Exact held command and pins

Commands.ps1.txt SHA256 C2D8D18660B734EB3A6FAC9BDFACC1847C86A007C11BC81ECBEFFD1EE11FC66C.
Root VERIFICATION-ADMISSION.json SHA256 4BE04F87B1AD858C05DCA789DEF05B602E80DF33274E7D19A9BB4E985B865D85.
Invoke-Verification.ps1 SHA2560477912DBEB37067DC5CB49975A91FD1A666BD9893D166385D833D4D4E24AABA.

No launch card is ready until Jim's independent review is reconciled. Static preparation checked537 packet pins,21 runtime pins, outer subjects and468 unchanged application files; no Python/AST parsing, compilation, imports or verification helpers were invoked.

## Proposed future verification boundary (still held)

One pinned Python outer/launcher/check chain and two capture readers;73 byte-fake controls. 30s collection +5s owned-check-child kill/wait +two5s reader joins =45s nominal collection/retirement; outer wait, file/hash/receipt work and process/OS latency excluded, no separate outer timeout. Capture64KiB per stream,256KiB result. Bounded owned-child retirement on timeout/error/overflow; exclusive evidence writes. Stop on failure, mismatch, timeout, unexpected output or UNKNOWN; no retries, repairs, fallback or additional cleanup.

No real sockets, TLS/PKI operations, providers, database, Docker, installation, native run, endpoint binding or new permissions. No application/vendor package imports; selected application definitions remain data until a separately authorized check extracts them. Endpoint unbound; all other holds stay.