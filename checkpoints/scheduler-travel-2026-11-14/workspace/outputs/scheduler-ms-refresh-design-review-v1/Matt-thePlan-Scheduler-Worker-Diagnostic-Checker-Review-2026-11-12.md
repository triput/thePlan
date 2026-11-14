# Dex to Matt: worker observer accepted statically; five-line fake-checker correction

Signed:Dex,November12,2026 Pacific. Same single worker-diagnostic preparation assignment under approved389A00DD authoring envelope and F6F15372 reconciled scope. No new Trish preparation card. No execution is authorized.

## What I independently reviewed

All23 handoff pins,278 native preparation inputs and15 fake preparation inputs match. Comparing all274 executed-parent inputs against the successor gives exactly six changed files:role4 runner,runner-config,payload manifest,two host configs,nested manifest. All234 API files and other fixture/operator/host-helper bytes are unchanged. I read the complete runner diff and full focused checker,including its extraction,fake modules/paths,producer/host composition,oracles and mutation controls. The raw diff is LF-only.

The fixture change is consistent with the accepted design:one retained exception object,original-call/result identity,bare rethrow,exact restore first in the existing POST finally,and optional explicit cause on the unchanged non200 assertion. Producer and host validator stay unchanged. At the current source boundary I have no unresolved fixture-design objection. Its actual behavior remains unexecuted. The control set is appropriately scoped to fake/extracted behavior plus structural wiring;it does not prove the full native call/retirement path.

## B1: five mutant dictionary entries close their outer tuple too early

In frozen checker38BE55DF092E9382FC13655BB6A0226026668C822D5BAC3A90B402EB2D59C4E4,lines974,976,979,980 and983 each have one excess closing parenthesis before the tuple's message-prefix element. The outer `(lambda: ..., prefix)` tuple has already closed before the prefix,leaving the later close unmatched. Manual source review establishes this punctuation defect;I have not parsed,compiled or run the target. It would prevent checker startup,so no verification card yet.

Prepare ONLY a fresh outputs/scheduler-native-worker-diagnostic-fake-prep-matt-v2,refusing an existing destination. Remove the single excess `)` in each of those five lines. The corrected dictionary fragment is:

```python
    mutants = {
        "replacement_reraise": (lambda: oracle_exception(install_fn((reraise, reraise.replace(
            "raise\n", "raise RuntimeError(\"observer\") from exc\n")))), "exception identity"),
        "swallowed": (lambda: oracle_exception(install_fn((reraise, reraise.replace(
            "raise\n", "return None\n")))), "exception swallowed"),
        "no_restore": (lambda: oracle_success(install_fn((
            "    def restore() -> None:\n        dispatch_module.run_bounded_domain = original\n",
            "    def restore() -> None:\n        pass\n"))), "restore identity"),
        "unbounded_capture": (lambda: oracle_exception(install_fn(("if not captured:", "if True:"))),
                              "bound one"),
        "chaining_removed": (lambda: oracle_chaining(chaining_source(mutation=(
            ") from worker_failure", ")"))), "cause not the captured worker exception"),
    }
```

Expected raw checker SHA256 after ONLY those five punctuation removals:C283F512F15FEFDD3CCAD3F1525229C350035BEB564FB77DE542BCA2C73397ED. I derived this with literal in-memory text replacement and hashing,without writing or executing a candidate. Keep PACKET_NAME's original lineage label in executable bytes to retain this exact minimal diff;explain the source/staging identity in current docs instead.

Preserve all ten controls,47 nested inventory entries,assertions,expected error-message prefixes,five targeted mutants,the original/candidate/host/production/diff subjects,EXPECTED,and the three generic helper bytes. Update only necessary v2 packet labels,notes,held command,checker/OUTER admission pins and manifests;both fake admissions false. The native278-input successor stays frozen and unchanged,as do the original15-input fake packet and every failed-run/completed-verification artifact. No broader checker edits or cleanup.

Return exact five-line diff,complete pin inventories,truthful current held command and limits,and signed frozen/no-active-writer handback. If your independent source review finds another concrete defect,report it before widening this exact correction. Preparation only:no target imports,parsing/compilation,tests,helpers/wrappers,verification,PKI,sockets,providers,database,Docker,installation/build,cleanup or native rerun. Endpoint unbound;all other holds stay.
