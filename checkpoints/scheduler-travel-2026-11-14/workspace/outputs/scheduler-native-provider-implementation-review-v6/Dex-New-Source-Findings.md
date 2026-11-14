# Native-provider v6 new-source review

Frozen intermediate v6, reviewed offline November 12, 2026. This is source review, not execution or PASS. The saved Integrity-Reconciliation.json records 285/285 mirror files, 234/234 selected application files and matching raw TIP preimage. No sources were changed and no code was invoked.

## Source improvements accepted for carry-forward

The primary alias is now placed on the lower string-sorted planted subscription ID; the unrelated stable calendar is on the higher ID, preserving inverted request order. The budget check now examines the actual bound counter.remaining callback against ingress work_remaining. The peer retirement attempt flag is set before the call and finally refuses a second attempt. These address the corresponding prior source findings; actual behavior remains unverified.

## Two new points for the active successor

1. The authored PKI caller is not yet connected to the native entry path. np_runner_entry.py main calls prepare_provider_pki_private_dir(generate=False), and the only occurrence of invoke_bounded_provider_pki_recipe( is its definition. Thus an approved future launch would still reach the first peer without this path generating its required disposable material. Keep preparation unexecuted now; author the future admitted native path to invoke the bounded caller exactly once, record its disposition and require successful generation before peer creation. Do not invoke it during preparation or represent metadata-only preparation as generation.

2. Recheck capture overflow after reader joins. The caller checks stdout_sink.overflow / stderr_sink.overflow inside the wait loop, then breaks when the leader exits. Readers can still drain buffered output after that point. After joins the code checks EOF and retirement but never checks overflow again, so a late overflow can coexist with leader exit 0, joined EOF readers and a GENERATED result. Add a final overflow admission check after retirement/join and before success, preserving any existing primary failure. A fake late-drain case should distinguish this path from an in-loop overflow. Late reader errors already affect readers_eof; this finding is specifically the missing final overflow gate.

## Already acknowledged work remains separate

Jim explicitly acknowledged the v5 formal review, checker-reference-patch-v2 and host-glue contribution while v6 was freezing, and is folding those into a fresh successor. They are not new requests or a reason to duplicate his assignment. This review does not accept those incomplete v6 areas as fixed. The first useful fake prerequisite can advance independently with truthful native HOLD labels; completing the other 26 native and four CF cases is not required for the first increment.

No launch card yet: exact complete admission, fake behavior checks and numeric native bounds remain to be reconciled. Endpoint unbound; all execution holds stay.