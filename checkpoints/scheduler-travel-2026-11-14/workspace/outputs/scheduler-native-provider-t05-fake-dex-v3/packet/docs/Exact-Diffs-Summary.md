# Exact diffs summary — t05-closure-prep-jim-v3 vs t05-closure-prep-jim-v2

Prep authoring only. Tip base 7CC58CDA… and other held packets not mutated.

## Mutable roles changed this successor

| Path | prep-v2 SHA256 | prep-v3 SHA256 |
| --- | --- | --- |
| payload/fixture/np_runner_entry.py | A43092575F7DA6FD6892195DEA3356314C0AF8083D7B60968E42C1080276ABB4 | 9C0F85733287BDCF4F526AB52F5685E7BC10CB1C4CC349818D8B0AC001B07E70 |
| verify/check_native_provider.py | 49233E917CA41FECB1E42ECDCC7D8985DE31F7B749D7BCA65421695567B7AB9F | 099BC9A4B3CFF811A573B95BFA0F2FBD194E92AA1A70B482AE5D75757F7B825F |
| verify/launch_check.py | 41F4EB8EE36715CBDE63AA3F8025FBBC073F319CDC397C830842D0C61B42FA49 | ABCFC1383F8A99100A2850834A5177CF698253469326B4C501160128D1CEDC64 |
| verify/verify_admission.py | 9B818F8E12AA2E654700AC44CBD2834C7640AB6D1EE2AEC49B8664DC76C5063C | 08975D02774BEA7A794F6420F9FFC4DE0BB5E3F2DB53A41716A894C5F48C6B49 |
| Invoke-Fake.ps1 | 2764F14ED01E70C39D1758E26EC7FDC8C025E28D42E4EFE14ABD7741BEF39721 | 9AE55D26604174AB84B71C841E9DB3C777D41E014CF56E6FCC7E3037843F2653 |
| verify/EXPECTED-FAKE-STRUCTURAL.json | CCC7824FEA9CA19C93148C20D079EE2011B850392E394F5B6A8177126DAC64FF | 080268BCCCCB63EB47A96A59F5EB4454575D98AA73A1B796FEAF640F1F0B260A |
| payload/SHA256SUMS.txt | 30EF98F8067B1D0476BF0F2923B1FD80B557286BB5AE494661044B96F98DE472 | 3E6F28EDCC6A8C681B176F722B3E6233346C8F8DB992083E3E8FA759276C390B |

## Semantic deltas (R2 taxonomy only)

1. **R2 FIXED:** Receive observer classifies only `SSLEOFError` → `abrupt_ssl_eof` and `ConnectionResetError`/`ConnectionAbortedError` → `abrupt_tcp_reset`
2. Generic `SSLError` → `ssl_error_non_eof`; unrelated `OSError`/TimeoutError → `os_error_non_reset` (STOP, not truncation)
3. Admission outcome terminals narrowed to SSLEOFError|ConnectionResetError|ConnectionAbortedError|IncompleteRead|CoveringTransportRefused (not every SSLError/OSError)
4. Fake extracted controls drive observer via fake JoinedTLS.receive, then actual admission: positive EOF/reset; negative generic SSL / OSError / timeout / cleanEOF / UNKNOWN
5. R1/R3/R4/R5 contracts preserved; production sources unchanged; suppress_ragged_eofs=False; JoinedTLS.close local-only; three observations preserved

## Unchanged selected (relative to tip base v2)

- np_provider_peer.py 4EEAB1E7F789AB4918B36466A50F29E09F84E6FA48A87C0C942ECD599E097D17
- np_provider_transcript.py 46327DF0A848672FFBCA85772C0EA764D370BDF7B487EFAE36831F451A6915D4
- np_suite.py 617D381A92F41DEC8376BA0F45A9DF9A9FBA3A54DE6D15B6F61BA2439DEFE562
- payload/runner-config.json 5A54F37CAD7A470CF2CCC2CC121818953E24848C19026C7EBC9D02114B10043D
- Application/assembly under payload/api/** (234 files)
- docker_transport.py; Invoke-Native-Provider.ps1
- Held candidate-v2 / fake-v1 / native-ready / prep-v9 / tip base v1 / tip base v2 packets