# D2 path-admission fake verification — launch review

Prepared by Dex, 2026-11-11. Execution HELD pending Trish's separate one-shot approval. Jim authored the source/check packet; Dex independently reconciled the pins, coverage and final MS context composition, staged the immutable copy and authored the admission wrapper. No Python imports, compilation, check execution, sockets or application execution occurred during preparation.

## Scope and static disposition

One fake-only verification: 41 approved core functional controls, three additional context refusal controls, three mutation controls and five inventory controls, for 52 ordered unique controls. All 41 core IDs are retained. Functional coverage includes path admission/refusal, unchanged wire targets, Google pagination, Microsoft builder-to-context/client-to-HTTP composition, observable duplicate-peer selection and independent context refusal before delegation. Mutation controls exercise the actual extracted HTTP admission path. This is a prerequisite to the broader T01–T08 provider-transport proof; it does not close that proof or establish live provider/native behavior.

The API copy contains 234 files. Exactly the three approved source files differ from the preserved base. The exact proposed diff is [Source-Changes.diff](packet/Source-Changes.diff), SHA256 `CDB3AF210C7DD2BDC725F44F61931AD39B8010D5D259289D5D1FEF3E98E3F4F4`.

Resulting source SHA256:

| File | SHA256 |
| --- | --- |
| covering_transport_policy.py | A265F81F72E719B23FE3DE9BF332E2DE01D8E90073F3AC04675EC6A4B2203598 |
| covering_http_transport.py | AECE10186CFFAE46D3EF2292D3772F1C287FD0A562AA9E764AAC4ABB10C861D8 |
| covering_provider_context.py | 875FBF61A386D661A4DD70609162E41540500F10AD6AEDCACAF790701D693240 |

Final Jim v4 TIP: `3FC58EF9A45A40C5147C26040B49896DE396531EE55FC0059BC3F034874A6064`. The 252 physical packet files match the drop copy byte for byte. Artifact/API/extraction/outer/launcher/runtime and stage comparisons total 782 successful hash comparisons, including overlapping layers; this is not a count of unique files. See Static-Reconciliation.json. The preserved predecessor packets and prior evidence remain unchanged.

Jim's independent static wrapper review reports NO BLOCKER. Its scope excludes execution and concrete admission data, which Dex subsequently generated and reconciled. Review SHA256: `D0ED4049868ED0C5E07BC4A840CED6B7D49E88A6A486F076ECFFC4D53F496BAE`.

## Exact admission and commands

Wrapper SHA256: `B72C1CBCAC9229F47FBB5E7A88462BB3D0C02DC8FA6B3DE163EE8FFECB195CA7`.

VERIFICATION-ADMISSION.json SHA256: `ED2488835774A1510ADAF67A6C17758F4684BF6AF3814D7A6C68C4C275736D3D`. It pins all 252 staged packet files plus the interpreter and 11 named standard-library provenance files before Python starts. These are explicit provenance pins, not an exhaustive inventory of every runtime dependency.

Raw INPUT-MANIFEST.json SHA256: `4E2AC286F3B9CA3DF888E4C6C2A2C40DBF092E38819F27A7EE1B0314E7F2E02D`.

Check-script SHA256: `CAAECE741F12F632FFC97207D47BEA6340EBFD62CB20AE86EE84C389BD73C4CB`.

EXPECTED-OUTPUT.json SHA256: `381536B156A37EE5C3F7A1FABBC0F0C2942FE97BBC68B68F67550BF715C368FC`. This is an oracle, not an observed result.

Held PowerShell command, to be used once only after approval:

```powershell
$d2Wrapper = 'C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-d2-fake-v1\Invoke-Verification.ps1'
if ((Get-FileHash -LiteralPath $d2Wrapper -Algorithm SHA256).Hash -ne 'B72C1CBCAC9229F47FBB5E7A88462BB3D0C02DC8FA6B3DE163EE8FFECB195CA7') { throw 'STOP: wrapper hash mismatch' }
& $d2Wrapper -AdmissionSHA256 'ED2488835774A1510ADAF67A6C17758F4684BF6AF3814D7A6C68C4C275736D3D'
```

The wrapper makes one pinned Python invocation with `-I -S -B` into admit_outer.py. The outer admission starts the local launcher, which starts one check child and two capture-reader threads. Extracted application definitions operate only with fake dependencies/transports. No application/vendor package imports, real sockets, PKI, providers, database, Docker, installation or native launch are included.

## Limits, retention and stop conditions

Child wait 30 seconds, child kill/wait 5 seconds, then two reader joins of 5 seconds each: 45 seconds nominal collection/retirement, excluding outer admission/hash/file operations and process/OS latency. Capture limits: 64 KiB stdout, 64 KiB stderr, 256 KiB result. Bounded owned-check-child termination on timeout/error/overflow is included. The existing launcher/outer capture and retirement behavior is retained.

Retain FAKE-D2-RESULT.json, FAKE-D2-LAUNCH-RECEIPT.json and tool/approval evidence; independently reconcile the actual ordered controls, outcomes and retirement before claiming PASS. Refuse existing result/receipt files before launch. Stop on failure, mismatch, timeout, unexpected output or UNKNOWN. No retries, repairs, installation or extra cleanup. Endpoint remains unbound; all other holds remain.
