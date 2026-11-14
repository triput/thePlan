# Native parser-source collection v3 — launch decision

Dex reconciled the frozen independent review (Justin for Jim): QUALIFIED ACCEPT, zero static blockers. All three artifact rows and the TIP raw/preimage hashes match; all 12 reviewed files, four packet inputs, 25 partial runtime pins and Docker executable hash match. Evidence directory remains absent. No launch, imports, compilation or tests occurred.

Exact held operator sequence: ../scheduler-t05-native-provenance-dex-v3/Commands.ps1.txt

- Command-file SHA256: 501FAB56FC51F8C8B147EE0B7F29FED8B3F2D95AD7C793FE691953D407C83C55
- Input-manifest SHA256: 4F2BAECBEBA79A4E5BFF6D2A6A04CB658DF8775BCE91F368BE6152260BE1AC37
- Supervisor SHA256: 6A5746C7513FEB438C3465FDA1A7F44B50208E90DE19F43D78294E6AEC760B9A
- Collector SHA256: 547151B1F530B7A7726C6FD3E5277CA3EF91EE7B0110E0C2C127E95D54AD2FFE
- Frozen peer review SHA256: AEBBF88EBE30091340AE2E45AC538D967A21D12CEBC43D766F91EF7BCC9D896C

Requested authority: one execution of that reviewed sequence outside the default execution restrictions. One pinned runner image sha256:c220110432cf4adbb4005518a02808b754e0efb050b5de202e71872fecdbd2ab; nonroot65534:65534, network-none, read-only root and /packet bind, cap-drop ALL, no-new-privileges, no pull/restart/logging/healthcheck, 256 MiB memory+swap total, one CPU,32 PIDs. No database or server, no installation/build, no credentials or providers.

Collect exactly /usr/local/lib/python3.12/http/client.py, /usr/local/lib/python3.12/ssl.py and /usr/local/lib/python3.12/email/message.py as nonsecret raw bytes plus sizes/hashes. At most128KiB each,384KiB raw total,768KiB envelope. No captured source is imported or executed.

Seven Docker commands: image inspect; create; exact-ID/config inspect(created); start/attach once; exact-ID/config inspect(exited0); success-only exact-ID removal; absence check. Removal occurs only after complete byte capture, durable saved-source verification and original admitted manifest/runtime continuity checks.

Limits:300s shared command supervision/admission;30s each except60s attach. A fault permits one owned CLI kill/wait5s plus two reader joins5s each,15s nominal retirement outside command budget. File/hash/fsync work and process/OS latency are excluded; no hard315s wall-clock guarantee. Per-command captures768KiB stdout/64KiB stderr; queue32x4KiB; result1MiB. Estimated retained files under8MiB, not a hard disk quota. CLI termination does not prove daemon cancellation.

Stop on failure, mismatch, timeout or UNKNOWN. No retries, repairs, fallback or container failure cleanup. Retain partial evidence and known ID. Include exact-ID removal/absence verification only on success. Any failure state change remains separately gated.

Peer qualifications remain:25 runtime pins are partial provenance; Healthcheck is disabled at create but not separately projected at inspect; mount Source is not separately compared, while exact HostConfig.Binds, mount Type/Destination/RW and sole-mount inventory are enforced. This authority does not relax any mismatch rule.

Proof boundary: a passing run establishes native source-byte provenance and resource cleanup only. It does not prove framing/TLS behavior or close T05/T01–T08. The separate Jim framing/custody handback remains pending and none of its helpers is used by this native packet. Endpoint unbound; all other holds remain.