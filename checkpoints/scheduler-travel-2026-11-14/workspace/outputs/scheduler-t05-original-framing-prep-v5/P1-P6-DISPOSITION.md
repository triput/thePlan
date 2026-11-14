# P1–P6 disposition (v5 fake four-role)

Sources: `V4-Provisional-Static-Review.md` (SHA256 `B8A4B3EA…`), `V4-Provisional-Launcher-Review.md` (SHA256 `00FF53C8…`), `V4-Frozen-Intake-and-Static-Reconciliation.json` (SHA256 `E4BD67FC…`, disposition REVISE). Frozen v4 tip `A40F0DEA…` / check `755181B7…` preserved immutable.

| ID | Defect (Dex) | v5 disposition | Changed pin |
| --- | --- | --- | --- |
| P1 | Policy extraction omitted `ProviderLimits` + path-helper/constant closure → NameError at first limits construction | INPUT-MANIFEST extracts unchanged `ProviderLimits`, `_opaque_calendar_id_indices`, `_inspect_opaque_id_segment`, `_admit_structural_segment` + helper/constant deps (`_PATH_INSPECT_STEP_BUDGET`, `_one_unquote`, `_refuse_path_admission`, `_is_dot_nav`, `_has_encoded_slash`, `_original_wire_percent_malformed`). Seed only declared external fake deps. No handwritten path-predicate substitute; no whole-app import. | check + INPUT-MANIFEST |
| P2 | `CoveringRootOutcomeUnknown` extracted into txn/http_ns but classifier/send-state read `policy["CoveringRootOutcomeUnknown"]` → KeyError | Bind the already-extracted exact class into policy (shared identity); http_ns uses same object; classifier + exception send-state read policy only. No second fake UNKNOWN. | check |
| P3 | `CALLER-REFRESH-TOKEN-F04` named owning Google caller but driver manually `client.post` without extracting/calling `refresh_access_token` | Extract `GOOGLE_TOKEN_URL`, `GoogleOAuthConfig`, `refresh_access_token`; invoke under covering context with fake `ApiError` + `calendar_client` deps. Driver `refresh_access_token`. Client-selection proof remains `CALLER-CLIENT-*`. | check + INPUT-MANIFEST + EXPECTED |
| P4 | send_state inferred from exceptions; status/body none after parse; incomplete contract_miss; bare ValueError admitted; 52 predictions need recheck | Observe `FakeTransport.sent` / counters; instrument `HTTPResponse.begin/read/close` for status/body evidence or label unavailable; `CONTRACT_MISS_TRUE` covers every desired miss (incl. accepted incomplete); ValueError only for frozen CL-conversion wires; mixed TE field-order (`H-TE-MIXED`) + list-order (`H-TE-NONEXACT+CL`) both pinned in inventory/oracle. | check + EXPECTED |
| P5 | Custody claimed `-B` explained pyc; `_refreeze` labeled false without receipt | Preserve pyc `72615E8E…`; state `-B` does not explain it; exact write command UNKNOWN; `_refreeze` invocation UNKNOWN (not verified false). No rerun/probes. | CUSTODY-REPORT.md |
| P6 | Launcher unlinked preexisting RESULT despite “refuse” comment | `invoke_t05_fake.py` STOPs on preexisting RESULT/RECEIPT without delete/overwrite; wrapper refusal retained. | invoke |
| B8 | Native supervisor | Deferred to Dex `native-dex-v3` — no Jim re-impl | n/a |

## Wire construction (carry-forward from v4; unchanged bytes)
C-DATA-SHORT / C-SEP-SHORT / C-ZERO-ABSENT / C-SEP-WRONG / C-TRAILER-MALFORMED / C-EXT-VALID / C-TRAILER-VALID / H-INVALID-* / H-TE-MIXED retain v4 SHA256 pins. Revised malformed/short wires keep their own original predictions in EXPECTED-ORIGINAL (not inherited IDs alone).

## Holds
`launch_ready=false` · `executed_in_preparation=false` · endpoint unbound · no Slack tip from Justin
