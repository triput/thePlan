# Worker-exception observer fake verification — Dex v3 staging, execution HELD

Use only this root's Reviewed-Worker-Diagnostic-Command.ps1.txt for any later reviewed invocation. Copied Launch-Decision.md,Future-Command-HELD.ps1.txt and Source-Input-Manifest.sha256 describe Matt's original preparation and are historical for invocation. True machine flags are scaffolding,not human execution permission. Endpoint unbound.

## Source and independent review status

The frozen native observer preparation remains at outputs/scheduler-native-provider-worker-diagnostic-prep-matt-v1,parent manifest9DCAA6FF06FF890E53AB867ECFDFA5617115A0B684762304E49AF6BE07F00A68,278 inputs. Its runner341074AEF88A9E438C0F488E6231572103E694FB5EB81D6F3AC6BD30517CD645 adds a one-object worker exception observer,identity-preserving delegation/bare rethrow,unconditional exact restoration and optional chaining on the existing non200 assertion. All234 application files,the diagnostic producer,host validator and other executable roles stay unchanged. Dex read the exact runner diff and complete focused checker and verified23 original handoff/278 native/15 fake inputs against the accepted F6F15372 preparation scope. This is static review,not native proof.

Matt's first checker contained five excess parentheses in its mutant dictionary. No run occurred. His fresh v2 implements exactly the five-character correction proposed by Dex.12 handoff pins match;checkerC283F512F15FEFDD3CCAD3F1525229C350035BEB564FB77DE542BCA2C73397ED is the expected exact corrected source.

Further review found B2 already present in v1 and missed in Dex's first pass:check_restore_wiring builds fn through one ast.parse,then obtains node through observer_try's separate ast.parse,but tests `n is node` across these distinct trees. No Try node from the second parse belongs by object identity to the first tree,so the enclosing-try selection would fail before the restoration controls. This conclusion is from source inspection;no target parser,compiler or check has run.

Dex prepared this fresh v3 under approved same-contract checker authoring authority. The only code change is line828:

```diff
-    outer = _single([s for s in fn.body if isinstance(s, ast.Try) and any(n is node for n in ast.walk(s))],
+    outer = _single([s for s in fn.body if isinstance(s, ast.Try) and any(ast.dump(n) == ast.dump(node) for n in ast.walk(s))],
```

Structural equality identifies the selected try across separate parses. The unique observer-try selection and every surrounding restoration/wiring assertion remain intact. Runtime identity checks for arguments,results,exception objects and the original callable remain unchanged;this correction applies only to AST membership. B2-AST-Membership-Correction.diff and Dex-Staging-Receipt.json pin the exact change. All ten control IDs,47 nested predicates,five targeted mutants,all six subject bytes,the expected inventory and the three generic helper executables remain unchanged from Matt v2.

Independent Matt review of this final staged correction/command/admission is required before an execution card. Its findings will be retained outside the frozen staging root. No reviewer acceptance grants execution permission.

## Exact proposed invocation and integrity

```powershell
& 'C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-native-worker-diagnostic-fake-dex-v3\packet\Invoke-Fake.ps1' -AdmissionSHA256 '406867681EE19E84FAE75D17651451CD655C553DA0EA3FFFF07A0E42FE0E2436'
```

- Command-file433BD07C5FAF5EA81A36F2478CBFAD9D563BDA34364D307A3987A376C4A81E70.
- VERIFICATION JSON406867681EE19E84FAE75D17651451CD655C553DA0EA3FFFF07A0E42FE0E2436.
- OUTER JSONE4E98EC3F7F165E7A903CD9CF545BB53EEDFE3AACCC637C394E4C406C0B27A91.
- Corrected checkerC3C4430288AB49E6B04ADF6FAA4F8D71253B854B6A8BACBD46F12141F147AF37.
- One-line diffE76F706B54C97B568A779FE51EB5158F28FFF4AE8523E90553ABF6472812B737.
- Source manifestB9B6A039B210FFD7A78A1AF44B03B2380DACB80CCF2EF5E4486DC0238777647B,15 entries.
- WrapperAE84E6325E7B932303B21D6F0A0FED788A717A28631C3577DAF860C6EFC4FEB7;outer executable7DCA32E2DEB3A1CFF6B8A7655D8BA72A1284D472C306E7BFDE505502F6E018FB;launcherD22C37E36E5D333C087C8EE80B6936756C69F7D369369C66F8E0FFE6906EBD07,all reused unchanged.
- Expected inventoryAEC7B0DB1909C1C269840EA44F72336A7EDA1DE13B5EEF567218BBD498B95FA9.
-12 contained packet pins and one interpreter executable pin5F7B89A612C9B8AF1D6456CDFCD1DBE5CA630849E79AEBCED9BEE9A6694952EC. Interpreter-only provenance does not lock all standard library,DLL or environment bytes.

The final Input-Manifest.sha256 covers all current staging files except itself,relative to this root. Source-Input-Manifest.sha256 covers the unmodified source preparation;it is not the current invocation inventory. Checker/result/EXPECTED intentionally keep their v1 lineage labels;the current exact absolute command and admission hashes identify v3 staging.

## Scope,limits and acceptance

One local PowerShell/isolated Python outer-admission/launcher/checker chain,one checker child,two capture-reader threads. Actual selected source is extracted into fake module/filesystem/traceback contexts;no real app/vendor package imports,sockets,TLS,PKI,providers,database,Docker,installation,build or native execution. The producer and host validator see fake manifest-owned paths/bytes;real object chains are exercised with synthetic exception classes. A control name containing end-to-end refers to this extracted fake composition,not the live native host path.

Exactly ten ordered controls:SUBJECT-PINS;DIFF-REDERIVATION;PRESERVED-OUTSIDE-CHANGE;PRODUCTION-BOUNDARY-STRUCTURE;OBSERVER-SUCCESS-IDENTITY;OBSERVER-EXCEPTION-IDENTITY;RESTORE-WIRING;CHAINING-WIRING;PRODUCER-HOST-END-TO-END;ACTUAL-SOURCE-MUTANTS. Require all PASS,exact47 nested inventory,preserved argument/result/exception/callable identity,one-object capture,bare rethrow,exact restoration,unchained fallback and unchanged status200 behavior. Five mutants must each be detected by its targeted oracle,not a generic unrelated failure. Require zero child streams,exit0,clean joined EOF readers,known retirement,exclusive result/receipt and unchanged postpins.

120s checker-child collection +at most one5s owned-child kill/wait +two5s reader joins=135s nominal collection/retirement. Construction/startup,outer waits,file/hash/fsync/receipt work and OS latency excluded;no separate outer timeout.64KiB per child stream,256KiB result. Child streams hash/count-only;retain disposition/result receipts and outer hashes/counts. Includes bounded owned-check-child termination on error,timeout or overflow. Stop on failure,mismatch,timeout,unexpected output or UNKNOWN. No retries,repairs,rerun,fallback or extra cleanup.

The existing diagnostic bounds remain3 exceptions,8 newest owned locations per exception,128 traversed nodes and4096-byte envelope;no messages,locals,SQL,bodies,keys,credentials,status/code values or unowned source text are exported. This check does not establish native execution of the observer,actual production fault classes/frames,worker thread hand-off or the original non200 cause. Exceptions before run_bounded_domain are not captured by this observer. The stopped native attempt and approved cleanup stay preserved. Native rerun and MS refresh remain separately held. All76 requirements stay open where evidence is incomplete;this verification adds no live-provider,endpoint-binding or activation authority.
