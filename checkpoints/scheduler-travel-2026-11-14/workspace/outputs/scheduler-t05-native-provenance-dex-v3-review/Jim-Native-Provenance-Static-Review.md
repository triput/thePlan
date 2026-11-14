# Jim Native Provenance Static Review v1 — scheduler-t05-native-provenance-dex-v3

**Reviewer:** Justin (for Jim)
**Date:** 2026-11-11
**Packet:** C:/Users/trish/Documents/Codex/2026-10-15/trish-wants-to-improve-dex-s/outputs/scheduler-t05-native-provenance-dex-v3/
**Method:** Read-only independent static review of Dex native-v3 (native-v2 + manifest-continuity guard + packet-label change). Hash-verify Dex-stated pins and every packet file. Reconcile Dex continuity note and proposed continuity diff against live supervisor. Preserve v2 as immutable/unexecuted peer. No packet edits. No Docker. No import/compile/invoke of packet helpers. No execution.
**Flags:** review_only=true; executed=false; launch_authorized=false
**Continuity note:** Native-V2-Manifest-Continuity-Review.md SHA256 9708406AAB6E222A5FA4425FDA75BCBF0B054E462305E1FBFABAA063AFD2F379 (MATCH)
**Continuity proposed diff:** Native-V2-Manifest-Continuity-Proposed.diff SHA256 AA59F9A407FD0213FAABB5BBC5D77B444CDC04392D823B09456A44B81689C130 (present; intent CLOSED in v3)

## Disposition

**QUALIFIED ACCEPT** — native-v3 statically closes the v2 pre-removal manifest continuity gap; Dex control-surface pins MATCH; held collector/supervisor are real (not descriptor-only); execution holds remain explicit. This review does **not** authorize launch.

Blocking findings: **0**.

## Dex-stated pin verification

| Subject | Expected SHA256 | Observed | Result |
| --- | --- | --- | --- |
| SHA256SUMS.txt (manifest) | 4F2BAECBEBA79A4E5BFF6D2A6A04CB658DF8775BCE91F368BE6152260BE1AC37 | 4F2BAECBEBA79A4E5BFF6D2A6A04CB658DF8775BCE91F368BE6152260BE1AC37 | MATCH |
| Commands.ps1.txt | 501FAB56FC51F8C8B147EE0B7F29FED8B3F2D95AD7C793FE691953D407C83C55 | 501FAB56FC51F8C8B147EE0B7F29FED8B3F2D95AD7C793FE691953D407C83C55 | MATCH |
| verify_native_provenance.py | 6A5746C7513FEB438C3465FDA1A7F44B50208E90DE19F43D78294E6AEC760B9A | 6A5746C7513FEB438C3465FDA1A7F44B50208E90DE19F43D78294E6AEC760B9A | MATCH |
| Proposed-New-Files.diff | 43486A343480644E8C755CF5B880893C6431DCA8367CEE725BB0801C8A89D289 | 43486A343480644E8C755CF5B880893C6431DCA8367CEE725BB0801C8A89D289 | MATCH |

Proposed-New-Files.diff reconstructs byte-identical to on-disk `verify_native_provenance.py` and `collect-parser-sources.sh` (extracted hashes MATCH live).

## Full packet hash table (reviewed)

| Relative path | SHA256 |
| --- | --- |
| collect-parser-sources.sh | 547151B1F530B7A7726C6FD3E5277CA3EF91EE7B0110E0C2C127E95D54AD2FFE |
| Commands.ps1.txt | 501FAB56FC51F8C8B147EE0B7F29FED8B3F2D95AD7C793FE691953D407C83C55 |
| Jim-Static-Review-Request.txt | 0287917026FD4EE87E6961176CA009C60D48569A0F30B00FCEAB21D01E8F63EE |
| Post-Run-Reconciliation-Checklist.md | 8A4789CF5CDD415A8906BE8DF9C47C5183F2C861B9CD76DF7B5FD5CC5D888688 |
| Preparation-Receipt.json | 945DCAA64A1B8675F9E7FFD76AFCB2DD2A13191AB4A94516B46022E702A4376F |
| Proposed-New-Files.diff | 43486A343480644E8C755CF5B880893C6431DCA8367CEE725BB0801C8A89D289 |
| Review-and-Commands.md | 793BC2E3E96F00F42E85A4040D4BD7ACBF51130AC862BCC9EC503D7AC4326AE7 |
| Runtime-Pins.json | 2A2F3BE4975DC8747D677CBD5C9EF0C940BD60D9F6A781BFA1F4F6BE3E14FCDC |
| SHA256SUMS.txt | 4F2BAECBEBA79A4E5BFF6D2A6A04CB658DF8775BCE91F368BE6152260BE1AC37 |
| Static-Preflight.json | 945DCAA64A1B8675F9E7FFD76AFCB2DD2A13191AB4A94516B46022E702A4376F |
| verify_native_provenance.py | 6A5746C7513FEB438C3465FDA1A7F44B50208E90DE19F43D78294E6AEC760B9A |
| docker-config/config.json | E3566B3A06430868D71E9287DFD6C6C520A3DA027AABEA01951D407EE131DC2F |

