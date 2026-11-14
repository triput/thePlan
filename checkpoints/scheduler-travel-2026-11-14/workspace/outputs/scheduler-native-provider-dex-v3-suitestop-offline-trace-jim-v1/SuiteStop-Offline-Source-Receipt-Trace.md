# SuiteStop offline source/receipt trace (Jim / Justin)

**Decision:** QUALIFIED TRACE — not native PASS. Docs-only. Zero execution. Packet + evidence preserved as-is. Endpoint unbound. No launch/retry authority.

## 1. Receipt sequence (verified)

Evidence root (read-only):
`…\scheduler-native-provider-first-native-launch-candidate-dex-v3.evidence\`

| Pin | Value |
|---|---|
| `native-provider-host-receipt.jsonl` SHA256 | `FC3822C3A1CA0DBD7F6903BDACB0E6F32E2553381044841B1B72AB3B73F63D6D` (on-disk match) |
| Runner id | `375621bd59780e2aaf7f9b83ec131c3a36afb5c785c3abab97842958caf74f56` |
| Runner exit | `125` |
| Runtime | StartedAt `…54.662Z` → FinishedAt `…59.608Z` (~5s; StartedAt ≠ FinishedAt) |
| Database | still `running` (exit 0) — cleanup not authorized |

Attach-tail events on receipt (in order):

1. `docker_command` → `["start","--attach", runner]`
2. `runner_stop` → `{cli_exit_code:125, diagnostic_unavailable:true, kind:SuiteStop, status:STOP}`
3. `docker_output` → `{bytes:40, stderr_sha256:49a5093c…, stdout_sha256:e3b0c442…}` (empty stdout)
4. `stopped` → `RuntimeError`, `automatic_cleanup:false`, `retry:false`, `failed_container_shutdown_gated:true`

No `provider_attach_report`. No `suite_pass`.

Byte identity of stderr envelope (already matched; not expanded):
UTF-8 `{"kind": "SuiteStop", "status": "STOP"}\n` = **40 bytes**, SHA256 `49a5093c39e74f793c10d9fd2d54f18774dbded638dce3ba6d83ee6c50ae399b`.

## 2. Host attach path (pinned sources)

Packet Input-Manifest file SHA256: `26560DF4DF4C33E3FCB1B9A983F30BF8F1569AB0BC5C9D23EC7F892C17B31EAF`.

| Relpath | SHA256 (verified) |
|---|---|
| `payload/fixture/np_supervisor.py` | `A1ADA2311B10631209DBA0588B8C9C6B947B3206F0EFBC51F4CF66B1F45303BC` |
| `payload/fixture/docker_transport.py` | `7F7EA8204879D312624DAEB7941504FEA1402F45C48BDA79DDAD94A23711AC53` |
| `payload/fixture/np_runner_entry.py` | `7FBDCAEE078CDBE3F695191ABBED93B827A31EB6FED55DCD839AB43A84355FF5` |
| `payload/fixture/np_integrated_runner.py` | `2C8B5BE78B5F042210D042DF1FB7FDBB07C486ED5A57CA36C00006F61E6040DF` |
| `payload/fixture/np_suite.py` | `AEC59FCDA058124FDF7265D41B8A660C4AD139CE13417F88FA637542CF9C1673` |

Causal chain (re-verified, no live Docker):

1. `np_supervisor.ProviderDockerOps` constructed with `reuse_legacy_gate_protocol=False` (~347). Attempt receipt stamps `attach_protocol=np_provider_no_n06_n07_default` (~203).
2. `run_attached` (~124–137) calls only `_cmd(['start','--attach', runner])` — no N06/N07 gate_pair.
3. On non-zero CLI / stderr, `docker_transport._cmd` (~181–183) calls `_record_runner_stop` then raises `RuntimeError('Docker exit/stderr failure')` (matches receipt `stopped.kind=RuntimeError`).
4. `_record_runner_stop` (~54–123) parses a **one-line** LF JSON STOP envelope. Schema `{status,kind}` without `diagnostic` → records `runner_stop` with `diagnostic_unavailable=true`. Optional `diagnostic` with owned `.py` path+line frames is already sketched here but was **not** present on this envelope.

## 3. Runner STOP-before-report contract

`np_runner_entry.py` `__main__` (~1455–1466): any `BaseException` → write
`json.dumps({"status":"STOP","kind":type(exc).__name__}, sort_keys=True)+"\n"` to stderr, `_exit_code=125`.

Success machine report is written **only** after `run_suite` returns (~1424–1452). STOP path never emits the report → empty stdout SHA matches `e3b0c442…`.

Kind `SuiteStop` ⇒ exception class reaching `__main__` was `SuiteStop` (defined in `np_suite.py` ~357; raised from NP-V-MS-NONEXPIRED case body / oracle / peer-retirement / `framework_stop` wrap in `np_runner_entry`). Early admission uses `RunnerEntryHeld`; integrated-runner mismatches use `RuntimeError` — neither matches this kind.

Exit 125 here is the runner’s intentional STOP exit, not Docker-daemon “125 before start”: inspect shows StartedAt≠FinishedAt with ~5s wall time.

## 4. Evidence vs hypotheses

**Attributed (evidence-backed):**

- Host attach used NP provider no-N06/N07 path; STOP envelope produced by runner `__main__` after `SuiteStop` escaped `main()`.
- Host recorded `runner_stop` via `_record_runner_stop`; `cli_exit_code=125`; `diagnostic_unavailable=true`.
- Report never emitted; no `provider_attach_report` / `suite_pass`.
- 40-byte stderr hash matches the `{kind,status}` STOP schema without diagnostic.

**Not attributed (by design — do not invent):**

- Which `raise SuiteStop(...)` site / message / case phase (pre-peer vs covering-refresh vs retirement).
- Any root cause among the many SuiteStop raise sites in the pinned runner/suite sources.

Do not recover or decode beyond the hashed 40-byte envelope identity above.

## 5. Limits of attribution

| Can | Cannot |
|---|---|
| STOP envelope identity + host record path + intentional exit 125 + report never written | Raise-site path/line/message/phase for this run |
| Distinguish SuiteStop vs RunnerEntryHeld vs bare RuntimeError at `__main__` | Expand this envelope into diagnostics |

## 6. Narrowest proposed next step (docs/design only — no execute)

**Propose:** a Trish-gated **failure-evidence design card** to optionally admit bounded STOP `diagnostic` frames (owned `.py` path+line only; schema already sketched in `docker_transport._record_runner_stop` ~81–120), with runner `__main__` STOP emission remaining failure-evidence-limited otherwise.

**Why this over a static SuiteStop site map:** a separately authorized static case-phase map of NP-V-MS-NONEXPIRED `raise SuiteStop` sites is useful inventory, but it still cannot select which site fired on **this** hashed envelope. Only bounded diagnostic frames (future authorized emission) unblock site-level attribution. The design card is therefore the narrowest step that actually opens attribution without claiming this packet can be decoded further.

**Why not rerun / repair:** launch authority already consumed (`Dex-Stopped-Run-Reconciliation.json`); endpoint unbound; no launch/retry authority on this seat; failed packet + evidence must stay frozen; success cleanup did not run and failure cleanup remains Trish’s separate gate. Rerun would mint a new attempt, not explain this STOP.

---

*Author: Justin (Jim Dex Scheduler lane). Documents-only offline trace. Not waiting on Trish for this tip completion — cleanup card remains hers separately.*
