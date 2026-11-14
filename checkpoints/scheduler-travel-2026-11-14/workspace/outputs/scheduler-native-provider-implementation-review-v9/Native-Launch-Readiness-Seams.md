# First native launch readiness seams

Dex offline source review, November 12, 2026. No code changes or execution. These observations concern the later native launch, not the already frozen fake-v1 command. Preserve fake-v1 and its pending execution card unchanged.

## 1. Entry import order precedes its own isolated bootstrap

np_runner_entry.py main begins with from np_integrated_runner import run_suite and from np_receipts import build_receipt. It calls admit_isolated_import_bootstrap only afterward. The entry's top-level code has no earlier fixture path admission. The reviewed isolated -I -S -B script invocation does not admit its script directory as an ordinary import root. Therefore the entry can fail to import the first sibling module before reaching its intended guarded bootstrap. The report-boundary fake supplies sibling modules in sys.modules, so it does not prove this native startup sequence.

Narrow future source correction: after UID/config admission, call the existing guarded bootstrap before importing those two sibling modules. Keep reviewed site/fixture/API roots and isolated flags intact. Do not widen ambient imports or install packages. Include this readiness correction in the native proposal, to be prepared in a fresh copy under the existing named-runner role when appropriate. Do not change the current reviewed fake packet or claim its result proves import bootstrap.

## 2. Bind the freshly generated database public CA at runtime

np_integrated_runner.run_suite hashes /public-ca/ca.crt and compares it to config["ca_sha256"]. The prepared runner-config currently contains an unfrozen sentinel. np_runner_entry.load_runner_config only reads that JSON; its main does not derive/admit the dynamic CA hash before calling run_suite.

The immutable DockerOps.verify_fixture_ready generates no CA itself: it checks DB readiness/runtime, reads only fixed public CA files from the running disposable DB, validates their PEM shape, exclusively writes them to the fresh public-CA directory and sets self.ca_hash. The outer provider attach path compares the reported ca_sha256 to that transferred public hash. A new disposable CA cannot have its final bytes pre-pinned before the launch generates it.

The passed I01/I02 entry already uses an ephemeral in-memory config CA hash from the runtime public file before run_suite; its host compares the report to the transferred hash. Reuse that custody pattern explicitly, retaining the actual public-CA hash in evidence and the host equality check. Do not weaken verify-full TLS, freeze a made-up CA hash, mutate the input runner-config after admission, pre-generate private material on the host, or conflate this DB trust with the separately generated provider CA.

## 3. Keep the launch input graph acyclic and complete

The host launch-config embeds manifest_sha256 and is itself separately admitted by the reviewed command's ExpectedConfigSHA256. If the payload manifest were naively generated over that same launch-config, it would create a raw-hash cycle. Define the exact excluded host-config/manifest inputs and root them separately in the outer reviewed input manifest/command. Root the concrete Docker operations config as well, including its source_directory, exact images, argv, read-only binds and isolation projection. The current native wrapper does not itself hash DockerConfigPath; do not treat the filename alone as its byte pin. No new mutable discovery or live checks are needed to document the intended graph.

## Existing preparation boundaries

The prepared launch-config still lists all27 native IDs and7 expected UNKNOWNs despite only one implemented body. The first launch packet must select exactly NP-V-MS-NONEXPIRED in both host and runner configs, with an empty expected-UNKNOWN set; retain other obligations in the master inventory. Freeze real site directories, runtime pins, images, exact isolation settings and numeric bounds from the preserved capability/passed-run records; do not quietly substitute host Python evidence for native runtime evidence.

Native source references read:
- prep-v9/payload/fixture/np_runner_entry.py (87D89F760BB7CD47764BA1C6574A9AFF9E6266E682F0CE752AE4B06B484B2E25)
- prep-v9/payload/fixture/np_supervisor.py (A1ADA2311B10631209DBA0588B8C9C6B947B3206F0EFBC51F4CF66B1F45303BC)
- prep-v9/payload/fixture/docker_transport.py (7F7EA8204879D312624DAEB7941504FEA1402F45C48BDA79DDAD94A23711AC53)
- prep-v9/Invoke-Native-Provider.ps1 (D6E14CC07AF1B3F35B32DBE1C0FB4F9E7C70B476957314B6D29299CD04B6AE8D)
- passed scheduler-native-i01-i02-v4/payload/fixture/runner_entry.py public-CA in-memory binding near line688.

This is source evidence for the current docs-only launch proposal. It grants no imports, tests, PKI generation, Docker/native execution, retries, installation or endpoint binding. The pending fake card remains the only surfaced execution decision.