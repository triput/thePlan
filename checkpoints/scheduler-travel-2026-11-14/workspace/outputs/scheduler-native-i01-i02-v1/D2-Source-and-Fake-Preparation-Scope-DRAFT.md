# D2 fresh-copy source and fake-verification preparation — draft

NOT AUTHORIZED. This draft will be finalized after Jim's current docs-only oracle correction is independently reconciled. Policy approval alone does not permit these source changes. No source apply or candidate execution has occurred.

## Proposed bounded authority

Permit Jim to prepare one new workspace copy of the pinned API tree, apply exactly the three-file proposed diff below, and author a separate fake-only verification packet for review. Return exact delivered diff, file/inventory hashes and held verification commands. Do not run imports, syntax checks, compilation, tests, verification commands or application code.

Starting tree: `outputs/scheduler-t02-fake-v1/packet/payload/workspace/apps/api`. Dex's read-only base inventory contains 234 files; inventory SHA256 8E84BB7DFE9058F49CB725284CB0544A57CAACCE1EC36B99CCAD7403766C1347 (`D2-Source-Preparation-Base-Inventory.json`). Preserve it and every prior packet/evidence file. Fresh destination, proposed: `outputs/scheduler-d2-source-prep-v1/` (or Jim's new uniquely named staging handback with the same bounded tree, then Dex review/staging). Never edit original T02/native sources or reuse a failed-run evidence destination.

Exact unapplied diff: SHA256 CDB3AF210C7DD2BDC725F44F61931AD39B8010D5D259289D5D1FEF3E98E3F4F4, frozen in corrected2/corrected3. The later docs correction must preserve that byte hash. Context-checked in-memory reconstruction independently matched these exact starting and resulting source hashes:

| API file | Starting SHA256 | Resulting SHA256 |
|---|---|---|
| app/services/covering_transport_policy.py | 1171F629B596AC0366B9BE495D475FD125507027582491989F96E2BF3D922485 | A265F81F72E719B23FE3DE9BF332E2DE01D8E90073F3AC04675EC6A4B2203598 |
| app/services/covering_http_transport.py | A1F68F7529724BFDA709663C353BD8CD65E3FE757D1EC10FB34970E8303CC9DF | AECE10186CFFAE46D3EF2292D3772F1C287FD0A562AA9E764AAC4ABB10C861D8 |
| app/services/covering_provider_context.py | 8A40B635467D3BB3CD12E57F96521ACF7AEEF7D4A7661DB9157AC7FED9802D9F | 875FBF61A386D661A4DD70609162E41540500F10AD6AEDCACAF790701D693240 |

No other existing API file changes. Source tree file count remains 234. New check, manifest, launcher and review artifacts live outside the API tree. Preparation metadata must state execution held and must not confer native launch authority.

## Source behavior already reviewed

Helper and two pre-send call sites only. Eight-transition inspection limit; strict UTF-8; original-wire malformed percent, encoded structural and empty/trailing segment refusal; fixed calendar-ID positions rather than scanning opaque values. Preserve named valid ID/query positives, unchanged send bytes, origin/route/purpose/target-authorization separation, redirect 0-versus-1+0 accounting, and existing counters/transaction/result/deadline/TLS/retirement contracts. No builder changes, endpoint/profile binding, method expansion, fallback or retry.

## Separate fake-only packet authoring

Author check source, exact input inventory, expected ordered result inventory, launcher/admission source, held wrapper command and review docs; return all hashes. This is authoring permission only, not check execution.

- Cover the forty control IDs in Jim's independently reconciled successor to corrected3, with concrete corrected entry points and branch-reachable stimuli. Do not drop/replace IDs to get a pass. Add separately named inventory refusal and narrowly scoped source-mutation controls when necessary; enumerate them explicitly for later execution review, not as wildcard accepted failures.
- Drive the real extracted, pinned helper, context and HTTP request definitions with coherent fake dependencies. Extract the actual relevant Google/Microsoft builder definitions and constants for builder composition controls. Predicate-only checks cannot substitute for the promised caller/context/HTTP path. No app/vendor package imports; host standard-library provenance must be pinned where consumed, including urllib and http.client. No tests or imports during this preparation stage.
- Use deterministic byte buffers and fake owned peers/transports/process objects. Names such as www.googleapis.com are test URL data only. Refuse real DNS, sockets, proxies, credentials, filesystems outside packet data or live provider traffic. No PKI, Docker, database, worker activation or network timing claims.
- Assert original wire targets, route/purpose, opened/sent/closed counts, no fallback/follow-up, exact exception at the named entry and independent target-authorization boundary. Separate provider result classification and real transport proof remain T01–T08 work; fake acknowledgments cannot establish native database terminal outcomes.
- Inventory self-check must first accept a complete known-good ordered result, then independently reject reordered, duplicate, missing and altered-outcome inputs. A synthetic baseline must never substitute for actual result completeness.
- Reuse the already reviewed T02 admission/launcher structure as a template, with newly pinned paths/labels/inputs and no old result/evidence reuse. Proposed later verification limits: one pinned Python invocation; 30-second child wait, 5-second termination/wait and two 5-second reader joins; 64 KiB each stdout/stderr and 256 KiB result. This remains 45 seconds nominal collection/retirement excluding outer admission/file operations and OS/process latency. Disclose all changed process/thread/socket behavior before a launch card. Do not silently relax the bounds or run the launcher to verify it during preparation.

## Delivery and stop conditions

Return the exact three-file diff and source hashes, all 234 starting/resulting inventory comparisons (only three existing source files changed), check inventory and expected outcomes, exact held commands, manifests and review notes. No independent executable checking is authorized by this scope. Any mismatch or extra source change stops preparation for review; no opportunistic repairs or scope expansion. Dex independently reviews before any execution request.

Preserve approved native-v4/T02 results and all failure evidence. Source preparation, fake execution, real synthetic TLS/native proof and later activation are separate gates. Endpoint unbound; all other holds retained.
