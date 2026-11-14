# Remaining gaps — t05-closure-prep-jim-v3

- Other 24 native + 4 CF case bodies: HOLD_EXPLICIT_NOT_PASS (T05 bodies authored outside launch batch)
- Launch batch remains NP-V-MS-NONEXPIRED only; T05 not folded in
- Provider PKI generation/invocation held
- Image presence and port 443 bind unverified (no live probe this prep)
- fake-v1 PASS prerequisite UNFULFILLED; staged packet untouched
- candidate-v2 TIP 34BBC408… held immutable; tip base v2 7CC58CDA… held immutable; tip base v1 C902F529… held immutable
- native launch still requires fake-v1 PASS + Trish exact command approval
- launch_ready / launch_authorized remain false — prep ≠ PASS; focused fake not invoked
- Native behavioral proof for T05 still requires later authorized run (shape + extracted fake predicates only here)
- Dex R2 taxonomy FIXED in authored fixture/checker; R1/R3/R4/R5 preserved; not yet exercised under authorized fake invoke