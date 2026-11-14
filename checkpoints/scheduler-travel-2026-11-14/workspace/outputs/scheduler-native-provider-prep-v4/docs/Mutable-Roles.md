# Sixteen mutable roles — native-provider prep-v3

Exact paths (same 16 named roles; fresh successor; no unnamed extras):

1. `Invoke-Native-Provider.ps1` — host operator admission scaffold (external ExpectedConfigSHA256)
2. `payload/fixture/np_supervisor.py` — host-side supervision + ProviderDockerOps composition
3. `payload/fixture/np_integrated_runner.py` — in-runner admission/registry guards
4. `payload/fixture/np_runner_entry.py` — in-runner entry + ASGI vertical / explicit HOLDs
5. `payload/fixture/np_suite.py` — finite declared cases + immediate STOP oracles
6. `payload/fixture/np_receipts.py` — bounded sanitized evidence + allowlisted token_rollback_ack
7. `payload/fixture/np_provider_peer.py` — synthetic peer socket/TLS + multi Connection:close inventory
8. `payload/fixture/np_provider_transcript.py` — finite exchange scripts / MS identity+calendarView inventory
9. `payload/fixture/np_provider_routes.py` — fixture routes/trust (`/tmp/np-provider-tls`; wrong-name leaf flag)
10. `payload/fixture/np_auth_seed.py` — disposable Settings/seed/covering-refresh body
11. `payload/fixture/np_alias_seed.py` — disposable canonicalization seed
12. `payload/fixture/prepare-np-provider-tls.sh` — recipe source only, NO generation
13. `verify/check_native_provider.py` — fake-only structural/fault-control checker
14. `verify/launch_check.py` — bounded local check launcher
15. `verify/verify_admission.py` — outer hash admission
16. `Invoke-Fake.ps1` — operator wrapper for separately held verification

Plus finite data/docs. No extra executable helper or unnamed mutable role.
Immutable helpers reused under `payload/fixture/` with lineage in `docs/Immutable-Helper-Lineage.json`
(including `i01_asgi_app.py`, `assessment_binding.py`).
