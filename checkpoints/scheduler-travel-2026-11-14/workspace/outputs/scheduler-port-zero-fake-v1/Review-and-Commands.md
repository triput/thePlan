# Exact-port admission increment: prepared, execution held

Dex, November 11, 2026. Trish approved narrow preparation in call_b66df08912ce4e8399ea9e7bf60ee8e2. This packet is awaiting independent static review; preparation is not a verification PASS or launch authority.

## Application diff and provenance

Both 234-file application copies derive from the passed routing candidate. Original is identical to that source; the candidate changes exactly one expression in covering_transport_policy.py. Proposed-Application.diff SHA256: C69EB5EFFAD47FBC1BB2A085DCF7620D736EF713BC09B4D4984736104BC9F8CB.

Original policy: A265F81F72E719B23FE3DE9BF332E2DE01D8E90073F3AC04675EC6A4B2203598.
Candidate policy: 5F48FD7ED50C57A6A47ADA20138678BB3C112A2A69D1C234A47580E6CD068B88.

Default only an absent URL port to 443; an explicit zero must refuse. This changes admission only. Dial destination/TLS, D2 path admission, ProviderCounter, transactions, results and deadlines stay unchanged. No framing-source merge is claimed; reconcile this file into the final framing candidate only after static review and applicable verification.

## Nine finite controls

Seven original/candidate cases use the extracted actual HTTPSPeer class and actual pinned host urllib.parse.urlsplit: peer443 with absent port, explicit443, explicit0, explicit444; peer8443 with absent port, explicit8443, explicit0. The original explicit0/peer443 case is expected to admit and the candidate to refuse. Other outcomes remain as frozen in EXPECTED.json. Two controls enforce the complete one-expression source inventory and rejection of a corrupted source hash. No dial or TLS behavior is inferred.

The check extracts only HTTPSPeer, supplies the fake refusal exception, and uses standard-library dataclass/ip_address/urlsplit. It does not import app/vendor packages. The pinned local urlsplit is a real parser dependency; all network and transport operations are absent. The four roles are check_port.py, invoke_port_fake.py, admit_outer.py and Invoke-Verification.ps1. Launcher and outer admission are copied from the passed routing packet with role/result labels changed; supervision/capture logic is retained. Source/check preparation used PowerShell file operations only; no Python parsing, compilation, imports, helper invocation or test run occurred.

## Exact held invocation and pins

Commands.ps1.txt contains the complete operator command. Do not invoke it during preparation.

Command-file SHA256: A98838452A0E7B6FA5BA504E38F2BA54E05890DFC759D33AE23412F94D87E048.
Admission SHA256: AE502E6BAA2CF8CA33B9E1137E5BB8C5E5FCC14F620239914DB3CAFCE1E86532.
Wrapper SHA256: DEBB3731B4C76DDA38AC3D32FD582A3EE5D121D5E6850757D07E5172B2C232D6.

475 packet-file pins and 19 runtime provenance pins were read/hash checked during static preparation. Runtime inventory is partial, not a claim of transitive stdlib/DLL closure. Wrapper admits the whole packet/runtime before Python; outer admission admits itself and launcher/check/data; launcher admits checker/expected/input manifest. No circular embedded self hashes.

## Future run scope and limits (not authorized)

One pinned Python outer/launcher/check chain, two capture-reader threads. 30s child collection +5s owned-child kill/wait +two5s reader joins =45s nominal collection/retirement. Outer admission/file/hash/receipt work and process/OS latency are excluded; no separate outer timeout. 64KiB per stdout/stderr,256KiB result. Bounded owned-check-child termination on timeout/error/overflow is included in the proposed future run. Result and receipt exclusively created; preexisting evidence stops replay. Stop on failure, mismatch, timeout, unexpected output or UNKNOWN. No retries, repairs, fallback or extra cleanup.

No real sockets, providers, PKI, database, Docker, installation or native run. No verification/launch authority is requested by this preparation document. Independent review must be reconciled before any launch card. Endpoint unbound; all other holds stay.
