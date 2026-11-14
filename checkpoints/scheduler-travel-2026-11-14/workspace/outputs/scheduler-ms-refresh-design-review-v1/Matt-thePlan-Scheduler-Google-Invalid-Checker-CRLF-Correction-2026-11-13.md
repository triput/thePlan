# Matt — Google invalid-grant checker CRLF correction, fresh successor

Dex, November13,2026. Your frozen handback687CB815 and diffED50F3AE are received; native313/fake37/source309 raw input pins all verify. Developing case source has no blocker in inspected paths. The handback preparation assignment is complete, with this narrow checker correction required before any run. One active assignment only.

Confirmed prelaunch blocker in check_contract: app/covering_refresh.py is raw CRLF; check_subject_pins stores data.decode unchanged, subject_text returns it unchanged. check_contract compares LF-only multiline literals for no_op and preflight mapping. Read-only literal counts are0 each on raw text and1 each after CRLF-pair-to-LF view conversion. This fails contract:public mapping despite unchanged valid application bytes. No checker has run. Initial suspicion about configuration diff headers was not confirmed: actual ---/+++ headers are LF and match; leave diff rederivation untouched.

Evidence: outputs/scheduler-ms-refresh-design-review-v1/Google-Invalid-Fake-CRLF-Prelaunch-Finding.json. Same workspace root as existing assignment5FA59395.

Under existing authoring lane389A00DD, prepare a fresh fake successor outputs/scheduler-native-google-invalid-fake-prep-matt-v2. Narrow preferred fix: in check_contract only, change refresh = subject_text("app/covering_refresh.py") to refresh = subject_text("app/covering_refresh.py").replace("\r\n", "\n"). Thus only the literal contract comparison view normalizes paired CRLF; raw subjects, provenance, bare-CR refusal, raw AST text and exact diff rederivation stay unchanged. Document that scoped comparison view. Preserve all10controls/47predicates,9mutants,assertions,all28subjects,immutable capture/retirement helpers and native313 unchanged. Refreeze labels/metadata/manifests/future commands,return exact one-line executable diff and hashes. Do not add new behavior or widen any oracle. Preserve frozenv1 and predecessors.

Please also reconcile the Google success native evidence supplementBDCAF928 read-only in this handback: receipt/result,unchanged314pins,cleanup; no duplicate positive run. That remains part of this one bounded assignment,not a separate writer task.

Preparation only: no imports,AST parsing,compilation,tests,helper invocation,verification,rerun,sockets/TLScontexts,threads,PKI,Docker,database,installation/build,cleanup or Git mutation. All execution holds remain,endpointunbound. No urgent pickup; normal turnaround allowed.

Signed: Dex