# Mutable roles — t05-closure-prep-jim-v3 (16)

Same approved 16-role native-provider assignment (Scope `389A00DD…` · Approval `5D1EA2F9…`). See Mutable-Role-Hashes.json for exact SHA256/bytes.

## Mutated this prep (Dex R2 taxonomy boundary)

| Role | Path | SHA256 |
| --- | --- | --- |
| 4 | np_runner_entry.py | 9C0F85733287BDCF4F526AB52F5685E7BC10CB1C4CC349818D8B0AC001B07E70 |
| 13 | check_native_provider.py | 099BC9A4B3CFF811A573B95BFA0F2FBD194E92AA1A70B482AE5D75757F7B825F |
| 14 | launch_check.py | ABCFC1383F8A99100A2850834A5177CF698253469326B4C501160128D1CEDC64 |
| 15 | verify_admission.py | 08975D02774BEA7A794F6420F9FFC4DE0BB5E3F2DB53A41716A894C5F48C6B49 |
| 16 | Invoke-Fake.ps1 | 9AE55D26604174AB84B71C841E9DB3C777D41E014CF56E6FCC7E3037843F2653 |

## Authored prior (tip base v2) — not re-mutated this successor

| Role | Path | SHA256 |
| --- | --- | --- |
| 5 | np_suite.py | 617D381A92F41DEC8376BA0F45A9DF9A9FBA3A54DE6D15B6F61BA2439DEFE562 |
| 7 | np_provider_peer.py | 4EEAB1E7F789AB4918B36466A50F29E09F84E6FA48A87C0C942ECD599E097D17 |
| 8 | np_provider_transcript.py | 46327DF0A848672FFBCA85772C0EA764D370BDF7B487EFAE36831F451A6915D4 |

## Four verification roles (13–16)

Focused fake-check packet: `T05-CLOSURE-FOCUSED` (+ 19 extracted R1–R4 controls incl. R2 observer taxonomy) in check_native_provider; launch_check / verify_admission / Invoke-Fake carry packet labels only; `launch_authorized=false`.

## Unchanged selected

- Invoke-Native-Provider.ps1 C4A883E8175F7AB40977CA482F78838C61C269E7CB46F5235FCDAD9E3C18A9AC
- np_supervisor.py A1ADA2311B10631209DBA0588B8C9C6B947B3206F0EFBC51F4CF66B1F45303BC
- docker_transport.py (immutable) 7F7EA8204879D312624DAEB7941504FEA1402F45C48BDA79DDAD94A23711AC53