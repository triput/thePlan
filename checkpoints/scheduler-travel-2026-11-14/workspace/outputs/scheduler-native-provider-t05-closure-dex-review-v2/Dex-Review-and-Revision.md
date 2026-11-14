# T05 v2 independent static review — remaining R2 boundary

Preparation review only. No imports, compilation, fake verification, sockets, PKI or native execution performed. Original v2 remains preserved. Its 23 ARTIFACT-HASHES entries match; TIP on-disk SHA256 7CC58CDAF6C6570583D68E94CB842A2810E49AF70F94A9296CBB30237433A638.

The successor visibly adds UNKNOWN refusal before primary unwrapping, helper-owned retirement after partial start, fresh validated plans for each exchange, and fake report dependencies. These are material improvements. This review does not claim executed proof of them.

## R2 remains: receive classification is broader than abrupt EOF/reset

In payload/fixture/np_runner_entry.py, _install_joinedtls_receive_observer catches every ssl.SSLError as abrupt_ssl_error and every OSError as abrupt_tcp_reset. _t05_measured_abrupt_receive then accepts either label without checking the retained exc_type. _t05_admit_abrupt_truncation accepts an OSError/SSLError outcome when those labels are present.

Consequently a generic SSL protocol error or an unrelated OSError at the actual receive boundary can satisfy the abrupt-truncation predicate. TimeoutError is an OSError subclass. Measuring an error at receive is stronger than inferring it from framing, but does not establish that it was EOF or reset. This follows directly from the catch and admission branches; no diagnostic execution was needed.

The extracted R2 checker currently constructs the admitted log directly as class=abrupt_ssl_error, exc_type=SSLError. It never exercises the actual observer's error taxonomy, so it would preserve this false-positive boundary.

## Same-assignment fresh-copy correction

Within the already approved native-provider authoring lane, prepare a fresh successor that distinguishes actual TLS EOF and explicitly selected TCP reset/abort terminal classes from generic SSL/OSError/timeout failures. Admit only the reviewed finite EOF/reset terminals for this case. Generic errors must STOP, not be relabeled as truncation. Preserve production sources, suppress_ragged_eofs=False, local-only close, UNKNOWN refusal, no retries, all retirement and planning contracts, and the first-vertical-only launch batch.

Add finite fake controls exercising the extracted observer with fake JoinedTLS.receive outcomes, then its actual admission predicate: positive EOF/reset, negative generic SSL error, unrelated OSError, timeout, clean EOF, and UNKNOWN. Keep fake dependencies isolated; author only, no invocation. Return exact diffs, labels, manifests and hashes. Do not add expected UNKNOWN or weaken assertions.

Retain one active Jim assignment: this T05 correction/check-packet successor. The separate Dex native-v3 packet is staged and will need an independent static review after this handback; no native launch authority exists.

## Independent native-v3 staging observation

Dex candidate scheduler-native-provider-first-native-launch-candidate-dex-v3 has 265 matching input entries and 257 matching payload entries. All prior 256 payload files (excluding the regenerated manifest) are byte-identical. The only added payload artifact is the pinned empty Docker CLI config, with its explicit directory in host DockerOps config. Evidence directory absent. Peer review remains pending; no execution.

Input-manifest SHA256 26560DF4DF4C33E3FCB1B9A983F30BF8F1569AB0BC5C9D23EC7F892C17B31EAF.
