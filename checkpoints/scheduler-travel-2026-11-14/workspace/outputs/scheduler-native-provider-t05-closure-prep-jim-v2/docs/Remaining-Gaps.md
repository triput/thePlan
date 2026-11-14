# Remaining gaps — t05-closure-prep-jim-v2

- Other 24 native + 4 CF case bodies: HOLD_EXPLICIT_NOT_PASS (T05 bodies authored outside launch batch)
- Launch batch remains NP-V-MS-NONEXPIRED only; T05 not folded in
- Provider PKI generation/invocation held
- Image presence and port 443 bind unverified (no live probe this prep)
- fake-v1 PASS prerequisite UNFULFILLED; staged packet untouched
- candidate-v2 TIP 34BBC408… held immutable; tip base C902F529… held immutable
- native launch still requires fake-v1 PASS + Trish exact command approval
- launch_ready / launch_authorized remain false — prep ≠ PASS; focused fake not invoked
- Native behavioral proof for T05 still requires later authorized run (shape + extracted fake predicates only here)
- Dex R1–R5 FIXED in authored fixture/checker; not yet exercised under authorized fake invoke
