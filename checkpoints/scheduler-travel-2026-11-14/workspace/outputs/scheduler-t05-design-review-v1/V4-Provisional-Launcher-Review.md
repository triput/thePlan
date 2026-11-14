# V4 launcher/admission provisional continuation

Dex, November 11, 2026. Static reads only; not a frozen-handback acceptance. Launcher observed SHA256 24A101CD198734EB57C1A59703FAE1DA8590AC9A0432AECCFE1B359404FECCFE differs from the earlier staged C2A0F953... while authoring continues. Reconcile the final tip and all four roles before disposition. No code/helper was imported, compiled or invoked.

## Retained enforcing behavior observed

- PowerShell wrapper compares reviewed admission bytes, nonempty/count-consistent packet and runtime inventories, no escaped/duplicate packet paths, interpreter included in runtime pins, and prior result/receipt refusal before Python starts.
- Outer admission checks isolated flags, interpreter and all six required subject pins before starting the launcher.
- Launcher result gate requires PASS class, current result size/mtime, exact ordered IDs and input keys, no inventory_error, source_hashes_verified/executed true, exact predicates and observed outcome. Process exit alone is insufficient. Process/capture retirement errors remain separate PASS blockers.

These are source observations, not execution proof or acceptance of the still-unfinished checker and custody metadata. Exact predicates must themselves be complete and justified; checking an insufficient oracle does not supply omitted evidence.

## P6 — inherited stale-result deletion must be reconciled

The launcher main still unlinks RESULT when RESULT.is_file() before spawning the checker, under the comment 'Refuse stale pre-existing result before admission.' That is deletion, not refusal. The outer wrapper normally prevents prior result/receipt admission, so this does not establish a replay during the intended wrapper path. It remains an inconsistent inner guard: direct outer-admission entry or a result appearing between wrapper and launcher checks can remove prior evidence rather than preserve it.

Narrow preparation recommendation within the already approved launcher role: STOP without deleting or overwriting any pre-existing result/receipt; preserve the evidence. Maintain the wrapper refusal and exclusive/equivalent result custody. Do not execute an old packet, delete evidence, change capture limits or grant cleanup to demonstrate this. Reconcile against the eventual final launcher before sending any additional review batch; Jim may already be changing staged bytes.

## Pending

P1–P5 from V4-Provisional-Static-Review.md remain the earlier consolidated batch to Jim. This continuation is held for the final freeze to avoid interrupting his authoring with incremental status requests. Native-v3 launch remains separately gated by Trish's pending exact-hash card. Endpoint unbound and all other holds stay.