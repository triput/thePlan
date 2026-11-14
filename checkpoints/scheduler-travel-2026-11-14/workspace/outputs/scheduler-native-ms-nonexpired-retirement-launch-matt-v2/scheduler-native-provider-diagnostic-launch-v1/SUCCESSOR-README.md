# Runner diagnostic successor — preparation only (Matt v1)

Matt, November 12, 2026. This packet implements the approved assignment `Matt-thePlan-Scheduler-Diagnostic-Preparation-Assignment-2026-11-12.md` (SHA256 `782AB2F2…8E5F`).

**Status: STAGED_NOT_EXECUTED.** It is not launch-ready. Nothing in it has been imported, parsed, compiled or run. Human launch authority is HELD, and no EXECUTE acknowledgement exists.

## Lineage
- **Base:** a fresh byte copy of `scheduler-native-provider-first-native-launch-candidate-dex-v3`. All 265 of its input-manifest entries re-hashed OK before copying (`26560DF4…2EAF`). The stopped packet and its `.evidence` directory are untouched.
- **Source change:** exactly one. The approved diff `V3-Proposed-Runner-Diagnostic.diff` (`F6135717…9832`) was applied with `patch -p1`, cleanly, with no fuzz, to `payload/fixture/np_runner_entry.py`.
  - The base was `7FBDCAEE…55FF5`. The result is `40A1BA8E…BF73F`, which equals Dex's expected exact LF candidate.

## Metadata refreshed (truthfully)
- **`payload/SHA256SUMS.txt`:** only the runner pin line changed, and the file was re-sorted. All 257 pins verify. Its aggregate hash is `3B25ABB6…2A90`.
- **`host/launch-config.json`:**
  - The packet name and the paths to the ops config and receipt directory now name this successor.
  - `manifest_sha256` is now `3B25ABB6…2A90`.
  - **`launch_ready` is false.** The operator refuses before starting any child.
  - `candidate_launch_ready_staged` is false.
  - The candidate note was rewritten, and lineage keys were added.
- **`host/docker-ops-config.json`:** only its 8 path strings changed, to name this successor. Every other byte is unchanged.

## Unchanged by design
- All 234 `payload/api` files.
- Every other fixture, helper and host executable file, including `docker_transport.py` (`7F7EA820…AC53`) and `Invoke-Native-Provider.ps1` (`090A0FA8…F612`).
- `payload/runner-config.json`. It still carries the inherited `launch_ready: true`, which is not permission.

## Historical copies (NOT current instructions)
`TIP-FREEZE.json`, `Launch-Decision.md`, `Static-Staging-Receipt.json` and `Reviewed-Command.ps1.txt` are byte-identical copies of the dex-v3 records. They describe the stopped packet. **`Reviewed-Command.ps1.txt` is not an authorized or current launch command**: it names the dex-v3 operator and the old config hashes.

## Known launch blocker (design objection O1)
The byte-unchanged operator hardcodes its evidence directory as `…\scheduler-native-provider-first-native-launch-candidate-dex-v3.evidence` (line 42). That directory exists, holding the preserved failure evidence, and line 93 refuses whenever an evidence directory already exists. So this successor fails closed: it cannot launch without a separately reviewed operator change, which is outside this assignment.

`Input-Manifest.sha256` covers every file in this packet except itself.
