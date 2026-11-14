# Provisional framing follow-through — source only
Dex, November11,2026. Read candidate29CBD53C85E8D40185A5E7DF73DF85B752A34837D25FCD65DB6504AFB775B368. Still in progress, not a frozen disposition or test result. No imports/compilation/tests.

P1 is statically addressed in this read: trailers_read starts0, increments for nonblank field lines and refuses above http.client._MAXHEADERS; required terminal CRLF remains. P2 is statically addressed: the size token must match unsigned hex before int conversion, with an additional negative-size hard stop. Future frozen checks must exercise these changes; no runtime PASS is claimed.

P3's gate now matches the base parser's parsed-value chunked recognition and asserts actual response.chunked. Content-Length stripping is limited to SP/HTAB. The proposed policy/oracles need one terminology correction: Message.get_all supplies parser-visible values, not literal wire bytes after the colon.

Read-only host email/feedparser.py calls policy.header_source_parse. In pinned host email/_policybase.py lines293-303, Compat32.header_source_parse lstrips leading SP/HTAB after the colon and rstrips CR/LF. Thus a real wire containing extra leading field OWS can become parser value "chunked" and be accepted, while trailing OWS stays visible and is refused by the new gate. A manually constructed Message storing value " chunked" does not establish the original wire parser's behavior.

Keep documentation and exact future wire oracles truthful at that boundary. No new raw-header interception or broader grammar restriction is requested. Use actual HTTPResponse parsing for any claimed wire-spelling outcome; helper-only injected metadata remains helper-only proof. Continue the same approved preparation and return the frozen handback. Endpoint unbound; execution held.
