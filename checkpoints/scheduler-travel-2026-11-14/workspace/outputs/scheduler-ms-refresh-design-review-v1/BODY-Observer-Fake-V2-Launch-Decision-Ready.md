# Corrected BODY observer fake v2 — exact one-shot decision ready

Matt's review 3EC40A2AE1C2FB4AA2A8D7F8488A936EDEF5E3C04D8ED82D524AC67AE55E98C9 is independently reconciled with no static blocker. All 49 staged inputs,32 packet pins and10 partial runtime pins match; result and receipt do not exist. All executable, subject and EXPECTED bytes are unchanged from accepted source EBB3BED6. No v2 run has occurred.

Current exact command file:
C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-native-t04-body-stall-fake-dex-v2\Reviewed-BODY-Observer-Fake-V2-Command.ps1.txt
Command SHA256: BEF8510660BDCF4D13811C6A2C59D75ABD6B9FEC0F26891068D094FAC6003675
Admission SHA256: 3AE7EDC9FFDD84F7FE4FA13270C790250D6000404001D38C60DFE1BAB1FC8B1E
Input-manifest SHA256: 0DB0A2FAD54E9630F9266141943A36A9DD8D1D59E5AC10C01CD71D381456DED9

Scope and bounds are in the packet's Review-and-Commands.md. Exactly13 ordered controls/66 reported predicates/ten mutants (7 behavioral,3 structural). New token observer capture/finally restore/identity predicate and actual-source omission mutant are structural. Prior 13/64/9 PASS remains at its old scope. Token-only identity guard and install-before-try window retained. First execution may expose checker defects; stop without repair or retry.

One local PowerShell/Python outer/launcher/check child and two capture readers.120s collection+one5s owned-child termination/wait+two5s joins=135s nominal. Startup,outer waits,file/hash/fsync/receipt operations and OS latency excluded;no separate outer timeout.64KiB per child stream,256KiB result. Ten-file partial runtime provenance. Retain result/disposition receipts and outer hashes/counts;child streams hash/count-only. Bounded owned-child termination on error,timeout or overflow must be included in approval.

Require exact PASS inventory/mutant oracles,zero child output,clean joined EOF readers and unchanged inputs. Stop failure,mismatch,timeout,unexpected output or framework/retirement UNKNOWN. No retries,repairs,rerun,fallback or extra cleanup. Memory-only dependencies and fixture clocks; stdlib socket/ssl may import without constructing fixture sockets/TLS contexts. No app/vendor imports,PKI,providers,DB,Docker,installation/build or native execution. Only exclusive result/disposition/outer writes. No real210-second deadline,TLS or rollback proof from this fake. Native BODY and its240-second allowance remain separately held. Endpoint unbound;all other holds stay. No authority until Trish explicitly approves this exact invocation.