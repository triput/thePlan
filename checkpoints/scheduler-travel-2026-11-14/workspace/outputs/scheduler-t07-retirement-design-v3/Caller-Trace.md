# Caller trace v3

Supersedes v2 tip `9522BC2F8166F508606E6ACB1912511DDDB39D472CBA2FE400419A7AC30163BB`.

Spine unchanged. Candidate finally primary is `invocation_primary` only.
Outer except handlers around `CoveringHTTP.request` cannot supply primary
via ambient exc_info. Cleanup always raises a new UNKNOWN; importer
deferred re-raise still required on event path; identity OSError preflight
hazard remains for unclassified raw OSError only.
