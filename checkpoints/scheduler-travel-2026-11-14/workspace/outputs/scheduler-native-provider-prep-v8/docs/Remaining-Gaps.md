# Remaining gaps — scheduler-native-provider-prep-v8

HOLD (explicit, not PASS):
- All native cases except NP-V-MS-NONEXPIRED
- Pure CF witnesses NP-T01-*
- T02-ITEMS-OVERFLOW / T02-BYTES-OVERFLOW full native closure
- T08-NESTED / T08-RESET full native (focused fake only)
- T01-ORIGIN-FOREIGN-PORT host PASS ≠ native dial/TLS
- close-delimited / wrong-name / oauth-path future bodies
- Numeric suite/runner bounds unfrozen pending launch card
- Provider PKI generation/invocation (generate-once call site authored; invoke held under prep)
- Fake/native invocation (launch_authorized=false)
- Actual sanitizer/host failure-path coverage (authored contract; not verified under prep)
- Actual native PKI run (prep must not invoke admit_provider_pki_generated_once)
- Partial runtime inventory (interpreter only; not a full runtime lock)

Confirmed first-vertical authoring complete for NP-V-MS-NONEXPIRED source path only.
Dex D3B6FAD3… R1/R2 FIXED; Dex 30FEEDFF… launcher retirement FIXED; unexecuted.
