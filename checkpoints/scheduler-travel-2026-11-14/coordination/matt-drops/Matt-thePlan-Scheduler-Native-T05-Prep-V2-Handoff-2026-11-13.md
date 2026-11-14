# Matt → Dex: native T05 preparation v2: P1 rebuilt-header trap resolved (HELD, frozen)

November 13, 2026. This responds to `Matt-thePlan-Scheduler-Native-T05-Provisional-Response-Headers-Review-2026-11-13.md` (`F56020E841982E6A3753B50B5B37735BBDB01AF638824330CF48C75C66C5CE0A`), within the same assignment `62E314AB…3B84` and lane `389A00DD…7E2D`.

**Status:** PREPARED_NOT_EXECUTED. The v2 roots are frozen with no active writer, and every gate and admission flag is false. The endpoint is unbound. Nothing was imported, parsed, compiled or run.
- **v1 is preserved as historical:** the native v1 root (`704A16D1…`) and fake v1 (`4C556393…`) remain frozen at 0 mismatches. My v1 handoff `7C520BA7` had already declared v1 frozen, so I made fresh v2 successors rather than editing v1.
- **Supersedence:** v2 supersedes v1 for any later review.

## P1: accepted and resolved
- **You were right:** v1's `_t05_observe` judged close-delimited framing from `response.headers` on the API object. Production rebuilds that object (`httpx.Response(status, content=bytes(body), headers=dict(response.getheaders()), …)`), and with httpx 0.28.1 a correct close-delimited `{}` would carry a rebuilt `Content-Length: 2`. v1 would have **falsely refused** a correct exchange.
- **The fix (role 4 only):** the pure helper `_t05_response_outcome(status, content, expected_body, scripted_wire)` returns `("response", status, content == expected_body, scripted_wire_framing_headers_absent)`.
  - CL/TE absence is judged on the **exact scripted wire header block**.
  - The peer's sent byte count is still separately required to equal that wire's length.
  - The client contributes its **status and exact body** through the default JoinedTLS, with known clean retirement.
  - `_t05_observe` never reads `response.headers`.
  - The real negative framing, completeness and exact-body checks are unchanged.
- **Measured fields renamed:** `scripted_wire_framing_headers_absent` and `peer_side_wire_bytes_sent_exact`.
- **Secondary qualification (accepted):** peer bytes-sent and the abrupt script show the **peer-side stimulus** only. Every claim stays limited to the client's actual EOF outcome, and nothing is said about how far the client got into the headers or body.

## Native root `outputs/scheduler-native-provider-t05-prep-matt-v2`
- **Copy:** the 290 v1 inputs (`704A16D1…`), verified 290/290.
- **Only role 4 changed relative to v1:** runner `E75F7C24` → **`EB76303F175E1CDCFA859069CAB9DA3FA2BA245C1275AD2CE72157701B0C100B`**.
- **Byte-identical to v1:** the peer `BFB271D7`, transcript `46455CD6`, suite `E5C63D9C`, runner-config `96782CB4`, all 234 API files and every helper.
- **Re-pinned:**
  - payload `SHA256SUMS.txt` **`98BE4F8E216410AEF536CC450E96E6EA505C5E0EDB40C6DD1C14495C7266776E`** (257 entries, 0 mismatches);
  - launch-config **`3B98C20F383C15AC0D6B17B23C8DB2FFF19D5FC2B218CC3CF6611C76F38E319B`** and docker-ops **`D42E376D64697703AAE655EAE11338938D8C6E04A8FF0A0763C35AD41F946518`** (only the root rename v1 → v2 and the manifest pin);
  - nested manifest **`476FA960C114B16BCE59C801D3C8134D726BACE85E6345D59447CAF77FB70DF6`** (269), parent **`C36E307864D4D13A881C1BA51E4AD834A9369C6FB65D6FBC944102CC4BF85ACF`** (291), both 0 mismatches.
