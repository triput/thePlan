# Matt — thePlan / Scheduler diagnostic preparation: pickup acknowledgement

To: Dex · From: Matt · November 12, 2026, about 18:10 PT · thePlan Matt session

## Picked up
- Assignment `Matt-thePlan-Scheduler-Diagnostic-Preparation-Assignment-2026-11-12.md`, SHA256 `782AB2F2FFD4DEF65190564E0D3979D42056240452764B7540F7E083F6B18E5F`. Signed Dex; it matches the Slack delivery pointer.
- Context zip, SHA256 `23F995D0C9888D84DF77D9454FCD5DF48F7F58D1C5B254E5615F0C6B47E888B2`. It matches the delivery `.sha256` and the Slack post.

## Intake checks (observed, read-only)
- **References:** `References.sha256` inside the zip checks out, 17/17 OK. I extracted it to a scratch folder outside the project.
- **Stopped packet `scheduler-native-provider-first-native-launch-candidate-dex-v3`:**
  - `Input-Manifest.sha256` = `26560DF4…2EAF`, 265 lines; all 265 inputs re-hash OK.
  - `payload/fixture/np_runner_entry.py` = `7FBDCAEE…55FF5`, matching the stopped baseline.
  - `payload/fixture/docker_transport.py` = `7F7EA820…AC53`, matching the immutable host validator.
- **Producer precedent:** `scheduler-native-i01-i02-v4/payload/fixture/runner_entry.py` = `2A4602CC…1FA3E`, as stated.
- **Approved diff:** `V3-Proposed-Runner-Diagnostic.diff` = `F6135717…9832`, as stated.
- **Approval:** `Diagnostic-Preparation-Approval.json` = `258EA8B9…6592`, matching the reference copy.
- **Target workspaces:** `…\outputs\scheduler-native-provider-runner-diagnostic-prep-matt-v1` and `…\outputs\scheduler-native-provider-runner-diagnostic-fake-prep-matt-v1` are both absent, so nothing will be overwritten.

No mismatch was found, so there is no blocker.

## Intended workspace
- Successor packet: `C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-native-provider-runner-diagnostic-prep-matt-v1`
- Fake preparation packet: `C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-native-provider-runner-diagnostic-fake-prep-matt-v1`

## Scope I'm holding to
- Authoring, reading, copying, literal patching, hashing and manifest/JSON authoring only.
- No import, AST parsing, compilation, tests, helper invocation, fake-check execution, certificates, sockets, Docker, database, installation, build or native run.
- No Git operations, and no edits to `F:\Code Repo\ThePlan`.
- No EXECUTE acknowledgement exists, and I'm not assuming one.
- T05 fake staging is out of scope and stays untouched.

The handback will be a signed `Matt-thePlan-Scheduler-…` handoff plus a hash manifest in this folder. Any questions will come as a new thePlan drop.

Signed: Matt
