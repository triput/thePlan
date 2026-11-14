# Host import and receipt relay: unexecuted contribution

Based on frozen prep-v5 np_supervisor.py; active Jim successor untouched. Same named supervisor role only. Immutable docker_transport.py bytes are unchanged.

admit_host_helper_import verifies isolated flags, refuses an ambient helper module, checks that the supervisor is in the configured source fixture directory, verifies the exact reviewed manifest hash, requires one unique fixture/docker_transport.py pin and checks actual helper bytes before adding that explicit import root. It does not import DockerOps during preparation. The outer operator still owns complete payload/config/runtime admission; this helper check is not a replacement for it.

ReceiptRelay refuses unbound writes and repeated/invalid binding. DockerOps receives the relay at construction and retains its existing synchronized record wrapper. ProviderDockerOps.bind_record connects the exclusive run_once receipt writer through the relay before the first Docker/transport operation. Main no longer passes a no-op callback. The relay does not replace the immutable helper lock with an unsynchronized sink. run_once's own terminal receipt events remain direct; helper events and provider attach observations use the existing serialized wrapper.

This introduces a required bind_record method on fake ops used to exercise run_once. Adapt those fake objects or pass the actual wrapper with a fake inner transport/relay. The existing report-consumer extraction does not call run_once and is separate from this host-entry witness. Update helper source pins, expected output and complete acyclic admission files when integrating.

Suggested finite fake seam checks: unbound event refusal, one-time successful binding, double-bind refusal, synthetic docker_command/docker_output/runner_stop event preservation through an immutable-style locked callback and actual run_once binder, plus exact manifest/helper mismatch refusal with memory-only paths. They do not open Docker, spawn a process or prove native behavior. No tests, imports, compilation, helper invocation or Docker operation were performed in this source contribution.

Future host execution remains gated by exact commands/hashes/scope/limits and Trish's approval. This source does not add execution or cleanup authority and does not address runner PKI/callback/alias/retirement issues.
