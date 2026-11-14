# Exact diffs summary — native-ready-prep-v1 vs tipped prep-v9

Prep authoring only. Predecessors not mutated.

## Mutable roles changed

| Path | prep-v9 SHA256 | native-ready-prep-v1 SHA256 |
| --- | --- | --- |
| Invoke-Native-Provider.ps1 | D6E14CC07AF1B3F35B32DBE1C0FB4F9E7C70B476957314B6D29299CD04B6AE8D | C4A883E8175F7AB40977CA482F78838C61C269E7CB46F5235FCDAD9E3C18A9AC |
| payload/fixture/np_runner_entry.py | 87D89F760BB7CD47764BA1C6574A9AFF9E6266E682F0CE752AE4B06B484B2E25 | 7FBDCAEE078CDBE3F695191ABBED93B827A31EB6FED55DCD839AB43A84355FF5 |

## Mutable roles unchanged (selected)

| Path | SHA256 |
| --- | --- |
| payload/fixture/np_supervisor.py | A1ADA2311B10631209DBA0588B8C9C6B947B3206F0EFBC51F4CF66B1F45303BC |
| payload/fixture/np_integrated_runner.py | 2C8B5BE78B5F042210D042DF1FB7FDBB07C486ED5A57CA36C00006F61E6040DF |
| payload/fixture/docker_transport.py (immutable helper) | 7F7EA8204879D312624DAEB7941504FEA1402F45C48BDA79DDAD94A23711AC53 |
| Invoke-Fake.ps1 | AE84E6325E7B932303B21D6F0A0FED788A717A28631C3577DAF860C6EFC4FEB7 |

## Layout / config moves

| Change | Detail |
| --- | --- |
| Move | `payload/launch-config.json` → `host/launch-config.json` (outside source_directory) |
| Add | `host/docker-ops-config.json` (outside source_directory; ExpectedDockerConfigSHA256 pin) |
| Add | `payload/SHA256SUMS.txt` (256 entries; excludes host configs + evidence) |
| Rewrite | `payload/runner-config.json` one-case + lineage runtime pins; ca_sha256 labeled runtime-bind |
| Evidence path | sibling `…/scheduler-native-provider-native-ready-prep-v1.evidence` (not created this prep) |

## np_runner_entry deltas (semantic)

1. Import order: bootstrap before sibling imports
2. `bind_runtime_public_ca_hash` before `run_suite`
3. `_provider_pki_typed_success_summary` wired into successful report
4. Removed stale `provider_pki_invoked=False`; success labels use GENERATED
5. STOP schema unchanged (`status`/`kind` only); failure-evidence limits disclosed on success receipt

## Invoke-Native-Provider deltas (semantic)

1. Host launch-config path under `host/`
2. Mandatory `-ExpectedDockerConfigSHA256` byte admission
3. Default docker-ops path `host/docker-ops-config.json`
4. Reject launch-config / docker-ops physically under payload
5. Evidence sibling + empty `public-ca` mkdir before supervisor
6. launch_ready still must be true to start child (remains false in authored configs)

## Not changed

Application/assembly sources under `payload/api/**`; `docker_transport.py`; fake-v1 packet; tipped prep-v1…v9 DropFolders; proposal TIP.
