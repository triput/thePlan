# Native T05 failure cleanup request — exact IDs only

The one authorized native T05 attempt stopped in the abrupt-response classification guard. Runner CLI exit125,host exit1.12 Docker commands were issued;no cleanup ran. All297 input pins remain unchanged. Read-only reconciliation used exactly2 inspect calls and verified both frozen identities,isolation,mount sources,tmpfs and states. No resource state changed during reconciliation.

## Exact sequence requested (outside default execution restrictions)

Use the same pinned interpreter,Docker executable,immutable docker_transport.py and Docker config3455510B25F32334C80508AB141D0432CA14587E5ECC005D8762E22A1EB8095B. Do not run the original launch command again.

1. Recheck runner eb569ce806a81e9ba0a0309dda75f1e8f30810a7845a4d8a7d95db33c851a7d6 with check_identity;require exited125 and exact frozen config.
2. remove_exact that runner without force;require the returned exact ID.
3. verify_absent that runner;require true.
4. Recheck database2c15f1c0ae065a0e5a8b728c28920c3143aa379c76b3691e1d1f9b03d200a857 with check_identity;require running and exact frozen config.
5. sigint_exact that DB;require the returned exact ID.
6. wait_exact that DB;require exit0.
7. Recheck DB identity;require exited0 and exact frozen config.
8. remove_exact that DB without force;require the returned exact ID.
9. verify_absent that DB;require true.

Save the cleanup receipt and independent reconciliation. Nine Docker commands,30s each within a300s cleanup admission. Existing1MiB per-command capture cap and32-command helper cap remain. Startup/file/hash/fsync/receipt/OS latency excluded. Inherited owned-CLI termination kills without waiting and does not prove daemon cancellation. Stop on failure,mismatch,timeout or UNKNOWN;no retries,force,repairs,restart,rerun,fallback or extra cleanup.

This is state-changing failure cleanup. The original launch's success-only cleanup authority does not cover it. Preserve all failed evidence/public CAs/frozen inputs. No other native run is authorized;endpoint unbound and all other holds stay.

Signed: Dex
