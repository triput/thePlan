# C06 corrected1 frozen review

Disposition: REVISE the held verification packet; no verification card and no execution. TIP SHA256 2F9D3EDA861F67A0881C46953B92248A1A6D996DF3BB41C87C1EA55A7E449676. Twenty artifact pins,268 payload pins and6 verification-package pins independently match. Compared with preserved v1, payload changes are only fixture/runner_entry.py and SHA256SUMS.txt. Parent TIP still046D670AC261A3E72920264C44DC16F3DB39B8D5E386CA4D4CAA726ED97108BA; launch_ready=false.

The runner improvements and pinned admission/extraction/result controls materially address the original five findings and three capture follow-ups. Thirty-eight controls are declared, but matching manifests and authored assertions do not prove they execute correctly. No tests, imports, compilation, sockets or PKI were run in this review.

## Blocking check-only corrections

1. Fake accepted client interface: extract_dual's FakeListener.accept returns a FakeListener lacking __enter__/__exit__. Actual extracted serve_i01_c06_gate uses with client. The backend-trust positive exercise therefore has a source-supported TypeError path before its intended completion. Implement the fake owned-client context contract and check its retirement without real sockets. Preserve actual fixture code.
2. Shared deadline oracle: the control sets fake_os.now=29 before prepare_c06_runner_tls captures entry+30, then rejects absolute now>=58. A valid clock origin29 yields deadline59. Inject setup elapsed time after capture and compare elapsed from entry, separating the existing retirement allowance. A fixed absolute cutoff is not a shared-budget witness. Preserve actual30/5/5/5 bounds.
3. Coverage truthfulness: C06_N_ROOT_FIXTURE_TLS is recorded behavioral REFUSE while it only compares default path values. Label it static inventory (and update expected output/review); do not add a new production/fixture refusal guard merely to satisfy a misleading label. Other descriptive controls must likewise report their actual exercised branch or static scope.

The earlier held-reader primary literal was corrected to eof unknown, consistent with post-join primary preservation; recheck its structured endpoint-retirement facts in the next copy.

## Continuation

These check-only corrections belong to the already-approved separate verification-authoring scope. Ask Jim to preserve this frozen corrected1, prepare a fresh corrected2, regenerate all admission/manifest/command pins and return the handback. No new fixture source changes or source scope increase is requested. No execution, retries, native launch, installation, Docker or certificate generation. Final command disclosure must explicitly distinguish fake processes within the check from the real outer/launcher/check supervisor chain.

The full integration goal remains open: new HTTP/native and actual owner contention runtime evidence plus all T01–T08 contracts and exact cleanup are still required.