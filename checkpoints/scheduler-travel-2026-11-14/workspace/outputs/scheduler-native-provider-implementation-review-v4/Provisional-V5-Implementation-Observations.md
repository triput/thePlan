# Two working-copy implementation observations

Not a frozen v5 review. Source is being edited; reconcile the final successor rather than treating this snapshot as acceptance or a new blocker declaration. Same approved first-vertical assignment; no execution.

## Observe the actual bound callback, not invented budget attributes

Selected CoveringReleasePlan.for_request constructs ProviderCounter(approved_provider_limits(), budget.work_remaining). ProviderCounter stores that callback as remaining; CoveringHTTP stores the counter as counter. Neither selected class defines a budget attribute.

The observed draft's transport.budget / counter.budget fallback therefore rejects the correct production construction after POST. For this exact selected source, inspect transport.counter.remaining.__self__ identity against the captured ingress context.budget, and its __func__ identity against the actual budget class work_remaining method. Observe rather than adding fixture-only budget attributes to the production objects. Do not call the callback merely to establish identity or substitute a separate budget.

The future fake control should exercise the actual selected for_request definition with fake factories/counter/transport dependencies and distinguish the same-bound-budget callback from a different-bound-budget mutant. This is callback wiring proof, not native timing or deadline proof.

## Authoring an invocation is different from invoking it

prepare_provider_pki_private_dir in the observed draft checks recipe existence and emits PREPARED_NOT_GENERATED metadata; it does not create/admit the directory or launch/collect/retire a child. Main calls that metadata path, then a real peer still needs generated files.

The approved named entry/operator/recipe roles permit authoring the actual bounded future PKI caller now. Do not execute it in preparation. Give it explicit directory ownership/mode/empty-path checks, exact recipe/interpreter inputs and later run admission, bounded output, owned process-group/readers retirement and no retry. Keep private keys in runner tmpfs and DB/provider trust separate. It may remain deliberately uninvoked until the separately approved launch. No new preparation card is needed to write this function within the named roles.

If the next deliverable intentionally freezes only a fake-control subset before native wiring is complete, label that limitation clearly; never describe metadata-only PKI as the implemented caller or the real first vertical as runnable. The native PKI invocation needs concrete commands/limits/authority before execution, as already required.
