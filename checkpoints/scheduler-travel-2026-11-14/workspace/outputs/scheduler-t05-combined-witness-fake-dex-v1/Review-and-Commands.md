# T05 combined truncated-body/invalid-JSON witness — execution HELD

Only Reviewed-T05-Combined-Command.ps1.txt in this root is the proposed future invocation. Copied Launch-Decision.md,Future-Command-HELD.ps1.txt and Source-Input-Manifest are historical. Machine admission flags are true solely for reviewed staging;no human execution permission is granted. This is separate from the existing peer-close fake card and cannot run on that approval.

## Independent review and corrected source expectation

Matt handback9FFF2CA9AF72F22E7BC3F2266F3098E6B757560A55B595BA2EAB5E555DB8D849 and all15 pins match. The13 source inputs,10 contained packet pins and10 runtime pins match. All executable/subject/oracle bytes remain unchanged from Matt's frozen preparation7BA33B54D525A6CA9FC77BCEA805F35D786CEE5DC409CD8D885FCF0C1EC87052;only two admission flags and the dependent outer hash change here.

Dex's assignment incorrectly expected the later fixed-length completion gate to raise CoveringTransportRefused on a short body. Actual current _GuardedHTTPResponse.read first raises http.client.IncompleteRead when EOF arrives with a remaining fixed length. The later completion gate and JSON decoder are not reached. Matt correctly designed the direct witness around that actual class/site and counts removing only the later gate as an equivalent mutant,not a detected defect. Layered mutants demonstrate the separate later gate when the read guard is deliberately bypassed. No application correction is proposed or needed to make an expectation pass.

One metadata correction is retained externally:Trish already approved framing compatibility policyAEAE5343 via call_f23e9cdb68d44ae0a628c63d2f096277. Unchanged source comments or copied documents saying REVIEW CANDIDATE are historical implementation labels,not a reopened policy decision. They confer no runtime proof or activation authority.

## Exact held command and pins

```powershell
& 'C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-t05-combined-witness-fake-dex-v1\packet\Invoke-Fake.ps1' -AdmissionSHA256 'D07EE140C235B0E0024ECDFD0434C7E33BB174F6A41200D4C3F813B5A7FD632A'
```

CommandF03685858A7F098405E4A1726B52A9A20CE4B47F7DCF5211ECDF6D6B2EFEDB3E;VERIFICATION D07EE140C235B0E0024ECDFD0434C7E33BB174F6A41200D4C3F813B5A7FD632A;OUTER4BD7DDC0D495019F79EA0F91C9C196A4E4F084EA2FBE63A06A780C6B6241A3A8;checkerCBC7DC4CFD14C64DF30E75AD342981E6B478DD14DEF99D9587168051840680BF;EXPECTED F98EA54B7E24C9D905B643700CF79C9BED57D3FC8DBA4B31654B68A915F8EB13.

WrapperAE84E632,outer7DCA32E2 and launcherD22C37E3 are byte-identical to the proven roles. Current parent Input-Manifest excludes itself and covers all final input bytes;its exact hash accompanies any later execution card. Source-Input-Manifest is historical.

## Finite proof and exact expected outcomes

Eleven ordered controls/40 reported predicates include raw source lineage,runtime provenance,source structure,four body scenarios,two independent refusal layers,ordered inventory rejection and three targeted actual-source mutants. No Python import,AST parse,compilation,test or helper invocation has run during preparation/review;syntax and behavior remain unexecuted.

Actual whole pinned policy and HTTP transport modules execute only in a future approved checker inside an exact fake sys.modules sandbox,restored after each scenario. Real host http.client.HTTPResponse under the actual guarded subclass parses synthetic byte responses. Actual json.loads runs through a delegating spy;the actual completion gate is counted through a delegating wrapper. Fake transport prevents real JoinedTLS construction. No actual app/vendor package is imported from disk;fake app/budget/target/httpx modules supply bounded seams. JoinedTLS source is structurally read only.

- Short valid JSON:declared20,12body bytes;IncompleteRead(partial=b'',expected=8) at actual guarded read,json0/gate0.
- Short invalid JSON:declared5,body'{';IncompleteRead(partial=b'',expected=4) at guarded read,json0/gate0. This is the direct T05-SHORT-LENGTH-INVALID-JSON witness.
- Complete invalid JSON:declared1,body'{';gate once before decoder once;exact JSONDecodeError object with pos1 propagates and is not called a framing refusal.
- Complete valid JSON:declared12,exact JSON body;typed fake response,exact bytes/headers/request echo,gate then decoder then transport retirement.

Transport opens/closes once and identity/byte counters are checked. Removing the read guard exposes the later completion gate;removing only the gate leaves the first refusal intact and is explicitly equivalent. Three mutants bypass both layers,invert later remaining-length comparison under read bypass,and weaken it under read bypass. Each must be detected by its exact decoder-invoked oracle prefix;unrelated import,anchor,cleanup or extraction failures cannot count. Ordered inventory rejects dropped,reordered or padded cases. Serialized result uses sort_keys;execution order is enforced before serialization.

## Runtime and side effects

Ten admission runtime pins cover Python executable,python311.dll,http/client.py,json initializer/decoder/scanner,email feedparser/parser,socket.py and ssl.py. The checker rehashes loaded parser/JSON modules. This is PARTIAL runtime provenance:_socket.pyd,_ssl.pyd,OpenSSL DLLs and remaining stdlib are not locked. Importing actual http.client transitively imports stdlib socket and ssl;the future run explicitly includes those module imports. No socket,SSL context,TLS connection,PKI or network is constructed or used.

One local PowerShell/Python outer/launcher/checker chain,one checker child,two capture readers.120s child collection+at most one5s owned-child kill/wait+two5s reader joins=135s nominal,excluding construction/startup,outer waits,file/hash/fsync/receipt work and process/OS latency;no separate outer timeout.64KiB cap per child stream,256KiB result. Retain exclusive result/disposition receipts and outer hashes/counts;child streams hash/count-only. Bounded owned-check-child termination on error/timeout/overflow included.

Require exact11top-level PASS/40predicates,three targeted mutants detected,zero child output,exit0,clean joined EOF readers and known retirement. Stop on failure,mismatch,timeout,unexpected output or framework/retirement UNKNOWN. No retries,repairs,rerun,fallback or extra cleanup. No real app/vendor imports,sockets,TLS,PKI,providers,database,Docker,installation/build or native launch.

This proves finite current framing source under the HOST parser only;not captured-native parser behavior,native orderly-versus-abrupt closure,positive close-delimited native support or fullT05/family closure. Peer-close source/evidence and previous native failure/cleanup evidence are preserved. Endpoint unbound;all other holds stay.
