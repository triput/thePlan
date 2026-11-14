# Corrected6 C06 fake-only verification — HELD

Fresh-copy preparation is independently reconciled with Trish approval call_32f9e623299f4b0e8bc3eed4532b8278. Exact approved check SHA256C59C547453A76ACF7C4F10B8A0E1576134AB24A978EE5CC8018D25E1EF775DF8 differs from the failed check only by fake_os.lexists → fake_os.path.lexists in the first control. All39 assertions/control IDs and every fixture payload byte are unchanged. Original failed evidence remains at scheduler-c06-fake-v1.

Source corrected6 TIP94BB0D3DDEBED09AF52174B37A478484F35F8B07175154B4F27991967C9024A4;20 artifact,268 payload and6 verification manifest entries match; all284 staged files match the source. Outer admission subject pins match. This is static preparation acceptance, not a passing test result.

Exact held invocation:

& 'C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-c06-fake-v2\Invoke-Verification.ps1'

Command SHA256319F67A9A4D7358901E08230CE67509EA754790720166492D6AD8C7CE3F6C6A1
Verification input-manifest SHA2562175053A1F14E5CE0DEBF675D8DCFD691A1D1725C1BF68F43D254C60BB4FDAB5
Outer admission SHA256C9A0B5214F752F2FFED9ACE3E983501F44B4D78FA6D030774ABC61DDFBC212BF

Scope: one separately authorized invocation of pinned Python311 outer admission, which starts a local Python launcher and one Python check child with two capture-reader threads. All processes/filesystem/TLS/signal operations inside the extracted fixture are fake. No app/vendor imports, network sockets, PKI, database, Docker, installation or native launch.

Limits:30s check-child wait +5s kill/wait +two5s capture-reader joins =45s collection/retirement. Outer hash admission/file operations and process-start/OS latency are excluded; no hard total wall-clock bound is claimed. Captures64KiB each stdout/stderr; result256KiB. Exact local check-child termination within these limits is included for timeout/error. Retain result and launch receipt; refuse pre-existing evidence before admission.

Stop on failure, mismatch, timeout, unexpected output or unconfirmed/UNKNOWN retirement. No retry, repair or additional cleanup. The failed attempt's authority is consumed; this packet needs a new execution decision. Endpoint unbound; all other holds remain. Passing this would establish only the reviewed fake prerequisite, not PKI/native or T01–T08 completion.