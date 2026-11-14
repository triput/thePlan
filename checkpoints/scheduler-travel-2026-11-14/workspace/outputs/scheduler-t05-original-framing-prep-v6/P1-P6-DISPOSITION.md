# P1–P6 disposition (v6 fake four-role)

Sources: Dex v5 REVISE `V5-Frozen-Intake-and-Static-Reconciliation.json` (`661E2537…`), `V5-Provisional-Static-Review.md` (`5C536FE2…`), `V4-P4-Host-Parser-Prediction-Trace.md` (`96D3D93C…`), host `client.py` (`3A752927…`). Frozen v5 tip `65DC4D69…` / check `4B693387…` / invoke `A67AD24C…` preserved immutable. v1–v4 untouched.

| ID | Defect | v6 disposition | Changed pin |
| --- | --- | --- | --- |
| P1 | ProviderLimits + path-helper closure | **Carry-forward closed in v5** — retained | (unchanged extract set) |
| P2 | UNKNOWN identity shared | **Carry-forward closed in v5** — retained | check (identity assert) |
| P3 | owning `refresh_access_token` | **Carry-forward closed in v5** — retained | check + manifest + EXPECTED |
| P4 | source-contradicted originals; missing finite TE/decimal variants; bare ValueError allowlist | **Integrated** P4 trace: flipped originals; both mixed-TE repeated-field orders; decimal-eq dup/list variants; `CONTRACT_MISS_TRUE` covers incomplete-framing + conflict-fields; empty `VALUEERROR_PARSER_WIRES` | check + EXPECTED + wires + inventory |
| P5 | custody honesty | **Carry-forward closed in v5** — retained UNKNOWN labels | CUSTODY-REPORT.md |
| P6 | preexisting RECEIPT refusal called overwrite-capable `write_bytes`; RESULT guard could clobber accompanying receipt; early failures same path | **Fixed**: preexisting RESULT/RECEIPT checked first → stderr-only STOP with **no write**; all newly owned receipts use **exclusive create** (`O_CREAT\|O_EXCL`); `_stop_receipt` refuses without overwrite if prior evidence exists; spawn/unguarded/final paths reconciled | invoke |
| B8 | Native supervisor | Deferred to Dex `native-dex-v3` — no Jim re-impl | n/a |

## Wire count
`wire_ids_frozen=57` (v5 had 52; +5 inventory expansions). 52 is not a cap.

## Holds
`launch_ready=false` · `executed_in_preparation=false` · endpoint unbound · no Slack tip from Justin
