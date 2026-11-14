# Preparation review — scheduler-native-provider-native-ready-prep-v1

Jim (Justin), 2026-11-12. PREPARATION ONLY. Fresh copy from tipped prep-v9 implementing Dex reconciled seams C7B8FD74… / 57AA3A80…. Zero execution.

## Authority

| Document | SHA256 |
| --- | --- |
| Reconciled-Authoring-Scope-For-Approval.md | 389A00DD444C610A93877362A574A1C93543F916F119D2D2FF71BA167FBF7E2D |
| Trish-Preparation-Approval.json | 5D1EA2F973FE110D35B65E4172821F014E74A8F2A65BCBB4AB8EE22458F80CA4 |
| Reconciliation-and-Next-Preparation.md | C7B8FD744D708A5009D971E7F56CF94B6D3FDC16A989B32D004C9FBF3BCC4E6B |
| Native-Launch-Readiness-Seams.md | 57AA3A80E26BC7EA29E47AE279E9FA94270F8DA5C5BD2EC586568BFCF154B3E3 |
| Proposal TIP (immutable) | FB9AF80E01BC48E60B082EE02A54D29957F52B64BC636751D19142B2D5982A7B |
| Prep-v9 TIP on-disk (immutable) | 6585E768FA64E455052368F75E47795ECC99708DC4EDCFBF6D33CD3B5A25F188 |

Same approved **16-role** authoring lane. No new preparation card.

## Per-seam FIXED evidence

| # | Seam | Disposition | Evidence |
| --- | --- | --- | --- |
| 1 | Runner entry import order | FIXED | `np_runner_entry.main`: UID → load config → `admit_isolated_import_bootstrap` → then import `np_integrated_runner` / `np_receipts`. Preserves `-I -S -B` and exact site/fixture/API roots. |
| 2 | Runtime DB public-CA bind | FIXED | `bind_runtime_public_ca_hash` derives ephemeral in-memory `ca_sha256` from `/public-ca/ca.crt` before `run_suite`; on-disk runner-config bytes preserved; host equality still ProviderDockerOps vs transferred hash; distinct from provider PKI. |
| 3 | Docker ops config byte admission | FIXED | `Invoke-Native-Provider.ps1` requires `-ExpectedDockerConfigSHA256` and compares exact bytes before host Python child; independent `-ExpectedConfigSHA256` preserved for launch-config. |
| 4 | Acyclic physical layout | FIXED | `host/launch-config.json`, `host/docker-ops-config.json`, and evidence path live OUTSIDE `payload/`; payload `SHA256SUMS.txt` covers every payload file except itself; operator rejects configs under payload. `docker_transport.py` unchanged `7F7EA820…`. |
| 5 | One-case freeze + caps + lineage | FIXED | `case_ids=["NP-V-MS-NONEXPIRED"]`, `expected_unknown_cases=[]`; suite900 / runner600 / peer120+join5 / PKI45 / command_count32 / 1MiB; retained images + runtime pins from Native-Runtime-Lineage-Reference.json; static success Docker command count **22** (unchanged; 32 hard cap). |
| 6 | Typed PKI success summary + label | FIXED | Successful report carries `provider_pki_summary` (typed status/generation/retirement/EOF/overflow/counts only). Case `provider_pki_status` / resource_disposition use `GENERATED` when generate-once done. Stale `provider_pki_invoked=False` removed (Dex acceptance docket). STOP remains `{status,kind}` only — no inferred PKI success on failure. |

## Flags

executed=false; launch_authorized=false; launch_ready=false; prep_is_not_pass=true; endpoint unbound; no invoke; Slack tip=false.

## HOLDs

- Other 26 native + 4 CF: HOLD_EXPLICIT_NOT_PASS (76 planning IDs retained)
- Provider PKI / native launch invocation unauthorized under this prep
- Image presence / port 443 bind unverified this prep (no live probe)
- fake-v1 PASS prerequisite UNFULFILLED; staged packet untouched
