# First vertical: real request construction and mapped-state observations

Static source findings after the v3 review. No execution. These are corrections within Jim's same approved role boundary, not a scope expansion or a new assignment.

## Real dispatch must construct the plan with its own budget

The selected production covering_http_dispatch._worker calls CoveringReleasePlan.for_request(context.budget) only when the installed object is exactly a CoveringReleasePlan. A prebuilt CoveringReleaseBinding takes the other branch.

Frozen v3 instead creates its own CoveringRequestBudget before POST, calls _for_request_capturing_transport, and installs the resulting binding. This bypasses the production worker's plan-construction branch and ties the provider counter to a different budget from the ingress/native connector budget. Also, build_i01_asgi_app defaults to a nonadvancing ControllableClock(0.0).

For the real plan/default transport claim, install the actual release_plan. Observe its constructor/request calls without replacing production construction or injecting a transport factory. Invoke the immutable app builder with the actual monotonic clock and capture the actual ingress context using its existing on_context hook. Record/check that the worker-created provider counter uses the same admitted request budget as ingress/connector. Restore observer hooks on both success and failure. Do not assert real deadline evidence from the existing frozen clock or from an independently constructed budget. No production changes are needed for these fixture corrections.

The existing class constructor interception can be adapted to observe the actual worker-created CoveringHTTP during POST rather than constructing a binding early. Any fake check must exercise that selected branch and reject a mutant that preconstructs the binding or uses an unrelated budget. Do not claim actual socket/ASGI timing from that fake check.

## Persisted measurement must use mapped fields

Selected app/models/calendar.py maps coverage_window_start/end, coverage_success_at, coverage_active_generation and coverage_success_generation. Frozen np_auth_seed.measure_subscription_coverage_state reads different nonexistent attributes and silently defaults them to None. Its after-state assertion therefore cannot see real success.

Separate unexecuted one-function contribution: outputs/scheduler-native-provider-coverage-patch-v1. Original SHA256 094BA73943684DBD310F7BD2F5442DB1BF7DAEFE4B27CA9948C52B207D1D6132; candidate SHA256 9EEF50BCAC923E43F9C7FED767DB541210E185A3B41E58DEEC612E77E5A38C7C; exact diff SHA256 A5FC6601521FFA4C5E99093EE8855D8D84D678644728DD30FB353C349A783891. Outside-function source unchanged. Static diff old/new context matched retained original/candidate text; no compilation or tests occurred.

Reconcile in a fresh successor, preserving response/final assessment assertions. Add extracted-helper fake controls whose row objects expose only the actual mapped attributes; verify before/after timestamps, windows and generation values, and reject the invented-attribute mutant. Non-null success timestamp is only an observation, not the complete production freshness predicate.
