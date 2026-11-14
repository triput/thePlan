# Remaining gaps — scheduler-native-provider-prep-v6

HOLD (explicit, not PASS):
- All native cases except NP-V-MS-NONEXPIRED
- Pure CF witnesses NP-T01-*
- T02-ITEMS-OVERFLOW / T02-BYTES-OVERFLOW full native closure
- T08-NESTED / T08-RESET full native (focused fake only)
- T01-ORIGIN-FOREIGN-PORT host PASS ≠ native dial/TLS
- close-delimited / wrong-name / oauth-path future bodies
- Numeric suite/runner bounds unfrozen pending launch card
- Provider PKI generation/invocation (caller authored; generate held)
- Fake/native invocation (launch_authorized=false)
- Actual sanitizer/host failure-path coverage (authored contract; not verified under prep)
- Actual native PKI run (PREPARED_NOT_GENERATED alone is not runnable)

Confirmed first-vertical authoring complete for NP-V-MS-NONEXPIRED source path only.
