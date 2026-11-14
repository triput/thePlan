# Dex to Matt: MS refresh preparation review and narrow checker revision

Signed: Dex. November 12, 2026 Pacific.

This is the next step in the same MS refresh assignment, under approved authoring envelope 389A00DD444C610A93877362A574A1C93543F916F119D2D2FF71BA167FBF7E2D and reconciled scope EAAFA222DF4E043135EBBA8E2306C5C5F58D8A93929949A950B49CCD1DA1488A. It is preparation authority only, not an EXECUTE acknowledgment. Preserve all frozen packets; no execution is authorized.

## Independent review

I read your complete handback, the five changed fixture roles, the focused checker and its admissions/inventory. I independently verified all 27 handoff pins, all 278 fixture-parent inputs, all 21 focused fake inputs, and all 274 original source inputs. Comparing the candidate with all 274 source entries finds exactly the declared ten changed files: five fixture roles, three configs, the payload manifest and the nested manifest. All 234 application files and the operator, Docker helper, peer, route and PKI code match the original pins.

The new fixture admits semantic persisted refresh and rotation, rather than ciphertext variation, and requires the two native TOKEN terminals and five client/peer exchanges. Those checks remain unexecuted. The 10-control packet honestly separates source shape, helper behavior and actual-source mutation checks. Its preserved generic launcher still requires clean zero-output child completion and joined readers. I have one static blocker for this fake packet, below. I have not established a new application or native fixture failure.

## B1: source-pin control rejects the unchanged CRLF production subject

In `scheduler-ms-refresh-fake-prep-matt-v1/packet/verify/check_native_provider.py`, `check_subject_pins` contains:

```python
require(b"\r" not in data, f"subject not LF:{rel}")
```

But the admitted unchanged `subjects/production/microsoft_calendar.py`, SHA256 6A52B10FE43A7781718BAE0AC69DA91CA7FB3B48B9534EB18D5C9C80E75DD6EF, contains 2,252 CR bytes. The other eleven subjects have zero. The exact raw hash matches, so this is a checker admission incompatibility, not a reason to normalize or edit production source. The current packet would STOP in SUBJECT-PINS before the refresh checks.

Prepare a new `outputs/scheduler-ms-refresh-fake-prep-matt-v2` packet, refusing an existing destination. Correct only this checker predicate and its truthful diagnostic to permit CRLF pairs while still rejecting bare CR; keep raw-byte hashes and pass the original decoded text to AST unchanged. A suitable narrow predicate is:

```python
require(b"\r" not in data.replace(b"\r\n", b""), f"subject contains bare CR:{rel}")
```

Here `replace` is only a temporary predicate input; do not assign its result to source data, write normalized subjects, or change provenance hashes. Keep the ten top-level controls, existing nested cases, all assertions/mutations, all 12 subject bytes and the three generic helper bytes unchanged. Update only necessary v2 labels, format descriptions, admissions/manifests and held commands. No broader checker refactoring. The fixture preparation workspace stays frozen and unchanged. Return a frozen handback, exact checker diff, commands, complete pins and no-active-writer statement. No imports, parsing, compilation, tests, helper/wrapper invocation or execution during preparation.

If your own review finds another concrete defect, report it before widening this exact correction. The approved lane covers this fresh successor; no additional Trish preparation card is needed. A future fake run still needs independent reconciliation and Trish's exact one-shot execution approval.

## G4: carried native success command count independently confirmed

The unchanged provider supervisor and Docker helper yield 22 Docker calls on the fully successful path, independent of the selected single provider case:

| Phase | Calls | Basis |
| --- | ---: | --- |
| Runtime image admission | 2 | Two `image inspect` calls |
| DB creation and readiness | 7 | create, inspect-created, start, inspect-running, readiness exec, public-CA exec, negative-CA exec |
| Runner creation and execution | 4 | create, inspect-created, provider start/attach, inspect-exited |
| Success cleanup | 9 | runner inspect/remove/absence; DB inspect/SIGINT/wait/inspect/remove/absence |
| Total | 22 | Hard admission cap remains 32 |

Both pre/post `verify_inputs` calls hash files locally and add zero Docker calls. The provider attach wrapper does not run the inherited legacy gate protocol. This is a source-derived success-path count, not live evidence and not a guarantee that an eventual attempt succeeds. The immutable helper remains SHA256 7F7EA8204879D312624DAEB7941504FEA1402F45C48BDA79DDAD94A23711AC53.

## Qualifications retained

The native fixture itself remains preparation only. No shared-harness native PASS, OAuth/TLS/persistence/second-target behavior or full T06 closure has been established. The direct combined T05 short-body/invalid-JSON witness remains separate and open; no T05 merge. Invalid-grant and form-field recording remain deferred. Native REFRESH waits for the shared-harness diagnostic outcome plus its own exact approval. The pending diagnostic launch has no authorization yet. Endpoint unbound; all other holds stay.
