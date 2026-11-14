# Framing fake v4 — one-shot launch decision

Jim's independent static review (Justin under Jim) is QUALIFIED ACCEPT, zero blockers. Dex verified the frozen peer artifacts,13 reviewed subject hashes, all537 packet pins and21 partial runtime pins. This packet is ready for launch review, not executed. It is the Dex scheduler-framing-ack-fake-v4 candidate; do not substitute Jim's separate prep-v4 copy.

## Exact command and pins

The complete held invocation is Commands.ps1.txt. It checks the absolute wrapper path/hash, then actually invokes Invoke-Verification.ps1 with the frozen admission hash.

Command-file SHA256: C2D8D18660B734EB3A6FAC9BDFACC1847C86A007C11BC81ECBEFFD1EE11FC66C.
Admission SHA256: 4BE04F87B1AD858C05DCA789DEF05B602E80DF33274E7D19A9BB4E985B865D85.
Wrapper SHA256: 0477912DBEB37067DC5CB49975A91FD1A666BD9893D166385D833D4D4E24AABA.
Checker SHA256: 1A422FB3D669B66C2FF590C4F74F8942D23DB3811087D0E3E7B8620896477080.

Review-and-Commands.md describes the exact application/check/command/data diffs and lineage. The73-control EXPECTED oracle is unchanged from Jim v3. The host parser is real; transport/TLS/retirement dependencies are fake. No current candidate owning-caller or native TLS behavior is claimed from direct HTTP replay rows.

## Requested future run scope and limits

One pinned Python outer/launcher/check process chain with two capture-reader threads.73 finite controls cover framed-body/chunk/header acknowledgment, exact TLS-option forwarding with fakes, bounded response item/byte excess and declared cleanup/UNKNOWN combinations. No app/vendor package imports, real sockets, PKI, providers, database, Docker, installation, native run or port merge.

30s check collection +5s owned-check-child kill/wait +two5s reader joins =45s nominal collection/retirement. Outer admission/launcher wait, file/hash/receipt I/O and process/OS latency are excluded; no separate outer timeout. Caps64KiB each stdout/stderr,256KiB result. Include bounded owned-check-child termination on timeout/error/overflow and retained result/receipt. Preexisting evidence stops replay. No retries, repairs, fallback or additional cleanup.

## Exact intentional UNKNOWN observations

Exactly12 controls require nested application OBSERVED_UNKNOWN and still pass only when the entire frozen predicate matches:

- F03-oauth and F05-oauth.
- F12a-INVALID-JSON-OAUTH, F12a-NONOBJECT-OAUTH and F12b-ENCODING-OAUTH.
- CLEANUP-C-R02, CLEANUP-C-R03, CLEANUP-C-R04, CLEANUP-C-R05 and CLEANUP-C-R06.
- PRIMARY-BOTH-CLOSES and OAUTH-UNKNOWN-RETIREMENT.

Expected-UNKNOWN-Inventory.json retains exact nested predicates and source-oracle hash. This is not an allowed-outcome override. Any other unexpected observation/UNKNOWN, or a launcher/child/capture/reader/retirement UNKNOWN, failure, mismatch, timeout or unexpected output stops. Intentional application fault witnesses do not waive framework retirement/STOP requirements.

## Proof limits and remaining work

A PASS would establish this finite host fake framing prerequisite only. Native TLS close_notify versus abrupt truncation, actual sockets/timing/thread ownership, owning-provider OAuth/native token state, port merge, final assembled integration and the remaining accepted T01–T08 requirements stay open. Peer-review optional expansions are outside this packet; required full-goal evidence is not made optional.

The earlier port-admission launch card is separate and still pending; no approval of this framing packet implies authority to run that command. Endpoint unbound; all other holds stay. No execution is authorized by this document.