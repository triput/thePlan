# Jim independent static review — native-provider fake-v1 launch packet

Prepared November 12, 2026. Reviewer seat: Justin under Jim’s Dex Scheduler lane. Docs-only / static only. No Invoke-Fake, launch_check, checker, app imports, PKI, Docker, or sockets were run. Prep-v9 tip was not mutated. Not waiting on Trish. No Slack tip from this seat.

## Disposition

**QUALIFIED ACCEPT**

Staged fake-v1 packet is hash-honest against Dex’s claims, admission-only delta vs frozen prep-v9 tip `6585E768…`, command/wrapper contract matches, limits and holds read as stated. Qualifications below are disclosures for the later Trish execution card — not rebuild blockers.

## Packet under review (frozen; not edited)

Root: `C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-native-provider-fake-v1\`

Compared to: `...\outputs\scheduler-native-provider-prep-v9\` (TIP on-disk `6585E768FA64E455052368F75E47795ECC99708DC4EDCFBF6D33CD3B5A25F188`)

## Exact hashes reviewed (observed = claimed)

| Role | Path | SHA256 |
|---|---|---|
| Reviewed command | `Reviewed-Command.ps1.txt` | `72938AA858697DC5314B63CCC44B56955EE783281BB188E1B8216BC65A01FD03` |
| Verification admission | `packet/verify/VERIFICATION-ADMISSION.json` | `1C0A415D1A9E342A87F5C1272870F46041BD2DE72CB3215B36CA5A9ED0236285` |
| Wrapper | `packet/Invoke-Fake.ps1` | `AE84E6325E7B932303B21D6F0A0FED788A717A28631C3577DAF860C6EFC4FEB7` |
| Input manifest | `Input-Manifest.sha256` | `7BA8972274CCED132D47155A65D92B21AE15CA6173D4798A036F14E5745ABD2B` |
| Outer admission | `packet/verify/OUTER-ADMISSION.json` | `C6B46DFBF968BE8CF5328722C45FC310DDBB5E46D74C0628EA622510710DDE34` |
| Checker | `packet/verify/check_native_provider.py` | `97EBFF21FFC545C6F8806750C88BFB493F2E5425BAFEDDD7A70401FB632A58F6` |
| Launcher | `packet/verify/launch_check.py` | `D22C37E36E5D333C087C8EE80B6936756C69F7D369369C66F8E0FFE6906EBD07` |

Also observed (not in Dex’s short claim list): `Static-Staging-Receipt.json` = `555C8F58B0BBB290BC2B5DE7150FE3DDD0150658E309DA9891DADF586282D82C`; `Launch-Decision.md` = `046D8515151A5AD57245C41BDD3A92D136AC2F97E70CB834F5902D388246B305`.

## 1. Hash integrity

- Recomputed all seven claimed role hashes: **MATCH**.
- `Input-Manifest.sha256`: **285/285** entries present under `packet/` and hash-match; packet file count = 285.
- Prep-v9 TIP on-disk SHA256 = `6585E768FA64E455052368F75E47795ECC99708DC4EDCFBF6D33CD3B5A25F188` (**MATCH** claimed TIP source); tip bytes CR=0.
- Packet tree vs prep-v9 root: **283 identical**, **exactly 2 changed**, **0 only-in-fake**, **0 only-in-v9**.
- Changed files only:
  - `verify/VERIFICATION-ADMISSION.json` (`E55A43F7…` → `1C0A415D…`)
  - `verify/OUTER-ADMISSION.json` (`1E40F71B…` → `C6B46DFB…`)
- Line-level admission delta vs v9:
  - VERIFICATION: `launch_authorized` false→true; dependent `packet_files` pin for `verify/OUTER-ADMISSION.json` updated to new OUTER hash.
  - OUTER: `launch_authorized` false→true.
- No code/application/checker/wrapper/launcher byte drift. Claim “admission-only delta (+ dependent OUTER pin)” **holds**.

## 2. Command honesty

Exact `Reviewed-Command.ps1.txt` (225 bytes; one CRLF terminator):

```text
& 'C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-native-provider-fake-v1\packet\Invoke-Fake.ps1' -AdmissionSHA256 '1C0A415D1A9E342A87F5C1272870F46041BD2DE72CB3215B36CA5A9ED0236285'
```

- Calls packet `Invoke-Fake.ps1` only; mandatory `-AdmissionSHA256` pins observed admission hash.
- No silent extras (switches, env, second commands).
- Wrapper contract: validates admission bytes, kind, `launch_authorized -eq $true`, 23 packet pins + 1 runtime interpreter pin, refuses preexisting result/receipt, runs `python -I -S -B verify_admission.py`, fails closed with no retry/repair.

## 3. Scope / limits

- **16** top-level controls labeled in Launch-Decision and `EXPECTED-FAKE-STRUCTURAL.json` `control_ids_in_order` (exact match): ASSEMBLY-PINS, SUITE-INVENTORY, PEER-RUNNER-SHAPE, CANDIDATE-SOURCE-SYNTAX, T02-OVERRUN-GAP, T02-FOCUSED-CROSSING, PORT-DEPENDENCY-PASS, T08-NESTED-RESET-BEHAVIOR, T07-INDIVIDUAL-NAMES, HOST-VS-RUNNER-DOCKER, REPORT-PRODUCER-CONSUMER-SINK, HOST-ENTRY-RECEIPT-RELAY, PKI-LATE-DRAIN-OVERFLOW, MAPPED-COVERAGE-MEASUREMENT, VERTICAL-CONTRACT-SHAPE, ADMISSION-SCHEMA-WRAPPER-FIELDS.
- Timing: admission + launcher constants show **120** collection + **5** post-kill wait + **5+5** reader joins = **135** nominal; `separate_outer_timeout=false`. Startup/hash/file/OS latency excluded as disclosed.
- Capture: **65536** stdout/stderr; **262144** result (`launch_check.py` constants + admission fields).
- Success requires exit 0, clean EOF readers, zero observed stdout/stderr, ordered 16-control PASS inventory, valid bounded result; exclusive create (`O_EXCL`); stop/no-retry on mismatch/timeout/overflow/unexpected output.
- Runtime inventory: **partial — interpreter only** (`5F7B89A612C9B8AF1D6456CDFCD1DBE5CA630849E79AEBCED9BEE9A6694952EC`).
- Scope honesty retained: does not close 27 native / 4 CF / 76 planning; host-fake / extracted seams only.

## 4. Holds

- Native `launch_ready` remains **false** in `payload/launch-config.json` and `payload/runner-config.json`; native wrapper still refuses without true.
- Static-Staging-Receipt: `human_launch_authorized=false`, `execution=not run`, `endpoint=unbound`.
- No result/receipt evidence files present under `packet/verify/`.
- Launch-Decision / Remaining-Gaps keep PKI/Docker/DB/sockets/native suite held; staging ≠ Trish execution card.
- Candidate admission booleans are true for the reviewed one-shot fake path only; human authority remains HELD pending Trish’s exact-hash card.

## 5. Qualifications (non-blocking)

1. **Stale admission prose:** both admission JSON `note` fields still say `launch_authorized=false` / “do not invoke under prep” while the machine boolean is `true`. Gates use the boolean. Execution card should quote the boolean + Launch-Decision human hold, not the leftover prep note.
2. **Historical prep metadata copied forward:** packet `HANDBACK.txt`, `TIP-FREEZE.json`, `Static-Preparation-Receipt.json`, `Remaining-Gaps.md`, and EXPECTED structural still record prep-era `launch_authorized=false` / `launch_ready=false`. Dex disclosed these as frozen predecessor records, not current launch authority — accepted as such.
3. **Harness locality disclosure (carry-forward):** when Trish later authorizes, the fake path starts local Python processes and capture-reader threads; that is not native provider / PKI / Docker / DB / endpoint bind. Already stated in Launch-Decision.
4. **Jim review ≠ Trish card:** this QUALIFIED ACCEPT clears independent review of the staged command/packet. It does not authorize invoke.

## REVISE blockers

None.

## Confirmations

- No invoke / no checker / no import / no PKI / no Docker / no sockets during this review.
- Prep-v9 tip untouched.
- Not waiting on Trish.
- Slack tip not sent from this seat.
