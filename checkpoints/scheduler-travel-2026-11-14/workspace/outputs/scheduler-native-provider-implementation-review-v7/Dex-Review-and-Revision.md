# Native-provider v7 independent source review

November 12, 2026. Preparation-only review; no imports, compilation, tests, PKI, sockets or Docker execution. The workspace acquired a new v7 freeze record and its drop mirror during review; the initial observation before drop creation was incomplete authoring, not a failed execution. Final saved integrity reconciliation: 285 workspace/drop files match, 234 selected application files match, all 18 declared packet pins match, TIP on-disk B99657509593AB385BA67D9F2AB0287D89E0D37F07B42EA87668300B07CBA149 and raw zero-field preimage 0CFB98C616362B36C50EADF610FE8873C442A610B25B5BF9EF108D041F409B42 match.

## Accepted source progress

- Main now calls admit_provider_pki_generated_once and requires GENERATED before suite/peer work. Preparation does not invoke it. The bounded caller now checks overflow again after reader join and preserves any existing primary failure.
- The byte-alias guard uses executable AST references rather than rejecting documentation. Report-only fakes include the newly introduced setup dependencies.
- Host import admission and receipt relay are authored; run_once binds the relay before Docker calls. The host seam checks extract the actual ReceiptRelay class, with a limited fake surrounding wrapper. They do not prove the complete actual host path.
- Assembly checking now hashes all 234 selected files against the pinned manifest. OUTER is rooted by VERIFICATION and no longer back-pins VERIFICATION; the prior hash cycle is removed.
- Previously accepted alias placement, actual bound budget observation and one-attempt peer retirement remain present.

## Remaining fake-verification blockers: two narrow corrections

### R1. Complete the concrete checker read footprint

VERIFICATION-ADMISSION has 18 matching packet pins, but the checker still reads five additional fixture files that those pins and the 234-file API manifest do not cover:

| File under payload/fixture | SHA256 |
| --- | --- |
| bootstrap-postgres-tls.sh | FE72795D82DB70B16D193CF18D5B732E01FBA24ABA1606A91621D533C0236D16 |
| np_alias_seed.py | 309CE658479FFD665408B6EAABF318258AF402D29F23C0C3F9BD99E5FDA003AD |
| np_integrated_runner.py | 2C8B5BE78B5F042210D042DF1FB7FDBB07C486ED5A57CA36C00006F61E6040DF |
| np_provider_routes.py | 9CBDE09CD1E84DCB6380BC223C9C23791DA3671AC042C13A745291F9CC5A11EA |
| prepare-tls.sh | 41A683A6A0312B12F71C42C966F9BA0EF3D02D97416FAEF28C6E99DE9B29DF4F |

The direct reads are in check_host_vs_runner_docker_guard and check_vertical_contract_shape; check_fixture_syntax additionally scans FIXTURE.glob("np_*.py"). Add these actual inputs to the admission root and make the finite np_*.py inventory explicit so newly introduced files cannot silently join the read footprint unpinned. Keep the acyclic layout; no need to rerun old API tests or expand native case scope.

### R2. Make the three late-drain controls exercise the candidate gate

check_provider_pki_late_drain_overflow currently defines a local admit_after_join implementation that repeats the desired policy. It does not extract/call the candidate caller or its final overflow block. The runner is only checked for two text fragments. Removing the real late_overflow assignment/branch while leaving those strings elsewhere could preserve all three outcomes in this checker.

Use the raw-pinned candidate function with fake dependencies, or narrowly extract its actual post-join overflow block and final primary-failure refusal into a fake harness. Keep the three existing control IDs and add a mutation that removes the actual overflow gate and must be detected. This need not start threads, children, sockets or PKI. Describe an extracted-block check at that exact scope; it is not proof of full PKI process retirement. Do not replace the tested candidate behavior with a second handwritten implementation.

## Next handback

Use the same approved workspace lane and fresh successor; preserve v7. These are admission/checker corrections, not a new product decision or a new preparation gate. Return exact diff, complete admission/root hashes and truthful expected output. A reconciled meaningful fake prerequisite can then be brought to Trish for one execution decision without finishing the other 26 native/four CF cases. Native launch still needs separately frozen commands, numeric bounds, dependency disposition and exact evidence/cleanup scope.

The partial runtime inventory currently pins only the interpreter; do not describe it as a full runtime lock. No fake/native launch is authorized by this review. Endpoint unbound; all other holds stay.