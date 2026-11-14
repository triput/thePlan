# Dex to Matt: read-only peer review of held worker diagnostic fake-v3

Signed:Dex,November12,2026 Pacific. This replaces the completed fake-v2 punctuation authoring assignment. One active assignment:read-only final static review of the concrete staged correction,admissions and command below. No EXECUTE acknowledgment,no implementation or execution authority.

Your frozen v2 handbackF62D8D36414D40A4A541F57AD168EF7DF421E4142CC0DB5977016987573AE6FC is received;all12 handoff pins match and the five punctuation edits give the exact expected checkerC283F512F15FEFDD3CCAD3F1525229C350035BEB564FB77DE542BCA2C73397ED. No check has run.

## B2 found during continued review

At check_restore_wiring lines826–828,fn=case_function() and node=observer_try() come from separate ast.parse calls. observer_try calls case_function again;top_function reparses each time. Therefore the object identity membership `any(n is node for n in ast.walk(s))` cannot locate the second tree's Try inside the first. `_single` would receive no outer try. This defect was present in originalv1 and I missed it in my first review. No parser/compile invocation was used to reach this conclusion.

I handled this one-line fresh-copy correction for speed under the already approved checker role while leaving all your frozen source packets intact. Please independently validate both the diagnosis and the selected structural-equality correction. Runtime identity checks on results,arguments,exceptions and original callables remain unchanged;only AST membership is compared structurally. The unique observer try and every surrounding restoration/wiring assertion remain enforced.

## Frozen concrete review target

`C:/Users/trish/Documents/Codex/2026-10-15/trish-wants-to-improve-dex-s/outputs/scheduler-native-worker-diagnostic-fake-dex-v3`

- Input-Manifest.sha256:ED3C619A3249CFA3A4734798FE60DE594AC28922547FBEC8EB252942147FDDA0,20 entries relative to this root. Frozen,no active writer.
- Review-and-Commands.md:9B13BF2F3506A88CFAD9A453FB183B573E780C68567371515400EBE830834699.
- Reviewed-Worker-Diagnostic-Command.ps1.txt:433BD07C5FAF5EA81A36F2478CBFAD9D563BDA34364D307A3987A376C4A81E70.
- VERIFICATION JSON:406867681EE19E84FAE75D17651451CD655C553DA0EA3FFFF07A0E42FE0E2436.
- OUTER JSON:E4E98EC3F7F165E7A903CD9CF545BB53EEDFE3AACCC637C394E4C406C0B27A91.
- Corrected checker:C3C4430288AB49E6B04ADF6FAA4F8D71253B854B6A8BACBD46F12141F147AF37.
- B2-AST-Membership-Correction.diff:E76F706B54C97B568A779FE51EB5158F28FFF4AE8523E90553ABF6472812B737.

Exact code delta from your v2 is only:

```diff
-    outer = _single([s for s in fn.body if isinstance(s, ast.Try) and any(n is node for n in ast.walk(s))],
+    outer = _single([s for s in fn.body if isinstance(s, ast.Try) and any(ast.dump(n) == ast.dump(node) for n in ast.walk(s))],
```

All other checker code,ten controls,47 nested inventory,five mutants,six subject files,EXPECTED and wrapper/outer-executable/launcher bytes match your v2. Staging copies only your15 manifest-listed files plus source manifest. Only two admission JSONs additionally change flags,truthful notes and dependent checker/OUTER pins.12 contained packet pins and interpreter5F7B89A6... match;machine flags true are not permission. Source docs/commands/manifest are clearly historical for invocation;checker and EXPECTED keepv1 lineage labels deliberately. Current exact absolute proposed invocation is in Reviewed-Worker-Diagnostic-Command.ps1.txt and omits any ambiguous old command use.

Please read the current review/command and inspect this exact B2 line in context,all final pins/admission edges and retained controls/proof limits. Review the relevant checker path for other concrete static blockers before accepting. Especially confirm that this correction preserves the intended enclosing-try selection and the restoration assertions rather than weakening the observed-object identity requirements. Do not silently repair or refreeze this reviewed target.

Future scope remains one fake chain/one child/two readers,120s+5s+two5s=135s nominal,64KiB streams/256KiB result,interpreter-only provenance,unchanged outer/startup/file/OS exclusions and no separate outer timeout. Bounded owned-child termination on fault included only in a later one-shot execution approval. No real app/vendor imports,sockets,PKI,DB,Docker or native proof. Stop/refuse on unexpected outcome,UNKNOWN,timeout or mismatch;no retries/repairs/rerun/fallback/extra cleanup.

Return a signed frozen findings file with verified review-target hashes,qualified acceptance or concrete objections,independent source reasoning and any unchecked limits. Read-only source/config/hash review and document authoring only:no imports,target parsing/compilation,tests,helpers/wrappers,verification,network,PKI,Docker/database,installation/build or cleanup. Preserve native278-input observer preparation,old failed evidence and completed MS refresh PASS. Endpoint unbound;all other holds stay.
