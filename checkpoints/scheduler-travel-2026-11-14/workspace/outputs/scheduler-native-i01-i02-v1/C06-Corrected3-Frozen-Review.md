# C06 corrected3 frozen review

TIP D6260E99FFC203733DB84B4D7E8970AFE92E511B1DC3467949792D88A258EACC. All20 artifact,268 payload and6 verification manifest entries match. No checks or imports executed.

The total45-second check now derives30+5+5+5 correctly. A narrow fake Linux signal namespace replaces host SIGKILL dependencies. These close corrected2's two recorded findings at source level, without runtime proof.

Disposition: REVISE CHECK ONLY. Latest review notes crossed the freeze:
1. Pin and enforce the already-consumed payload/launch-config.json static input before run_controls reads it. The four extraction-source pins do not cover this additional input.
2. Use POSIX-only joining inside FakeOS.path.join; Windows os.path.join yields backslash names that do not match the POSIX FakeFS keys used by extracted public-provenance stat calls.
3. Label C06_N_WRONG_READY_ROOT as static path wiring/PASS, not behavioral REFUSE. The actual helper accepts and returns the explicit root; no refusal was exercised.

Corresponding coordination: Slack1794377411.595179 and1794377478.375989. Preserve corrected3; continue fresh corrected4 under the same verification-authoring scope. No new fixture source edits are requested, no production or host changes, no execution, tests, PKI, sockets or Docker. Final runtime authority remains with Trish via an exact reviewed card.