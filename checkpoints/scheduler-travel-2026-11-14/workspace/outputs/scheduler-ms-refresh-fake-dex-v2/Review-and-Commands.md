# Microsoft refresh focused fake verification — reviewed staging, execution HELD

Only this root's `Reviewed-MS-Refresh-Command.ps1.txt` is the current proposed invocation. The copied Launch-Decision.md, Future-Command-HELD.ps1.txt and Source-Input-Manifest.sha256 describe Matt's preserved source preparation; they are historical for invocation. True machine admission flags do not authorize execution. Endpoint unbound.

## Review and integrity

Dex independently reviewed the five fixture deltas and complete focused checker against scope EAAFA222DF4E043135EBBA8E2306C5C5F58D8A93929949A950B49CCD1DA1488A, verified the original27 handoff pins and278 fixture inputs, and compared all274 predecessor inputs: exactly ten declared files differ and all234 application files remain unchanged. The fixture is frozen in scheduler-ms-refresh-prep-matt-v1.

The first fake preparation was never run. Static review caught its LF-only guard rejecting the unchanged CRLF Microsoft source. Matt accepted and returned a fresh v2. Dex verified12 handoff pins,21 source inputs and the exact single checker line correction. The checker now permits CRLF pairs but still refuses bare CR, with raw hashes and original AST input unchanged. Production microsoft_calendar.py remains6A52B10FE43A7781718BAE0AC69DA91CA7FB3B48B9534EB18D5C9C80E75DD6EF,2252 CRLF pairs and no bare CR. No normalized application copy was introduced.

This staging copies only Matt's21 manifest-listed files plus the source manifest. All executable,subject and oracle bytes remain identical to his frozen v2. Only the two admission JSON documents change: machine flags,truthful staging notes,and the dependent OUTER pin.18 contained packet pins and one interpreter pin are independently checked. The final Input-Manifest.sha256 covers all current staging files except itself,relative to this root. Source-Input-Manifest.sha256 is the original21-file source inventory,not the current staging admission.

- Checker:6F4D83C04640E596A806E19FFCECDA026662CEB51B6B138C3C79EFBDD1FD2971.
- Wrapper:AE84E6325E7B932303B21D6F0A0FED788A717A28631C3577DAF860C6EFC4FEB7.
- Outer executable:7DCA32E2DEB3A1CFF6B8A7655D8BA72A1284D472C306E7BFDE505502F6E018FB.
- Launcher:D22C37E36E5D333C087C8EE80B6936756C69F7D369369C66F8E0FFE6906EBD07.
- Expected inventory:FD98745D2B83A2FD0C9233C16B050BDC5A1C719FA572793D99A95949B2EBDB71.
- Staged OUTER JSON:0CD0706B9CD62B1F8697158547C0DF633DD2BAAD3C140D1BB0BFC6D62CE03645.
- Staged VERIFICATION JSON:EB3CD87D63CC14FB9E2E2C5E16859533FC10FA5D12B300BB63CBF990320C1F50.
- Command-file:E7473EEC6A99FDB41FCCC03C88857D6596A0FC1CE138D03648CA98304C044914.
- Interpreter executable:5F7B89A612C9B8AF1D6456CDFCD1DBE5CA630849E79AEBCED9BEE9A6694952EC. This is interpreter-only provenance; standard library,DLLs and environment are not fully pinned.

## Exact proposed command

```powershell
& 'C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-ms-refresh-fake-dex-v2\packet\Invoke-Fake.ps1' -AdmissionSHA256 'EB3CD87D63CC14FB9E2E2C5E16859533FC10FA5D12B300BB63CBF990320C1F50'
```

## Scope and acceptance

One local PowerShell/isolated Python outer-admission/launcher/checker chain,one checker child and two capture-reader threads. The checker executes pinned stdlib-only fixture modules and extracted definitions using in-memory fake app models,crypto,HTTPSPeer and DB/session objects. Imports of app dependencies are supplied as temporary fake modules and restored; no real application/vendor package imports. Production URL builder is extracted from hash-pinned text. No real sockets,TLS,PKI,providers,database,Docker,installation,build or native run.

Exactly ten ordered controls: SUBJECT-PINS;NONEXPIRED-AND-DIAGNOSTIC-PRESERVED;TENANT-PATH-AGREEMENT;OAUTH-ROUTE-TABLE;REFRESH-INVENTORY-ORDER;SEMANTIC-PERSISTENCE-ADMISSION;SECRET-EXCLUSION-PROJECTION;REGISTRY-MAPPING;REFRESH-BODY-SHAPE;ACTUAL-SOURCE-MUTANTS. They comprise raw pin/text identity,actual helper behavior with fakes,two structural source controls,and four actual-source mutants. The latter target ciphertext-only persistence,legacy token path,missing OAuth script and graph-only routes. The semantic cases explicitly refuse changed ciphertext with unchanged plaintext,wrong values,missing rotation and insufficient expiry.

Require exact inventory and proof-layer labels,all ten PASS,failed0,exit0,zero child output,clean EOF/joined readers and known retirement. Reconcile the24 preserved text-identity cases,11 semantic cases and four targeted mutants independently against the frozen inventory/source. The checker/result's v1 PACKET_NAME intentionally records lineage;the current wrapper path and admission hashes identify this v2 execution. Do not confuse that label with execution of the old packet. Require all postpins unchanged and retain result/disposition receipt plus outer output hashes/counts. No target Python syntax or behavior check has yet run.

Limits:120s checker-child collection,at most one5s owned-child kill/wait,and two5s reader joins=135s nominal collection/retirement. Construction/startup,outer waits,file/hash/fsync/receipt work and process/OS latency are excluded;no separate outer timeout.64KiB per child stream,256KiB result. Child streams retained as hashes/counts only; no raw child logs. Includes bounded owned-check-child termination on error,timeout or overflow. Same preserved launcher behavior;no new lifecycle mechanism.

Stop on failure,mismatch,timeout,unexpected output or UNKNOWN. Named negative controls catch their precise expected fake exceptions;they do not authorize an unexpected framework or retirement UNKNOWN. No retries,repairs,rerun,fallback or extra cleanup.

Even PASS establishes only these finite helper/source properties. It does not prove native OAuth/TLS/persistence/Fernet,one live peer serving both hostnames,second-target native rollback,full refresh-body behavior or T06/all76 closure. The separate native diagnostic attempt STOPped at its non200 HTTP-status check and was cleaned up under separate approval;the actual status/cause remain unknown. MS refresh native launch stays held while Matt traces that shared harness. This fake verification does not repair or rerun the stopped native packet. Original packets and all failed evidence stay preserved. No product endpoint binding,live credentials,provider operations or activation authority is added.