Manifest four rows each MATCH live packet bytes. Preparation-Receipt.json and Static-Preflight.json are byte-identical (same SHA). Evidence dir `scheduler-t05-native-provenance-dex-v3.evidence` **absent**.

## V2 finding preserved and reconciled (manifest continuity)

Dex continuity note (v2 target supervisor 4122E5DD…): admission verified `SHA256SUMS.txt` against `manifest_pin`, but pre-removal re-read the manifest file and compared packet files against **freshly read** rows without rechecking the manifest file hash against the approved pin — a static continuity gap.

v3 closes that gap exactly (static read of verify_native_provenance.py 6A5746C7…):

1. **Retain admitted pairs** at admission: `admitted_inputs = []` then `admitted_inputs.append((pin, path))` (lines 56–64).
2. **Rehash manifest against approved pin before cleanup:** `if sha(manifest) != manifest_pin.upper(): raise … 'post-collection manifest drift'` (lines 294–295) — precedes `container rm`.
3. **Compare original admitted pairs**, not a freshly trusted inventory: `for pin, path in admitted_inputs: if sha(path) != pin: raise … 'post-collection packet drift'` (lines 296–298).

This matches Native-V2-Manifest-Continuity-Proposed.diff intent. v2 peer packet remains immutable/unexecuted (manifest A526C8E3…; supervisor 4122E5DD… still lacks the guard). Checklist V3 note requiring independent verification of that guard: **satisfied**.

## Packet-label change (coherent / truthful)

| Surface | Observation |
| --- | --- |
| PACKET constant | `scheduler-t05-native-provenance-dex-v3` (supervisor L21) |
| Commands.ps1.txt `$packetRoot` | exact v3 absolute path |
| Commands `--manifest-sha256` | 4F2BAECB… (v3 manifest) |
| Evidence root | `ROOT.parent / (PACKET + '.evidence')` → v3-named |
| Docker label | `dex.native-validation=` + PACKET; inspect requires `obj['label'] == PACKET` |
| Receipt/preflight | kind “v3; not executed”; predecessor points at v2; predecessor_manifest A526C8E3… |
| Review-and-Commands | states only packet label/root + continuity guard change executable behavior; collector/runtime byte-identical to v2 |

Collector SHA 547151B1… and Runtime-Pins SHA 2A2F3BE4… are **byte-identical** to v2 (confirmed). Label/root/manifest/supervisor pins differ as expected. No stale v2 root or v2 manifest pin remains in the v3 operator sequence.

## Held roles — not descriptor-only

- **collect-parser-sources.sh** (1176 B): real `/bin/sh` + in-container `/usr/local/bin/python3 -I -S -B` heredoc; reads exactly three TARGET paths; size refusals; stdout-only base64/json envelope `T05-NATIVE-SOURCE-BYTES-V1`; no app/vendor imports; no writes.
- **verify_native_provenance.py** (17350 B / 327 lines): real seven-command Docker supervisor adapted from runner-only-v3 pattern — not a stub. Full process custody (readers, caps, retirement, receipt.jsonl), identity/isolation/mount/state inspect, envelope decode + saved-byte rehash, success-only exact-ID rm + absence check.

## Control checklist (static)

