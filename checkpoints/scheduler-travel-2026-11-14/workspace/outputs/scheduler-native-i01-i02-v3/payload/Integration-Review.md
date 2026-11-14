# REVISE3 native integration

Fresh workspace based on passing integrated-fake v3, with Jim's two accepted REVISE3 test files added. Original frozen packets remain unchanged. Production source is carried forward unchanged.

New AssessmentFactory binds real production NativeORMFactories for ASSESSMENT. Setup and mutator sessions are separately labeled fixture transactions using explicit verify-full peer configuration, bounded connect/query/lock settings and no ambient DSN. The binding tracks session identity and owner thread. Native UNKNOWN latches the fixture stopped and bypasses any new terminal command; local quarantine is limited to the existing driver. Known retirement uses the production close_known receipt inside the cleanup budget.

Assessment pytest composition disables repository conftest and external plugin autoload, requires an exact reviewed node inventory, stops on first failure, rejects any skip and checks all sessions are drained. No case is reported passed during preparation. Its console output must be captured by the final runner into bounded evidence, not mixed into transport JSON.

The DB-side gate service now supplies one-shot loopback TLS server setup, readiness metadata and sanitized fault receipts for N06/N07. It accepts one client and returns only after the terminal acknowledgment was withheld. No keys leave DB tmpfs. Its process still needs a concrete supervisor launch/join operation; a ready file alone is not process completion evidence.

Open integration work: final native case registry (N01/N04/N05/N08 and fault-case callers), gate process launch/join transport, assessment schema setup and complete exact pytest inventory, bounded runner output composition, immutable runtime/tool pins and executable invocation. These are not replaced by passing stubs or inferred historical pins. This workspace is not launch-ready.

Verification in this preparation is source/hash comparison and AST parsing only. No Docker, application import, tests, certificate generation or endpoint binding.
