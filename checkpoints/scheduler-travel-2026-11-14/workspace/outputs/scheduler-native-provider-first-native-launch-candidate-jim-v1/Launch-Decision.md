# First-native launch candidate: execution review brief

Prepared November 12, 2026. Jim / Justin under Dex Scheduler lane. STAGING / DOCS ONLY — ZERO EXECUTION.

HUMAN LAUNCH AUTHORITY IS HELD. Staged `launch_ready=true` in host launch-config (and docker-ops) is a **candidate admission flag for review only**. It is not Trish permission, not `human_launch_authorized`, and must not be interpreted as an execution card. `human_launch_authorized=false` everywhere in this packet. No command, helper, import-to-execute, test, PKI, Docker, database, or socket operation was invoked during staging.

## Source freeze (untouched)

| Artifact | SHA256 |
| --- | --- |
| Native-ready TIP on-disk | A321FB198A69FBA4864C14D1CE474D49E68DF887F087EF0673DAA588CDB3FF57 |
| Native-ready tip_sha256 (LF preimage) | 044862EF2B8DDC81C944DD8B576E3DE18F6DC198E8E55B1BC2EBE174CEACA2C1 |
| Dex native-ready review | 992611715EFAE1B5D2B88E5C9F47EA6432EA09609AC9A5A0F74164BD29134670 |
| Scope | 389A00DD444C610A93877362A574A1C93543F916F119D2D2FF71BA167FBF7E2D |
| Approval | 5D1EA2F973FE110D35B65E4172821F014E74A8F2A65BCBB4AB8EE22458F80CA4 |
| Reconciliation | C7B8FD744D708A5009D971E7F56CF94B6D3FDC16A989B32D004C9FBF3BCC4E6B |
| Seams | 57AA3A80E26BC7EA29E47AE279E9FA94270F8DA5C5BD2EC586568BFCF154B3E3 |

Native-ready DropFolder `post-native-provider-native-ready-prep-jim-v1-2026-11-12` and fake-v1 packet are **not mutated**.

## Fake-v1 PASS prerequisite (UNMET — DO NOT RUN)

Fake-v1 PASS remains an unmet prerequisite. Cite **only** the pending absolute fake-v1 operator/admission/command (Dex docs correction: native-ready Commands-Held `B924153C…` is inherited prep admission, **not** the pending card):

- Reviewed-Command.ps1.txt SHA256: `72938AA858697DC5314B63CCC44B56955EE783281BB188E1B8216BC65A01FD03`
- VERIFICATION-ADMISSION.json SHA256: `1C0A415D1A9E342A87F5C1272870F46041BD2DE72CB3215B36CA5A9ED0236285`
- Invoke-Fake.ps1 SHA256: `AE84E6325E7B932303B21D6F0A0FED788A717A28631C3577DAF860C6EFC4FEB7`
- Absolute operator: `C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-native-provider-fake-v1\packet\Invoke-Fake.ps1` with `-AdmissionSHA256 '1C0A415D1A9E342A87F5C1272870F46041BD2DE72CB3215B36CA5A9ED0236285'`

Fake-v1 scope covers preserved prep-v9 primitives under fakes. It does **not** prove native-ready entry/operator changes: import-order bootstrap-before-siblings, in-memory runtime public-CA bind, external Docker-ops byte admission, host configs/evidence outside payload, typed provider PKI success summary, or actual TLS/PKI/Docker/DB native behavior. No new redundant fake run is required merely to rename the batch; native first vertical must prove those boundaries on its own evidence if/when authorized.

## Exact future invocation (HELD)

Execute **once only** after Trish explicitly approves a final reviewed packet matching these frozen bytes, using exact `Reviewed-Command.ps1.txt` contents (SHA256 `C323012B66D52C754DF553E2A5F080494A65FB8E2749B5BC1540716E5CCDAB27`):

```
& 'C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-native-provider-first-native-launch-candidate-jim-v1\Invoke-Native-Provider.ps1' -ExpectedConfigSHA256 '63B7BC36605A4EBEE71C29B550F178B6260E58E777DEE4D542D7467B5BD7BE48' -ExpectedDockerConfigSHA256 '471C7284A7425CD0FE6F164DD6886B906A7770F8FAFB4D41AC02B7FD471DC6F8' -DockerConfigPath 'C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-native-provider-first-native-launch-candidate-jim-v1\host\docker-ops-config.json'
```

### External pins

