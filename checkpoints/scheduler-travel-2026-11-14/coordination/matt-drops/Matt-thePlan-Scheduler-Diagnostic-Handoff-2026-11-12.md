# Matt → Dex: thePlan / Scheduler runner-diagnostic preparation handback

November 12, 2026, about 18:40 PT. This responds to `Matt-thePlan-Scheduler-Diagnostic-Preparation-Assignment-2026-11-12.md` (SHA256 `782AB2F2…8E5F`); the pickup ack is `Matt-thePlan-Scheduler-Diagnostic-Pickup-Ack-2026-11-12.md`.

**Status: both deliverables are authored and frozen. No writer is active.** Nothing was imported, parsed, compiled, tested or run. Execution and native readiness remain HELD, and no EXECUTE acknowledgement exists or is assumed.

## 1. Diagnostic successor packet
**Workspace:** `C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-native-provider-runner-diagnostic-prep-matt-v1`

**Base.** A fresh byte copy of `scheduler-native-provider-first-native-launch-candidate-dex-v3`. All 265 input-manifest entries re-hashed OK before the copy, and again after all work (manifest `26560DF4…2EAF`). The stopped packet and its `.evidence` directory are untouched.

**Source change.** Exactly one: `patch -p1` applied the approved diff `F6135717…9832` to `payload/fixture/np_runner_entry.py`, cleanly, with no fuzz or offsets.
- **Candidate SHA256 `40A1BA8E9C3E320DD7DF9E06102CC29C0E1AFAAD4213EC0FECF9FE34455BF73F`, which equals the expected exact LF candidate.**
- The file is LF only.

**Metadata refreshed truthfully.** The full diff against dex-v3 is in `Matt-thePlan-Scheduler-Diagnostic-Successor-Diff-2026-11-12.diff`.
- **`payload/SHA256SUMS.txt`:** only the runner pin line changed, and the file was re-sorted. All 257 pins verify; the new aggregate is `3B25ABB656F991B3B80F012C9E67E5840E48AAACD3AE2336DE13AFB8039B2A90`. The candidate `stop_payload` reads this file for owned paths, so leaving it stale would have made every runner frame look unowned.
- **`host/launch-config.json`** (now `33B56B7A…F6A`):
  - packet name and the ops-config and receipt paths now name the successor;
  - `manifest_sha256` is now `3B25ABB6…`;
  - **`launch_ready` is false** and `candidate_launch_ready_staged` is false;
  - the candidate note was rewritten, and five `diagnostic_successor_*` lineage keys were added.
- **`host/docker-ops-config.json`** (now `201A7A72…0CA`): only its 8 path strings changed (dex-v3 → successor). Every other byte is unchanged.
- **New `SUCCESSOR-README.md`:** lineage, the historical-copy labels and blocker O1.
- **`Input-Manifest.sha256`** (`899B06F6…0DA7`) covers 266 files and re-verifies 266/266.

**Unchanged by design.**
- All 234 `payload/api` files.
- Every other fixture, helper and host executable file, including `docker_transport.py` `7F7EA820…AC53` and `Invoke-Native-Provider.ps1` `090A0FA8…F612`.
- `payload/runner-config.json`: inherited `launch_ready: true`, not permission. See question Q1.
- `TIP-FREEZE.json`, `Launch-Decision.md`, `Static-Staging-Receipt.json` and `Reviewed-Command.ps1.txt` are byte-identical **historical** dex-v3 records, labeled as such in the README. They are not current launch instructions or pins.

## 2. Fake-verification preparation packet
**Workspace:** `C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-native-provider-runner-diagnostic-fake-prep-matt-v1`. It has 14 files; `Input-Manifest.sha256` is `398F8A3C4CE2C77640AE0D812CB5E6C3FFAECB045D19F2FCFB5D49E7194DCA3D`.

**Roles.**
- **Reused byte-identical** from the reviewed `scheduler-native-provider-fake-v1`, so the accepted bounded capture, owned-child retirement and exclusive-evidence behavior carry over unweakened:
  - `Invoke-Fake.ps1` `AE84E632…`
  - `verify_admission.py` `7DCA32E2…`
  - `launch_check.py` `D22C37E3…`
- **New:**
  - checker `check_native_provider.py` `D4010F1BBA744F65DAB118E8FF384C69BD217427BEC0A7FF690CD1D0D954EBE8`. The name is kept so the reused launcher stays unchanged.
  - `EXPECTED-FAKE-STRUCTURAL.json` `D6702FE7…EE32`
  - `OUTER-ADMISSION.json` `23460848…DBD9`
  - `VERIFICATION-ADMISSION.json` `D482CEB1…7F54`

**Admissions.** Both have **`launch_authorized=false`**. VERIFICATION pins 11 packet files plus 1 runtime file, the interpreter `5F7B89A6…52EC`, which I re-hashed today. The chain is acyclic: the wrapper takes the VERIFICATION hash, VERIFICATION pins OUTER, and OUTER pins the checker, launcher, expected inventory and interpreter.

**Subjects.** Raw copies pinned by both the admission and the checker:
- original `7FBDCAEE…`
- candidate `40A1BA8E…`
- host validator `7F7EA820…`
- I01/I02 producer `2A4602CC…`
- approved diff `F6135717…`

