# Fake-only C06 runner-TLS verification — HELD (corrected6)

Authored under Trish fresh-copy check preparation approval `call_32f9e623299f4b0e8bc3eed4532b8278` (Fresh-Preparation-Approval.json) plus retained C06 prep scope `B6D6ED1A…` / approval `4382DFBE…`. **Not invoked.** This packet is not native PKI/lost-ack proof and does not close C06-Static-Blocker.

Fresh-copy from tipped corrected5 `post-native-c06-runner-tls-prep-jim-v1-corrected5-2026-11-10` TIP `5F8D87526F9D2C114C2B81A0D06D3ED2A5CEBC7E2DC97A562225C9C2FB23C602` (UNCHANGED). Tipped corrected4 `914268E0…`, corrected3 `D6260E99…`, corrected2 `91E699ED…`, corrected1 `2F9D3EDA…`, tipped v1 `046D670A…`, frozen fake 22 PASS / corrected7, the blocked native draft, and failed workspace `scheduler-c06-fake-v1/` are not mutated.

Sole source change vs corrected5: first preexisting-directory control assignment in `check_c06_runner_tls_fake.py` — `fake_os.lexists` → `fake_os.path.lexists` (Proposed-Fix.diff `2F798B6F1F4B0C968A198746F36FF55D9776935B678A6DA6F08962D563D23F47`). Check SHA256 `99C3049C69C5837C728236D6ED8332A286A0E22FF6A35A8C47157165CF78D51E` → `C59C547453A76ACF7C4F10B8A0E1576134AB24A978EE5CC8018D25E1EF775DF8`. Four fixture sources byte-identical to corrected5. Assertions / 39-control inventory / EXPECTED-OUTPUT / T02 review packet unchanged. Launch-config `B94DEFE32C2C25B22D0AFBCBA0CC5E2365CBB5AD8FEE291C83667DC51145B4A9` remains a **separate pinned static input**.

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
- `launch_ready=false`; endpoint unbound

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
- Preexist refuse path assigns `fake_os.path.lexists` (corrected6 one-line fix)

## Coverage boundaries (truthful)
- `C06_N_ROOT_FIXTURE_TLS` does not refuse a production guard; it inventories the extracted default root path
- `C06_N_WRONG_READY_ROOT` does not add a new guard; it inventories that `c06_artifact_paths` honors an explicit supplied root
- Native cert-gen, Docker, and lost-COMMIT-ack remain out of this harness

## Later execution card
A separate card must authorize `admit_outer.py` (not ambient `python check_...`). Native cert-gen and Docker remain separately gated.
