# Sixteen mutable roles — native-provider prep-v1

Exact paths (corrected; do not mutate frozen jim-v2 docs):

1. `Invoke-Native-Provider.ps1` — host operator admission scaffold
2. `payload/fixture/np_supervisor.py` — host-side supervision only; never in-runner Docker authority
3. `payload/fixture/np_integrated_runner.py` — in-runner admission/registry guards
4. `payload/fixture/np_runner_entry.py` — in-runner entry
5. `payload/fixture/np_suite.py` — finite declared cases + immediate STOP oracles
6. `payload/fixture/np_receipts.py` — bounded sanitized evidence
7. `payload/fixture/np_provider_peer.py` — synthetic peer
8. `payload/fixture/np_provider_transcript.py` — finite exchange scripts
9. `payload/fixture/np_provider_routes.py` — fixture routes/trust only
10. `payload/fixture/np_auth_seed.py` — disposable tokens/settings + per-case planning
11. `payload/fixture/np_alias_seed.py` — disposable canonicalization seed
12. `payload/fixture/prepare-np-provider-tls.sh` — recipe source only, NO generation
13. `verify/check_native_provider.py` — fake-only structural/fault-control checker
14. `verify/launch_check.py` — bounded local check launcher
15. `verify/verify_admission.py` — outer hash admission
16. `Invoke-Fake.ps1` — operator wrapper for separately held verification

Plus finite data/docs: `payload/launch-config.json`, `payload/runner-config.json`, case/oracle/config/manifest/diff/review artifacts under `data/` and `docs/`.

No extra executable helper, optional DB wrapper, or unnamed mutable role.
Immutable helpers reused under `payload/fixture/` with lineage in `docs/Immutable-Helper-Lineage.json`.
