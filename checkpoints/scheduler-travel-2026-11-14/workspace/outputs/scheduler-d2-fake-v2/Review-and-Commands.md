# D2 fake-only v2 — reviewed successor, execution held

Dex, November 11, 2026. Trish approved fresh-copy preparation of the narrow CRLF check correction. Preparation is complete. No successor check/import/compilation/verification/run has occurred. One later execution requires separate approval.

## Exact change and retained evidence

Only two executable lines change, inside extract_symbols: its guard now permits CRLF pairs and refuses bare CR, with a matching error message. The original decoded text still goes unchanged to ast.parse; raw bytes still supply source hashes. The mutation-source loader and all application code remain unchanged. Exact approved check diff SHA256: `FE65B6B54A9FE2B3412E25515F3873C1E1047C8D3C6C08144E6D63CDB76EF659` (Approved-Check-Fix.diff).

All252 successor packet files are pinned. Of those,241 match the predecessor byte for byte;11 differ: the check file and10 metadata/review/hash files. All238 payload files, including234 API files and three original source witnesses, remain byte-identical. All52 ordered control IDs, their full oracle objects, extraction symbols, source hashes and runtime pins are unchanged. The host wrapper, outer Python admission script and bounded launcher are byte-identical. Static-Reconciliation.json records the independent comparisons; SHA256 `18B25521877F929CA49935E9D598F81B10F8A5F65D64730C54D2E26676D037CF`.

The stopped v1 result (`B9E06AEE93AD981D0AFD4FC7CB05E03FD40D9FFC259364982351804677896ED7`) and launch receipt (`AC36E46D7A772E9D897673BBE05768BB619C3658F29CF475FA5295410E201D90`) are unchanged in the predecessor packet. They are not copied as successor outputs. V1's one-shot authority was consumed; it does not authorize this run.

This verification covers the same52 fake-only path-admission controls:41 core functional, three additional context refusal, three mutation and five inventory controls. It does not close full T01–T08 transport proof, real provider/TLS/native behavior or target authorization.

## Pins and exact held command

| Subject | SHA256 |
| --- | --- |
| Invoke-Verification.ps1 | B72C1CBCAC9229F47FBB5E7A88462BB3D0C02DC8FA6B3DE163EE8FFECB195CA7 |
| VERIFICATION-ADMISSION.json | D7F088CBBCCDA3C32860F14AED475824BE260B70E9389289580B787C0C4A9591 |
| packet/TIP-FREEZE.json | 863BE8CEFDAC644C908E318BB4301DD1B1CFCC921DC04BAFBA226C5793486C32 |
| check_d2_path_admission_fake.py | 65AA2582C9EB6636BDFCE4B9AD6AE16D6A32910CFE5008D54C336C3C1ECD1286 |
| INPUT-MANIFEST.json | 685C3B7F02B2E704985B901D0C286535C0CC086D3825454495242050ED9C64D4 |
| EXPECTED-OUTPUT.json | F3ADF7346FCB2CD7BD3D1C176A21D5446AA9C72D25D81AA6170F5CF756E0E692 |
| OUTER-ADMISSION.json | B6ABBA75F77B8225EF90C2CD284B4DDE0B63E300AE551E0D8CBA0A2DF6D567EC |

The external admission pins all252 packet files and12 runtime provenance files before Python starts. These are explicit provenance pins, not a claim to inventory every runtime dependency.

Held PowerShell invocation, once only after separate approval:

```powershell
$d2Wrapper = 'C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-d2-fake-v2\Invoke-Verification.ps1'
if ((Get-FileHash -LiteralPath $d2Wrapper -Algorithm SHA256).Hash -ne 'B72C1CBCAC9229F47FBB5E7A88462BB3D0C02DC8FA6B3DE163EE8FFECB195CA7') { throw 'STOP: wrapper hash mismatch' }
& $d2Wrapper -AdmissionSHA256 'D7F088CBBCCDA3C32860F14AED475824BE260B70E9389289580B787C0C4A9591'
```

## Scope, limits and stop conditions

Same pinned Python `-I -S -B` chain: host admission → Python outer admission → local Python launcher → one check child and two capture-reader threads. Extracted definitions use fake dependencies/transports. No application/vendor package imports, real sockets, PKI, provider traffic, database, Docker, installation or native launch.

30-second child wait +5-second child kill/wait +two5-second reader joins =45 seconds nominal collection/retirement, excluding outer admission/hash/file operations and process/OS latency. Captures:64 KiB stdout,64 KiB stderr,256 KiB result. Bounded owned-check-child termination on timeout/error/overflow is included. Retain result, launch receipt and tool/approval evidence; independently reconcile actual ordered controls, outcomes and retirement. Refuse existing successor outputs before launch.

Stop on failure, mismatch, timeout, unexpected output or UNKNOWN. No retries, repairs, installation or extra cleanup. Jim's T07 workspace-only preparation continues separately and grants no T07 execution. Endpoint remains unbound and all other holds stay.
