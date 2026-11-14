# T07 owning caller selection and claim boundary

Dex, November 11, 2026. Read-only source trace; no imports, compilation or execution. Current check-authoring successor remains Jim's one active assignment. No extra implementation scope is introduced.

Inspected accepted payload: covering_domain_adapters.py BA82577E8CF4B27D4EDD5A1B9D31B35E87990A381B83E22D4DB2A4D89352A53C; covering_provider_context.py 875FBF61A386D661A4DD70609162E41540500F10AD6AEDCACAF790701D693240. All source bytes are already in the verified staged payload inventory.

## Layers that must not be conflated

- _CoveringClient.post/_request selects the OAuth route and delegates to CoveringHTTP. This proves the context/client routing layer when actually extracted and driven, but by itself does not exercise the token adapter's policy-refusal catch or terminal decision.
- Provider refresh functions (for example Google refresh_access_token) call calendar_client.post and decode the result only after the exchange returns. They do not convert CoveringRootOutcomeUnknown into a known error in the inspected direct refresh function. Account token-cache selection, encryption and persistence are additional code paths; these cannot be claimed tested if replaced with fakes.
- make_domain_ports.token in covering_domain_adapters owns the CoveringReauthorizationRequired-to-TokenRejected catch and the known COMMIT/ROLLBACK terminal decision. Its refresh call is inside covering_provider_transport. An escaping cleanup UNKNOWN must bypass both the known reauthorization result and the terminal call that assumes a known result. A stub terminal acknowledgment is not observed native evidence.
- run_bounded_domain owns ordered target iteration, result retention and completed_results on escaping UNKNOWN. CoveringRoleConnector owns role admission stop/quarantine. These are separate from the token adapter and must receive the same propagated failure rather than a replacement manufactured in a fake port.

For event transport, the specific regression under repair is the owning importer catch around _pull_provider: the old source converts ordinary Exception into a failed import result, while the reviewed candidate rethrows CoveringRootOutcomeUnknown. This complete owning try/except must run around the HTTP fault in the integrated fake witness. Direct HTTP in a custom apply port bypasses the changed application behavior.

## Final review criteria

Identify explicitly which of these layers the successor extracts. A method called an OAuth adapter in prose must be named with its actual source symbol. Fake dependencies may supply database/account/locks/terminal inputs, but selected production exception handling must remain unchanged. If a deliberately narrower layer is used, retain that limitation and the unproved owning-adapter obligation rather than declaring the full caller path closed.

For an UNKNOWN token result, observe that no successful token result or known token terminal is invented after the exchange fault, no event parent is admitted for that target, no later target or final assessment is admitted, and the completed prior target remains. For an event fault, observe the importer rethrow, parent/connector stop and the same later-work restrictions. Retain exchange/terminal object identity and sanitized provenance without raw exception messages or token material.

The fake check can establish these selected source paths only. Actual credentials, token persistence, native terminal acknowledgments and real provider socket retirement remain outside its evidence unless separately included in a later exact reviewed packet. Existing native integration proof is reused at its actual scope.
