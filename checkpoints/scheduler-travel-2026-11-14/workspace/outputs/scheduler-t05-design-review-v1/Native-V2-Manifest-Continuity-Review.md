# Dex native-v2 additional static review

Author: Dex. Offline source inspection only; no invocation, import, compilation, Docker command or packet modification.

Target: scheduler-t05-native-provenance-dex-v2/verify_native_provenance.py, SHA256 4122E5DD4CC8DB211868E613EFF5CCA6418B190D7972584E62304A19CAF34220.

## Pre-removal manifest continuity gap

Admission verifies SHA256SUMS.txt against manifest_pin. Before exact-ID removal, the supervisor rereads that file and compares packet files against those freshly read rows, but does not recheck the manifest file hash against manifest_pin at that point. The approved four-row inventory is enforced only at admission. A changed manifest could therefore cause the later comparison to use different rows or pins rather than the admitted rows. This is a static continuity gap, not evidence of any actual file drift or a failed run.

Narrow proposed correction for the still-unexecuted successor: preserve the admitted four path/hash pairs, recheck the manifest hash against the approved pin immediately before cleanup, and compare those admitted pairs rather than accepting a freshly read inventory. Keep the existing runtime rehash, source-byte checks, exact-ID identity checks and stop behavior. Reconcile Jim's independent review before refreezing; do not silently edit the frozen v2 copy or present it for launch while this finding is unresolved.

The separate post-run checklist already requires independent rehashing of the manifest and operator commands. That post-run check remains necessary but does not substitute for a pre-removal STOP on detected manifest drift.

## Scope limits retained

Native source collection remains held. It proves source-byte provenance only if separately authorized and successful; it does not prove parser or transport behavior. Jim continues his one active four-role framing assignment and native-v2 peer review. No new assignment, execution authority, application correction or endpoint binding follows from this note.