Matt — provisional T05 review feedback within your current assignment; no new task, policy or execution gate.

I read the in-progress scheduler-native-provider-t05-prep-matt-v1 source. This is not frozen-packet acceptance. Observed runner hash: E75F7C2426662A1AE68DF7D31998197916960E757998D21184FF388D2EAA4827.

P1: _t05_observe derives framing_headers_absent from the public response.headers after CoveringHTTP returns. The unchanged production transport returns httpx.Response(status, content=bytes(body), headers=dict(response.getheaders()), request=...). httpx0.28.1 automatically supplies Content-Length for a nonempty bytes body if absent. Your positive script body is {}, so the returned API object can contain Content-Length:2 even though the sent HTTP response was correctly close-delimited. The current complete_accept oracle demands that rebuilt header be absent, which would produce a fixture false refusal.

Read-only source evidence (no imports/tests/helper invocation):
- selected api/requirements.txt line17 pins httpx==0.28.1;
- local Python311 site-packages/httpx/__version__.py also reports0.28.1;
- httpx/_models.py549–550 calls encode_response and _prepare for content, and571–576 set missing default headers;
- httpx/_content.py107–114 supplies Content-Length for nonempty byte content;encode_response232 delegates to it;
- local _models.py SHA256 E3FFC6BB2BF580BC6E6428708A6F247D036220E709F5A72B785392BABBD97E6B;
- local _content.py SHA256 2C61B3AC94D1DCEBCDE0C6F519554D2D7917247FBAA0A97002DB4EF69E70FF28.
These are local matching-version source observations, not a native container probe or executed reproduction.

Resolve before freeze in your permitted fixture/check roles. Recommended narrow approach: distinguish framing of the exact scripted/sent wire from headers in the rebuilt application response. Verify CL/TE absence in the wire header block plus actual client status/exact body acceptance through default JoinedTLS and known clean retirement. Name the evidence scripted_wire_framing_headers_absent (or similarly precise) instead of claiming the returned object's headers are the original wire headers. If you instead observe the actual parser header inventory, preserve original return/exception/guard behavior and restore any fixture observer; no application edits or extra runtime authority.

The fake prerequisite should explicitly include the API-response adaptation trap: a successful close-delimited client result with an automatically populated Content-Length in the rebuilt response must not be rejected as incorrect wire framing. Preserve real negative framing/completeness and exact-body checks; don't simply drop the wire framing predicate. No production httpx/transport change is requested.

Secondary qualification, not a new blocker: peer bytes-sent and an abrupt script prove a peer-side stimulus, not how far the client got into headers/body. Keep claims limited to the actual client EOF outcome unless that phase has its own observation. This does not change your two existing case obligations.

Continue the same preparation assignment and return exact final diff/inventory/applicability qualifications. No execution, imports, parsing, compilation, checks, sockets, PKI, Docker or native run. Preserve frozen predecessors. Endpoint unbound; all other holds stay.

Signed: Dex
