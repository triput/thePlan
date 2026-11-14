# Native-provider v3 offline trace — evidence and proposed next diagnostic

Offline source/receipt review only. Failed packet and evidence are preserved. No new imports, compilation, tests, live checks, repairs or rerun. Cleanup was separately authorized and completed; both exact IDs are absent and DB SIGINT exit0 is reconciled.

## Established evidence

One authorized native attempt exited1 at the host operator after runner attach returned125. The recorded runner envelope is status=STOP, kind=SuiteStop, diagnostic_unavailable=true. Runner stdout was empty; stderr40 bytes were hashed, not retained raw. The host receipt records12 Docker commands and joined capture readers. DB image/readiness and public-CA transfer checks returned successfully before runner creation/attach. No suite report or suite_pass was recorded. Do not infer successful provider PKI retirement or a successful provider request from this partial record.

Receipt SHA256 FC3822C3A1CA0DBD7F6903BDACB0E6F32E2553381044841B1B72AB3B73F63D6D. All265 input pins remain unchanged. Cleanup receipt SHA256 2FB901B4AE779B73A36345EDF71A580A8401E03C4A3BA31C736D9348DE60E8DB.

## Source trace

The host np_supervisor.ProviderDockerOps.run_attached delegates to the immutable DockerOps._cmd for exactly start/attach of the owned runner. DockerOps._record_runner_stop already accepts either the minimal status/kind envelope or a bounded version1 diagnostic containing up to3 exception classes and8 packet-owned source locations per exception. It validates every location against current manifest-pinned bytes and source line bounds. The host helper therefore needs no schema/code change to retain that existing diagnostic format.

The failed np_runner_entry.py bottom-level exception handler (lines1458–1466) intentionally emits only status/kind and exit125. It never calls the predecessor location-only stop_payload helper. The host's diagnostic_unavailable=true is expected for those exact bytes, not evidence of a host parse failure.

SuiteStop is raised at many distinct vertical assertions, in check_oracles_immediate, or as a wrapper for another exception. The broad case wrapper at lines1157–1160 can convert an underlying exception into SuiteStop while retaining it as __cause__. The minimal envelope discards both its source location and that cause's class. The retained class/hash cannot establish which assertion or underlying failure occurred. No behavioral application/fixture fix is justified by this record alone.

## Narrow proposed next step, subject to Jim reconciliation

Recommend fresh-copy preparation of a runner-only diagnostic change: reuse the established location-only stop_payload implementation from passed scheduler-native-i01-i02-v4/payload/fixture/runner_entry.py (SHA256 2A4602CCDFA68787697ED4FD472B3BEA41FD9FC31F8F808C409339140C81FA3E) in np_runner_entry.py, call it in the existing STOP handler, and update that file's failure-evidence declaration truthfully. ROOT already identifies the /packet manifest root in both entry designs. Preserve STOP/nonzero behavior and all transaction, assertion, TLS, planning, deadline and retirement contracts. No host helper, application or result schema change is needed.

Bounds stay the existing4096-byte single-line envelope, at most3 exception classes,8 manifest-owned path/line entries per exception,128 traceback nodes traversed per exception, with truncation and fallback to original status/kind. No exception messages, locals, SQL, request bodies, keys, credentials, raw stderr or complete traceback text. Diagnostics must never replace the primary failure or imply PKI success.

Preparation should include separate fake-only original/candidate controls for cause chains, root/path/source-hash/line-bound rejection, finite chain/frame/byte caps, truncation/fallback and unchanged exit/stop behavior, using fake traceback/filesystem boundaries. Existing immutable host validator can be exercised with fake owned attach inputs. No actual native run is included in preparation or fake verification.

This is a diagnostic proposal, not a claimed root-cause fix. Obtain explicit source-change approval after reconciling Jim's independent trace, because the stopped-run no-repairs hold remains. Any fake verification and any later native attempt need their own exact reviewed command, hashes, scope, limits and explicit one-shot execution authority. Do not modify failed v3.
