# Acyclic input graph — native-ready-prep-v1

| Root | Admission | Physical location | Contents |
| --- | --- | --- | --- |
| A | Operator `-ExpectedConfigSHA256` | `host/launch-config.json` | One-case freeze, caps, `manifest_sha256` pointer, host exe pins |
| B | `launch-config.manifest_sha256` → | `payload/SHA256SUMS.txt` | Every payload file except the manifest itself (api/, fixture/, runner-config.json) |
| C | Operator `-ExpectedDockerConfigSHA256` | `host/docker-ops-config.json` | `source_directory`, images, argv, binds, isolation, runtime pins, command_count_cap |
| D | launch-config `python_sha256` / `docker_sha256` | Host executables | Retained host Python 3.11 + docker.exe pins |
| E | Created only on authorized launch | `…native-ready-prep-v1.evidence/` | Receipts + fresh `public-ca/` (outside payload) |

Immutable `DockerOps.verify_inputs` compares every actual payload file except the manifest to Root B. Host JSON must not remain under payload even if omitted from the manifest.
