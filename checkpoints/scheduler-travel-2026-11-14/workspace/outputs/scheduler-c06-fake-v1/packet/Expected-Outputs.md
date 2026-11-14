# Expected outputs — HELD fake-only C06 runner-TLS (corrected5)

Canonical machine file: `fake-only-c06-verification/EXPECTED-OUTPUT.json`.

When a later card authorizes the harness via admit_outer.py, expect:

- status `PASS`, class `FAKE-C06-RUNNER-TLS`
- executed=true, held=false, source_hashes_verified=true, inventory_error=null
- control IDs in exact EXPECTED order (39 controls)
- Behavioral REFUSE: dir/uid/mode, extracted trust/occupied-port, generation refuse/timeout/cap, group custody (leader-exited vs SIGTERM-ignored via fake Linux SIGTERM=15/SIGKILL=9), reader join (primary `c06 reader eof unknown` plus unjoined/pipes_unretired), late reader error, pipe unretired under live reader, bounded cap evidence, partial start, partial Thread constructor (two pipe close attempts, one constructed / zero started, primary preserved, STOP), primary preserve, dual-fault, shared deadline (elapsed from entry; setup after deadline; disclosed total 45s = 30+5+5+5), observed-vs-retained
- Behavioral PASS: distinct CA, synthetic module registration, occupied port 15432
- Static PASS (labeled): default-root path inventory (`C06_N_ROOT_FIXTURE_TLS`), supplied-root path-wiring inventory (`C06_N_WRONG_READY_ROOT`), AST main() hook-order, MAP separate, UNKNOWN inventory, abs binaries, recipe literals, launch_ready false, child env, suite CA evidence, explicit root wiring, 600/900 budgets (disclosed 45 is total not extra)
- Pre-control pins: four fixture sources plus separate launch-config SHA `B94DEFE32C2C25B22D0AFBCBA0CC5E2365CBB5AD8FEE291C83667DC51145B4A9`; FakeOS.path.join is posixpath.join

Sanitized receipts only. No raw OpenSSL output. No key hashes. No PEM bodies.

This is not native TLS/lost-COMMIT-ack proof.
