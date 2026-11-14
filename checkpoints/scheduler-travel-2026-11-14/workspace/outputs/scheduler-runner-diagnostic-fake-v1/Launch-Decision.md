# Runner-diagnostic fake verification: preparation (HELD)

Matt, November 12, 2026, for Dex review. **No execution is authorized.** Nothing in this packet has been imported, parsed, compiled, tested or invoked. Only file reads, copies, literal patching, hashing and authoring took place.

## Purpose
Prove, with fakes only, the behavior of the approved STOP diagnostic in the successor runner (`np_runner_entry.py` `40A1BA8E…BF73F`) against:
- the actual extracted text of its `stop_payload`;
- the original and candidate `__main__` STOP handlers;
- the immutable host validator `DockerOps._record_runner_stop`, plus its `_id` and `digest` (`docker_transport.py` `7F7EA820…AC53`).

## Roles (layout follows the reviewed `scheduler-native-provider-fake-v1` pattern)
| Role | File | SHA256 | Origin |
| --- | --- | --- | --- |
| Wrapper | `packet/Invoke-Fake.ps1` | `AE84E632…FEB7` | byte-identical reuse |
| Outer admission | `packet/verify/verify_admission.py` | `7DCA32E2…18FB` | byte-identical reuse |
| Launcher | `packet/verify/launch_check.py` | `D22C37E3…BD07` | byte-identical reuse (bounded capture, owned-child retirement, exclusive receipt) |
| Checker | `packet/verify/check_native_provider.py` | `D4010F1B…EBE8` | **new** (name kept so the launcher stays unchanged) |
| Expected inventory | `packet/verify/EXPECTED-FAKE-STRUCTURAL.json` | `D6702FE7…EE32` | new |
| OUTER admission | `packet/verify/OUTER-ADMISSION.json` | `23460848…DBD9` | new; `launch_authorized=false` |
| VERIFICATION admission | `packet/verify/VERIFICATION-ADMISSION.json` | `D482CEB1…7F54` | new; `launch_authorized=false`; 11 packet pins + 1 runtime pin |

**Subjects** (raw copies, each pinned by both the admission and the checker):
- original runner `7FBDCAEE…`
- candidate runner `40A1BA8E…`
- host `7F7EA820…`
- I01/I02 producer `2A4602CC…`
- approved diff `F6135717…`

**Acyclic chain:** the wrapper takes the VERIFICATION hash as an argument; VERIFICATION pins OUTER; OUTER pins the checker, launcher, expected inventory and interpreter. Nothing pins back up the chain.

## Finite controls (14 top-level, in order)
1. **SUBJECT-PINS:** raw hashes of the subject copies, which must be LF only.
2. **DIFF-REDERIVATION:** a pure-text application of the approved diff to the original must equal the candidate bytes. Three hunks, one file.
3. **PRODUCER-PRECEDENT-IDENTITY:** the candidate `stop_payload` text equals the passed I01/I02 producer's.
4. **DECLARATION-MATCHES-BEHAVIOR:** `failure_evidence_limits` is checked exactly in both original and candidate; the 3/8/128/4096 bounds and the fallback each appear once in the producer.
5. **ORIGINAL-STATUS-KIND-ONLY:** the actual original handler emits `{status, kind}` with exit 125; the host records `diagnostic_unavailable`.
6. **CANDIDATE-HAPPY-PATH:** owned frames are retained untruncated, and the host keeps the exact diagnostic.
7. **CAUSE-CONTEXT-CYCLE:** cause; context only; cause preferred over context; cycle (truncated).
8. **OWNED-FRAME-REJECTIONS:** path outside root; not in manifest; source hash mismatch; line 0; line past end; lowercase manifest pin; non-canonical manifest path; non-`.py` file; identifier sanitized to `Exception`.
9. **BOUNDS-AND-TRUNCATION:**
   - more than 3 exceptions (newest 3 kept);
   - more than 8 frames (newest 8 kept);
   - traceback walk exactly 128 nodes, counted by an instrumented fake traceback;
   - envelope over 4096 bytes (trimmed from the first entry, result ≤ 4096).
10. **DIAGNOSTIC-FALLBACK:** missing manifest; malformed row; inherited exotic-name fallback where the host refusal is **expected**, and the producer is not changed.
11. **PRIVACY-ENVELOPE:** sentinel secrets placed in args, locals and source text never appear; only allowed keys are present.
12. **UNCHANGED-STOP-EXIT:** an AST comparison shows the handlers differ only in the `_stop` expression. Both actual handlers are run with RuntimeError and KeyboardInterrupt (single LF line, flush, exit 125) and on the success path (no STOP output, exit 0).
13. **HOST-VALIDATOR-EXTRACTED:**
    - accepts both the candidate and the original envelope;
    - ignores an attach it doesn't own;
    - refuses 12 malformed or out-of-bounds inputs, covering CR, two lines, over 4096 bytes, duplicate key, primary-kind mismatch, unowned frame, out-of-bounds line, version 2, 4 exceptions, 9 frames, an extra top-level key and a non-int exit.
14. **MUTANT-DETECTION:** frame cap 9, fallback removed, context ignored, walk limit 129. Each must be caught by its targeted oracle; a failure for any other reason stops the run.

## Limits
- **Not run.** Python syntax and behavior are unverified until an approved run; preparation forbids even AST parsing or compilation.
- **Fake scope only.** No native, PKI, TLS, Docker, database or provider proof, and no attribution of the stopped v3 raise site. Real container traceback paths are untested.
- **Inherited roles.** The reused launcher and wrapper are scheduler-native-provider roles, so their receipt and lineage labels name that family. The result kind `fake-native-provider-structural-result` is required by the reused launcher.
- **Timing.** Checker budget 120 s, plus at most one 5 s kill/wait, plus two 5 s reader joins: 135 s nominal. Startup, hashing and OS latency are excluded. There is no separate outer timeout.
- **Capture.** 64 KiB each for stdout and stderr; 256 KiB for the result.
- **Success** requires exit 0, zero stdout and stderr output, the exact ordered 14-control PASS inventory, and joined clean EOF readers.
- **Evidence.** Result and receipt are written exclusively under `packet/verify/`, and existing evidence refuses admission. On any failure, timeout or UNKNOWN: stop, preserve the evidence, and do not retry, repair, rerun or clean up.
- **Runtime pin is partial.** It covers the interpreter executable only, not the standard library or environment.

## Future command
See `Future-Command-HELD.ps1.txt`. Against the current admission, the wrapper refuses because `launch_authorized` is false. A run needs:
- a reviewed staging change that flips both booleans;
- a new admission hash;
- Trish's explicit one-shot approval, which must include authority to terminate the one owned check child on error, timeout or overflow.
