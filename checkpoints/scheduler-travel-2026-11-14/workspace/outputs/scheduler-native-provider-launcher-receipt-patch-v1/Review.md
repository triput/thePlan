# Launcher receipt and stream admission companion

Dex source contribution, November 12, 2026. Existing mutable role verify/launch_check.py; fresh separate copy only. Original v8 candidate source F096D9C24664FDA31514769303160DACFE770E214100857C35542B99DE988FEB. Candidate D22C37E36E5D333C087C8EE80B6936756C69F7D369369C66F8E0FFE6906EBD07. Diff D8D779767E9CB2046B836EF91C59989837467DCFFDF695EC7AE0E4C5509A2F13.

Only two logical edits:

1. In _write_failure_receipt, refuse an already existing RECEIPT, rather than RECEIPT or RESULT. The unchanged initial main guard still refuses either preexisting file before the attempt. A RESULT written by the current check is evidence to retain, not a reason to suppress this attempt's separate failure/disposition RECEIPT. No result write/delete is added. Receipt creation stays exclusive and its FileExistsError path stays intact.

2. After clean exit/EOF admission, refuse nonzero observed stdout or stderr before validating success. The checker intentionally writes its result file and emits no success output. This enforces the held-run STOP-on-unexpected-output contract; byte-capture caps remain unchanged.

The active Jim copy and all frozen evidence remain untouched. This contribution has not been imported, parsed, compiled, tested or invoked. The single-hunk diff includes the unchanged span between the two edits; the candidate is the exact source of truth. Jim should independently review/fold into the appropriate fresh successor and regenerate pins/expected labels. No new preparation permission or native case expansion is needed. No execution authority is added; endpoint unbound.