# Native fixture wiring: source preparation complete, launch held

The source path is now connected from `invoke.py` through the one-attempt supervisor, Docker Ops, TLS bootstrap, bounded local readiness check, public-CA transfer, paired fault-gate process and integrated runner. The runner provisions the real application schema in a labeled setup transaction, provisions native probe tables, runs N01–N08, then runs all 16 assessment cases from accepted REVISE3. The source case inventory is nine groups containing 24 individual native/assessment cases. No case has run in this preparation.

Native cases cover valid TLS checkout and negative hostname/CA controls; acknowledged parent COMMIT/ROLLBACK with separate persistence observers; root/owner refusal; real ORM unique_external_event collision rollback; withheld COMMIT/ROLLBACK acknowledgment; and pre-dispatch deadline refusal with charged cleanup. N01's negative checkouts and N04's deliberate identity-refusal exceptions are expected fixture controls; N06/N07 are explicitly expected UNKNOWN transaction outcomes. No other UNKNOWN is accepted. Native partial results are not release proof.

The two TLS gates listen once on separate loopback ports, share no private keys with the runner, and exit after withholding their exact terminal acknowledgments. Host transport joins the single gate-pair exec process and validates both server-side receipts before accepting runner success. Gate readiness is a bounded local-file wait, not a connection retry. Failure stops the host CLI and preserves container state for separately authorized reconciliation; no container cleanup runs on the failure path.

The fixture now transfers two PUBLIC certificates: the trusted CA and the deliberately unrelated CA used by N01. Both are exclusively written/read back and mounted read-only. All private keys remain in database tmpfs. Post-run hashes include both transferred public certificates. This supersedes earlier single-public-certificate wording.

The outer runner watchdog covers imports and schema setup as well as cases. The suite checks exact inventory, zero skips/xfails, native pin equality, stopped admission after expected UNKNOWN, native terminal/retirement observations and joined workers. Pytest output is bounded and hashed, and the final stdout is one JSON receipt. No conftest, plugin autoload, ambient SessionLocal or provider HTTP is admitted by the runner.

All existing production files and Jim's accepted two test files remain unchanged. Jim is independently reviewing the assessment binding; his findings must be reconciled before launch review. Syntax parsing and source tracing are not evidence that private psycopg hooks, TLS protocol forwarding or ORM fixture assumptions work at runtime.

## Remaining launch gates

Both JSON configurations deliberately say `launch_ready: false`. Exact image/runtime pins and image-specific users, binary/site paths, mounts and Docker inspect projections are not yet established. Historical image IDs are not sufficient evidence that the database image includes the Python and OpenSSL required by the DB-side gates. No installation, image build, image pull or container probe is authorized by this packet. The Docker executable was hashed read-only and still matches 8985CD8AC002C3240B5AA48FE401FCB55DCA5D849B537E3C835564E8E8C49A70.

Proposed caps are 900 seconds for the whole supervisor, 600 for the runner (including schema/setup), and 240 for the gate pair. These are review candidates, not approved execution budgets; production request budgets remain 240/210/30. Once runtime facts and review findings are resolved, freeze a new launch packet with exact configuration hashes and commands. No current invocation can pass the held-config guard.

Prepared invocation shape (NOT executable approval):

`<reviewed-host-python> -I -S -B invoke.py --config-sha256 <final-launch-config-sha256> --manifest-sha256 <final-manifest-sha256>`

Endpoint remains unbound. Production deployment/platform readiness, full public ingress-to-native proof and A07 lock-contention proof are not claimed by these fixtures.
