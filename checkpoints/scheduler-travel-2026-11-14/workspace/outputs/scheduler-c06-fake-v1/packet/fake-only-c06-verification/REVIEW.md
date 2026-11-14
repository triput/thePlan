# Fake-only C06 runner-TLS verification — HELD (corrected5)

Authored under Trish source-preparation plus Dex closure p1794377787 (pipe custody before Thread constructors) and retained corrected4 check-only closures (p1794377411, p1794377478). **Not invoked.** This packet is not native PKI/lost-ack proof and does not close C06-Static-Blocker.

Tipped corrected4 `post-native-c06-runner-tls-prep-jim-v1-corrected4-2026-11-10` TIP `914268E0C980FEAB4DC93752D733AB4AF1133F5C1869BB99032FB71CE8EE7192` is preserved. Tipped corrected3 `D6260E99…`, tipped corrected2 `91E699ED…`, tipped corrected1 `2F9D3EDA…`, tipped v1 `046D670A…`, frozen fake 22 PASS / corrected7, and the blocked native draft are not mutated.

`runner_entry.py` is the only four-target change vs corrected4. `prepare-c06-runner-tls.sh`, `i01_c06_dual_peer.py`, and `i01_i02_suite.py` are byte-identical. Launch-config `B94DEFE32C2C25B22D0AFBCBA0CC5E2365CBB5AD8FEE291C83667DC51145B4A9` is unchanged and remains a **separate pinned static input** (not a fifth fixture source).

## Bounds
- No app/vendor imports
- No real child processes, sockets, or OpenSSL/PKI generation
- Fake Popen/process-group, fake pipes, in-memory FS, AST extracts
- Narrow fake Linux `signal` namespace (`SIGTERM=15`, `SIGKILL=9`) injected into extracted runner globals and used by FakeOS / assertions; host `signal` is not imported; no real signal calls
- `FakeOS.path.join` is `posixpath.join` (POSIX-only in-memory FakeFS keys); host `os.path.join` is not used for extracted provenance paths; `posixpath` is an explicit stdlib-import allowlist entry
- FakeListener implements owned client `__enter__`/`__exit__` and records retirement (no real socket)
- Synthetic ModuleType registered in sys.modules; exec into that same `__dict__`; required symbols fail closed
- Pinned interpreter + outer admission + bounded launcher (authored, not run)
- Later authorized run must set `executed=true` (this card does not invoke)

## Coverage (closes Dex check-only mismatches)
1. Group custody via killpg(0) independent of leader poll; leader-exited/descendant-alive and SIGTERM-ignored are separate fakes; SIGTERM/SIGKILL compared via fake Linux constants, not host `signal`
2. Generation primary preserved on prepare_c06_runner_tls; started readers / owned pipes tracked; partial start, partial Thread constructor (pipes registered before construct; second constructor throw closes both pipes once, one constructed / zero started, primary preserved, STOP), and dual-fault
3. Shared 30s generation/admission deadline from **entry**; FakePopen/setup clock advance **after** deadline capture; nonzero origin valid; elapsed from entry vs disclosed **total 45s** (`C06_DISCLOSED_RETIREMENT_SECONDS` = 30+5+5+5, additional retirement 15s, not gen+45=75); 600/900 unchanged; observed vs retained bytes
4. Held started readers: expect_raise searches the **rejecting primary** `c06 reader eof unknown`; structured extra `readers_joined` / `pipes_unretired`; do **not** expect `retirement unknown`
5. Default-root / AST / recipe inventory labeled **static** (not behavioral REFUSE). `C06_N_ROOT_FIXTURE_TLS` is default-path inequality only; `C06_N_WRONG_READY_ROOT` is supplied-root path-wiring inventory labeled **static/PASS** like default-root; production fixture guards not added
- Consumed `payload/launch-config.json` (UNKNOWN inventory, budgets, launch_ready) is pinned and enforced as a separate static input **before controls**; `verify_source_pins` still admits exactly four fixture sources
- Extracted occupied-bind / trust / serve branches remain behavioral
- FakeListener client context-manager contract records retirement under `with client:`
- Late reader error after wait rechecked post-join; cannot reach prepared
- No buffered close under an unjoined live reader; unretired endpoints recorded
- Repeated cap is bounded flag/counter, not a growing events list

## Coverage boundaries (truthful)
- `C06_N_ROOT_FIXTURE_TLS` does not refuse a production guard; it inventories the extracted default root path
- `C06_N_WRONG_READY_ROOT` does not add a new guard; it inventories that `c06_artifact_paths` honors an explicit supplied root
- Native cert-gen, Docker, and lost-COMMIT-ack remain out of this harness

## Later execution card
A separate card must authorize `admit_outer.py` (not ambient `python check_...`). Native cert-gen and Docker remain separately gated.