| Role | Path | SHA256 |
| --- | --- | --- |
| Operator script | `Invoke-Native-Provider.ps1` | `F44D14DC246A76CA2F7844AA67EFEFA93383B2DC4BAA8665B047B8B2879C35C2` |
| Launch config | `host/launch-config.json` | `63B7BC36605A4EBEE71C29B550F178B6260E58E777DEE4D542D7467B5BD7BE48` |
| Docker ops config | `host/docker-ops-config.json` | `471C7284A7425CD0FE6F164DD6886B906A7770F8FAFB4D41AC02B7FD471DC6F8` |
| Payload exact-set manifest | `payload/SHA256SUMS.txt` (256 entries) | `4F3147BA6DAD068CE446AD0118FC5C5A1525D01D117F07AF2D13B1696DA98427` |
| Runner config | `payload/runner-config.json` | `72EE396DE1379C2183579D08D41258C6479B79D3BB606482371037FB6B348B80` |
| Runner entry | `payload/fixture/np_runner_entry.py` | `7FBDCAEE078CDBE3F695191ABBED93B827A31EB6FED55DCD839AB43A84355FF5` |
| Supervisor | `payload/fixture/np_supervisor.py` | `A1ADA2311B10631209DBA0588B8C9C6B947B3206F0EFBC51F4CF66B1F45303BC` |
| docker_transport (immutable) | `payload/fixture/docker_transport.py` | `7F7EA8204879D312624DAEB7941504FEA1402F45C48BDA79DDAD94A23711AC53` |
| Suite | `payload/fixture/np_suite.py` | `AEC59FCDA058124FDF7265D41B8A660C4AD139CE13417F88FA637542CF9C1673` |
| Peer | `payload/fixture/np_provider_peer.py` | `5568AF73DD42FEB5B8E2FE4D723AD4FB0339CBF4B889F5472995ABC628F72A55` |
| Auth seed | `payload/fixture/np_auth_seed.py` | `66FEEA815C7B196A78117229F80769ADDF8428CB073A586B59E2D81491419150` |
| Python 3.11 (partial runtime) | host exe | `5F7B89A612C9B8AF1D6456CDFCD1DBE5CA630849E79AEBCED9BEE9A6694952EC` |
| docker.exe | host exe | `8985CD8AC002C3240B5AA48FE401FCB55DCA5D849B537E3C835564E8E8C49A70` |

Fresh evidence path (must not exist before a future authorized run): `C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-native-provider-first-native-launch-candidate-jim-v1.evidence` — distinct from native-ready `…native-ready-prep-v1.evidence`.

Acyclic roots: A = ExpectedConfigSHA256 admits host launch-config; B = manifest admits payload exact-set (excludes host configs/evidence); C = ExpectedDockerConfigSHA256 admits host docker-ops; D = python/docker exe pins.

## Scope / limits / retirement (frozen from native-ready)

- Case batch: **NP-V-MS-NONEXPIRED** only; `expected_unknown_cases=[]`; other **26 native + 4 CF** HOLD_EXPLICIT_NOT_PASS; **76** planning IDs retained; same **16-role** lane; no new product decision.
- Caps: suite **900** / runner **600** / peer **120** + join **5** / provider PKI retirement total **45** / command_count_cap **32** / output **1MiB** (1048576). Product clocks 210/240/30 and attempt validity 600 remain distinct. Caps are not observed timings.
- Static success Docker command count **22** (unchanged); hard cap 32.
- Retirement: success-only exact-ID cleanup; fail/mismatch/timeout/unexpected → **UNKNOWN STOP**; no retry/repair/failure cleanup; unjoined → UNKNOWN; failed container shutdown separately gated.
- Topology: host Docker ownership; no runner Docker socket; no new privileges; dial 127.0.0.1:443; endpoint **unbound**; image presence / port 443 **unverified** this staging.

## Candidate vs human authority

| Flag | Value | Meaning |
| --- | --- | --- |
| `launch_ready` (host configs) | **true** | Staged candidate admission for Dex/Jim launch review |
| `launch_authorized` (host configs) | **false** | Not an embedded execution grant |
| `human_launch_authorized` | **false** | Trish execution authority HELD |
| `candidate_launch_ready_staged` | **true** | Explicit staging marker |
| `executed` | **false** | No invoke |
| `prep_is_not_pass` | **true** | Staging ≠ PASS |
| `endpoint` | unbound | No bind |

## Remaining gate

Jim/Dex independent review of this candidate command and pins is requested before any Trish execution card. This seat is **not waiting on Trish**. Fake-v1 PASS unmet; native differences vs old fakes disclosed. No Slack tip from this seat.