**Controls.** A finite inventory of 14 top-level controls in order, with about 50 nested cases. `Launch-Decision.md` in the packet has the full list and maps them to Justin's control design.
1. SUBJECT-PINS
2. DIFF-REDERIVATION (pure-text re-application must reproduce the candidate bytes exactly)
3. PRODUCER-PRECEDENT-IDENTITY
4. DECLARATION-MATCHES-BEHAVIOR
5. ORIGINAL-STATUS-KIND-ONLY
6. CANDIDATE-HAPPY-PATH
7. CAUSE-CONTEXT-CYCLE
8. OWNED-FRAME-REJECTIONS
9. BOUNDS-AND-TRUNCATION (3, 8, an exact 128-node walk via an instrumented fake traceback, 4096)
10. DIAGNOSTIC-FALLBACK, including the inherited exotic-name fallback, where a host refusal is **expected** and the producer is unchanged
11. PRIVACY-ENVELOPE
12. UNCHANGED-STOP-EXIT (AST equality apart from the `_stop` expression, plus actual handler runs for RuntimeError, KeyboardInterrupt and success)
13. HOST-VALIDATOR-EXTRACTED (accepts candidate and original envelopes, ignores unowned attach, 12 refusals)
14. MUTANT-DETECTION (four mutants, each of which must be caught by its targeted oracle)

**How the checks work.** Everything is driven by the *actual extracted source text* (`stop_payload`, both `__main__` handlers, and `_record_runner_stop`/`_id`/`digest`). It runs against an in-memory fake filesystem, fake tracebacks and fake exceptions. Only the standard library is imported: no app or vendor imports, sockets, TLS, PKI, Docker, database, child processes or network inside the checks.

**Future command:** `Future-Command-HELD.ps1.txt`. Against the current admission the wrapper refuses before starting any child. A run needs:
- a reviewed staging change that flips both booleans;
- a new admission hash;
- Trish's one-shot approval, including authority to terminate the one owned check child.

**Bounds.** 120 s, plus 5 s for the kill/wait, plus two 5 s reader joins: 135 s nominal. 64 KiB per stream and 256 KiB for the result. The result and receipt go exclusively to `packet/verify/`, and existing evidence refuses admission. On failure, timeout or UNKNOWN: stop, with no retry, repair, rerun or cleanup.

## 3. Proof status (kept distinct)
- **Authored behavior:** the candidate runner equals the approved diff, and the metadata and fake packet were authored as described above.
- **Static review (mine, by reading only):**
  - the approved hunks match the stopped baseline;
  - the producer's dependencies (`ROOT`, `Path`, `hashlib`, `json`) exist in the runner;
  - the manifest format matches both the producer and host parsers;
  - I hand-computed the 4096-byte trim case: the first exception is trimmed to 0 frames and the other two keep 8, which the assertion allows;
  - host refusal inputs were traced through `_record_runner_stop`.
- **Fake proof: NOT RUN.** The checker's Python syntax and behavior are unverified. Preparation forbids parsing and compiling, so a syntax or logic error in my checker is possible, and the first approved run is its first execution.
- **Native proof: NOT RUN.** There is no attach, real traceback paths, PKI, TLS, database or provider proof, and no attribution of the v3 raise site.

## 4. Design objections and questions
- **O1 (blocker for any later native launch; no change made).** The byte-unchanged operator `Invoke-Native-Provider.ps1` hardcodes `$evidence = …\scheduler-native-provider-first-native-launch-candidate-dex-v3.evidence` (line 42) and refuses an existing evidence directory (line 93). That directory exists and holds the preserved failure evidence, so the successor fails closed: an invocation stops before starting any child.
  - The successor cannot launch without a separately reviewed operator change; earlier successors each changed this line.
  - The assignment forbade host-executable changes, so I flagged this rather than fixing it. Suggest folding it into the later launch card.
- **Q1.** Your acceptance says "native launch flags remain false". I set the host gate (`launch_ready`, `candidate_launch_ready_staged`) to false and left `payload/runner-config.json` byte-unchanged (inherited `launch_ready: true`). Flipping that file would change a payload input the runner admits. If you want it false too, it's a one-line metadata change plus a re-pin of the manifest.
- **Q2.** The reused launcher and wrapper carry "native-provider" kinds and lineage labels, and the result kind `fake-native-provider-structural-result` is required by the reused launcher. I chose byte-identical reuse over relabeling. Tell me if you'd rather have relabeled copies, which would then need fresh review.
- **Note.** The checker includes four mutation controls beyond Justin's design. They prove the bounds, fallback and context oracles have teeth.

## 5. Completed and incomplete
- **Completed:**
  - intake verification;
  - the successor packet and metadata;
  - the fake packet, admissions, expected inventory, launch-decision document and future command;
  - freeze manifests;
  - this handoff, the successor diff and the hash manifest.
- **Incomplete or held:**
  - any fake run, and syntax verification of the checker;
  - the operator evidence-path change (O1);
  - Q1 and Q2;
  - all native work;
  - T05 (untouched).

## Scope statement
I stayed within the assignment:
- Only reading, copying, literal patching, hashing and file/JSON authoring were done.
- No imports, AST parsing or compilation of authored or staged Python, and no tests or helper invocation.
- No certificates, sockets, Docker, database, installation, build or native run.
- No Git operations, no edits to `F:\Code Repo\ThePlan`, and no existing drops or pickup logs were overwritten.
- One read-only PowerShell JSON parse check was attempted and blocked by the harness, so JSON validity is checked by eye only.
- New writes were limited to the two named workspaces, a scratch extraction of the context zip and my own Matt-Drops files.

Signed: Matt
