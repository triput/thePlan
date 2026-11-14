# Native T05 fixture fake verification — reviewed, execution HELD

Dex independently reviewed Matt's native T05 v3 implementation and 14-control/74-predicate checker. The native 292-input manifest and fake 33-input manifest match. The reviewed fixture covers three orderly observations (supplementary close-delimited acceptance, exact fixed-length acceptance, short fixed-length refusal) and a separate abrupt-EOF observation. All 31 declarations and the planning-ID union are preserved. Only the fixed-length positive maps to T05-VALID-COMPLETE-CONTENT-LENGTH; the supplementary close-delimited oracle is unmapped. No fixture/application/checker bytes changed in this staging.

Static admission reading found two improperly escaped Windows paths in Matt's VERIFICATION JSON. The original packet and incomplete Dex v1 staging are preserved. This fresh v2 corrects only those two JSON string spellings, flips the two machine admission booleans as staging data, and regenerates OUTER's dependent pin. Semantic path targets are unchanged. All other 31 source input entries are byte-identical, including all executable, subject and EXPECTED files. All 28 packet pins and ten partial runtime pins match. JSON admission files parse successfully. No Python imports, parsing, compilation, checks or invocation occurred.

Command SHA256: 0FBE49FCA90945B4D2565C6BC3767E51A5CFAE5F262F2FA183F70A5A59691B7A
Admission SHA256: 97DC6603A7749889CE0723AB41CCDF2AE0CF268C1D7C65F1759CFC22B7BF49C0
Outer admission SHA256: 1C57C545A9519697801ED8BE3D476E77AFC27D43983418BFECB8D74A2FB7E6DD

Exact current invocation, subject to a later one-shot approval:

& 'C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-native-t05-fake-dex-v2\packet\Invoke-Fake.ps1' -AdmissionSHA256 '97DC6603A7749889CE0723AB41CCDF2AE0CF268C1D7C65F1759CFC22B7BF49C0'


Only Reviewed-Native-T05-Fake-Command.ps1.txt in this staging root is current. Copied Future-Command-HELD.ps1.txt, Launch-Decision.md and earlier freezes retain history. Source packet labels intentionally retain Matt v3. Machine launch booleans true are staging data, not human authority. No invocation is authorized by this document.

One local PowerShell/Python admission-launcher-checker chain, one checker child and two capture-reader threads. The checker executes exact fixture modules/extracted definitions and actual host HTTP parser/JSON code with fake dependencies. It may import standard-library socket/ssl without constructing sockets or SSL contexts. No real application/vendor package imports, real sockets, PKI, providers, database, Docker, installation/build or native execution.

Limits: 120 seconds child collection, at most one five-second owned-child kill/wait and two five-second reader joins: 135 seconds nominal. Construction/startup, outer waits, file/hash/fsync/receipt work and process/OS latency excluded; no separate outer timeout. 64 KiB per child stream, 256 KiB result. Ten runtime files are partial provenance, not a full standard-library/DLL/environment lock. Retain result/disposition receipt and outer hashes/counts; child streams hash/count only. A future execution approval must include bounded owned-child termination on error, timeout or overflow.

Success requires exact ordered 14 top-level controls and 74 nested predicates, ten targeted mutant oracles, exit zero, zero child/outer output, two clean EOF/joined readers, known retirement and unchanged admitted inputs. Nested maps serialize sorted keys; the checker enforces their order before serialization. Stop on failure, mismatch, timeout, unexpected output or UNKNOWN; no retries, repairs, rerun, fallback or extra cleanup.

Qualifications: the finite HTTPX fake models rebuilt Content-Length insertion for these cases; it is not full HTTPX proof. Fixed-length success does not prove the client read TLS close_notify despite the inherited outcome label. Mutant controls include structural construction and retirement checks. Native TLS exception classes, real peer retirement and full T05 remain open. The native four-peer 500-second nominal peer allotment is not a strict wall-clock guarantee; future native review must preserve runner/suite supervision. This card grants no native run.

Signed: Dex