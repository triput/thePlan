# Native T05 client-cause diagnostic preparation v1 (CURRENT README)

Matt, November 13, 2026. This is for `Matt-thePlan-Scheduler-T05-Client-Cause-Diagnostic-Preparation-2026-11-13.md` (`9F9FF48E…D511`), under lane `389A00DD…7E2D`. It's a fresh copy of the failed-run source root `scheduler-native-provider-t05-launch-dex-v1` (`417BEA58…596F`, 297 inputs, verified 297/297). That root, its evidence and its cleanup reconciliation are untouched.

**Status: PREPARED_NOT_EXECUTED, frozen.**
- **False:** host `launch_ready` and `candidate_launch_ready_staged`, and runner `launch_ready`.
- **True, as copied machine data:** the docker-ops flags. That is never human authority.
- The endpoint is unbound.

## Current versus historical
- **Current:** this README, `T05-Client-Cause-Prep-Freeze.json`, `T05-Client-Cause-Native-Command-HELD.ps1.txt` and this root's `Input-Manifest.sha256`.
- **Historical:** every other top-level document or command, including the copied `Reviewed-Native-T05-Command.ps1.txt`, `T05-Native-Review-and-Commands.md`, `Dex-T05-Staging-Receipt.json` and `Prerequisites-HELD.json`. They describe other roots.
- **Lineage:** `Source-T05-Launch-Dex-V1-Input-Manifest.sha256`.

## The only behavioral source change (role 4, diagnostic)
- **In `_t05_observe`:**
  - `client_exc: BaseException | None = None` sits beside `outcome`;
  - the existing `except Exception as exc:` also sets `client_exc = exc`, and the outcome tuple is unchanged;
  - the classifier call, still placed after the bounded retirement, the joined/no-worker-error check and the exact peer-inventory check, is now `_t05_classify_or_chain(expectation, outcome, client_exc)`.
- **New pure `_t05_classify_or_chain`** (local `from np_suite import SuiteStop`):
  - it calls the unchanged `_t05_classify_client_outcome`;
  - it returns an admitted label unchanged;
  - on `SuiteStop` with a client exception, it re-raises the **same** guard object `from` the **same** client exception;
  - with `None`, it does a bare re-raise, as today;
  - any other exception propagates unchanged.
- **Byte-identical:** the classifier, the exact expected tuples, every assertion, the transcript, peer, `stop_payload`, host validator, application and helpers.
- **No changes to:** the STOP fields, the messages, or the 3/8/128/4096 bounds.

## Path agreement (unchanged operator `5A8A04B6`)
- **Evidence:** `…\scheduler-native-provider-t05-client-cause-prep-matt-v1\scheduler-native-provider-diagnostic-launch-v1.evidence`, which is the host `receipt_directory` and the docker-ops evidence mount. It is absent.
- **Default receipt:** `…\native-provider-host-receipt.jsonl` (operator l.135–137).
- **Public CA:** `…\public-ca`, mounted at `/public-ca`. The runner binds it in `bind_runtime_public_ca_hash`, and `run_suite` checks it.
- There's no `-ReceiptPath` in the held command.

## Not claimed
Nothing native. Whatever class a later run would reveal is unknown until an approved run, and the failed run's actual client outcome stays unretained.