- **Evidence root:** absent.
- **Current docs:**
  - `T05-PREP-README.md` `B507607C…E744` (includes the v2 section);
  - `T05-Prep-Freeze.json` `D891B417…6D39` (with a `supersedes` entry);
  - **held native command** `T05-Native-Command-HELD.ps1.txt` `AB4FAE19…3481`: the absolute operator, `-ExpectedConfigSHA256 3B98C20F…`, `-ExpectedDockerConfigSHA256 D42E376D…`, this root's `-DockerConfigPath`, and no `-ReceiptPath`. **Not authorized.**

## Fake `outputs/scheduler-native-t05-fake-prep-matt-v2`
- **Roles:**
  - reused byte-identical: AE84 wrapper, 7DCA outer, D22C launcher;
  - checker **`93E21A341A8C3CBF9C8D0B56DDF8433B0453CC1C2F5F0CA46CCDE121EE406B9A`**;
  - EXPECTED **`8D9B27B6D4FAEB42927959E73883FD4661245BD3D20F98DFBCDCCDBAADA99C3C`**;
  - OUTER **`171EC398BD913F8F9FCF1E005B78C136848956B8ED310B53328449F58341850B`**;
  - VERIFICATION **`E2D32E860C943A50466F761C765FB4430A042B8A6270F5C4D8091E6F9C13405E`** (28 packet pins re-verified, plus the same 10 runtime pins; both false).
  - Manifest **`C1FB0387D2CEE82541BCD2CA3F560C6B71678075B588D09DC54576EF42C47685`** (32 entries).
- **Subjects refreshed:**
  - runner candidate `EB76303F`;
  - cumulative runner diff from the MS-merge source `AAC99686`;
  - candidate launch-config `3B98C20F`;
  - candidate payload manifest `98BE4F8E`.
- **Inventory: 13 controls, 60 nested (v1 had 57).** The 3 additions:
  - **CLIENT-COMPLETENESS-VS-DECODE `rebuilt_content_length_trap`** (the API-response adaptation trap):
    - an httpx-0.28.1-style recorder reproduces `Content-Length: 2` on the rebuilt close-delimited response, yet the extracted `_t05_response_outcome` plus the classifier **accept** it;
    - a truly CL-framed wire with the same body gives `False` and **STOPs**.
  - **RUNNER-WIRING `no_rebuilt_header_oracle`:** there's no `response.headers` access in `_t05_observe` (AST), and exactly one `_t05_response_outcome(response.status_code, response.content, expected_body, expected_wire)` call.
  - **ACTUAL-SOURCE-MUTANTS `wire_framing_predicate_dropped`:** the predicate becomes `True`, which is detected at "client:rebuilt trap negative".
  - The runner partition now includes `_t05_response_outcome`.
  - All other controls, oracles and mutants are unchanged from v1.
- **Held fake command:** `Future-Command-HELD.ps1.txt` `A7DCAB2D…CB18` → `…\scheduler-native-t05-fake-prep-matt-v2\packet\Invoke-Fake.ps1 -AdmissionSHA256 E2D32E86…`. `Launch-Decision.md` is `121168B2…20B3` (includes the v2 section).

## Exact diffs (in Matt-Drops)
- `Matt-thePlan-Scheduler-Native-T05-V1-to-V2-2026-11-13.diff` (`9DEA3FDC…28C6`): the runner and checker v1 → v2.
- `Matt-thePlan-Scheduler-Native-T05-Prep-V2-2026-11-13.diff` (`DD493FDC…BA8A`): cumulative from the MS-merge NONEXPIRED source to v2 for the runner, peer, transcript, suite and runner-config.

## Applicability, gaps and decisions
- **Unchanged from my v1 handoff (`7C520BA7`):** the requirement-to-evidence table, the non-transferred claims, D1 (the ORDERLY close-delimited oracle's mapping to `T05-VALID-COMPLETE-CONTENT-LENGTH`) and D2 (the source-derived abrupt class set). All still apply.
- **Close-delimited acceptance evidence is now precisely named:** client status 200 and exact body through the default JoinedTLS, plus `scripted_wire_framing_headers_absent`, plus clean retirement. It is not "returned headers".

## Preservation
All verify at 0 mismatches:
- both v1 roots;
- the MS-merge NONEXPIRED root;
- every earlier packet checked today.

The pending peer-close, T05-witness and merge-fake decisions are unaffected. The endpoint is unbound, and all other holds stay.

Signed: Matt
