# C06 correction: independent review criteria

Offline source review only. No implementation, certificate generation, subprocess, socket or native launch executed.

Current reviewed sources constrain a runner-owned gate proposal:
- PostgreSQLPeer.ca_file controls client sslrootcert while verify-full hostname/address are separate fields. A replacement C06 parent profile can select runner-owned public CA material without modifying the direct-session DB profile or production checkout.
- tls_ack_gate.serve_one explicitly requires backend SSL CERT_REQUIRED and check_hostname=True, and wraps the backend with server_hostname=native-fixture.invalid. Its backend trust must remain the DB public CA, independent of the runner gate's server certificate/issuer.
- serve_i01_c06_gate currently uses the same default root for its server chain, backend CA, ready marker and final receipt. Moving only the server key files is insufficient; every ready/result reader and client trust path must be reconciled.
- The original commit-bound-method wrapper, post-flush arm marker, exact COMMIT/idle observation and zero forwarded terminal bytes remain required. C06-MAP cannot replace this proof.

A narrow proposal should account for:
1. Exact source files and API/parameter changes; no production/host helper edit by implication.
2. Runner-owned exclusive path under existing /tmp tmpfs, UID65534, restrictive directory/key modes, fixed synthetic hostname/port, no new host bind/port or DB-key transfer.
3. Exact bounded OpenSSL commands/inputs, output-size limits and child retirement on timeout/error; no installation. Command success/version availability alone is not SAN/serverAuth/trust proof.
4. Explicit separation of gate-client CA from backend DB CA, preserved verify-full and concrete wrong-trust/hostname controls in later authorized proof.
5. Generation charged to existing runner/suite budget; gate deadline starts at a clearly named phase. Any new per-step limit is disclosed; no silent increase of600s runner/900s suite or existing240s fault-gate maxima.
6. All key/CSR/serial/cert outputs remain inside the isolated runner; no key/raw SQL/credential material in host receipts. On failed native run, state-changing container cleanup remains separately gated. Success-only container removal disposes its tmpfs.
7. Gate readiness, receipt collection, stop/join and primary-error precedence use the same explicit owned root. No broad exception swallowing, detached child, fallback trust, automatic retry or cleanup success claim from an attempted close alone.
8. Offline fake controls can prove wiring/refusal/primary preservation but not real certificate/PKI correctness or native lost-ack behavior. Preserve fake22 PASS and add separately gated proof where needed.

The runner image CLI presence is established by Runner-OpenSSL-Retained-Evidence.md; actual generator and TLS behavior remain unproved. Native draft remains launch_ready=false; its pre-blocker Commands.ps1.txt is superseded and cannot be used as a launch request.