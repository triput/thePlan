# Exact diffs summary — t05-closure-prep-jim-v2 vs t05-closure-prep-jim-v1

Prep authoring only. Tip base C902F529… and other held packets not mutated.

## Mutable roles changed this successor

| Path | prep-v1 SHA256 | prep-v2 SHA256 |
| --- | --- | --- |
| payload/fixture/np_runner_entry.py | 1E85218C887804FE4E9F88D3C4960FF77C7F7D90277761D9574D0101AE7D0860 | A43092575F7DA6FD6892195DEA3356314C0AF8083D7B60968E42C1080276ABB4 |
| verify/check_native_provider.py | 60148BBC8247D7332823B2354706549A2CB7EBBB588ABB5F470D1852D2AE69F0 | 49233E917CA41FECB1E42ECDCC7D8985DE31F7B749D7BCA65421695567B7AB9F |
| verify/launch_check.py | A3C68F4F3FB70F85621167205A2B4E73642F49DF648B054D3DEC9DE22E9C5B24 | 41F4EB8EE36715CBDE63AA3F8025FBBC073F319CDC397C830842D0C61B42FA49 |
| verify/verify_admission.py | EA1F184F87214302D9CF7FFEA493B6F1125E0380BC8FDD816870B72502E9EE1E | 9B818F8E12AA2E654700AC44CBD2834C7640AB6D1EE2AEC49B8664DC76C5063C |
| Invoke-Fake.ps1 | 6C4994C969794ACDBA798E9AD267F8BEB6E43E48178C8D426E4DF03642E99A6C | 2764F14ED01E70C39D1758E26EC7FDC8C025E28D42E4EFE14ABD7741BEF39721 |
| verify/EXPECTED-FAKE-STRUCTURAL.json | 217E0DCDFAC1D9D6BDCAE7C0F38BAB87C4E20F3100AEA7B78EA550936A113681 | CCC7824FEA9CA19C93148C20D079EE2011B850392E394F5B6A8177126DAC64FF |
| payload/SHA256SUMS.txt | 3D476458BF61E81D16652159C8D1C802E76A2221C3E977A5DAA5D7E61FE41170 | 30EF98F8067B1D0476BF0F2923B1FD80B557286BB5AE494661044B96F98DE472 |

## Semantic deltas (R1–R5)

1. **R1:** Event refusal stops on CoveringRootOutcomeUnknown before primary unwrap
2. **R2:** Abrupt oracle requires measured TLS EOF/reset receive class + stimulus; rejects generic/deadline/malformed/UNKNOWN
3. **R3:** Helper-owned one retirement on start_background partial failure; no double cleanup
4. **R4:** Fresh validated plan per a/b/abrupt exchange; no now-fallback; expiry/failure STOP
5. **R5:** Report-producer fake deps admitted; 14 extracted actual-helper controls + mutations; structural scope labeled honestly
6. Receive observer adds `abrupt_tcp_reset` at OSError boundary (alongside `abrupt_ssl_error`)

## Unchanged selected (relative to tip base)

- np_provider_peer.py 4EEAB1E7F789AB4918B36466A50F29E09F84E6FA48A87C0C942ECD599E097D17
- np_provider_transcript.py 46327DF0A848672FFBCA85772C0EA764D370BDF7B487EFAE36831F451A6915D4
- np_suite.py 617D381A92F41DEC8376BA0F45A9DF9A9FBA3A54DE6D15B6F61BA2439DEFE562
- payload/runner-config.json 5A54F37CAD7A470CF2CCC2CC121818953E24848C19026C7EBC9D02114B10043D
- Application/assembly under payload/api/** (234 files)
- docker_transport.py; Invoke-Native-Provider.ps1
- Held candidate-v2 / fake-v1 / native-ready / prep-v9 / tip base v1 packets
