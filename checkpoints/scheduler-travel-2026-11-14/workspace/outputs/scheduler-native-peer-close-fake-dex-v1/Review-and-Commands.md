# Peer-close focused fake verification — reviewed staging, execution HELD

Only Reviewed-Peer-Close-Command.ps1.txt in THIS root is the proposed invocation. Copied Launch-Decision.md,Future-Command-HELD.ps1.txt and Source-Input-Manifest.sha256 are historical preparation references. Current two admission flags are true solely for reviewed staging;they grant no human permission. Explicit Trish one-shot approval is required before invocation.

## Reviewed change and independent evidence

Matt's signed handback1C5A155A4971D146D8C4AA08DF2A69AA4AB383F147C9BD2C461ADC5236AC4DD2 and all24 handoff pins match. Native preparation manifests282parent/269nested/257payload and fake source12inputs match. Compared with the278-input observer preparation,the native successor changes exactly peer,dependent payload/nested manifests and two host configurations. All234 application files,observer runner341074AE,operator5A8A04B6,host helper7F7EA820 and other executables are unchanged. Native launch flags remain false.

Dex independently rederived the sole peer correction from the unique raw-text anchor:5568AF73DD42FEB5B8E2FE4D723AD4FB0339CBF4B889F5472995ABC628F72A55 ->17EA148E6DE9E30485992FC49C310975076F5F4A71AB3AA9441B3B63C1ADA039. Diff023303AC81AC8F3F3460CBDE9E2AFAFFB4A3EA85D97FE547AD5C78E60B54B30D changes only orderly-close handler ssl.SSLError to OSError. Exact prior native peer failure remains a hypothesis;no source or fake claim substitutes for native proof.

The current fake staging copies only12 source-manifest-listed inputs from scheduler-native-peer-close-fake-prep-matt-v1,manifest52D24FDDBDD59E00DDCAB8C60E28C36821D3E1870517288CF80E2C337ECC2639. Executables,subjects,EXPECTED and all11 controls/35 reported predicates/four mutants are byte-identical. Only two admission booleans and the dependent outer hash changed. Source preparation documents/labels remain preserved lineage. No parser,compile,test or helper invocation has run during this review.

## Exact proposed invocation and pins

```powershell
& 'C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-native-peer-close-fake-dex-v1\packet\Invoke-Fake.ps1' -AdmissionSHA256 '4104D6EBCEB4BB3DC4CFDC17C2905E2BDB4FA56A0B9E30619317DC6462589B9B'
```

- Reviewed command SHA256:8B44B8BC0277A70A2E9B739C0DBE0BC840B7F63DB62E89B5DAB8D7C0DDD008C6.
- VERIFICATION admission:4104D6EBCEB4BB3DC4CFDC17C2905E2BDB4FA56A0B9E30619317DC6462589B9B.
- OUTER admission:9C7024D05FC1D87B2D17619586A33776B73D894CE6B8974B8AC5C28849935ED7.
- Checker:CE60B3D3E46E7E41EFD712A9E19CDC672605A36DF45C5B0A7B1C4CC9784F7184.
- EXPECTED:780456E21BF45BC378D3A1053842042BF9344F628E839F6488C57D991A0402C5.
- Wrapper AE84E6325E7B932303B21D6F0A0FED788A717A28631C3577DAF860C6EFC4FEB7,outer7DCA32E2DEB3A1CFF6B8A7655D8BA72A1284D472C306E7BFDE505502F6E018FB,launcherD22C37E36E5D333C087C8EE80B6936756C69F7D369369C66F8E0FFE6906EBD07 unchanged.
- Python311 interpreter:5F7B89A612C9B8AF1D6456CDFCD1DBE5CA630849E79AEBCED9BEE9A6694952EC. Runtime provenance is interpreter-only,not a standard-library/DLL/environment lock.

Parent Input-Manifest.sha256 is the current complete input inventory,excluding itself;Source-Input-Manifest is historical. The VERIFICATION admission pins9 contained packet files plus one interpreter;OUTER pins launcher/checker/EXPECTED,with no cyclic back-reference. Current manifest hash accompanies the separate approval card.

## Reviewed finite proof surface

Eleven ordered controls cover raw subject pins,literal diff,unchanged definitions/lifecycle field names,unwrap success,source-versus-candidate reset/broken-pipe/timeout handling,already tolerated SSL errors,non-OSError exact propagation,existing close-error guards,unchanged abrupt/normal branch behavior,two-connection composition and four targeted actual-source mutants. EXPECTED fixes35 reported predicates,including singleton controls. Nested cases are checked in order before sort_keys result serialization;on-disk object order is not claimed as execution order.

The actual extracted execute_script/_run_one_connection/_close_connection and related methods drive fake listener/client/TLS bytes. Certificate loading is replaced with a fake server context;ssl/socket/select namespaces are fake. threading.Event is synchronization data;the composition creates no threads or sockets. The source's propagating reset closes TLS in both nested finally paths and skips the attempted note;the candidate continues to the second connection. Non-OSError must still escape as the identical object. A marker says attempted TLS closure,not clean native closure.

Four mutants:revert tolerance,broaden to Exception,remove finally close,and drop listener retention. Each must fail through its exact targeted WitnessFailure prefix;unrelated exceptions or anchor failures cannot count as detection. Source text/mutation indentation and extraction globals were reviewed statically. Syntax and behavior remain unexecuted until approval.

This finite fake proves the extracted fixture mechanism only. Actual native cause,real TLS shutdown/socket behavior and the rest of the native Microsoft assessment remain open. No full transport requirement family is closed by this run.

## Process/output/retirement and stop conditions

One local PowerShell/Python outer-admission/launcher/checker chain,one checker child,two capture-reader threads.120s child collection plus at most one5s owned-child kill/wait and two5s reader joins=135s nominal. Construction/startup,outer waits,file/hash/fsync/receipt work and process/OS latency excluded;no separate outer timeout.64KiB cap per child stream,256KiB result. Composition uses a1s fake accept deadline;it adds no live sockets.

Retain exclusive result/disposition receipts and outer output hashes/counts. Child streams hash/count-only. Exact11top-level PASS/35predicates/four detected targeted mutants,zero child output,exit0,clean joined EOF readers and known retirement required. Includes bounded owned-check-child termination on error/timeout/overflow. Stop on failure,mismatch,timeout,unexpected output or UNKNOWN. No retries,repairs,rerun,fallback or extra cleanup.

No app/vendor imports,real sockets,real SSL/PKI,providers,database,Docker,installation/build or native run. Earlier native failure and verified cleanup evidence remain intact. Native rerun remains separately held;endpoint unbound,all other holds stay.
