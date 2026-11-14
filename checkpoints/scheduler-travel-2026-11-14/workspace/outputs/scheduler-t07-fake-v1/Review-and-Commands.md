# T07 fake-only verification — held launch review

Prepared by Dex, November 11, 2026. No execution authorization is supplied by this document. Trish's exact one-shot approval is required. Frozen Jim v6 is accepted for this bounded fake-verification scope; prior packets and all evidence remain preserved.

## Exact invocation and hashes

Run the single line retained in Commands.ps1.txt only after approval:

```powershell
& 'C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-t07-fake-v1\Invoke-Verification.ps1' -AdmissionSHA256 '4EEAE5B1C12F7FC6B97E00B62EAEB12CAE0F94C34A17D7E0744888367203695B'
```

| Subject | SHA256 |
| --- | --- |
| Commands.ps1.txt | 52E73835D67C04D2A27B047F49499C779DB3CBBAB682E485528EDA2DD1ED538C |
| Invoke-Verification.ps1 | 1DEA20EC5AC6C475EEEEC22EEE9B38381F31EA319B7A059409BC2BE52CE9D16B |
| VERIFICATION-ADMISSION.json | 4EEAE5B1C12F7FC6B97E00B62EAEB12CAE0F94C34A17D7E0744888367203695B |
| Jim v6 TIP-FREEZE.json | 671E008FA26ABB3EFC4BBCBB32B57C3828A50CAB2ABC343A039B29FE2F2CB599 |
| Checker | 7CD8D26B5E402F4548E4E7DA3EFD64F6A7738D54731C6E7FEC67FE7CACB6C899 |
| EXPECTED-OUTPUT.json | AD4B9F38A95BB80929806F54994C0C7A13ED3AE580CB662681400238AD4F5110 |
| INPUT-MANIFEST.json | A9DD0588E6F99EB57DC4EB5F9F030136EC6790D0063091BD3C29FD3C20772255 |
| Inner OUTER-ADMISSION.json | E937357ACED10BD87DD91C7A57036F5B7490F8200933C58740D607687BFA8867 |

Host admission pins all253 packet files and17 explicit interpreter/stdlib files. The prior12 runtime pins are unchanged; copy.py, enum.py, datetime.py, pathlib.py and typing.py add provenance for selected code dependencies. This is not a complete runtime dependency closure or immutable-filesystem claim. All234 API files plus3 original references are pinned; internal extraction inventory's nine explicit rows are supplemented by complete host pinning of connector/domain/Google source consumed by dynamic extraction.

## Behavior and proof boundary

One pinned Python outer admission starts one local launcher, which starts one check child and two capture-reader threads. Python uses -I -S -B. Selected production definitions are extracted/compiled in memory with fake dependencies; whole application/vendor packages are not imported.

The exact ordered41-control inventory requires31 PASS and10 PASS_WITNESS results. The latter are explicitly expected original-source contract-miss observations, not permission to accept an arbitrary failure. Controls include cleanup/provenance/ownership cases, original-versus-candidate owning importer behavior, Google refresh_access_token-to-HTTP propagation, actual extracted connector/domain stop with retained prior result and later target refusal, four mutations and five inventory checks. Failure or unexpected output stops the one attempt.

Native DB/parent/transaction/session completion, budget clocks, sockets/TLS and ownership identities remain fake. The event witness runs the selected complete owning importer try/except, not its full setup/post-fetch logic. OAuth means the extracted Google refresh function; account persistence and make_domain_ports.token policy/terminal logic are not proved. The run does not close full T07 or T01–T08, establish real provider retirement, or replace native integration evidence.

## Limits and evidence

- 30-second child wait, one5-second kill/wait and two5-second reader joins:45 seconds nominal collection/retirement, excluding outer hash/file operations and process/OS latency.
- 64 KiB each stdout/stderr and256 KiB result. Capture is bounded while collecting. Existing result/receipt refuses replay or overwrite.
- Retain FAKE-T07-RESULT.json and FAKE-T07-LAUNCH-RECEIPT.json. Independently reconcile exact ordered outcomes, source provenance, child exit, capture-reader retirement and post-run pins before claiming PASS.
- Bounded owned check-child termination on timeout/error/overflow is included. Failure to confirm exit or joined readers is STOP/UNKNOWN; no extra cleanup is implied.
- Stop on failure, mismatch, timeout, unexpected output or UNKNOWN. No retries, repairs, installation, real sockets, PKI, providers, database, Docker or native launch. No endpoint binding, deployment, activation or expanded permissions. All other holds stay.

Jim's prior static wrapper review is pinned in the packet and returned NO_BLOCKER. Final host-admission review is requested separately before presenting the launch card. No checker has run.
