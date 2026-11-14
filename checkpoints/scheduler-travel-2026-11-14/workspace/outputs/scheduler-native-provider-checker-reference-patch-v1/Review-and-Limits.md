# Byte-transport reference checker: unexecuted contribution

Based on immutable prep-v5 check_native_provider.py; Jim's active successor untouched. Replaces the blanket runner-text membership predicate with an AST reference inventory guard. It inspects names, attributes, imports (including renamed imports), and named definitions. Comments and literal documentation strings are not executable references and are ignored. Pinned-source review still matters; this finite guard is not a dynamic-alias/obfuscation detector.

Four declared controls exercise that same guard: documentation accepted, renamed forbidden import refused, constructor call refused, and alias-install attribute call refused. The three negative controls fail if the guard is a no-op. Candidate runner source is checked by the same helper. No source is imported or executed by this preparation work; parsing occurs only if a later separately approved fake invocation runs the checker.

The existing vertical group remains a source/shape check and does not become native proof. No production/fixture behavior changes. The result adds byte_alias_reference_control_ids inside VERTICAL-CONTRACT-SHAPE; update exact expected output and all source/admission hashes when integrating. This contribution does not fix input-pin completeness, native callback/alias/PKI/retirement gaps, or confer launch authority.

No imports, AST calls, compilation, tests or checker invocation were performed during authoring. Original/candidate/diff hashes retained beside this note. Integrate in a fresh successor under the approved checker role, then independently reconcile before any execution card.
