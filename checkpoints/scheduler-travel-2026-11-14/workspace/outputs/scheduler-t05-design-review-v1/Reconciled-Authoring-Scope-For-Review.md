# T05 bounded workspace authoring scope — for review

Dex, November 11, 2026. Reconciles Jim's documents-only v2 design (raw TIP FA13F24FC0EDE7534D9ED335E04CB2782F56376EC6EBAB61D7F5C206841EF740; proposed scope C142291EEA4B1B5DDF3F5C8E462372DE2C08B655D9BDF01579C161EB5DF42602). This document does not authorize authoring or execution. The existing source-change hold requires Trish's preparation approval before new checker/fixture code is written.

## Authorized result if approved

Prepare two separately held workspace packets: an original-framing byte-driver verification packet and a native parser-source acquisition packet. Jim leads code authoring; Dex reviews/integrates. Return exact diffs, commands, complete source/runtime/control manifests and hashes. Preserve all existing packets and pending T07 inputs unchanged. Each later invocation needs its own separate exact reviewed launch approval.

## Six new or adapted executable files

| Packet-relative file | Bounded purpose |
| --- | --- |
| fake/check_t05_framing_original.py | Drive unchanged selected CoveringHTTP/_CoveringClient and owning caller definitions with fake byte transport/dependencies and the actual pinned host HTTPResponse parser. Do not replace the parser/body loop with a hand-written imitation. Record exact original outcomes and contract misses against separately frozen per-input predictions. |
| fake/invoke_t05_fake.py | Adapt the reviewed local child/capture/result-gate launcher. Preserve30s child wait,5s kill/wait,two5s reader joins,64 KiB each pipe and256 KiB result; disclose excluded outer file/hash and OS latency. No retries/fallback/extra cleanup. |
| fake/admit_outer.py | Adapt the reviewed isolated Python outer pin admission to the T05 subject names/kind. No application import or test work at admission. |
| Invoke-Verification.ps1 | Adapt the reviewed host wrapper to the fresh T05 packet root/kind/result names. Retain full packet/runtime hash checks and refusal of prior result/receipt before child start. |
| native-provenance/collect-parser-sources.sh | Prepare a nonsecret read-only collection recipe for exactly /usr/local/lib/python3.12/http/client.py, /usr/local/lib/python3.12/ssl.py and /usr/local/lib/python3.12/email/message.py plus their file hashes/sizes. No application imports, server, network, package operations or arbitrary paths. |
| native-provenance/verify_native_provenance.py | Prepare a host supervisor derived from the reviewed runner-only capability pattern, pinned to runner c220110432cf4adbb4005518a02808b754e0efb050b5de202e71872fecdbd2ab. Describe identity/isolation, bounded source capture and success-only exact-ID removal/absence verification for later launch review. No invocation is included in this approval. |

No other executable module authoring or existing code edits are included without returning a concrete scope amendment. Existing reviewed process/transport helpers may be copied byte-for-byte and pinned as immutable inputs, with their exact source/copy paths listed in the handback; any logic change must be disclosed for review. Do not execute copied or newly authored code during preparation.

## Data and evidence authoring

- Copy/pin the accepted234-file API snapshot and necessary original references as read-only-under-test inputs; do not alter application bytes or host stdlib. Pin actual host parser/message/SSL sources consumed by the fake driver and retain the three-way host/upstream/native provenance distinction.
- Author exact wire transcripts and individual IDs for the fixed-length, chunk/separator/zero/trailer, encoding/JSON, raw duplicate/conflicting header and close-delimited mapping families in the reconciled design. Expand grouped rows into exact per-purpose stimuli. Freeze the complete finite transcript/ID/order/count/byte-size inventory before any launch card; the thirteen planning IDs are not a cap or a substitute for variants.
- Use an exact ORIGINAL prediction/outcome predicate for each input. A predicted original contract miss is recorded as such, not corrected success and not arbitrary allowed failure. Stop on any unpredicted observation. Keep desired corrected outcomes in a separate file that is not scored against the original.
- Generate manifests, expected outcomes, review notes, immutable freeze metadata and held operator command files for both packets. These are preparation artifacts, not invocation permission. Every emitted result must be JSON-safe through explicit primitive projection, with observable counters and actual assertions rather than assumed evidence.

## Contracts and policy boundaries

Keep bounded reads, the16 MiB cumulative response ceiling, approved page/item limits, original request deadlines, no retry, independent close attempts and T07 uncertainty provenance. Byte fakes may establish selected framing/control flow only; orderly close_notify, actual socket ownership/timing and native caller/transaction behavior remain separately gated proof.

No application correction or compatibility restriction is approved. Valid fixed-length, chunked/extension/trailer and orderly close-delimited positives remain required. D1 duplicate-length handling and D2 TE+CL recommendations are retained as future proposals; do not freeze a restrictive corrected oracle as an accepted product decision in this original-characterization task. D4 TLS-option changes remain source-gated. D5 native source acquisition remains launch-gated. Native3.12.16 version evidence is already retained, but actual bytes/hashes are still unestablished until a later approved collection.

## Holds

Preparation only: no imports, compilation, checks/tests, serialization probes, wrapper/command invocation, Docker, PKI, sockets, provider calls, credentials, installation, builds, deployment, endpoint binding or activation. Native resource/time/capture bounds and exact command count must be concrete in the returned launch review; no current permission to create/start/remove a container is added. Stop authoring and return a specific scope question if these six files and immutable helper copies cannot meet the full requirements.

T07 fake-v2's pending launch card remains independent and unchanged. Full Scheduler integration/transport goal remains active and incomplete.
