# C06 prepared packet v1: independent static review

Disposition: REVISE within the approved preparation scope. No verification or native execution requested.

Frozen packet F:DropFolderpendingpost-native-c06-runner-tls-prep-jim-v1-2026-11-10, TIP046D670AC261A3E72920264C44DC16F3DB39B8D5E386CA4D4CAA726ED97108BA. All17 artifact entries and268 payload-manifest entries independently match. Full comparison with the blocked payload finds only the approved three changed fixture files, one new TLS recipe and regenerated manifest. launch-config remains unchanged and false. Production/host helpers, original blocked draft and prior fake PASS remain preserved.

Positive source findings: runner-owned root and exclusive directory checks, distinct parent gate CA versus backend DB CA, public-CA identity evidence, original protocol/commit guards, port15432 and case order are carried forward. Recipe is authored only; actual PKI/TLS proof remains absent.

## 1. Process-group retirement is inferred from shell leader

runner_entry.py _c06_retire_process_group loops only while proc.poll() is None and returns that leader state. SIGTERM may end the shell before a descendant exits; the loop then omits the later SIGKILL/escalation and claims retirement. prepare_c06_runner_tls skips the group helper entirely when the leader already exited. EOF of capture pipes is not group absence; a descendant can close pipes and remain alive.

Required: retain exact owned group custody and establish group retirement independently of leader state under the disclosed bounds. Treat absence/permission/error/unknown honestly. Preserve leader-exited/descendant-alive and SIGTERM-ignored cases in fake controls. The current FakeOS.killpg always kills leader and descendant together, which cannot expose this defect. No broad process enumeration or kill scope is implied.

## 2. Primary precedence and partial capture startup/retirement

The new generation primary is replaced by a retirement exception with the original as cause. Existing scope requires preserving the primary and attaching secondary cleanup evidence. _c06_join_readers may join an unstarted reader if a Thread.start fails; a join exception can skip remaining retirement and replace the primary. Pipe EOF/close/error retirement is not explicitly captured.

Required: track constructed versus started readers and owned pipe endpoints; attempt each required retirement once even when another fails; preserve the actual generation/admission primary, attach bounded secondary evidence, and refuse success on unknown retirement. Exercise the new prepare_c06_runner_tls path with dual faults and partial starts. Current PRIMARY_PRESERVE control instead calls the unchanged suite attach_cleanup_failures_to_primary helper and therefore does not prove the new path.

## 3. Generation/admission budget and capture-stop accounting

A fresh proc.wait(timeout=30) is granted after creation/startup, without a shared generation/admission deadline. The main thread waits out that whole period before inspecting overflow/reader error. During-read retained-buffer bounds alone do not establish prompt stop or truthful total-versus-retained byte observations.

Required: use the reviewed shared30s phase budget rather than renewing it after setup; observe capture failure during collection; keep5s group retirement/two5s joins within disclosed accounting, without increasing600/900 limits. Distinguish total observed bytes from retained buffer lengths. No new hard guarantee over arbitrary OS/file operation latency should be claimed.

## 4. Several negative controls record string checks as behavioral refusal

Trust-parent/backend negatives inspect source strings rather than executing the changed builder/context with fakes. Wrong-root negative only proves two paths differ. Occupied-port and N06 order controls do not invoke the actual refusal branch. Hook-order test finds the first text prepare_c06_runner_tls(), which can be its def rather than the call in main, so moving the call after the audit hook need not fail it.

Required: run extracted actual changed functions/branches against fake dependencies and deliberately wrong inputs; mutation/negative controls must fail if the guard is removed or miswired. Static inventory/recipe/AST checks remain useful but must be labeled as static checks rather than counted as behavioral refusal. Inspect the actual call site within main for audit ordering. Keep real PKI/native claims deferred.

## 5. Held harness admission, provenance and result truthfulness

Verification-Commands-Held.md currently invokes ambient python directly, without a pinned interpreter, bounded launcher, exact input-manifest enforcement, output caps or retained launcher/retirement receipt. check_c06_runner_tls_fake.py defines MANIFEST_PATH/sha256_file but does not enforce extraction pins in main. Its successful runtime result writes executed=false/held=true, falsely describing a later actual run as unexecuted. _module_from_defs executes into one dict then copies it into a new unregistered ModuleType, recreating the function-global/module-dict mismatch already fixed in the original22-control packet.

Required: prepare a pinned bounded held launcher/outer admission and complete enforcing manifests, retaining exact source provenance/order/outcomes and child/reader retirement. The authored script should mark actual run truthfully when invoked under later authority. Create/register the synthetic module before exec into that same module.__dict__, enforce required symbols, and fail closed on pin mismatch. Do not run anything while authoring. Previously reviewed22-control patterns can inform this packet; its frozen inputs/results must not be changed.

## Continuation within authority

Jim should prepare a fresh revised copy under the same four-file source scope and separate verification-authoring authorization; preserve this v1 and all evidence. No source scope increase, app/host helper modification, tests/imports, certificate generation, Docker or native launch. Return exact diff/hashes/manifests and held commands. These findings concern preparation acceptance; the original C06 native blocker is not yet proven closed.