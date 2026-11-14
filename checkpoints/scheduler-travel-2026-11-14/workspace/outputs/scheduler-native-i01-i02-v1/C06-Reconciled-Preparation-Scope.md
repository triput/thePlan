# C06 runner-owned TLS: reconciled fresh-copy preparation scope

DRAFT FOR JIM RECONCILIATION; no implementation or execution authorization. Dex independently verified28 artifact/evidence/callsite pins in Jim proposal TIP F8A8EA4676BB05E1A9C52D4114667DD6CB7A14E3ADBA6A82C2F773853807341D. OptionA is the narrow fixture-only direction: runner-owned CA/leaf in existing /tmp; client-gate trust distinct from backend DB trust. Preserve the current blocked draft and all fake/native evidence in full.

Proposed source-preparation authorization:
- One fresh workspace copy based on the blocked native draft.
- NEW payload/fixture/prepare-c06-runner-tls.sh.
- EDIT payload/fixture/runner_entry.py only for bounded generation/admission and sanitized public-material provenance before the existing subprocess audit hook.
- EDIT payload/fixture/i01_c06_dual_peer.py only for runner-owned root, explicit gate-client CA and independent backend DB CA.
- EDIT payload/fixture/i01_i02_suite.py only for the same explicit ready/result/root/trust wiring and public CA identity evidence.
- Regenerate complete payload SHA256SUMS and author separate fake-only verification harness/expected output/command/manifests/review documents. This is preparation, not permission to run them. Return exact diffs and hashes.
- Keep launch-config.launch_ready=false. No host helper, production, runner-config, image, mount, namespace, CPU/memory or existing deadline changes. Native command remains held; no silent pin-only workaround.

Required invariants:
1. Exclusively create /tmp/c06-gate-tls under existing runner tmpfs as UID65534, directory0700 and umask077; refuse any pre-existing path. The script then requires that owned directory to exist and be empty. This reconciles Jim's mkdir-versus-missing-directory wording; no retry, reuse or directory deletion.
2. Use fixed absolute /bin/sh and /usr/bin/openssl with explicit minimal child environment and controlled PATH. Run once before the unchanged process audit hook. App/provider subprocess policy remains enforced afterward.
3. Prepare a30-second generation/admission deadline, plus at most5seconds owned process-group termination/reap and two5second capture-reader joins:45seconds disclosed collection/retirement accounting. These remain within existing600second runner/900second suite budgets. Any failure/timeout/mismatch/unconfirmed child or reader retirement stops the suite; no retry/repair. Killing only the shell is insufficient: its OpenSSL children must remain owned and retired. This is proposed future behavior only, not execution authority.
4. During-read stdout/stderr caps64KiB each; inherited1MiB artifact file-size ceiling; no raw output or key material in host receipts. Retain sanitized status/class and bounded length/hash provenance. No key hashes in receipts. Key/CSR/serial/cert files stay inside runner /tmp and are disposed with separately authorized exact-ID container cleanup.
5. RSA3072 CA/leaf recipe following the reviewed DB generator pattern; fixed synthetic hostname native-fixture.invalid, SAN DNS:native-fixture.invalid and serverAuth; explicit chain/hostname verification. Directory/key ownership/modes must be checked. Source preparation does not execute the recipe.
6. Client-to-C06 parent uses runner CA; C06-to-DB uses /public-ca/ca.crt and unchanged verify-full/server_hostname; direct DB sessions retain original profile. Record public gate CA hash and DB public CA hash distinctly in fixture evidence; do not widen trust or transfer any DB private key.
7. Keep port15432 and exact existing case order. Native N06 must be completed/joined before C06; occupied port stops without retry. No host bind/publication or new network namespace. Existing120second C06 gate limit starts after successful generation and remains within suite budget.
8. Same explicit root for serve, readiness and receipt load. Preserve original commit method/guards, post-flush arm, exact backend COMMIT/idle/zero-forwarded-terminal-byte proof and all joins/primary precedence. C06-MAP stays separate; expected UNKNOWN inventory unchanged.
9. Fake-only check authoring must cover wrong trust/root/mode/ordering, generation refusal/timeout/output cap/child+reader retirement and primary-error preservation with fake processes/TLS/FS; no app/vendor imports, real child processes, sockets or PKI generation. Actual recipe/trust/TLS/native lost-ack proof requires later execution authority.

After approved preparation, Dex independently reviews exact changes before any verification or native-launch card. Neither source preparation nor policyD2 authorizes tests, Docker, certificate generation, installation, deployment, endpoint/profile binding or repairs to preserved evidence. All other holds stay.