| Control | Location / observation | Status |
| --- | --- | --- |
| Docker identity | image pin `sha256:c220…d2ab`; create/inspect ID; user `65534:65534`; label=PACKET; entrypoint `/bin/sh`; cmd collector | PASS (static) |
| Isolation | network none; read-only root; cap-drop ALL; no-new-privileges; 256MiB mem+swap; 1 CPU; 32 PIDs; no ports/devices/tmpfs/CapAdd/AutoRemove; restart no; log none; `--pull=never` | PASS (static) |
| State checks | inspect requires Status match + not Running + not OOMKilled; exited requires ExitCode 0 | PASS (static) |
| ro /packet | create `--volume ROOT:/packet:ro`; Binds exact; mounts Dest=/packet RW=false; no writes into /packet by collector (stdout only); host writes only under fresh evidence | PASS (static) |
| Source hash/size | PER_FILE 128KiB; TOTAL_RAW 384KiB; envelope 768KiB; nonempty; sha256+bytes vs decoded; saved file rehash before rm | PASS (static) |
| Success-only exact-ID rm | rm only after envelope+saved+runtime+manifest+admitted-pair checks; rm stdout must equal identifier; then ps filter absence | PASS (static) |
| Capture limits | CAPS stdout 768KiB / stderr 64KiB; queue 32×4KiB; RESULT_CAP 1MiB; overflow STOP incomplete | PASS (static) |
| Command supervision | COMMAND_MAX=7; SUITE_SECONDS=300; 30s default / 60s attach; kill wait 5s + two reader joins 5s; CLI kill ≠ daemon cancel (documented) | PASS (static) |
| Ambient Docker refused | `DOCKER_*` env keys raise | PASS (static) |
| Empty docker-config | `{}` SHA E3566B3A…; `--config` points at packet docker-config | PASS (static) |
| Runtime pins | 25 explicit rows; kind discloses partial/not complete closure; live hash-verify 25/25 MATCH; interpreter required in inventory | PASS (static) + qualification |
| Docker.exe pin | Commands + supervisor DOCKER_SHA 8985CD8A…; live MATCH (hash only; no docker invoke) | PASS (static) |
| Replay refuse | Commands refuse existing `$packetRoot.evidence`; supervisor `mkdir(exist_ok=False)` | PASS (static) |
| Execution holds | Review/receipt/preflight: execution_performed=false; launch_ready=false; peer_review pending; Commands “NOT been invoked”; endpoint unbound | PASS (static) |
| Result boundary | RESULT `behavior_proven: False`; kind `T05-NATIVE-SOURCE-PROVENANCE` | PASS (static) |

## Truthful proof boundaries

Consistent across Review-and-Commands.md, Post-Run-Reconciliation-Checklist.md, supervisor RESULT shape, and continuity note:

- Proves **native source-byte provenance only if** separately authorized **and** successful.
- Does **not** prove parser/transport behavior, TLS EOF semantics, framing, provider retirement, native transactions.
- Does **not** close full T05 or T01–T08.
- Host 3.11 / published 3.12.16 reference / captured native bytes remain separate provenance lanes.
- Runtime pins are an explicit subset — not a complete interpreter dependency closure or immutable-FS claim (disclosed in Runtime-Pins.json kind + Review-and-Commands).

## V2 peer findings carried forward

| v2 item | v3 status |
| --- | --- |
| Pre-removal manifest continuity gap (Dex note) | **CLOSED** in v3 supervisor |
| Reader-join / saved-source / durable-result checks (v2→ inherited) | **Retained** (static) |
| Collector + Runtime-Pins byte-identical claim | **Confirmed** |
| Partial runtime inventory disclosure | **Retained** (25 pins; kind truthful) |
| No failure cleanup / no retry / CLI≠daemon | **Retained** (intentional holds) |
| launch_authorized / executed false | **Retained** |
| v2 packet immutability | **Preserved** (not edited by this review) |

No separate prior Jim freeze for native-dex-v2 was present under DropFolder pending; the authoritative v2 static finding reconciled here is Dex’s continuity note + proposed continuity diff.

## Qualifications (non-blocking)

1. Runtime inventory is partial by design (25 files) — disclosed; not a complete dependency closure.
2. Inspect projection does not separately assert a Healthcheck field beyond create `--no-healthcheck` (inherited pattern; create/isolation gates otherwise intact).
3. Mount Source absolute path is not asserted equal to ROOT (Destination/RW/Type + HostConfig.Binds are); Review asks reconcile without broadening Docker projection differences — no blocker.
4. Peer receipt still `peer_review: pending` / `launch_ready: false` until Dex reconciles this note and Trish issues a separate exact-hash card.
5. Native capture still proves source bytes only — not framing/T05/T01–T08 closure.

## Blocking findings

None.

## Explicit non-claims / holds

- launch_authorized=false
- executed=false
- review_only=true
- No Docker commands, no packet helper import/compile/invoke, no Commands.ps1 invocation, no evidence creation by this review.
- Endpoint unbound; no retries/repairs/failure cleanup authorization.
- Qualified accept of static readiness for Dex→Trish card prep only — not a collection PASS and not full T05/T01–T08 closure.
- Predecessor packets scheduler-t05-native-provenance-dex-v2 (and v1 if present) remain preserved/immutable/unexecuted.

## Confirmation

Dex packet files were **not** edited. No Docker. No import/compile/invoke. No launch performed.
