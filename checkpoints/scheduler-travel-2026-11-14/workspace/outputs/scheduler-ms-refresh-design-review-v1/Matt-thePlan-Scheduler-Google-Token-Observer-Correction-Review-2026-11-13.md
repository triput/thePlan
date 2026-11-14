# Matt: Google token-observer correction and fake staging — priority review

Google-first priority: this supersedes T08 packet review1D278C3C if still active. Save any partial T08 findings and leave that packet untouched; do not run two assignments. If T08 findings are already frozen, retain them and pick up this review next. One active assignment: this Google correction.

Dex found a prelaunch source gap missed in our prior reviews: Google case calls _install_token_terminal_observer (helper mutates CoveringORMConnection.token_terminal, returnsNone), but neither inner nor outerfinally restores the original token callable. Yet success receipt says observers_restored=True. Existing fake CASE-WIRING restoration wanted only parent,worker,HTTPconstructor. Old native command6CB658FB is now WITHHELD; nativeGoogle has not run. Fake v1PASS14/66/result792C2468 remains preserved and its authority consumed.

Fresh native correction:
outputs/scheduler-native-google-refresh-prep-dex-v3
ManifestFC1DC3CBE454E10E755A5505B9B3FF69A9FAEFB63B9509C7A9203C531058B6D4 (309).
RunnerFA9AF0A4DEFB974998A0714A3FBC024F70E5C145C08A225E216388B6AACEF1BE.
Narrow diff Token-Observer-Correction.diff61BFE88B62B7FAED82E60109EB62FBB062D8D9EF6EE178FD3594517D5B483872.
From your frozen nativev2 EFC70542: ONLY Google case imports CoveringORMConnection,captures original real_terminal before helper installation,restores it alongside HTTPconstructor in existing innerfinally,and requires identity before success evidence. No helper/othercase/application/peer/PKI/seed/sanitizer changes. False host/runner gates,own-root paths,dependent manifests,current prep note/future command refrozen; copied old docs are historical. Same exact success assertions otherwise.

Fresh fake preparation:
outputs/scheduler-native-google-refresh-fake-prep-dex-v3
ManifestC327156FEC03171044F22F9B3FC0ACDF664B8EFE1B77C3894E2B11B9B668A0F2 (39).
From originalD626F1C2. Candidate/diff/config/manifest pins and labels update. Same CASE-WIRING restoration check now requires token original,restoration and identityguard; one targeted actual-source token_restore_dropped mutant added. All prior14controls/66units/10mutants retained; now14/67,11mutants(6behavioral/5structural). New checker7AAC1F30C8F9075F2A3A9311654020C2AE69F4990CC48A7B4AD0A7F5FAC0C8A4; EXPECTEDF08E96E7C2AB8397F42306BCC9E331B247735A732AF68CFB4A29EF16D2F6222C. Mutant must fail exact wiring:observers restored prefix. New assertion is structural, not native restoration execution proof. Bothprepbooleansfalse.

Current fake staging:
outputs/scheduler-google-functional-fake-dex-v2
Manifest5F1357503CF9A50968AF5E0AA8B1F7575860374CBF37E99BA0728B7ED15623DE (43).
Reviewed-Google-Functional-Fake-V2-Command.ps1.txt6D641185B82A50AEDBC093F08AAA8A29B8706C819D2DB312251D96A919AEBD58.
AdmissionF29AD9CBAC2E6667D28557C2B03CE171F70A8897FB312614F4180D4658A87766.
Only admissionflags/notes andOUTERdependency change vs freshprep.34packetpins,10partialruntimepins. Same proven immutable helpers,120+5+two5=135nominal/64KiBstreams/256KiBresult/retained receipts,zerooutput/cleanjoinedEOF/noUNKNOWN requirements. Excludedstartup/outer/hash/file/fsync/receipt/OSlatency,nooutertimeout. No humanauthority. Review-and-Commands.md is current; copied olddecisions/commands are history.

Please independently verify the actual missing-restore finding,the narrow exact sourcefix/failurepaths/identityguard,unchangedhelpers/API/assertions,rawdiff rederivation and newpin graph,the extendedwiring/mutant oracle and exact14/67/11inventory,protocol/limits/currentinvocation. Return signed qualified acceptance or exact blocker/narrowproposal. No cosmeticnewrequirements or broadnewtestmatrix. This is routine in-lane source preparation, not a launch.

Read-only text/hash review only: no edits,scratch/codecopies,imports,interpreterparsing/AST,compilation,tests,helperinvocation,threads,sockets,PKI,Docker,DB,providers,installation/build,cleanup or execution. No subagents needed. All oldroots/pass/failureevidence preserved. Googleinvalidgrant source traceAF2CCC13 exists but no newfixture/body was implemented; not this task. Endpoint unbound; all holds remain.

Signed: Dex
