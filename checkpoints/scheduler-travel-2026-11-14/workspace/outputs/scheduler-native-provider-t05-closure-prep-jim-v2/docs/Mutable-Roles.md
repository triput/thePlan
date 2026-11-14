# Mutable roles — t05-closure-prep-jim-v2 (16)

Same approved 16-role native-provider assignment (Scope `389A00DD…` · Approval `5D1EA2F9…`). See Mutable-Role-Hashes.json for exact SHA256/bytes.

## Mutated this prep (Dex R1–R5 consolidation)

| Role | Path | SHA256 |
| --- | --- | --- |
| 4 | np_runner_entry.py | A43092575F7DA6FD6892195DEA3356314C0AF8083D7B60968E42C1080276ABB4 |
| 13 | check_native_provider.py | 49233E917CA41FECB1E42ECDCC7D8985DE31F7B749D7BCA65421695567B7AB9F |
| 14 | launch_check.py | 41F4EB8EE36715CBDE63AA3F8025FBBC073F319CDC397C830842D0C61B42FA49 |
| 15 | verify_admission.py | 9B818F8E12AA2E654700AC44CBD2834C7640AB6D1EE2AEC49B8664DC76C5063C |
| 16 | Invoke-Fake.ps1 | 2764F14ED01E70C39D1758E26EC7FDC8C025E28D42E4EFE14ABD7741BEF39721 |

## Authored prior (tip base) — not re-mutated this successor

| Role | Path | SHA256 |
| --- | --- | --- |
| 5 | np_suite.py | 617D381A92F41DEC8376BA0F45A9DF9A9FBA3A54DE6D15B6F61BA2439DEFE562 |
| 7 | np_provider_peer.py | 4EEAB1E7F789AB4918B36466A50F29E09F84E6FA48A87C0C942ECD599E097D17 |
| 8 | np_provider_transcript.py | 46327DF0A848672FFBCA85772C0EA764D370BDF7B487EFAE36831F451A6915D4 |

## Four verification roles (13–16)

Focused fake-check packet: `T05-CLOSURE-FOCUSED` (+ 14 extracted R1–R4 controls) in check_native_provider; launch_check / verify_admission / Invoke-Fake carry packet labels only; `launch_authorized=false`.

## Unchanged selected

- Invoke-Native-Provider.ps1 C4A883E8175F7AB40977CA482F78838C61C269E7CB46F5235FCDAD9E3C18A9AC
- np_supervisor.py A1ADA2311B10631209DBA0588B8C9C6B947B3206F0EFBC51F4CF66B1F45303BC
- docker_transport.py (immutable) 7F7EA8204879D312624DAEB7941504FEA1402F45C48BDA79DDAD94A23711AC53
