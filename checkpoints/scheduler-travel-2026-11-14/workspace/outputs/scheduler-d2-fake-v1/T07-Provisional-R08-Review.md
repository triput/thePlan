# T07 provisional R08 review — earlier retirement failure

Dex, 2026-11-11. Jim's T07 documents-only packet was still being authored when inspected; no frozen TIP existed. This is provisional feedback, not acceptance or a review of immutable final bytes. No source changes or execution.

Authoritative application subjects are the unchanged staged D2 copy: covering_http_transport.py AECE10186CFFAE46D3EF2292D3772F1C287FD0A562AA9E764AAC4ABB10C861D8 and covering_joined_https.py C58382900BE1C190ED39242B4992FE88E1155E55F7E8C33D32065DBFCC993468.

The initial README recommends dual-attempt cleanup classification in CoveringHTTP plus a deferred UNKNOWN re-raise in the importer pull catch. Before accepting that as the narrowest coherent design, reconcile the earlier JoinedTLS.open cleanup failure:

1. open encounters a primary failure and calls self.close from its exception handler.
2. close sets closed=True, then raw sock.close raises. The close exception becomes the escaping exception; implicit exception context may retain the original primary, but no explicitly acknowledged retirement exists.
3. CoveringHTTP reaches its finally and calls transport.close again. That method returns because closed=True; there is no second raw close attempt or newly thrown cleanup error.
4. A candidate that only observes errors thrown by its own outer finally can miss the prior uncertain retirement. For non-OAuth work, the raw error can survive as OSError and be caught as ordinary identity/preflight or event failure. Merely adding an importer re-raise for CoveringRootOutcomeUnknown cannot help if that type was never produced.

This is a concrete source-supported challenge to the provisional design, not an executed failure or a claim that every possible two-file design must fail. Jim should show the exact candidate mechanism that represents prior retirement uncertainty and preserves primary provenance, or propose the additional narrow change required. There is no arbitrary two-file ceiling. Do not infer successful raw retirement from closed=True, a successful no-op method return, DB rollback or a second method-call count. No automatic raw-close retry is authorized.

Feedback delivered in the standing Slack thread at 1794424179.855909. The same message noted control-byte escaping artifacts in unfinished README labels for cleanup before final freeze. Jim's sole assignment remains the same documents-only proposal; no source/check implementation or launch authority was added. The D2 fake-verification card remains pending and unchanged.

## Follow-up: HTTP cleanup provenance

A later in-progress proposed diff adds UNKNOWN classification inside JoinedTLS.open when its inner close fails, which addresses the direction of the earlier R08 challenge. Final acceptance remains open. The HTTP finally proposal still sets only cleanup_failed=True inside each cleanup except block, then raises UNKNOWN after both handlers exit. It retains neither cleanup exception object. On a pending successful return there is no active cleanup exception at that later raise; with a pending primary, exception state may restore that primary rather than preserve the handled cleanup. With both cleanup operations failing, a Boolean cannot distinguish their classes/causes or establish both provenances. The final design must retain primary and both cleanup failures in an explicitly bounded, sanitizable form and show how the candidate witnesses observe them. Do not assume implicit __context__ retains exceptions already handled and discarded.

Follow-up delivered at Slack1794424460.870669. During this read the handback files were still updating, including the TIP; no immutable final packet was accepted. Strict System.Text.Json parsing found a trailing literal backslash-n outside INPUT-PINS.json, and README contained three non-whitespace ASCII control bytes. These are authoring corrections for Jim's final documents-only freeze, not permission to rewrite a completed run or application source. No new implementation approval card is ready.
