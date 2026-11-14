# Fake launcher retirement review supplement

November 12, 2026. Offline source read only. Candidate source: scheduler-native-provider-prep-v7/verify/launch_check.py; SHA256 CE1A64193DC30ADB4D800151BD97CE331379612C75F4655BBA038B79BBFB739D. No invocation or imports.

The launcher is mutable role verify/launch_check.py in the existing 16-role lane. This is a launch-prerequisite correction, not a new product policy or expanded case matrix.

## Material gaps

1. After Popen, t_out.start and t_err.start are outside a guarded owned-child retirement path. A reader construction/start exception escapes the outer except LaunchStop, leaving an already created check child without a bounded kill/wait or joins for readers that did start. Other unexpected collection exceptions have the same exposure. The nominal timeout/overflow path is present, but does not cover partial setup.

2. After joins the launcher refuses overflow and unjoined readers, but does not refuse sink.reader_error or require both sink.saw_eof before result admission and return 0. The receipt merely writes readers_joined_eof=false. A read error can set the overflow Event after leader exit, without sink.overflow=true; the loop may already have broken. Thus an actual capture-unknown condition can still admit a successful result.

3. Existing collection failures return 125 after printing an error, without saving the owned-child/reader disposition receipt. For a held launch advertised as retained output/receipt plus bounded retirement on error, save a bounded exclusive failure receipt as well. Preserve the primary failure and distinguish unresolved retirement as UNKNOWN. Do not overwrite any prior evidence.

## Bounded correction

Track the owned child, constructed versus started readers, and whether kill/wait/join attempts have already occurred. On partial setup or collection error, attempt the disclosed retirement once for the owned check child and started readers; do not add duplicate kill/wait/join attempts after a previous retirement failure. Require exit and joined, clean EOF readers with no reader errors before success. Persist a bounded failure/disposition receipt using the existing exclusive-write approach. Keep the existing no-network fake scope and stream/result caps.

Freeze truthful limits after the correction: current admission selects a120-second collection budget, then up to5-second kill/wait plus two5-second reader joins. Outer hash/file/receipt operations and process/OS latency remain outside that nominal total; no separate outer timeout is claimed. If this structure changes, update the exact command/limits rather than inheriting the old statement. This is all future authored behavior: no child, thread or cleanup operation is authorized or executed during preparation.

Reuse the previously reviewed bounded launcher/partial-setup patterns where suitable. No full additional test matrix is required before the first fake increment; independently review the concrete source and include focused fake partial-setup/error/EOF behavior if authoring it. Native/PKI execution stays held.